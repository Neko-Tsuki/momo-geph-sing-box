#!/bin/sh
# Run once on OpenWrt to schedule daily updates at 04:35 local router time.
set -eu
SCRIPT="/usr/bin/update-momo-rules.sh"
[ -x "$SCRIPT" ] || { echo "Missing executable $SCRIPT" >&2; exit 1; }
CRON_LINE='35 4 * * * /usr/bin/update-momo-rules.sh >> /tmp/momo-rule-update.log 2>&1'
grep -Fqx "$CRON_LINE" /etc/crontabs/root 2>/dev/null || {
  echo "$CRON_LINE" >> /etc/crontabs/root
}
 /etc/init.d/cron restart
echo "Scheduled daily Momo rule update at 04:35 router local time."
