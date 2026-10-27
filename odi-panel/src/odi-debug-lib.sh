#!/bin/sh
DEBUGCONF=/var/config/odi-panel-debug.conf
DEBUGROOT=/tmp/odi-debug
DEBUGKEYS='DEBUG_SECONDS DEBUG_REMOTE DEBUG_BOOT'
debug_get() {
 dg=$(sed -n "s/^$1=//p" "$DEBUGCONF" 2>/dev/null)
 if [ -z "$dg" ];then case "$1" in DEBUG_SECONDS) dg=180;; *) dg=0;; esac;fi
 printf '%s' "$dg"
}
debug_valid() {
 case "$1:$2" in DEBUG_SECONDS:60|DEBUG_SECONDS:180|DEBUG_SECONDS:300|DEBUG_SECONDS:600|DEBUG_REMOTE:0|DEBUG_REMOTE:1|DEBUG_BOOT:0|DEBUG_BOOT:1) return 0;; esac
 return 1
}
debug_status() {
 printf 'state=%s\nstarted_uptime=%s\nupdated_uptime=%s\nseconds=%s\nremote=%s\n' "$1" "${started:-0}" "$(log_tick)" "${seconds:-0}" "${remote:-0}" >"$DEBUGROOT/status"
}
debug_cli() {
 /bin/omcicli "$@" >"$DEBUGROOT/cli-result" 2>&1 & cli_pid=$!
 (sleep 2;kill -TERM "$cli_pid" 2>/dev/null;sleep 1;kill -KILL "$cli_pid" 2>/dev/null) & cli_timer=$!
 wait "$cli_pid";cli_rc=$?
 kill "$cli_timer" 2>/dev/null;wait "$cli_timer" 2>/dev/null;cli_pid='';cli_timer=''
 return "$cli_rc"
}
debug_send() {
 [ "$remote" = 1 ] || return 0
 host=$(log_get LOG_HOST);port=$(log_get LOG_PORT);tag=$(log_get LOG_TAG)
 log_valid LOG_HOST "$host" && [ -n "$host" ] && log_valid LOG_PORT "$port" && log_valid LOG_TAG "$tag" || return 1
 set --
 for part in credentials-wire wire.1 wire;do [ ! -f "$DEBUGROOT/$part" ] || set -- "$@" "$DEBUGROOT/$part";done
 [ "$#" -gt 0 ] || return 0
 # Native ASCII lines are carried without filtering. Avoid blocking FIFO readers.
 awk -F'|' -v seen="$sent" -v tag="$tag" '
  {id=$1+0;if(id<=seen)next;line=substr($0,index($0,"|")+1);msg="<134>1 - " tag " odi-full - RAW - seq=" id " " line;
   if(total+length(msg)+12>32768)exit;printf "%d %s",length(msg),msg;total+=length(msg)+12;last=id}
  END{if(last)print last >lastfile}
 ' lastfile="$DEBUGROOT/sent-new" "$@" >"$DEBUGROOT/batch" 2>/dev/null
 [ -s "$DEBUGROOT/batch" ] || return 0
 /bin/nc "$host" "$port" <"$DEBUGROOT/batch" >/dev/null 2>&1 & net_pid=$!
 (sleep 2;kill -TERM "$net_pid" 2>/dev/null;sleep 1;kill -KILL "$net_pid" 2>/dev/null) & net_timer=$!
 wait "$net_pid";net_rc=$?
 kill "$net_timer" 2>/dev/null;wait "$net_timer" 2>/dev/null;net_pid='';net_timer=''
 [ ! -s "$DEBUGROOT/sent-new" ] || sent=$(cat "$DEBUGROOT/sent-new")
 printf 'rc=%s\nuptime=%s\nattempted_sequence=%s\n' "$net_rc" "$(log_tick)" "$sent" >"$DEBUGROOT/syslog-status"
}
