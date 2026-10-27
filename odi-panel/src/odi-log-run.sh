#!/bin/sh
PATH=/bin:/sbin:/usr/bin:/usr/sbin
export PATH
LC_ALL=C
export LC_ALL
umask 077
. /etc/scripts/odi-log-lib.sh
case "$1" in ''|once|test) ;; *) exit 2;; esac
mkdir -p "$LOGSTATE" || exit 1
run_lock=logger.lock;[ "$1" != test ] || run_lock=logger-test.lock
mkdir "$LOGSTATE/$run_lock" 2>/dev/null || exit 75
read_pid='';read_timer='';net_pid='';net_timer='';owns_read=0;owns_send=0
cleanup() {
 [ -z "$read_pid" ] || kill -TERM "$read_pid" 2>/dev/null
 [ -z "$read_timer" ] || kill "$read_timer" 2>/dev/null
 [ -z "$net_pid" ] || kill -TERM "$net_pid" 2>/dev/null
 [ -z "$net_timer" ] || kill "$net_timer" 2>/dev/null
 [ "$owns_read" = 0 ] || rm -r "$LOGSTATE/read.lock"
 [ "$owns_send" = 0 ] || rm -r "$LOGSTATE/syslog.lock"
 rm -r "$LOGSTATE/$run_lock"
}
trap cleanup 0
trap 'exit 0' 1 2 15
if [ "$1" = test ]; then
 [ "$(log_get LOG_REMOTE)" = 1 ] && [ -n "$(log_get LOG_HOST)" ] || exit 2
 log_event 'event=SYSLOG_TEST';exit $?
fi
# The kernel boot id gives restart correlation without a device serial or MAC.
IFS= read -r boot_id </proc/sys/kernel/random/boot_id
case "$boot_id" in ''|*[!a-f0-9-]*) boot_id=unknown;; esac
log_event "event=LOGGER_START boot=$boot_id" || :
last_stage='';last_mode='';last_mods='';last_config='';heartbeat=0
while :; do
 config="$(log_get LOG_LOCAL):$(log_get LOG_REMOTE):$(log_get LOG_HOST):$(log_get LOG_PORT):$(log_get LOG_TAG)"
 if [ "$config" != "$last_config" ]; then log_event 'event=LOG_CONFIG_CHANGED' || :;last_config=$config; fi
 if [ ! -d "$LOGSTATE/write.lock" ] && mkdir "$LOGSTATE/read.lock" 2>/dev/null; then
  owns_read=1
  if [ ! -d "$LOGSTATE/write.lock" ]; then
   /bin/diag gpon get onu-state >"$LOGSTATE/logger.lock/pon" 2>&1 & read_pid=$!
   (sleep 2;kill -TERM "$read_pid" 2>/dev/null;sleep 1;kill -KILL "$read_pid" 2>/dev/null) & read_timer=$!
   wait "$read_pid";read_rc=$?
   kill "$read_timer" 2>/dev/null;wait "$read_timer" 2>/dev/null;read_pid='';read_timer=''
   stage=read_error
   if [ "$read_rc" = 0 ]; then
    stage=$(sed -n 's/.*ONU *State *: *O\{0,1\}\([1-7]\).*/O\1/p' "$LOGSTATE/logger.lock/pon")
    case "$stage" in O1|O2|O3|O4|O5|O6|O7) ;; *) stage=unknown;; esac
   fi
   mode=$(sed -n 's/.*lan_sds_mode *= *\([0-7]\).*/\1/p' /proc/lan_sds/lan_sds_cfg 2>/dev/null)
   case "$mode" in 0|1|2|3|4|5|6|7) ;; *) mode=unknown;; esac
  else stage='';mode=''; fi
  rm -r "$LOGSTATE/read.lock";owns_read=0
  if [ -n "$stage" ] && [ "$stage" != "$last_stage" ]; then log_event "event=PON_STATE previous=${last_stage:-unknown} state=$stage rc=$read_rc" || :;last_stage=$stage; fi
  if [ -n "$mode" ] && [ "$mode" != "$last_mode" ]; then log_event "event=SFP_MODE mode=$mode" || :;last_mode=$mode; fi
 fi
 mods=$(sed -n 's/^speed=//p' "$LOGSTATE/mods-status" 2>/dev/null)
 case "$mods" in off|0|1|2|3|75) ;; *) mods=unknown;; esac
 if [ "$mods" != "$last_mods" ]; then log_event "event=MOD_RESULT speed=$mods" || :;last_mods=$mods; fi
 now=$(log_tick)
 if [ $((now - heartbeat)) -ge 60 ]; then
  free=$(awk '/^MemFree:/{print $2;exit}' /proc/meminfo);case "$free" in ''|*[!0-9]*) free=0;; esac
  log_event "event=HEARTBEAT boot=$boot_id pon=${last_stage:-unknown} free_kb=$free" || :;heartbeat=$now
 fi
 printf 'pid=%s\nuptime=%s\npon=%s\nmode=%s\n' "$$" "$now" "${last_stage:-unknown}" "${last_mode:-unknown}" >"$LOGSTATE/logger-status"
 [ "$1" != once ] || exit 0
 sleep 5
done
