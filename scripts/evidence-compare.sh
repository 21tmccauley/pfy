#!/usr/bin/env bash
#
# evidence-compare.sh — build a CSV comparing PROD evidence-set names (from
# mapping.json) against the TEST workspace's evidence sets. Full outer join on
# normalized name (lowercase + trimmed + collapsed whitespace); pass an ALIASES
# file to align known renames (e.g. "RDS Encryption Status" -> "RDS Encryption")
# onto one "both" row instead of two.
#
#   DST_KEY=<test-token> ./scripts/evidence-compare.sh [mapping.json] [out.csv]
#   ALIASES=aliases.json DST_KEY=<test-token> ./scripts/evidence-compare.sh
#
# Env: DST_KEY (required), DST_URL (default stage), ALIASES (optional).
# Requires: pfy, jq.

set -euo pipefail

DST_URL="${DST_URL:-https://stage.paramify.com/api/v0}"
die() { printf 'error: %s\n' "$*" >&2; exit 1; }

command -v pfy >/dev/null || die "pfy not found on PATH"
command -v jq  >/dev/null || die "jq not found on PATH"
[ -n "${DST_KEY:-}" ] || die "DST_KEY is required"

in="${1:-mapping.json}"
out="${2:-evidence-compare.csv}"
[ -f "$in" ] || die "mapping file not found: $in"

alias_arg=/dev/null
if [ -n "${ALIASES:-}" ]; then
  [ -f "$ALIASES" ] || die "ALIASES file not found: $ALIASES"
  alias_arg="$ALIASES"
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

printf '▶ TEST = %s — listing evidence sets…\n' "$DST_URL" >&2
PARAMIFY_URL="$DST_URL" PARAMIFY_API_KEY="$DST_KEY" pfy api GET evidence \
  | jq '(.evidences // .) | map({name, referenceId})' > "$TMP/test.json"

jq -rn \
  --slurpfile mp "$in" \
  --slurpfile tv "$TMP/test.json" \
  --slurpfile al "$alias_arg" \
  '
  def norm: ascii_downcase | gsub("^\\s+|\\s+$";"") | gsub("\\s+";" ");
  ($mp[0]) as $m | ($tv[0]) as $Tlist | (($al[0]) // {}) as $A |
  # prod sets keyed by normalized name (or the alias target, so renames align)
  ( [ $m.evidenceSets[]
      | { pname: .name,
          pref: (.referenceId // ""),
          key:  (if ($A[.name]|type)=="string" then ($A[.name]|norm) else (.name|norm) end),
          vc:   (.validators | length) } ] ) as $prod |
  ( [ $Tlist[] | { tname:.name, tref:(.referenceId // ""), key:(.name|norm) } ] ) as $test |
  ( reduce $prod[] as $p ({}; .[$p.key] += [$p]) ) as $P |
  ( reduce $test[] as $t ({}; .[$t.key] += [$t]) ) as $Tk |
  ( (($P|keys) + ($Tk|keys)) | unique ) as $keys |
  ( [ $keys[]
      | ($P[.] // []) as $p | ($Tk[.] // []) as $t
      | { prod:   ([$p[].pname] | join(" ; ")),
          pref:   ([$p[].pref] | join(" ; ")),
          test:   ([$t[].tname] | join(" ; ")),
          tref:   ([$t[].tref] | join(" ; ")),
          status: (if ($p|length>0) and ($t|length>0) then "both"
                   elif ($p|length>0) then "prod_only" else "test_only" end),
          vc:     (if ($p|length>0) then ([$p[].vc] | add) else null end) } ]
    | sort_by( (if .status=="both" then 0 elif .status=="prod_only" then 1 else 2 end),
               (.prod + .test) ) ) as $rows |
  (["prod_reference_id","prod_name","test_reference_id","test_name","status","prod_validator_count"]),
  ( $rows[] | [ .pref, .prod, .tref, .test, .status, (.vc // "") ] )
  | @csv
  ' > "$out"

printf '✔ wrote %s\n' "$out" >&2
python3 - "$out" <<'PY' >&2
import csv, sys
from collections import Counter
rows = list(csv.DictReader(open(sys.argv[1])))
c = Counter(r["status"] for r in rows)
print(f"  rows: {len(rows)}")
for k in ("both", "prod_only", "test_only"):
    print(f"  {k}: {c.get(k, 0)}")
PY
