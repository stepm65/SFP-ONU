#!/bin/sh
# Small event journal. Configuration is data, never sourced as shell code.
LOGCONF=/var/config/odi-panel-logging.conf
LOGSTATE=/tmp/odi-panel
LOGKEYS='LOG_LOCAL LOG_REMOTE LOG_HOST LOG_PORT LOG_TAG'
. /etc/scripts/odi-debug-lib.sh
log_default() {
 case "$1" in LOG_LOCAL) printf 1;; LOG_REMOTE) printf 0;; LOG_PORT) printf 514;; LOG_TAG) printf onu;; esac
}
log_get() {
 lg=$(sed -n "s/^$1=//p" "$LOGCONF" 2>/dev/null)
 [ -n "$lg" ] || lg=$(log_default "$1")
 printf '%s' "$lg"
}
log_valid() {
 case "$1" in
 LOG_LOCAL|LOG_REMOTE) case "$2" in 0|1) return 0;; esac;;
 LOG_HOST) [ -z "$2" ] && return 0; [ "${#2}" -le 15 ] && printf '%s\n' "$2" | awk -F. 'NF!=4{exit 1}{for(i=1;i<=4;i++)if($i!~/^[0-9]+$/||length($i)>3||$i+0>255||length($i)>1&&substr($i,1,1)=="0")exit 1;if($1==0||$1>=224)exit 1}' ;return $?;;
 LOG_PORT) case "$2" in ''|*[!0-9]*|0*) return 1;; esac; [ "${#2}" -le 5 ] && [ "$2" -le 65535 ];return $?;;
 LOG_TAG) [ "${#2}" -ge 1 ] && [ "${#2}" -le 32 ] || return 1;case "$2" in *[!A-Za-z0-9._-]*) return 1;; *) return 0;; esac;;
 esac
 return 1
}
log_tick() { IFS=' ' read -r lt rest </proc/uptime; printf '%s' "${lt%%.*}"; }
log_local() {
 [ "$(log_get LOG_LOCAL)" = 1 ] || return 0
 mkdir -p "$LOGSTATE" || return 1
 mkdir "$LOGSTATE/events.lock" 2>/dev/null || return 1
 # Each file is <=32768 bytes, with one rotated predecessor.
 if [ -f "$LOGSTATE/events.log" ]; then
  set -- $(cksum "$LOGSTATE/events.log")
  if [ $(($2 + ${#log_line} + 1)) -gt 32768 ]; then
   cp "$LOGSTATE/events.log" "$LOGSTATE/events.log.1" || { rm -r "$LOGSTATE/events.lock"; return 1; }
   : >"$LOGSTATE/events.log"
  fi
 fi
 printf '%s\n' "$log_line" >>"$LOGSTATE/events.log"
 rm -r "$LOGSTATE/events.lock"
}
log_send() {
 [ "$(log_get LOG_REMOTE)" = 1 ] || return 0
 lh=$(log_get LOG_HOST);lp=$(log_get LOG_PORT);label=$(log_get LOG_TAG)
 log_valid LOG_HOST "$lh" && [ -n "$lh" ] && log_valid LOG_PORT "$lp" && log_valid LOG_TAG "$label" || return 1
 mkdir "$LOGSTATE/syslog.lock" 2>/dev/null || return 75
 owns_send=1
 # RFC 5424: unsynchronised clock is NILVALUE, uptime is in MSG.
 # RFC 6587: octet-counted framing. Every event is printable ASCII.
 packet="<134>1 - $label odi-panel - EVENT - $log_line"
 printf '%s %s' "${#packet}" "$packet" >"$LOGSTATE/syslog.lock/packet"
 # Target BusyBox nc has only -l/-p; its own -w option is NOT compiled in.
 /bin/nc "$lh" "$lp" <"$LOGSTATE/syslog.lock/packet" >/dev/null 2>&1 & net_pid=$!
 (sleep 2; kill -TERM "$net_pid" 2>/dev/null; sleep 1; kill -KILL "$net_pid" 2>/dev/null) & net_timer=$!
 wait "$net_pid"; net_rc=$?
 kill "$net_timer" 2>/dev/null; wait "$net_timer" 2>/dev/null
 net_pid='';net_timer=''
 rm -r "$LOGSTATE/syslog.lock";owns_send=0
 # A completed TCP send is not an acknowledgement by the syslog application.
 printf 'rc=%s\nuptime=%s\n' "$net_rc" "$(log_tick)" >"$LOGSTATE/syslog-status"
 [ "$net_rc" = 0 ]
}
log_event() {
 # Callers supply only fixed, credential-free event summaries. No raw OMCI.
 [ "${#1}" -le 240 ] || return 1
 case "$1" in ''|*[!A-Za-z0-9._:/=\ -]*) return 1;; esac
 log_line="uptime=$(log_tick) $1"
 log_local || :
 log_send
}
