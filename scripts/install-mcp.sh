#!/usr/bin/env bash
# Install each config/mcp/<name>.json into one or more tools' MCP config, merging
# into the tool's existing file (never overwriting the user's other servers).
# Usage: install-mcp.sh <target>... [--workspace DIR]
#   targets: any name in config/mcp-targets.tsv, or 'all'   (global by default)
# Secrets: ${KIT_SECRET:NAME} in an env value is resolved from config/secrets.env.
# A missing secret or missing toml module makes install fail loudly (no partial
# or literal write).
set -euo pipefail
kit=$(cd "$(dirname "$0")/.." && pwd)
. "$kit/scripts/lib/tools.sh"
MCP_TSV="$kit/config/mcp-targets.tsv"
secrets="$kit/config/secrets.env"

targets=(); ws=""
while [ $# -gt 0 ]; do
  case $1 in
    --workspace) ws=$2; shift 2 ;;
    -*) echo "unknown arg: $1" >&2; exit 2 ;;
    *) targets+=("$1"); shift ;;
  esac
done
[ ${#targets[@]} -gt 0 ] || { sed -n '2,6p' "$0"; exit 2; }

# expand 'all' / validate against the MCP table (not tools.tsv: a tool might
# support skills but we list it here only if it has MCP)
mcp_names=$(grep -v '^#' "$MCP_TSV" | awk -F'\t' 'NF{print $1}')
resolved=()
for want in "${targets[@]}"; do
  if [ "$want" = all ]; then resolved+=($mcp_names)
  elif printf '%s\n' $mcp_names | grep -qxF "$want"; then resolved+=("$want")
  else echo "unknown mcp target: $want (known: $(echo $mcp_names | tr '\n' ' '))" >&2; exit 1; fi
done

mcp_field() { grep -v '^#' "$MCP_TSV" | awk -F'\t' -v n="$1" -v c="$2" '$1==n{print $c}'; }
mcp_path()  { local v; v=$(mcp_field "$1" "$2"); case $v in '~/'*) printf '%s\n' "$HOME/${v#'~/'}" ;; *) printf '%s\n' "$v" ;; esac; }

[ -f "$secrets" ] || echo "note: no config/secrets.env; \${KIT_SECRET:...} refs will fail if used" >&2

# resolve ${KIT_SECRET:NAME} in a JSON file's string values. Fails if a key is absent.
resolve_secrets() { # infile outfile
  python3 - "$1" "$2" "$secrets" <<'PY'
import json,sys,re,os
inf,outf,secf=sys.argv[1:4]
sec={}
if os.path.exists(secf):
    for line in open(secf):
        line=line.strip()
        if not line or line.startswith('#') or '=' not in line: continue
        k,v=line.split('=',1); sec[k.strip()]=v.strip()
pat=re.compile(r'\$\{KIT_SECRET:([A-Za-z0-9_]+)\}')
def sub(s):
    def r(m):
        k=m.group(1)
        if k not in sec: sys.exit(f"missing secret {k} in {secf} (referenced by MCP def)")
        return sec[k]
    return pat.sub(r,s)
def walk(o):
    if isinstance(o,dict): return {k:walk(v) for k,v in o.items()}
    if isinstance(o,list): return [walk(x) for x in o]
    if isinstance(o,str): return sub(o)
    return o
d=json.load(open(inf))
json.dump(walk(d),open(outf,'w'),indent=2)
PY
}

for t in "${resolved[@]}"; do
  fmt=$(mcp_field "$t" 4); container=$(mcp_field "$t" 5)
  if [ -n "$ws" ]; then dest=$(mcp_path "$t" 3); [ "$dest" = - ] && { echo "SKIP $t: no project MCP file"; continue; }; dest="$ws/$dest"
  else dest=$(mcp_path "$t" 2); [ "$dest" = - ] && { echo "SKIP $t: no global MCP file"; continue; }; fi
  [ "$fmt" = toml ] && { python3 -c 'import toml' 2>/dev/null || { echo "SKIP $t: python 'toml' missing (pip install -r requirements.txt)"; continue; }; }
  mkdir -p "$(dirname "$dest")"

  installed=0
  for src in "$kit"/config/mcp/*.json; do
    [ -e "$src" ] || { echo "SKIP $t: no servers in config/mcp/"; break; }
    name=$(basename "$src" .json)
    tgts=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("targets","all"))' "$src")
    case ",$tgts," in *,all,*|*",$t,"*) ;; *) echo "SKIP $t: $name (targets=$tgts)"; continue ;; esac
    # strip kit metadata, resolve secrets
    clean=$(mktemp); resolved_f=$(mktemp)
    python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); [d.pop(k,None) for k in ("targets",)]; json.dump(d,open(sys.argv[2],"w"))' "$src" "$clean"
    resolve_secrets "$clean" "$resolved_f"
    if [ "$fmt" = json ]; then
      merge_mcp_json "$dest" "$container" "$name" "$resolved_f"
    else
      merge_mcp_toml "$dest" "$container" "$name" "$resolved_f"
    fi
    rm -f "$clean" "$resolved_f"
    echo "OK   $t: $name"; installed=$((installed+1))
  done
done
