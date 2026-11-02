#!/bin/sh
DEBUGCONF=/var/config/odi-panel-debug.conf
DEBUGROOT=/tmp/odi-debug
DEBUGKEYS='DEBUG_SECONDS DEBUG_REMOTE DEBUG_BOOT DEBUG_REGISTRATION'
debug_get() {
 dg=$(sed -n "s/^$1=//p" "$DEBUGCONF" 2>/dev/null)
 if [ -z "$dg" ];then case "$1" in DEBUG_SECONDS) dg=180;; *) dg=0;; esac;fi
 printf '%s' "$dg"
}
debug_valid() {
 case "$1:$2" in DEBUG_SECONDS:60|DEBUG_SECONDS:180|DEBUG_SECONDS:300|DEBUG_SECONDS:600|DEBUG_REMOTE:0|DEBUG_REMOTE:1|DEBUG_BOOT:0|DEBUG_BOOT:1|DEBUG_REGISTRATION:0|DEBUG_REGISTRATION:1) return 0;; esac
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

debug_pid_tick() {
 # LinuxThreads task names are not reliable identities; cmdline can stall SSH.
 case "$1" in ''|*[!0-9]*) return 1;; esac
 IFS= read -r dp_stat <"/proc/$1/stat" || return 1
 printf '%s\n' "${dp_stat##*) }" | awk '{print $20}'
}
debug_stop_readers() {
 while read -r dr_pid dr_tick;do
  case "$dr_pid:$dr_tick" in *[!0-9:]*|:*) continue;; esac
  [ -n "$dr_tick" ] && [ "$(debug_pid_tick "$dr_pid" 2>/dev/null)" = "$dr_tick" ] && kill "$dr_pid" 2>/dev/null
 done <"$DEBUGROOT/readers"
}
debug_trace_ready() {
 debug_cli get logfile || return 1
 grep -q 'Raw Mode' "$DEBUGROOT/cli-result" && grep -q 'Parsed Mode' "$DEBUGROOT/cli-result" &&
 grep -qi '^0xffffffff' "$DEBUGROOT/cli-result" && grep -q '^/tmp/omcilog$' "$DEBUGROOT/cli-result"
}
debug_guard_remaining() {
 dg_until=$(cat "$DEBUGROOT/reboot-until" 2>/dev/null)
 case "$dg_until" in ''|*[!0-9]*|0*) printf 0;return;; esac
 [ "${#dg_until}" -le 9 ] || { printf 0;return; }
 dg_now=$(log_tick);dg_left=$((dg_until-dg_now))
 if [ "$dg_left" -gt 0 ] && [ "$dg_left" -le 300 ] && grep -q '^state=capturing$' "$DEBUGROOT/status" 2>/dev/null;then printf '%s' "$dg_left";else printf 0;fi
}
debug_send() {
 [ "$remote" = 1 ] || return 0
 host=$(log_get LOG_HOST);port=$(log_get LOG_PORT);tag=$(log_get LOG_TAG)
 log_valid LOG_HOST "$host" && [ -n "$host" ] && log_valid LOG_PORT "$port" && log_valid LOG_TAG "$tag" || return 1
 set --
 for part in credentials-wire wire.1 wire;do [ ! -f "$DEBUGROOT/$part" ] || set -- "$@" "$DEBUGROOT/$part";done
 debug_send_batch RAW "$sent" "$@";sent=$next_sent
 set --
 for part in reg-wire.1 reg-wire;do [ ! -f "$DEBUGROOT/$part" ] || set -- "$@" "$DEBUGROOT/$part";done
 debug_send_batch REGISTRATION "${reg_sent:-0}" "$@";reg_sent=$next_sent
}
debug_send_batch() {
 stream=$1;seen=$2;shift 2;next_sent=$seen
 [ "$#" -gt 0 ] || return 0
 # Native ASCII lines are carried without filtering. Avoid blocking FIFO readers.
 rm -f "$DEBUGROOT/sent-new"
 awk -F'|' -v seen="$seen" -v tag="$tag" -v stream="$stream" '
  {id=$1+0;if(id<=seen)next;line=substr($0,index($0,"|")+1);msg="<134>1 - " tag " odi-full - " stream " - seq=" id " " line;
   if(total+length(msg)+12>32768)exit;printf "%d %s",length(msg),msg;total+=length(msg)+12;last=id}
  END{if(last)print last >lastfile}
 ' lastfile="$DEBUGROOT/sent-new" "$@" >"$DEBUGROOT/batch" 2>/dev/null
 [ -s "$DEBUGROOT/batch" ] || return 0
 /bin/nc "$host" "$port" <"$DEBUGROOT/batch" >/dev/null 2>&1 & net_pid=$!
 (sleep 2;kill -TERM "$net_pid" 2>/dev/null;sleep 1;kill -KILL "$net_pid" 2>/dev/null) & net_timer=$!
 wait "$net_pid";net_rc=$?
 kill "$net_timer" 2>/dev/null;wait "$net_timer" 2>/dev/null;net_pid='';net_timer=''
 [ ! -s "$DEBUGROOT/sent-new" ] || next_sent=$(cat "$DEBUGROOT/sent-new")
 printf 'rc=%s\nuptime=%s\nstream=%s\nattempted_sequence=%s\n' "$net_rc" "$(log_tick)" "$stream" "$next_sent" >"$DEBUGROOT/syslog-status"
}

debug_reg_command() {
 [ $(($(log_tick)-started)) -lt "$seconds" ] && [ ! -f "$DEBUGROOT/stop" ] || return
 reg_time=$(log_tick)
 "$@" >"$DEBUGROOT/reg-result" 2>&1 & reg_pid=$!
 (sleep 2;kill -TERM "$reg_pid" 2>/dev/null;sleep 1;kill -KILL "$reg_pid" 2>/dev/null) & reg_timer=$!
 wait "$reg_pid";reg_rc=$?
 kill "$reg_timer" 2>/dev/null;wait "$reg_timer" 2>/dev/null
 reg_bytes=0;reg_wirebytes=0
 [ ! -f "$DEBUGROOT/registration" ] || reg_bytes=$(cksum "$DEBUGROOT/registration" | awk '{print $2}')
 [ ! -f "$DEBUGROOT/reg-wire" ] || reg_wirebytes=$(cksum "$DEBUGROOT/reg-wire" | awk '{print $2}')
 { printf 'uptime=%s command=%s rc=%s\n' "$reg_time" "$*" "$reg_rc";cat "$DEBUGROOT/reg-result"; } |
  awk -v output="$DEBUGROOT/registration" -v wire="$DEBUGROOT/reg-wire" -v errorfile="$DEBUGROOT/reader-error" -v limit=32768 -v initial_bytes="$reg_bytes" -v initial_wirebytes="$reg_wirebytes" -v initial_seq="$reg_seq" -v seqfile="$DEBUGROOT/reg-seq" -f /etc/scripts/odi-debug-ring.awk
 reg_seq=$(cat "$DEBUGROOT/reg-seq")
}
debug_registration() {
 reg_now=$(log_tick)
 [ $((reg_now-reg_last)) -ge 2 ] || return
 [ ! -d /tmp/odi-panel/write.lock ] || return
 reg_last=$reg_now
 debug_reg_command /bin/diag gpon get onu-state
 reg_stage=$(log_pon_state "$DEBUGROOT/reg-result")
 for reg_side in ds-omci us-omci;do debug_reg_command /bin/diag gpon show counter global "$reg_side";done
 # These hardware counters may clear on read; preserve raw samples and times.
 if [ "$reg_o5" = 0 ] && [ "$reg_stage" = O5 ];then
  reg_o5=$reg_now
  debug_reg_command /bin/diag gpon get alarm-status
  for reg_side in active ds-plm us-plm;do debug_reg_command /bin/diag gpon show counter global "$reg_side";done
 fi
 if [ "$reg_o5" -gt 0 ] && [ "$reg_stage" = O5 ] && [ "$reg_mib" = 0 ] && [ $((reg_now-reg_o5)) -ge 10 ];then
  reg_mib=1
  for reg_class in 262 268 45;do debug_reg_command /bin/omcicli mib get "$reg_class";done
 fi
}
