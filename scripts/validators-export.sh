#!/usr/bin/env bash
#
# validators-export.sh — pull the FULL validator catalog from prod (GET
# /validators) and write a CSV of every validator + its metadata + the evidence
# sets it's associated with.
#
#   SRC_KEY=<prod-token> ./scripts/validators-export.sh [mapping.json] [out.csv]
#
# Associations are the OBSERVED ones — a validator is linked to an evidence set
# only where it actually ran on that set's artifacts (the API exposes the link
# nowhere else). So a blank association means "never observed on any set's
# artifacts", NOT a guaranteed "unassociated" (it could be attached to a set
# that has no artifacts yet). Associations are read from mapping.json (the
# prod export snapshot); re-run clone-validators.sh export to refresh it.
#
# Env: SRC_KEY (required), SRC_URL (default prod). Requires: pfy, jq.

set -euo pipefail

SRC_URL="${SRC_URL:-https://app.paramify.com/api/v0}"
die() { printf 'error: %s\n' "$*" >&2; exit 1; }

command -v pfy >/dev/null || die "pfy not found on PATH"
command -v jq  >/dev/null || die "jq not found on PATH"
[ -n "${SRC_KEY:-}" ] || die "SRC_KEY is required"

map="${1:-mapping.json}"
out="${2:-validators-export.csv}"
[ -f "$map" ] || die "mapping file not found: $map (run clone-validators.sh export first)"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

printf '▶ SOURCE = %s — fetching validator catalog…\n' "$SRC_URL" >&2
PARAMIFY_URL="$SRC_URL" PARAMIFY_API_KEY="$SRC_KEY" pfy api GET validators \
  | jq '(.validators // .)' > "$TMP/catalog.json"

jq -rn \
  --slurpfile cat "$TMP/catalog.json" \
  --slurpfile mp  "$map" \
  '
  def ruleStr:
    ( .regexOperation as $ro
      | if   $ro==null              then "?"
        elif $ro.type=="MATCH_GROUP"  then "MATCH_GROUP[\($ro.groupNumber)]"
        else $ro.type end )
    + " " + (.criteria // "?") + " "
    + ( .value as $v
        | if   $v==null              then "?"
          elif $v.type=="CUSTOM_TEXT"  then "'"'"'\($v.customText)'"'"'"
          elif $v.type=="MATCH_GROUP"  then "MATCH_GROUP[\($v.groupNumber)]"
          else $v.type end );

  ($cat[0]) as $C | ($mp[0]) as $m |
  # validator id -> [ {name, ref} ] of evidence sets it was observed on
  ( reduce ( $m.evidenceSets[] | . as $es | $es.validators[]?
             | {id:.id, name:$es.name, ref:($es.referenceId // "")} ) as $x
      ({}; .[$x.id] += [{name:$x.name, ref:$x.ref}]) ) as $U |

  (["id","name","type","statement","regex","rules_summary",
    "validationRules_json","attestationRules_json",
    "observed_association_count","observed_evidence_sets","observed_evidence_refs"]),
  ( $C | sort_by(.name)[]
    | ( ($U[.id] // []) | unique ) as $sets
    | [ .id, .name, .type, (.statement // ""), (.regex // ""),
        ( [ (.validationRules // [])[] | ruleStr ] | join(" ; ") ),
        ( (.validationRules  // []) | tojson ),
        ( (.attestationRules // []) | tojson ),
        ( $sets | length ),
        ( [ $sets[].name ] | join(" | ") ),
        ( [ $sets[].ref ] | map(select(. != "")) | join(" | ") ) ] )
  | @csv
  ' > "$out"

printf '✔ wrote %s\n' "$out" >&2
python3 - "$out" <<'PY' >&2
import csv, sys
rows = list(csv.DictReader(open(sys.argv[1])))
linked = sum(1 for r in rows if int(r["observed_association_count"]) > 0)
print(f"  validators in catalog: {len(rows)}")
print(f"  with >=1 observed association: {linked}")
print(f"  with none (orphan / unobserved): {len(rows) - linked}")
PY
