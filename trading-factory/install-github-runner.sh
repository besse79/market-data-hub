#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
REPO="besse79/market-data-hub"
ROOT="$HOME/trading-factory-agent"
DIR="$ROOT/runner-mkd"
mkdir -p "$ROOT/reports"
if [[ -e "$DIR/.runner" ]]; then
  echo "Runner already registered at $DIR; no changes made."
  exit 0
fi
if [[ -e "$DIR" ]] && [[ -n "$(ls -A "$DIR")" ]]; then
  echo "BLOCKED: $DIR is non-empty and not a registered runner" >&2
  exit 2
fi
for cmd in gh curl tar sha256sum python3; do command -v "$cmd" >/dev/null || { echo "BLOCKED: missing $cmd" >&2; exit 2; }; done
gh auth status >/dev/null 2>&1 || { echo "BLOCKED: gh not authenticated" >&2; exit 2; }
echo "Installing official GitHub Actions runner for $REPO"
echo "Runner scope: repository only. Label: trading-factory. No DB changes."
release="$(gh api repos/actions/runner/releases/latest)"
readarray -t asset < <(printf '%s' "$release" | python3 -c '
import json,sys
d=json.load(sys.stdin)
a=[x for x in d.get("assets",[]) if x["name"].startswith("actions-runner-linux-x64-") and x["name"].endswith(".tar.gz")]
if len(a)!=1:raise SystemExit("BLOCKED: expected one Linux x64 runner asset")
x=a[0];digest=x.get("digest","")
if not digest.startswith("sha256:"):raise SystemExit("BLOCKED: release asset SHA256 unavailable")
print(x["browser_download_url"]);print(digest[7:])
')
[[ "${#asset[@]}" == 2 ]] || exit 2
mkdir -p "$DIR"
archive="$(mktemp "$ROOT/runner.XXXXXXXX.tar.gz")"
trap 'rm -f "$archive"' EXIT
curl -fL --retry 3 --connect-timeout 15 --max-time 300 "${asset[0]}" -o "$archive"
printf '%s  %s\n' "${asset[1]}" "$archive" | sha256sum --check --status || { echo "BLOCKED: SHA256 mismatch" >&2; exit 3; }
tar -xzf "$archive" -C "$DIR" --no-same-owner
cd "$DIR"
token="$(gh api -X POST "repos/$REPO/actions/runners/registration-token" --jq .token)"
[[ -n "$token" ]] || { echo "BLOCKED: no registration token" >&2; exit 3; }
./config.sh --unattended --url "https://github.com/$REPO" --token "$token" --name "trading-factory-wsl-$(hostname | tr -cd '[:alnum:]-')" --labels trading-factory --work "_work" --replace
unset token
echo "REGISTERED: $REPO"
echo "Runner is installed but NOT started."
echo "Start in a dedicated WSL terminal: cd '$DIR' && ./run.sh"
echo "Stop: Ctrl+C. Keep this terminal open while executing jobs."
echo "Runner location: $DIR"
