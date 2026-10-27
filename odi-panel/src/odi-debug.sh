#!/bin/sh
# Full private diagnostic session; no HTTP-supplied paths or shell commands.
PATH=/bin:/sbin:/usr/bin:/usr/sbin
export PATH
LC_ALL=C
export LC_ALL
umask 077
. /etc/scripts/odi-log-lib.sh
. /etc/scripts/odi-debug-lib.sh
case "$1" in start|boot|worker|stop) ;; *) exit 2;; esac
if [ "$1" = boot ] && [ "$(debug_get DEBUG_BOOT)" != 1 ];then exit 0;fi
mkdir -p "$DEBUGROOT" || exit 1
if [ "$1" = stop ];then
 : >"$DEBUGROOT/stop"
 if grep -q '^state=stop_failed$' "$DEBUGROOT/status" 2>/dev/null;then
  debug_cli set logfile 0 || exit 1
  while IFS= read -r reader;do
   case "$reader" in ''|*[!0-9]*) continue;; esac
   if grep -q 'odi-debug-ring.awk' "/proc/$reader/cmdline" 2>/dev/null;then kill "$reader" 2>/dev/null;fi
  done <"$DEBUGROOT/readers"
  rm -f /tmp/omcilog /tmp/omcilog.par "$DEBUGROOT/ready" "$DEBUGROOT/boot-active"
  debug_status stopped;rm -r "$DEBUGROOT/running"
 fi
 exit 0
fi
if [ "$1" != worker ];then
 mkdir "$DEBUGROOT/starting" 2>/dev/null || exit 75
 if [ -d "$DEBUGROOT/running" ];then rm -r "$DEBUGROOT/starting";exit 75;fi
 # All removed files are fixed outputs inside this session directory.
 rm -f "$DEBUGROOT/stop" "$DEBUGROOT/status" "$DEBUGROOT/reader-error" "$DEBUGROOT/raw" "$DEBUGROOT/raw.1" "$DEBUGROOT/parsed" "$DEBUGROOT/parsed.1" "$DEBUGROOT/wire" "$DEBUGROOT/wire.1" "$DEBUGROOT/sent-new" "$DEBUGROOT/syslog-status" "$DEBUGROOT/ready" "$DEBUGROOT/failed" "$DEBUGROOT/credentials-wire"
 rm -f "$DEBUGROOT/previous-omcilog" "$DEBUGROOT/previous-omcilog.par" "$DEBUGROOT/native-before.txt" "$DEBUGROOT/credentials.txt"
 started=$(log_tick);seconds=$(debug_get DEBUG_SECONDS);remote=$(debug_get DEBUG_REMOTE);debug_status preparing
 mode=live;[ "$1" != boot ] || mode=boot
 /etc/scripts/odi-debug.sh worker "$mode" </dev/null >/dev/null 2>&1 &
 if [ "$mode" = live ];then
  attempt=0
  while [ "$attempt" -lt 5 ] && [ ! -d "$DEBUGROOT/running" ];do sleep 1;attempt=$((attempt+1));done
  rm -r "$DEBUGROOT/starting"
  [ -d "$DEBUGROOT/running" ] || exit 1
  exit 0
 fi
 # A short bounded handshake reports preparation failures to CGI/startup.
 attempt=0
 while [ "$attempt" -lt 5 ];do
  [ ! -f "$DEBUGROOT/ready" ] || { rm -r "$DEBUGROOT/starting";exit 0; }
  [ ! -f "$DEBUGROOT/failed" ] || { rm -r "$DEBUGROOT/starting";exit 1; }
  sleep 1;attempt=$((attempt+1))
 done
 rm -r "$DEBUGROOT/starting";exit 1
fi
mkdir "$DEBUGROOT/running" 2>/dev/null || exit 75
seconds=$(debug_get DEBUG_SECONDS);remote=$(debug_get DEBUG_REMOTE)
if ! debug_valid DEBUG_SECONDS "$seconds" || ! debug_valid DEBUG_REMOTE "$remote";then
 debug_status invalid_config;: >"$DEBUGROOT/failed";rm -r "$DEBUGROOT/running";exit 2
fi
worker_mode=$2;finish_state=stopped
started=$(log_tick);sent=0;cli_pid='';cli_timer='';net_pid='';net_timer='';raw_pid='';parsed_pid='';trace_on=0;owns_fifo=0
cleanup() {
 # Closing the native writers before removing FIFO readers avoids SIGPIPE.
 if [ "$trace_on" = 1 ];then debug_cli set logfile 0 || { debug_status stop_failed;return; };fi
 # Allow complete final records to drain after fclose in the native daemon.
 if [ -n "$raw_pid$parsed_pid" ];then
  (sleep 2;printf 'drain_timeout\n' >"$DEBUGROOT/reader-error";[ -z "$raw_pid" ] || kill "$raw_pid" 2>/dev/null;[ -z "$parsed_pid" ] || kill "$parsed_pid" 2>/dev/null) & drain_timer=$!
  [ -z "$raw_pid" ] || wait "$raw_pid" 2>/dev/null
  [ -z "$parsed_pid" ] || wait "$parsed_pid" 2>/dev/null
  kill "$drain_timer" 2>/dev/null;wait "$drain_timer" 2>/dev/null
 fi
 [ -z "$net_pid" ] || kill "$net_pid" 2>/dev/null
 [ -z "$net_timer" ] || kill "$net_timer" 2>/dev/null
 if [ "$owns_fifo" = 1 ];then rm -f /tmp/omcilog /tmp/omcilog.par;fi
 rm -f "$DEBUGROOT/ready"
 rm -f "$DEBUGROOT/boot-active"
 debug_status "$finish_state"
 rm -r "$DEBUGROOT/running"
}
trap cleanup 0
trap 'exit 0' 1 2 15
rm -f "$DEBUGROOT/failed" "$DEBUGROOT/ready"
# Preserve original native logging configuration as reference for the archive.
if [ "$worker_mode" != boot ];then
 debug_cli get logfile || :
 cp "$DEBUGROOT/cli-result" "$DEBUGROOT/native-before.txt"
 debug_cli set logfile 0 || { finish_state=disable_failed;: >"$DEBUGROOT/failed";exit 1; }
fi
# Default logging file names are fixed in libomci_mib.so (SFU 240408).
for item in /tmp/omcilog /tmp/omcilog.par;do
 if [ -f "$item" ];then
  existing_bytes=$(cksum "$item" | awk '{print $2}')
  if [ "$existing_bytes" -gt 131072 ];then finish_state=existing_log_too_large;: >"$DEBUGROOT/failed";exit 1;fi
  cp "$item" "$DEBUGROOT/previous-${item##*/}" || exit 1
 fi
done
rm -f /tmp/omcilog /tmp/omcilog.par
owns_fifo=1
mknod /tmp/omcilog p && mknod /tmp/omcilog.par p || { finish_state=fifo_setup_failed;: >"$DEBUGROOT/failed";exit 1; }
for part in raw raw.1 parsed parsed.1 wire wire.1 credentials-wire;do : >"$DEBUGROOT/$part";done
awk -v output="$DEBUGROOT/raw" -v wire="$DEBUGROOT/wire" -v errorfile="$DEBUGROOT/reader-error" -f /etc/scripts/odi-debug-ring.awk </tmp/omcilog & raw_pid=$!
awk -v output="$DEBUGROOT/parsed" -v errorfile="$DEBUGROOT/reader-error" -f /etc/scripts/odi-debug-ring.awk </tmp/omcilog.par & parsed_pid=$!
printf '%s\n%s\n' "$raw_pid" "$parsed_pid" >"$DEBUGROOT/readers"
trace_on=1
if [ "$worker_mode" != boot ];then
 debug_cli set logfile 3 ffffffff || { finish_state=native_trace_setup_failed;: >"$DEBUGROOT/failed";exit 1; }
fi
debug_status capturing
if [ "$worker_mode" = boot ];then printf 1 >"$DEBUGROOT/boot-active";fi
: >"$DEBUGROOT/ready"
if [ "$worker_mode" = boot ];then
 # Native startup will open the FIFO writers after this handshake.
 printf 'DEBUG_SECONDS=%s\nDEBUG_REMOTE=%s\nDEBUG_BOOT=0\n' "$seconds" "$remote" >"$DEBUGROOT/boot-consumed"
 cp "$DEBUGROOT/boot-consumed" "$DEBUGCONF"
fi
{
 printf 'PRIVATE FULL DEBUG - unredacted values\nuptime=%s\n' "$(log_tick)"
 IFS= read -r capture_boot </proc/sys/kernel/random/boot_id;printf 'kernel_boot_id=%s\n' "$capture_boot"
 for key in GPON_SN GPON_PLOAM_FORMAT GPON_PLOAM_PASSWD LOID LOID_PASSWD LOID_OLD LOID_PASSWD_OLD ELAN_MAC_ADDR MAC_KEY SUSER_NAME SUSER_PASSWORD USER_NAME USER_PASSWORD PON_VENDOR_ID GPON_ONU_MODEL HW_HWVER HW_SERIAL_NO OUI OMCI_OLT_MODE OMCI_TM_OPT OMCI_FAKE_OK OMCC_VER OMCI_CUSTOM_ME OMCI_VEIP_SLOT_ID OMCI_LOGFILE OMCI_LOGFILE_MASK OMCI_DBGLVL VLAN_CFG_TYPE VLAN_MANU_MODE VLAN_MANU_TAG_VID VLAN_MANU_TAG_PRI LAN_SPEED_MODE;do /etc/scripts/flash get "$key" 2>/dev/null;done
} >"$DEBUGROOT/credentials.txt"
# Explicit full syslog selection also includes the credential snapshot once.
if [ "$remote" = 1 ];then awk '{print (NR-1000) "|CREDENTIAL " $0}' "$DEBUGROOT/credentials.txt" >"$DEBUGROOT/credentials-wire";sent=-1001;fi
while :;do
 [ ! -f "$DEBUGROOT/stop" ] || break
 [ $(($(log_tick)-started)) -lt "$seconds" ] || break
 debug_send || :
 debug_status capturing
 sleep 1
done
exit 0
