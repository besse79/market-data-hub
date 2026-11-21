#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
ROOT="$HOME/trading-factory-agent"
mkdir -p "$ROOT"/{reports,workspaces,logs}
for cmd in git gh python3 node npm docker; do
 if command -v "$cmd" >/dev/null 2>&1; then
  printf '%s: %s\n' "$cmd" "$(command -v "$cmd")"
 else
  printf '%s: MISSING\n' "$cmd"
 fi
done
python3 - "$ROOT" <<'PY'
import json,sys,datetime,os,platform,shutil
root=sys.argv[1]
report={
 "timestamp_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
 "hostname":platform.node(),
 "mode":"diagnostic_only",
 "commands":{k:bool(shutil.which(k)) for k in ("git","gh","python3","node","npm","docker")},
 "github_runner_registered":False,
 "codex_authenticated":False,
 "database_writes":False,
 "production_deploy":False,
}
path=os.path.join(root,"reports","bootstrap.json")
with open(path,"w") as f:json.dump(report,f,indent=2)
print("REPORT="+path)
PY
echo "NEXT: inspect report, then configure a dedicated GitHub runner account and scoped permissions."
