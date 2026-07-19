#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LOCK_FILE="$PROJECT_DIR/deploy/upstreams.lock.json"
PROFILE="${1:-hosted-voice-mvp}"
TARGET_DIR="${2:-$PROJECT_DIR/.upstreams}"

if ! command -v jq >/dev/null 2>&1; then
  printf '%s\n' 'jq is required to read deploy/upstreams.lock.json.' >&2
  exit 1
fi

mkdir -p "$TARGET_DIR"

clone_pinned() {
  local id="$1"
  local repository="$2"
  local revision="$3"
  local destination="$TARGET_DIR/$id"

  if [ -d "$destination/.git" ]; then
    local existing_origin
    existing_origin="$(git -C "$destination" remote get-url origin)"
    if [ "$existing_origin" != "$repository" ]; then
      printf 'Refusing to reuse %s: origin is %s, expected %s\n' "$destination" "$existing_origin" "$repository" >&2
      exit 1
    fi
  else
    git clone --filter=blob:none --no-checkout "$repository" "$destination"
  fi

  git -C "$destination" fetch --depth 1 origin "$revision"
  git -C "$destination" checkout --detach "$revision"
  printf '%-24s %s\n' "$id" "$(git -C "$destination" rev-parse HEAD)"
}

# These are development source bundles, not end-user runtime profiles.
case "$PROFILE" in
  hosted-voice-mvp)
    JQ_FILTER='select(.profiles | index("hosted-voice-mvp"))'
    ;;
  core)
    JQ_FILTER='select(.profiles | index("core"))'
    ;;
  android-bt)
    JQ_FILTER='select((.profiles | index("core")) or (.profiles | index("android-bt")))'
    ;;
  telecom-lab)
    JQ_FILTER='select((.profiles | index("core")) or (.profiles | index("telecom-lab")))'
    ;;
  voice-lab)
    JQ_FILTER='select((.profiles | index("core")) or (.profiles | index("voice-lab")) or (.profiles | index("wow-lab")))'
    ;;
  linux-nvidia)
    JQ_FILTER='select((.profiles | index("core")) or (.profiles | index("linux-nvidia")))'
    ;;
  all)
    JQ_FILTER='.'
    ;;
  *)
    printf 'Unknown source bundle %s. Use hosted-voice-mvp, core, telecom-lab, voice-lab, android-bt, linux-nvidia, or all.\n' "$PROFILE" >&2
    exit 1
    ;;
esac

while IFS=$'\t' read -r id repository revision; do
  clone_pinned "$id" "$repository" "$revision"
done < <(jq -r ".upstreams[] | $JQ_FILTER | [.id, .repository, .revision] | @tsv" "$LOCK_FILE")
