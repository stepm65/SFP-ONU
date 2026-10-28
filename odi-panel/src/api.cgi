#!/bin/sh
# ODI Panel: authenticated, fixed-operation CGI. No eval / arbitrary commands.
PATH=/bin:/sbin:/usr/bin:/usr/sbin
export PATH
LC_ALL=C
export LC_ALL
umask 077
PANEL_VERSION=1.9.18
STATE=/tmp/odi-panel
FLASH=/etc/scripts/flash
NV=/bin/nv
XML=/bin/xmlconfig
. /etc/scripts/odi-mods-lib.sh
. /etc/scripts/odi-log-lib.sh
KEYS='OMCI_TM_OPT OMCI_VEIP_SLOT_ID OMCI_CUSTOM_ME GPON_SN GPON_PLOAM_FORMAT GPON_PLOAM_PASSWD LOID LOID_PASSWD PON_VENDOR_ID GPON_ONU_MODEL HW_HWVER HW_SERIAL_NO OUI OMCI_OLT_MODE OMCI_FAKE_OK OMCC_VER OMCI_SW_VER1 OMCI_SW_VER2 ELAN_MAC_ADDR MAC_KEY VLAN_CFG_TYPE VLAN_MANU_MODE VLAN_MANU_TAG_VID VLAN_MANU_TAG_PRI LAN_SPEED_MODE'
hex() {
 printf '%s' "$1" | awk 'BEGIN{for(i=1;i<256;i++)ord[sprintf("%c",i)]=i} {if(NR>1)printf "0a";for(i=1;i<=length($0);i++)printf "%02x",ord[substr($0,i,1)]}'
}
emit() { printf '%s=' "$1"; hex "$2"; printf '\n'; }
headers() {
 printf 'Content-Type: text/plain; charset=utf-8\r\nCache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\nX-Frame-Options: SAMEORIGIN\r\n\r\n'
}
fail() { printf 'Status: %s\r\n' "$1"; headers; emit error "$2"; exit 1; }
[ -n "$REMOTE_USER" ] || fail '403 Forbidden' 'Authentication required. Open the panel with the administrator account.'
case "$REQUEST_METHOD" in GET|POST) ;; *) fail '405 Method Not Allowed' 'GET or POST required';; esac
mkdir -p "$STATE" || fail '500 Internal Server Error' 'Cannot initialize runtime directory'
if [ ! -s "$STATE/token" ]; then
 if mkdir "$STATE/token.lock" 2>/dev/null; then
  IFS= read -r token </proc/sys/kernel/random/uuid
  case "$token" in ''|*[!0-9a-f-]*) rm -r "$STATE/token.lock"; fail '500 Internal Server Error' 'Random token unavailable';; esac
  printf '%s\n' "$token" >"$STATE/token"
  rm -r "$STATE/token.lock"
 else
  fail '503 Service Unavailable' 'Initialization in progress. Retry.'
 fi
fi
IFS= read -r token <"$STATE/token"
get_flash() {
 gf=$($FLASH get "$1" 2>/dev/null)
 case "$gf" in "$1="*) printf '%s' "${gf#*=}";; *) return 1;; esac
}
get_nv() {
 gn=$($NV getenv "$1" 2>/dev/null)
 case "$gn" in "$1="*) printf '%s' "${gn#*=}";; *) return 1;; esac
}
# xmlconfig renders the 3-byte OUI array as "aa,bb,cc" (at least while unset),
# while the factory form and this panel use 6 hex digits. Compare one canonical form.
norm_oui() { printf '%s' "$1" | sed 's/,//g;y/ABCDEF/abcdef/'; }
get_value() {
 case "$1" in
 sw_custom_version0|sw_custom_version1) get_nv "$1" || :;;
 OUI) go=$(get_flash OUI) || return 1; norm_oui "$go";;
 *) get_flash "$1";;
 esac
}
if [ "$REQUEST_METHOD" = GET ]; then
 case "$QUERY_STRING" in debug_status)
  headers;for key in $DEBUGKEYS;do emit "$key" "$(debug_get "$key")";done
  emit debug_status "$(cat "$DEBUGROOT/status" 2>/dev/null)"
  emit debug_error "$(cat "$DEBUGROOT/reader-error" 2>/dev/null)"
  for kind in raw parsed;do
   total=0
   for suffix in '' .1;do if [ -f "$DEBUGROOT/$kind$suffix" ];then bytes=$(cksum "$DEBUGROOT/$kind$suffix" | awk '{print $2}');total=$((total+bytes));fi;done
   emit "debug_$kind""_bytes" "$total"
  done
  emit debug_syslog_status "$(cat "$DEBUGROOT/syslog-status" 2>/dev/null)"
  emit ok 1;exit 0;;
 logs)
  headers
  for key in $LOGKEYS;do emit "$key" "$(log_get "$key")";done
  emit logger_status "$(cat "$STATE/logger-status" 2>/dev/null)"
  emit syslog_status "$(cat "$STATE/syslog-status" 2>/dev/null)"
  emit event_log "$(cat "$STATE/events.log.1" "$STATE/events.log" 2>/dev/null)"
  emit ok 1;exit 0;;
 operation)
  headers
  emit firmware_status "$(cat "$STATE/firmware-status" 2>/dev/null)"
  worker_pid=$(cat "$STATE/firmware-worker.pid" 2>/dev/null)
  case "$worker_pid" in ''|*[!0-9]*) ;; *) emit firmware_worker_alive "$(kill -0 "$worker_pid" 2>/dev/null && printf 1 || printf 0)";;esac
  emit firmware_phase "$(cat "$STATE/firmware-phase" 2>/dev/null)"
  emit firmware_error "$(cat "$STATE/firmware-error" 2>/dev/null)"
  # Erase progress uses carriage returns, so line limits alone can return the
  # entire log. Keep status polling small and show the most recent progress.
  emit firmware_log "$(awk 'BEGIN{RS="\r"}{if(NR>1)s=s "\r";s=s $0;if(length(s)>2048)s=substr(s,length(s)-2047)}END{printf "%s",s}' "$STATE/firmware-update.log" 2>/dev/null)"
  emit ok 1; exit 0;;
 telemetry|diagnostics)
  . /etc/scripts/odi-diagnostics.sh
  diag_collect || fail '503 Service Unavailable' 'Diagnostics busy. Retry.'
  exit 0;; esac
 [ "$QUERY_STRING" = state ] || fail '400 Bad Request' 'Unknown query'
 headers; emit csrf "$token"
 for key in $LOGKEYS;do emit "$key" "$(log_get "$key")";done
 for key in $DEBUGKEYS;do emit "$key" "$(debug_get "$key")";done
 emit panel_version "$PANEL_VERSION"
 emit uptime "$(cat /proc/uptime)"
 emit pending_keys "$(cat "$STATE/pending-keys" 2>/dev/null)"
 emit mods_status "$(cat "$STATE/mods-status" 2>/dev/null)"
 emit mods_log "$(cat "$STATE/mods.log" 2>/dev/null)"
 for item in status ingress egress ability ports; do emit "uplink_$item" "$(cat "$STATE/uplink-$item" 2>/dev/null)"; done
 for item in LAN_SDS_MODE DEVICE_TYPE PON_MODE; do emit "$item" "$(get_flash "$item")"; done
 emit firmware_phase "$(cat "$STATE/firmware-phase" 2>/dev/null)"
 emit boot_confirmed "$(get_nv sw_active)"
 mirror=unknown
 if lc=$(get_flash LOID) && lm=$(get_flash LOID_OLD) && pc=$(get_flash LOID_PASSWD) && pm=$(get_flash LOID_PASSWD_OLD); then
  mirror=0; [ "$lc" != "$lm" ] || [ "$pc" != "$pm" ] || mirror=1
 fi
 emit LOID_MIRROR_OK "$mirror"
 for key in OMCI_SW_VER1 OMCI_SW_VER2; do emit "original_$key" "$(sed -n "s/^$key=//p" /var/config/odi-original-omci.conf 2>/dev/null)"; done
 for key in $MODKEYS;do emit "$key" "$(mod_get "$key")";done
 for key in $KEYS; do
  if value=$(get_value "$key"); then emit "$key" "$value"; fi
 done
 for key in sw_active sw_commit sw_version0 sw_version1 sw_custom_version0 sw_custom_version1; do
  value=$(get_nv "$key") || value=''
  emit "$key" "$value"
 done
 IFS= read -r version </etc/version; emit firmware "$version"
 emit link_actual "$(cat /proc/lan_sds/lan_sds_cfg 2>/dev/null)"
 emit partitions "$(cat /proc/mtd 2>/dev/null)"
 emit pending "$([ -f "$STATE/pending" ] && printf 1 || printf 0)"
 emit firmware_status "$(cat "$STATE/firmware-status" 2>/dev/null)"
 for n in 0 1; do emit "bank_invalid$n" "$([ -f "/var/config/odi-invalid-bank$n" ] && printf 1 || printf 0)"; done
 emit ok 1; exit 0
fi
case "$CONTENT_LENGTH" in ''|*[!0-9]*) fail '400 Bad Request' 'Invalid request length';; esac
[ "${#CONTENT_LENGTH}" -le 4 ] && [ "$CONTENT_LENGTH" -le 4096 ] || fail '413 Payload Too Large' 'Request exceeds 4096 bytes'
case "$CONTENT_TYPE" in 'text/plain'|'text/plain;charset=UTF-8'|'text/plain; charset=UTF-8') ;; *) fail '415 Unsupported Media Type' 'text/plain required';; esac
IFS= read -r action
case "$action" in action=save|action=bank|action=reboot|action=mods|action=restore_versions|action=uplink_apply|action=uplink_check|action=logging|action=log_test|action=log_clear|action=debug_config|action=debug_start|action=debug_stop|action=debug_export) action=${action#*=};; *) fail '400 Bad Request' 'Unknown action';; esac
IFS= read -r supplied
[ "$supplied" = "csrf=$token" ] || fail '403 Forbidden' 'Invalid CSRF token. Reload the page.'
mkdir "$STATE/write.lock" 2>/dev/null || fail '409 Conflict' 'Another operation is running'
WORK=$STATE/write.lock
trap 'rm -r "$WORK"' 0
trap 'exit 1' 1 2 15
[ ! -d "$STATE/read.lock" ] || fail '409 Conflict' 'Diagnostics running. Retry after collection.'
case "$action" in uplink_apply|uplink_check)
 while IFS= read -r extra; do [ -z "$extra" ] || fail '400 Bad Request' 'Uplink operation accepts no parameters'; done
 /etc/scripts/odi-uplink.sh "${action#uplink_}" api >/dev/null 2>&1
 uplink_rc=$?
 [ "$uplink_rc" != 75 ] || fail '409 Conflict' 'Uplink operation is already running'
 headers; emit uplink_rc "$uplink_rc"
 for item in status ingress egress ability ports; do emit "uplink_$item" "$(cat "$STATE/uplink-$item" 2>/dev/null)"; done
 emit ok 1; exit 0;; esac
# All request values are hex-encoded printable ASCII; decoded data never becomes shell code.
decode() {
 dec=''; rest=$1
 case "$rest" in *[!0-9a-fA-F]*) return 1;; esac
 [ "${#rest}" -le 240 ] || return 1
 while [ -n "$rest" ]; do
  [ "${#rest}" -ge 2 ] || return 1
  pair=${rest%"${rest#??}"}; rest=${rest#??}
  n=$((0x$pair)); [ "$n" -ge 32 ] && [ "$n" -le 126 ] || return 1
  oct=$(printf '%03o' "$n"); ch=$(printf "\\$oct"); dec=$dec$ch
 done
}
if [ "$action" = debug_config ];then
 count=0
 while IFS='=' read -r key value;do
  case " $DEBUGKEYS " in *" $key "*) [ -n "$key" ] || fail '400 Bad Request' 'Unknown debug field';; *) fail '400 Bad Request' 'Unknown debug field';; esac
  [ ! -f "$WORK/$key" ] || fail '400 Bad Request' 'Duplicate debug field'
  decode "$value" && debug_valid "$key" "$dec" || fail '400 Bad Request' "Invalid value: $key"
  printf '%s' "$dec" >"$WORK/$key";count=$((count+1))
 done
 [ "$count" -gt 0 ] || fail '400 Bad Request' 'No debug fields'
 for key in $DEBUGKEYS;do [ -f "$WORK/$key" ] || debug_get "$key" >"$WORK/$key";done
 if [ "$(cat "$WORK/DEBUG_REMOTE")" = 1 ];then
  log_valid LOG_HOST "$(log_get LOG_HOST)" && [ -n "$(log_get LOG_HOST)" ] || fail '400 Bad Request' 'Configure the syslog server before forwarding full debug'
 fi
 for key in $DEBUGKEYS;do printf '%s=%s\n' "$key" "$(cat "$WORK/$key")";done >"$WORK/debug.conf"
 cp "$WORK/debug.conf" "$DEBUGCONF" && cmp "$WORK/debug.conf" "$DEBUGCONF" >/dev/null || fail '500 Internal Server Error' 'Debug configuration read-back failed'
 headers;for key in $DEBUGKEYS;do emit "$key" "$(debug_get "$key")";done;emit ok 1;exit 0
fi
case "$action" in debug_start|debug_stop|debug_export)
 while IFS= read -r extra;do [ -z "$extra" ] || fail '400 Bad Request' 'Debug action accepts no parameters';done
 if [ "$action" = debug_export ];then
  [ ! -d "$DEBUGROOT/running" ] && [ ! -d "$DEBUGROOT/starting" ] || fail '409 Conflict' 'Stop full debug before downloading'
  [ -f "$DEBUGROOT/credentials.txt" ] || fail '409 Conflict' 'No private capture is available'
  set -- status credentials.txt
  for part in raw raw.1 parsed parsed.1 native-before.txt previous-omcilog previous-omcilog.par reader-error syslog-status;do [ ! -f "$DEBUGROOT/$part" ] || set -- "$@" "$part";done
  printf 'Content-Type: application/x-tar\r\nContent-Disposition: attachment; filename="ODI-full-debug-PRIVATE.tar"\r\nCache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\n\r\n'
  tar -cf - -C "$DEBUGROOT" "$@";exit $?
 fi
 debug_job=stop;[ "$action" != debug_start ] || debug_job=start
 /etc/scripts/odi-debug.sh "$debug_job" >/dev/null 2>&1;debug_rc=$?
 [ "$debug_rc" != 75 ] || fail '409 Conflict' 'Full debug is already running'
 headers;emit debug_rc "$debug_rc";emit debug_status "$(cat "$DEBUGROOT/status" 2>/dev/null)";emit ok 1;exit 0;;esac
if [ "$action" = logging ]; then
 count=0
 while IFS='=' read -r key value;do
  case " $LOGKEYS " in *" $key "*) [ -n "$key" ] || fail '400 Bad Request' 'Unknown log field';; *) fail '400 Bad Request' 'Unknown log field';; esac
  [ ! -f "$WORK/$key" ] || fail '400 Bad Request' 'Duplicate log field'
  decode "$value" && log_valid "$key" "$dec" || fail '400 Bad Request' "Invalid value: $key"
  printf '%s' "$dec" >"$WORK/$key";count=$((count+1))
 done
 [ "$count" -gt 0 ] || fail '400 Bad Request' 'No logging fields provided'
 for key in $LOGKEYS;do [ -f "$WORK/$key" ] || log_get "$key" >"$WORK/$key";done
 if [ "$(cat "$WORK/LOG_REMOTE")" = 1 ];then [ -s "$WORK/LOG_HOST" ] || fail '400 Bad Request' 'Syslog IPv4 address required';fi
 for key in $LOGKEYS;do printf '%s=%s\n' "$key" "$(cat "$WORK/$key")";done >"$WORK/logging.conf"
 cp "$WORK/logging.conf" "$LOGCONF" || fail '500 Internal Server Error' 'Cannot save logging configuration'
 cmp "$WORK/logging.conf" "$LOGCONF" >/dev/null || fail '500 Internal Server Error' 'Logging read-back failed'
 headers;for key in $LOGKEYS;do emit "$key" "$(log_get "$key")";done;emit ok 1;exit 0
fi
case "$action" in log_clear|log_test)
 while IFS= read -r extra;do [ -z "$extra" ] || fail '400 Bad Request' 'Log operation accepts no parameters';done
 if [ "$action" = log_clear ];then
  mkdir "$STATE/events.lock" 2>/dev/null || fail '409 Conflict' 'Journal busy. Retry.'
  rm -f "$STATE/events.log" "$STATE/events.log.1";rm -r "$STATE/events.lock"
  headers;emit ok 1
 else
  /etc/scripts/odi-log-run.sh test >/dev/null 2>&1;test_rc=$?
  headers;emit syslog_test_rc "$test_rc";emit syslog_status "$(cat "$STATE/syslog-status" 2>/dev/null)";emit ok 1
 fi
 exit 0;;esac
valid() {
 vk=$1; vv=$2
 case "$vk" in
 GPON_SN) [ "${#vv}" = 12 ] && case "$vv" in *[!A-Za-z0-9]*) false;; *) tail=${vv#????}; case "$tail" in *[!0-9A-Fa-f]*) false;; *) true;; esac;; esac;;
 PON_VENDOR_ID) [ "${#vv}" = 4 ] && case "$vv" in *[!A-Za-z0-9]*) false;; *) true;; esac;;
 GPON_PLOAM_PASSWD) [ "${#vv}" = 20 ] && case "$vv" in *[!0-9a-fA-F]*) false;; *) true;; esac;;
 GPON_PLOAM_FORMAT) case "$vv" in 0|1) true;; *) false;; esac;;
 OUI) [ "${#vv}" = 6 ] && case "$vv" in *[!0-9A-Fa-f]*) false;; *) true;; esac;;
 OMCI_OLT_MODE) case "$vv" in 0|1|2|3) true;; *) false;; esac;;
 OMCI_TM_OPT) case "$vv" in 0|1|2) true;; *) false;; esac;;
 OMCI_VEIP_SLOT_ID) case "$vv" in ''|*[!0-9]*) false;; *) [ "${#vv}" -le 3 ] && [ "$vv" -le 255 ];; esac;;
 OMCI_CUSTOM_ME) case "$vv" in ''|*[!0-9]*) false;; *) [ "${#vv}" -le 10 ] && awk -v n="$vv" 'BEGIN{exit !(n<=4294967295)}';; esac;;
 OMCI_FAKE_OK|VLAN_CFG_TYPE|VLAN_MANU_MODE) case "$vv" in 0|1) true;; *) false;; esac;;
 LAN_SPEED_MODE) case "$vv" in 1|2|3|4|5|6|7) true;; *) false;; esac;;
 OMCC_VER) case "$vv" in 128|129|130|131|132|133|134|150|160|161|162|163|176|177|178|179) true;; *) false;; esac;;
 VLAN_MANU_TAG_PRI) case "$vv" in 0|1|2|3|4|5|6|7) true;; *) false;; esac;;
 VLAN_MANU_TAG_VID) case "$vv" in ''|*[!0-9]*|0*) false;; *) [ "${#vv}" -le 4 ] && [ "$vv" -le 4094 ];; esac;;
 ELAN_MAC_ADDR) [ "${#vv}" = 12 ] && case "$vv" in *[!0-9A-Fa-f]*) false;; *) true;; esac;;
 MAC_KEY) [ "${#vv}" = 32 ] && case "$vv" in *[!0-9A-Fa-f]*) false;; *) true;; esac;;
 GPON_ONU_MODEL) text_valid "$vv" 20;; HW_HWVER) text_valid "$vv" 14;;
 sw_custom_version0|sw_custom_version1) [ -z "$vv" ] || text_valid "$vv" 14;;
 LOID) [ -z "$vv" ] || text_valid "$vv" 28;; LOID_PASSWD) [ -z "$vv" ] || text_valid "$vv" 12;; HW_SERIAL_NO) text_valid "$vv" 64;;
 *) false;;
 esac
}
text_valid() {
 [ -n "$1" ] && [ "${#1}" -le "$2" ] || return 1
 case "$1" in *[!a-zA-Z0-9._:/+@\ -]*) return 1;; esac
}
if [ "$action" = mods ]; then
 count=0
 while IFS='=' read -r key value;do
  case " $MODKEYS " in *" $key "*) [ -n "$key" ] || fail '400 Bad Request' 'Unknown field';; *) fail '400 Bad Request' 'Unknown field';; esac
  [ ! -f "$WORK/$key" ] || fail '400 Bad Request' 'Duplicate field'
  decode "$value" && mod_valid "$key" "$dec" || fail '400 Bad Request' "Invalid value: $key"
  printf '%s' "$dec" >"$WORK/$key";printf '%s\n' "$key" >>"$WORK/submitted";count=$((count+1))
 done
 [ "$count" -gt 0 ] || fail '400 Bad Request' 'No mod fields provided'
 # Merge a partial request with saved values; unrelated mods remain untouched.
 vlan_changed=0
 for key in MOD_VLAN MOD_VLANS MOD_ENTITIES MOD_FWDOP MOD_PAIRS;do
  [ ! -f "$WORK/$key" ] || vlan_changed=1
 done
 for key in $MODKEYS;do
  [ -f "$WORK/$key" ] || mod_get "$key" >"$WORK/$key"
 done
 mode=$(cat "$WORK/MOD_VLAN")
 if [ "$vlan_changed" = 1 ] && [ "$mode" = tag ];then
  mod_valid MOD_FWDOP "$(cat "$WORK/MOD_FWDOP")" && mod_valid MOD_VLANS "$(cat "$WORK/MOD_VLANS")" && mod_valid MOD_ENTITIES "$(cat "$WORK/MOD_ENTITIES")" || fail '400 Bad Request' 'Invalid VLAN filter'
  [ -s "$WORK/MOD_VLANS" ] || [ -s "$WORK/MOD_ENTITIES" ] || fail '400 Bad Request' 'Select VLAN IDs or entities'
 fi
 if [ "$vlan_changed" = 1 ] && [ "$mode" = fwdop ];then
  mod_valid MOD_PAIRS "$(cat "$WORK/MOD_PAIRS")" || fail '400 Bad Request' 'Invalid entity and FwdOp pairs'
  [ -s "$WORK/MOD_PAIRS" ] || fail '400 Bad Request' 'Specify entity and FwdOp pairs'
 fi
 # Complete file is built first, then copied over the config; no eval or sourced data.
 tmpconf=$MODCONF.new.$$
 for key in $MODKEYS;do printf '%s=%s\n' "$key" "$(cat "$WORK/$key")";done >"$tmpconf" || fail '500 Internal Server Error' 'Cannot save mod configuration'
 # BusyBox on SFU 240408 has no mv/rename: copy the complete file, then remove it.
 if ! cp "$tmpconf" "$MODCONF";then rm -f "$tmpconf";fail '500 Internal Server Error' 'Cannot save mod configuration';fi
 rm -f "$tmpconf"
 : >"$STATE/pending"
 cat "$WORK/submitted" >>"$STATE/pending-keys"
 headers;emit ok 1;exit 0
fi
count=0
while IFS='=' read -r key value; do
 [ -n "$key" ] || continue
 count=$((count+1)); [ "$count" -le 32 ] || fail '400 Bad Request' 'Too many fields'
 if [ "$action" = save ]; then
  case " $KEYS sw_custom_version0 sw_custom_version1 " in *" $key "*) ;; *) fail '400 Bad Request' 'Unknown field';; esac
  [ ! -f "$WORK/new-$key" ] || fail '400 Bad Request' 'Duplicate field'
  decode "$value" && valid "$key" "$dec" || fail '400 Bad Request' "Invalid value: $key"
  case "$key" in OMCI_CUSTOM_ME|OMCI_VEIP_SLOT_ID) dec=$(awk -v n="$dec" 'BEGIN{printf "%.0f",n}');; esac
  [ "$key" != OUI ] || dec=$(norm_oui "$dec")
  old=$(get_value "$key") || fail '400 Bad Request' "Unsupported field: $key"
  printf '%s' "$dec" >"$WORK/new-$key"; printf '%s' "$old" >"$WORK/old-$key"
 elif [ "$action" = bank ]; then
  [ "$key" = bank ] && [ "$count" = 1 ] || fail '400 Bad Request' 'Invalid bank request'
  case "$value" in 0|1) target=$value;; *) fail '400 Bad Request' 'Invalid bank';; esac
 else
  fail '400 Bad Request' 'Unexpected reboot parameter'
 fi
done
if [ "$action" = restore_versions ]; then
 [ "$count" = 0 ] || fail '400 Bad Request' 'Unexpected restore parameter'
 [ "$(mod_get MOD_SWVER)" = 0 ] || fail '409 Conflict' 'Disable software version mod before restoring'
 [ "$(get_flash OMCI_OLT_MODE)" = 3 ] || fail '409 Conflict' 'Custom OMCI mode 3 is required to restore versions'
 for key in OMCI_SW_VER1 OMCI_SW_VER2 sw_custom_version0 sw_custom_version1; do
  case "$key" in OMCI_*) value=$(sed -n "s/^$key=//p" /var/config/odi-original-omci.conf); text_valid "$value" 14 || fail '409 Conflict' 'Original versions unavailable';; *) value='';; esac
  old=$(get_value "$key") || fail '400 Bad Request' "Unsupported field: $key"
  printf '%s' "$value" >"$WORK/new-$key"; printf '%s' "$old" >"$WORK/old-$key"
 done
 action=save; count=4
fi
write_value() {
 wk=$1; wv=$2
 case "$wk" in
 sw_custom_version0|sw_custom_version1) $NV setenv "$wk" "$wv" >/dev/null 2>&1;;
 *)
  # xmlconfig supports empty values for rollback; flash wrapper rejects them.
  if [ -n "$wv" ]; then $FLASH set "$wk" "$wv" >/dev/null 2>&1
  else
   wr=$($XML -s "$wk" "$wv" 2>/dev/null) || return 1
   case "$wr" in __hs__*) $XML -of -hs /var/config/lastgood_hs.xml >/dev/null 2>&1;; *) $XML -of /var/config/lastgood.xml >/dev/null 2>&1;; esac
  fi;;
 esac
 check=$(get_value "$wk") && [ "$check" = "$wv" ]
}
if [ "$action" = save ]; then
 [ "$count" -gt 0 ] || fail '400 Bad Request' 'No changes'
 if [ -f "$WORK/new-GPON_PLOAM_PASSWD" ]; then
  [ -s "$WORK/new-GPON_PLOAM_FORMAT" ] || fail '400 Bad Request' 'PLOAM requires an explicit display format'
 fi
 if [ -f "$WORK/new-ELAN_MAC_ADDR" ]; then
  [ -f "$WORK/new-MAC_KEY" ] || fail '400 Bad Request' 'Changing MAC requires its matching MAC_KEY'
 fi
 # Native GPON form saves both current and mirror LOID credentials.
 if [ -f "$WORK/new-LOID" ] || [ -f "$WORK/new-LOID_PASSWD" ]; then
  for key in LOID LOID_PASSWD; do
   if [ -f "$WORK/new-$key" ]; then value=$(cat "$WORK/new-$key"); else value=$(get_flash "$key") || fail '400 Bad Request' "Unsupported field: $key"; fi
   old=$(get_flash "${key}_OLD") || fail '400 Bad Request' "Unsupported field: ${key}_OLD"
   printf '%s' "$value" >"$WORK/new-${key}_OLD"; printf '%s' "$old" >"$WORK/old-${key}_OLD"
  done
 fi
 # Validate the effective VLAN tuple before any write.
 for key in VLAN_CFG_TYPE VLAN_MANU_MODE VLAN_MANU_TAG_VID VLAN_MANU_TAG_PRI; do
  if [ -f "$WORK/new-$key" ]; then
   cfg=$(get_flash VLAN_CFG_TYPE); mode=$(get_flash VLAN_MANU_MODE); vid=$(get_flash VLAN_MANU_TAG_VID); pri=$(get_flash VLAN_MANU_TAG_PRI)
   [ ! -f "$WORK/new-VLAN_CFG_TYPE" ] || cfg=$(cat "$WORK/new-VLAN_CFG_TYPE")
   [ ! -f "$WORK/new-VLAN_MANU_MODE" ] || mode=$(cat "$WORK/new-VLAN_MANU_MODE")
   [ ! -f "$WORK/new-VLAN_MANU_TAG_VID" ] || vid=$(cat "$WORK/new-VLAN_MANU_TAG_VID")
   [ ! -f "$WORK/new-VLAN_MANU_TAG_PRI" ] || pri=$(cat "$WORK/new-VLAN_MANU_TAG_PRI")
   if [ "$cfg" = 1 ] && [ "$mode" = 1 ]; then
    valid VLAN_MANU_TAG_VID "$vid" && valid VLAN_MANU_TAG_PRI "$pri" || fail '400 Bad Request' 'Tagging requires VLAN 1..4094 and PCP 0..7'
   fi
   break
  fi
 done
 for path in "$WORK"/new-*; do
  key=${path##*/new-}; value=$(cat "$path")
  if ! write_value "$key" "$value"; then
   rollback=ok
   for previous in "$WORK"/old-*; do
    oldkey=${previous##*/old-}; oldval=$(cat "$previous")
    write_value "$oldkey" "$oldval" || rollback=failed
   done
   fail '500 Internal Server Error' "Read-back failed for $key; rollback=$rollback. Reload and verify settings."
  fi
 done
 : >"$STATE/pending"
 for path in "$WORK"/new-*; do key=${path##*/new-}; case "$key" in *_OLD) ;; *) printf '%s\n' "$key" >>"$STATE/pending-keys";; esac; done
 headers; emit ok 1; emit message 'Saved and read back. Reboot separately to apply.'
elif [ "$action" = bank ]; then
 [ "$count" = 1 ] || fail '400 Bad Request' 'Bank is required'
 [ ! -f "/var/config/odi-invalid-bank$target" ] || fail '409 Conflict' 'Target bank has an unverified update. Reinstall it before selecting it.'
 active=$(get_nv sw_active); old=$(get_nv sw_commit)
 case "$active:$old" in 0:0|0:1|1:0|1:1) ;; *) fail '409 Conflict' 'Unknown current bank state';; esac
 grep -q "\"k$target\"" /proc/mtd && grep -q "\"r$target\"" /proc/mtd || fail '409 Conflict' 'Target partitions not found'
 $NV setenv sw_commit "$target" >/dev/null 2>&1
 if [ "$(get_nv sw_commit)" != "$target" ]; then
  $NV setenv sw_commit "$old" >/dev/null 2>&1
  fail '500 Internal Server Error' 'Bank selection failed. Reload to verify.'
 fi
 headers; emit ok 1; emit message 'Next boot bank selected. Current bank is unchanged.'
else
 headers; emit ok 1; emit message 'Reboot requested. The connection will close.'
 (sleep 3; /bin/reboot) </dev/null >/dev/null 2>&1 &
fi
