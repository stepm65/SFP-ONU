#!/bin/sh
# Called only by the reviewed normal ONU-G Reboot handler, after its response.
PATH=/bin:/sbin:/usr/bin:/usr/sbin
export PATH
umask 077
. /etc/scripts/odi-log-lib.sh
remaining=$(debug_guard_remaining)
decision=accepted
[ "$remaining" = 0 ] || decision=skipped
# No network I/O or flash writes on the native OMCI thread.
mkdir -p "$DEBUGROOT"
if mkdir "$DEBUGROOT/reboot-event.lock" 2>/dev/null;then
 size=0
 [ ! -f "$DEBUGROOT/reboot-events" ] || size=$(cksum "$DEBUGROOT/reboot-events" | awk '{print $2}')
 if [ "$size" -gt 7900 ];then cp "$DEBUGROOT/reboot-events" "$DEBUGROOT/reboot-events.1";: >"$DEBUGROOT/reboot-events";fi
 printf 'uptime=%s event=OMCI_REBOOT decision=%s remaining=%s\n' "$(log_tick)" "$decision" "$remaining" >>"$DEBUGROOT/reboot-events"
 rm -r "$DEBUGROOT/reboot-event.lock"
fi
[ "$decision" = skipped ] && exit 0
printf '1\n' >/proc/load_reboot
