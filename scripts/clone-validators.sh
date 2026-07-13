#!/usr/bin/env bash
#
# clone-validators.sh — clone validators + their evidence-set associations from
# a SOURCE Paramify workspace (e.g. prod) into a TARGET workspace (e.g. test),
# scoped to evidence sets whose NAME exists in both.
#
# This orchestrates the `pfy api` raw escape hatch + jq. It is NOT a built-in
# pfy command by design — it's a one-off migration helper you re-run as the
# evidence-set format iterates.
#
# ── The API constraint this works around ─────────────────────────────────────
# The Paramify API (v0.5.1) has NO readable evidence↔validator association:
#   GET /evidence/{id}   -> no validators field
#   GET /validators/{id} -> no evidence reference
# The only place a validator appears tied to an evidence set is on an artifact
# run: GET /evidence/{id}/artifacts -> artifacts[].validators[]. So we can only
# recover an association if the validator has actually RUN on an artifact in
# that set. Sets with no artifacts are reported as "unobservable", never
# silently dropped.
#
# ── Workflow (checkpoint in the middle) ──────────────────────────────────────
#   1. export : read SOURCE, walk evidence -> artifacts -> validators, resolve
#               each validator definition, write mapping.json.  READ-ONLY.
#   2. (review mapping.json — this is your checkpoint)
#   3. apply  : read mapping.json + TARGET, scope by name, DRY-RUN by default.
#               Add --go to actually create validators + associate them.
#
# ── Usage ────────────────────────────────────────────────────────────────────
#   SRC_KEY=<prod-token> ./scripts/clone-validators.sh export [mapping.json]
#   DST_KEY=<test-token> ./scripts/clone-validators.sh apply  [mapping.json]
#   DST_KEY=<test-token> ./scripts/clone-validators.sh apply  [mapping.json] --go
#
# ── Environment ──────────────────────────────────────────────────────────────
#   SRC_KEY   Paramify API token for the SOURCE workspace   (required: export)
#   SRC_URL   SOURCE base URL   (default: https://app.paramify.com/api/v0 = prod)
#   DST_KEY   Paramify API token for the TARGET workspace   (required: apply)
#   DST_URL   TARGET base URL   (default: https://stage.paramify.com/api/v0)
#
# Requires: pfy (on PATH), jq.

set -euo pipefail

SRC_URL="${SRC_URL:-https://app.paramify.com/api/v0}"
DST_URL="${DST_URL:-https://stage.paramify.com/api/v0}"

die() { printf 'error: %s\n' "$*" >&2; exit 1; }
info() { printf '%s\n' "$*" >&2; }

command -v pfy >/dev/null || die "pfy not found on PATH"
command -v jq  >/dev/null || die "jq not found on PATH"

# pfy reads PARAMIFY_URL / PARAMIFY_API_KEY from the env (they outrank .env).
src_api() { PARAMIFY_URL="$SRC_URL" PARAMIFY_API_KEY="$SRC_KEY" pfy api "$@"; }
dst_api() { PARAMIFY_URL="$DST_URL" PARAMIFY_API_KEY="$DST_KEY" pfy api "$@"; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# ─────────────────────────────────────────────────────────────────────────────
# export: read SOURCE -> mapping.json  (read-only)
# ─────────────────────────────────────────────────────────────────────────────
do_export() {
  local out="${1:-mapping.json}"
  [ -n "${SRC_KEY:-}" ] || die "SRC_KEY is required for export"

  info "▶ SOURCE = $SRC_URL"
  info "▶ Listing evidence sets…"
  src_api GET evidence | jq '.evidences // .' > "$TMP/ev.json"
  local n; n="$(jq 'length' "$TMP/ev.json")"
  info "  $n evidence sets found"

  : > "$TMP/sets.jsonl"
  : > "$TMP/vids.txt"

  local i=0
  while IFS= read -r ev; do
    i=$((i + 1))
    local id name ref ac vals observed
    id="$(jq -r '.id' <<<"$ev")"
    name="$(jq -r '.name' <<<"$ev")"
    ref="$(jq -r '.referenceId // ""' <<<"$ev")"
    ac="$(jq -r '.artifactCount // 0' <<<"$ev")"

    if [ "${ac:-0}" -gt 0 ]; then
      # union of validators observed across ALL artifacts in this set
      src_api GET "evidence/$id/artifacts" > "$TMP/arts.json" 2>/dev/null || echo '{}' > "$TMP/arts.json"
      vals="$(jq -c '[ (.artifacts // .)[]?.validators[]? ] | map(select(.id != null)) | unique_by(.id)' "$TMP/arts.json")"
      observed=true
    else
      vals='[]'
      observed=false
    fi

    local vcount; vcount="$(jq 'length' <<<"$vals")"
    printf '  [%d/%d] %-45s artifacts=%-4s validators=%s\n' "$i" "$n" "$name" "$ac" "$vcount" >&2

    jq -r '.[].id' <<<"$vals" >> "$TMP/vids.txt"
    jq -nc \
      --arg name "$name" --arg ref "$ref" --arg sid "$id" \
      --argjson ac "${ac:-0}" --argjson observed "$observed" --argjson vals "$vals" \
      '{name:$name, referenceId:$ref, sourceEvidenceId:$sid,
        artifactCount:$ac, observed:$observed, validators:$vals}' \
      >> "$TMP/sets.jsonl"
  done < <(jq -c '.[]' "$TMP/ev.json")

  # Fetch each unique validator's full definition.
  sort -u "$TMP/vids.txt" | grep -v '^$' > "$TMP/vids.uniq" || true
  local vc; vc="$(wc -l < "$TMP/vids.uniq" | tr -d ' ')"
  info "▶ Fetching $vc unique validator definitions…"
  : > "$TMP/defs.jsonl"
  while IFS= read -r vid; do
    [ -z "$vid" ] && continue
    src_api GET "validators/$vid" \
      | jq -c '{id, name, statement, type, regex, validationRules, attestationRules}' \
      >> "$TMP/defs.jsonl"
  done < "$TMP/vids.uniq"

  jq -n \
    --arg src "$SRC_URL" \
    --slurpfile sets "$TMP/sets.jsonl" \
    --slurpfile defs "$TMP/defs.jsonl" \
    '{ sourceUrl: $src,
       evidenceSets: $sets,
       validatorDefs: ($defs | map({key: .id, value: .}) | from_entries) }' \
    > "$out"

  local unobs; unobs="$(jq '[.evidenceSets[] | select(.observed==false)] | length' "$out")"
  info ""
  info "✔ wrote $out"
  info "  evidence sets:            $n"
  info "  unobservable (no artifacts): $unobs   <- association can't be read for these"
  info "  unique validators:        $vc"
  info ""
  info "  Review $out, then:  DST_KEY=… $0 apply $out"
}

# ─────────────────────────────────────────────────────────────────────────────
# apply: mapping.json + TARGET -> plan (dry-run) or writes (--go)
# ─────────────────────────────────────────────────────────────────────────────
do_apply() {
  local in="${1:-mapping.json}"
  local go="${2:-}"
  [ -f "$in" ] || die "mapping file not found: $in (run 'export' first)"
  [ -n "${DST_KEY:-}" ] || die "DST_KEY is required for apply"

  info "▶ TARGET = $DST_URL"
  # Keep target evidence as a raw list so the plan can normalize names itself.
  dst_api GET evidence   | jq '(.evidences // .)  | map({name, id})'                 > "$TMP/tev.json"
  dst_api GET validators | jq '(.validators // .) | map({key:.name, value:.id}) | from_entries' > "$TMP/tval.json"

  # Optional alias file: { "<source name>": "<target name>", ... } forces
  # matches the automatic rules can't make (e.g. a word dropped in the target).
  local alias_arg=/dev/null
  if [ -n "${ALIASES:-}" ]; then
    [ -f "$ALIASES" ] || die "ALIASES file not found: $ALIASES"
    alias_arg="$ALIASES"
    info "  using alias overrides: $ALIASES"
  fi

  # Build the plan. Evidence-set names match by (in order): exact/trimmed name
  # (or fully normalized when NORMALIZE=1), then an explicit ALIASES entry.
  #   normalizedNearMatches — unmatched only due to case/whitespace (flip NORMALIZE=1)
  #   fuzzyNearMatches       — unmatched but token-similar (a word differs); review then alias
  # Associations reference validators by NAME; the target UUID is resolved at write time.
  jq -n \
    --slurpfile mp  "$in" \
    --slurpfile tev "$TMP/tev.json" \
    --slurpfile tvl "$TMP/tval.json" \
    --slurpfile al  "$alias_arg" \
    --arg normalize "${NORMALIZE:-}" \
    '
    def t:    gsub("^\\s+|\\s+$";"");
    def norm: ascii_downcase | gsub("^\\s+|\\s+$";"") | gsub("\\s+";" ");
    def toks: (norm | split(" ") | map(select(length>0)) | unique);
    def jac($a;$b): (($a-($a-$b))|length) as $i | (($a+$b)|unique|length) as $u
                    | (if $u==0 then 0 else ($i/$u) end);

    ($mp[0]) as $m | ($tev[0]) as $Elist | ($tvl[0]) as $V | (($al[0]) // {}) as $A |
    ($normalize == "1") as $useNorm |
    def key: if $useNorm then norm else t end;
    ($Elist | map({key:(.name|key),  value:.id})   | from_entries) as $E |
    ($Elist | map({key:(.name|norm), value:.name}) | from_entries) as $EnormName |
    ($Elist | map({name, tk:(.name|toks)}))                        as $T |
    # target id for a source name: direct key match, else via alias -> target name
    def tid($nm): ($E[($nm|key)]) // ($A[$nm] as $a | if ($a|type)=="string" then $E[($a|key)] else null end);

    ($m.evidenceSets | map(select((.validators|length) > 0)))          as $withVals |
    ($withVals | map(select(tid(.name) != null)))                      as $matched |
    ($withVals | map(select(tid(.name) == null)))                      as $unmatchedSets |
    ($unmatchedSets | map(.name))                                      as $unmatched |
    ($unmatchedSets | map(.name)
        | map({source:., target:$EnormName[(.|norm)]})
        | map(select(.target != null)))                               as $near |
    ( [ $unmatchedSets[].name | . as $s | ($s|toks) as $st |
          { source:$s,
            candidates: ( [ $T[] | {target:.name, score:(jac($st; .tk))} ]
                          | map(select(.score >= 0.34)) | sort_by(-.score) | .[0:3] ) } ]
      | map(select(.candidates|length > 0)) )                         as $fuzzy |
    ( [ $withVals[] | select(($A[.name]|type)=="string" and ($E[(.name|key)]==null))
        | {source:.name, alias:$A[.name]} ] )                         as $aliased |
    ([ $matched[].validators[] ] | unique_by(.id))                     as $needed |
    ([ $matched[] | .name as $en | tid($en) as $eid | .validators[]
       | {evidenceName:$en, targetEvidenceId:$eid, validatorName:.name} ]) as $assoc |
    # Two+ distinct source sets resolving to the same target set = a merge.
    ( $assoc | group_by(.targetEvidenceId)
      | map({targetEvidenceId:.[0].targetEvidenceId, sources:([.[].evidenceName]|unique)})
      | map(select(.sources|length > 1)) )                             as $dupes |
    {
      unmatchedSets:         $unmatched,
      normalizedNearMatches: $near,
      fuzzyNearMatches:      $fuzzy,
      aliasMatched:          $aliased,
      duplicateTargets:      $dupes,
      matchedSets:           ($matched | length),
      toCreate:              ($needed | map(select($V[.name] == null)) | map(.name)),
      toReuse:               ($needed | map(select($V[.name] != null)) | map(.name)),
      associations:          $assoc
    }
    ' > "$TMP/plan.json"

  local nMatch nUnmatch nCreate nReuse nAssoc nNear nFuzzy nAlias nDup
  nMatch="$(jq '.matchedSets'                 "$TMP/plan.json")"
  nUnmatch="$(jq '.unmatchedSets|length'      "$TMP/plan.json")"
  nCreate="$(jq '.toCreate|length'            "$TMP/plan.json")"
  nReuse="$(jq '.toReuse|length'              "$TMP/plan.json")"
  nAssoc="$(jq '.associations|length'         "$TMP/plan.json")"
  nNear="$(jq '.normalizedNearMatches|length' "$TMP/plan.json")"
  nFuzzy="$(jq '.fuzzyNearMatches|length'     "$TMP/plan.json")"
  nAlias="$(jq '.aliasMatched|length'         "$TMP/plan.json")"
  nDup="$(jq '.duplicateTargets|length'       "$TMP/plan.json")"

  info ""
  info "── plan ── (match mode: ${NORMALIZE:+normalized}${NORMALIZE:-trim}) ──"
  info "  matched evidence sets:      $nMatch  (of which via alias: $nAlias)"
  info "  validators to CREATE:       $nCreate"
  info "  validators to REUSE (exist):$nReuse"
  info "  associations to CONNECT:    $nAssoc"
  info "  UNMATCHED sets (skipped):   $nUnmatch"
  if [ "$nUnmatch" -gt 0 ]; then
    jq -r '.unmatchedSets[] | "      - \"" + . + "\""' "$TMP/plan.json" >&2
  fi
  if [ "$nNear" -gt 0 ]; then
    info ""
    info "  ⚠ $nNear set(s) match once case/whitespace is normalized — re-run with NORMALIZE=1:"
    jq -r '.normalizedNearMatches[] | "      \"" + .source + "\"  →  \"" + .target + "\""' "$TMP/plan.json" >&2
  fi
  if [ "$nFuzzy" -gt 0 ]; then
    info ""
    info "  ⚠ $nFuzzy unmatched set(s) look token-similar to a target (a word differs)."
    info "    Review; put the correct ones in an alias file and pass ALIASES=aliases.json:"
    jq -r '.fuzzyNearMatches[] | "      \"" + .source + "\"  →  "
             + ( [ .candidates[] | "\"" + .target + "\" (" + (.score*100|floor|tostring) + "%)" ] | join(", ") )' \
      "$TMP/plan.json" >&2
    # Drop a ready-to-edit starter alias file (best candidate per set).
    if [ "$go" != "--go" ]; then
      jq '.fuzzyNearMatches | map({(.source): .candidates[0].target}) | add // {}' \
        "$TMP/plan.json" > aliases.suggested.json
      info ""
      info "  → wrote aliases.suggested.json (best guess each) — prune/fix it, then:"
      info "      ALIASES=aliases.suggested.json DST_KEY=… $0 apply $in"
    fi
  fi
  if [ "$nDup" -gt 0 ]; then
    info ""
    info "  ✖ $nDup target set(s) would receive validators from MORE THAN ONE prod set"
    info "    (usually a bad alias). Each target and its colliding sources:"
    jq -r '.duplicateTargets[] | "      target " + .targetEvidenceId + " ← "
             + ( [ .sources[] | "\"" + . + "\"" ] | join("  +  ") )' "$TMP/plan.json" >&2
    info "    Fix the alias file, or set ALLOW_DUPLICATE_TARGETS=1 to proceed anyway."
  fi
  info "─────────────────────────────────────────────────────"

  if [ "$go" != "--go" ]; then
    info ""
    info "DRY RUN — no writes made. Re-run with --go to execute."
    info "Full plan:"
    jq . "$TMP/plan.json"
    return 0
  fi

  # Refuse to write if two source sets collide on one target, unless overridden.
  if [ "$nDup" -gt 0 ] && [ "${ALLOW_DUPLICATE_TARGETS:-}" != "1" ]; then
    die "$nDup target set(s) receive validators from multiple prod sets (see ✖ above). Fix the alias file, or set ALLOW_DUPLICATE_TARGETS=1 to override."
  fi

  # ── execute ────────────────────────────────────────────────────────────────
  # Resumable: creating a validator that already exists, or connecting a pair
  # that's already connected, is treated as a no-op — so a re-run after a
  # partial/failed run converges instead of aborting.
  info ""
  info "▶ EXECUTING against $DST_URL"
  cp "$TMP/tval.json" "$TMP/idmap.json"   # name -> target validator UUID
  : > "$TMP/failures.txt"
  local cCreated=0 cExisting=0 aOk=0 aExisting=0 aFail=0

  # 1. create missing validators
  while IFS= read -r vname; do
    [ -z "$vname" ] && continue
    local def type body out newid
    def="$(jq --arg n "$vname" '.validatorDefs | to_entries | map(.value) | map(select(.name==$n)) | .[0]' "$in")"
    type="$(jq -r '.type' <<<"$def")"
    if [ "$type" = "AUTOMATED" ]; then
      body="$(jq '{name, statement, type, regex, validationRules}' <<<"$def")"
    else
      body="$(jq '{name, statement, type, attestationRules}' <<<"$def")"
    fi
    if out="$( { printf '%s' "$body" | dst_api POST validators --stdin; } 2>&1 )"; then
      newid="$(jq -r '.id // empty' <<<"$out" 2>/dev/null || true)"
      info "  + created validator: $vname ($type)"
      cCreated=$((cCreated + 1))
    elif printf '%s' "$out" | grep -qiE "already exists|must be unique|duplicate"; then
      info "  = validator already exists: $vname"
      cExisting=$((cExisting + 1))
      newid=""   # id already in idmap from the target fetch
    else
      info "  ! create FAILED '$vname' :: $(printf '%s' "$out" | tr '\n' ' ' | head -c 200)"
      echo "create|$vname|$out" >> "$TMP/failures.txt"
      newid=""
    fi
    if [ -n "$newid" ] && [ "$newid" != "null" ]; then
      jq --arg n "$vname" --arg i "$newid" '. + {($n): $i}' "$TMP/idmap.json" > "$TMP/idmap.tmp"
      mv "$TMP/idmap.tmp" "$TMP/idmap.json"
    fi
  done < <(jq -r '.toCreate[]' "$TMP/plan.json")

  # 2. associate. NOTE: CONNECT is NOT idempotent — the API 400s if the pair is
  # already connected; we treat that as success so re-runs converge.
  while IFS= read -r a; do
    local en eid vn vid body err
    en="$(jq -r '.evidenceName'      <<<"$a")"
    eid="$(jq -r '.targetEvidenceId' <<<"$a")"
    vn="$(jq -r '.validatorName'     <<<"$a")"
    vid="$(jq -r --arg n "$vn" '.[$n] // empty' "$TMP/idmap.json")"
    if [ -z "$vid" ]; then
      info "  ! no target UUID for validator '$vn' — skipped"
      echo "assoc-noid|$en|$vn|" >> "$TMP/failures.txt"
      aFail=$((aFail + 1)); continue
    fi
    body="$(jq -nc --arg sid "$vid" '{associationType:"CONNECT", subjectType:"VALIDATOR", subjectId:$sid}')"
    if err="$( { printf '%s' "$body" | dst_api POST "evidence/$eid/associate" --stdin; } 2>&1 1>/dev/null )"; then
      info "  ↔ associate '$vn' → '$en'"
      aOk=$((aOk + 1))
    elif printf '%s' "$err" | grep -qi "already connected"; then
      info "  = already connected: '$vn' → '$en'"
      aExisting=$((aExisting + 1))
    else
      info "  ! associate FAILED '$vn' → '$en' :: $(printf '%s' "$err" | tr '\n' ' ' | head -c 200)"
      echo "assoc|$en|$vn|$err" >> "$TMP/failures.txt"
      aFail=$((aFail + 1))
    fi
  done < <(jq -c '.associations[]' "$TMP/plan.json")

  info ""
  info "✔ done"
  info "  validators: created $cCreated, already existed $cExisting"
  info "  associations: connected $aOk, already connected $aExisting, failed $aFail"
  if [ "$aFail" -gt 0 ] || grep -q '^create|' "$TMP/failures.txt" 2>/dev/null; then
    info ""
    info "  ⚠ failures (not 'already connected/exists'):"
    sed 's/^/      /' "$TMP/failures.txt" >&2
    return 1
  fi
}

# ─────────────────────────────────────────────────────────────────────────────
case "${1:-}" in
  export) shift; do_export "$@" ;;
  apply)  shift; do_apply  "$@" ;;
  *) cat >&2 <<EOF
usage:
  SRC_KEY=<prod-token> $0 export [mapping.json]
  DST_KEY=<test-token> $0 apply  [mapping.json]        # dry-run
  DST_KEY=<test-token> $0 apply  [mapping.json] --go   # execute
EOF
     exit 2 ;;
esac
