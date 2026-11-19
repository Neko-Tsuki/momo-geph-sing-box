#!/bin/sh
# Download latest SRS bundle from a public GitHub Release and install it safely.
set -eu

CONFIG="/etc/momo/rule-updater.conf"
[ -r "$CONFIG" ] || {
  echo "Missing $CONFIG; copy rule-updater.conf.example and edit GITHUB_REPO." >&2
  exit 1
}
. "$CONFIG"

: "${GITHUB_REPO:?Set GITHUB_REPO=owner/repository in $CONFIG}"
RELEASE_TAG="${RELEASE_TAG:-rules-latest}"
DEST_DIR="${DEST_DIR:-/etc/momo/rule_set}"
STATE_FILE="${STATE_FILE:-/etc/momo/.momo-rule-set-sha256}"
RESTART_SERVICE="${RESTART_SERVICE:-}"

case "$GITHUB_REPO" in
  */*) ;;
  *) echo "GITHUB_REPO must be owner/repository" >&2; exit 1 ;;
esac
OWNER="${GITHUB_REPO%%/*}"
REPOSITORY="${GITHUB_REPO#*/}"
case "$OWNER$REPOSITORY" in
  *[!A-Za-z0-9_.-]*|'') echo "Invalid GITHUB_REPO: $GITHUB_REPO" >&2; exit 1 ;;
esac
case "$REPOSITORY" in
  */*) echo "GITHUB_REPO must contain exactly one slash" >&2; exit 1 ;;
esac
case "$RELEASE_TAG" in
  *[!A-Za-z0-9_.-]*|'')
    echo "Invalid RELEASE_TAG" >&2
    exit 1
    ;;
esac

BASE="https://github.com/${GITHUB_REPO}/releases/download/${RELEASE_TAG}"
TMP="/tmp/momo-rule-update.$$"
BACKUP=""
mkdir -p "$TMP"
cleanup() {
  if [ -n "$BACKUP" ] && [ -d "$BACKUP" ] && [ ! -e "$DEST_DIR" ]; then
    mv "$BACKUP" "$DEST_DIR" 2>/dev/null || true
  fi
  rm -rf "$TMP"
}
trap cleanup EXIT HUP INT TERM

fetch() {
  url="$1"; output="$2"
  if command -v curl >/dev/null 2>&1; then
    curl -fL --retry 3 --connect-timeout 20 "$url" -o "$output"
  elif command -v wget >/dev/null 2>&1; then
    wget -q "$url" -O "$output"
  else
    echo "Install curl or wget first." >&2
    return 1
  fi
}

echo "[momo-rule-updater] Fetching latest.txt"
fetch "$BASE/latest.txt" "$TMP/latest.txt"

ASSET="$(sed -n 's/^asset=//p' "$TMP/latest.txt" | head -n1)"
EXPECTED_SHA="$(sed -n 's/^sha256=//p' "$TMP/latest.txt" | head -n1)"

case "$ASSET" in
  rule-set-[A-Za-z0-9._-]*.tar.gz) ;;
  *) echo "Invalid archive name in latest.txt: $ASSET" >&2; exit 1 ;;
esac
case "$ASSET" in
  */*|*..*) echo "Unsafe archive name in latest.txt: $ASSET" >&2; exit 1 ;;
esac
case "$EXPECTED_SHA" in
  *[!0-9a-f]*|'') echo "Invalid SHA-256 in latest.txt" >&2; exit 1 ;;
esac
[ "${#EXPECTED_SHA}" -eq 64 ] || { echo "SHA-256 must be 64 hex chars" >&2; exit 1; }

if [ -r "$STATE_FILE" ] && [ "$(cat "$STATE_FILE")" = "$EXPECTED_SHA" ]; then
  echo "[momo-rule-updater] Already up to date ($EXPECTED_SHA)"
  exit 0
fi

echo "[momo-rule-updater] Downloading $ASSET"
fetch "$BASE/$ASSET" "$TMP/rule-set.tar.gz"

printf '%s  %s\n' "$EXPECTED_SHA" "$TMP/rule-set.tar.gz" | sha256sum -c -

# Validate archive entries: flat files only, exactly 20 non-empty .srs files after extraction.
tar -tzf "$TMP/rule-set.tar.gz" > "$TMP/archive.list"
COUNT=0
while IFS= read -r entry; do
  case "$entry" in
    *.srs) ;;
    *) echo "Unexpected archive entry: $entry" >&2; exit 1 ;;
  esac
  case "$entry" in
    */*|.*) echo "Archive must contain flat SRS filenames only: $entry" >&2; exit 1 ;;
  esac
  COUNT=$((COUNT + 1))
done < "$TMP/archive.list"
[ "$COUNT" -eq 20 ] || { echo "Expected 20 SRS files, found $COUNT" >&2; exit 1; }

mkdir "$TMP/stage"
tar -xzf "$TMP/rule-set.tar.gz" -C "$TMP/stage"
for name in \
  geosite-fakeipfilter geosite-ai geosite-youtube geosite-google geosite-github \
  geosite-onedrive geosite-microsoft geosite-apple geosite-telegram geosite-tiktok \
  geosite-netflix geosite-paypal geosite-steam geosite-steamcn geosite-\\!cn geosite-cn \
  geoip-cn geoip-google geoip-telegram geoip-netflix
do
  [ -s "$TMP/stage/$name.srs" ] || {
    echo "Missing/empty rule set: $name.srs" >&2
    exit 1
  }
done

PARENT="$(dirname "$DEST_DIR")"
mkdir -p "$PARENT"
BACKUP="${DEST_DIR}.backup.$$"
if [ -d "$DEST_DIR" ]; then
  mv "$DEST_DIR" "$BACKUP"
fi
if ! mv "$TMP/stage" "$DEST_DIR"; then
  if [ -d "$BACKUP" ]; then mv "$BACKUP" "$DEST_DIR"; BACKUP=""; fi
  echo "Could not install new rule directory; restored previous directory." >&2
  exit 1
fi
[ ! -d "$BACKUP" ] || rm -rf "$BACKUP"
BACKUP=""

mkdir -p "$(dirname "$STATE_FILE")"
printf '%s\n' "$EXPECTED_SHA" > "$STATE_FILE"

echo "[momo-rule-updater] Installed 20 SRS files. SHA-256: $EXPECTED_SHA"

if [ -n "$RESTART_SERVICE" ]; then
  case "$RESTART_SERVICE" in
    *[!A-Za-z0-9_-]*) echo "Invalid RESTART_SERVICE name" >&2; exit 1 ;;
  esac
  if [ -x "/etc/init.d/$RESTART_SERVICE" ]; then
    "/etc/init.d/$RESTART_SERVICE" restart
  else
    echo "Service /etc/init.d/$RESTART_SERVICE not found; rules installed but service not restarted." >&2
    exit 1
  fi
else
  echo "[momo-rule-updater] No restart requested. Restart/reload Momo if your core requires it to reload local rule sets."
fi
