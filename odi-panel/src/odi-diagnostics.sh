#!/bin/sh
# Fixed read operations only. No command or ME ID comes from HTTP input.
diag_now() { IFS=' ' read -r tick rest </proc/uptime; printf '%s' "${tick%%.*}"; }
diag_redact() {
 awk '{
  line=tolower($0)
  if(line ~ /(password|passwd|pwd|ploam|loid[ :=]|mac_key|csrf|challenge|serialnumber|serial number|(^|[ :])sn[ :=])/) print "[redacted]"
  else print
 }'
}
diag_run() {
 if [ $(($(diag_now) - diag_started)) -ge 50 ]; then printf 'READ_ERROR collection deadline\n' >"$DWORK/out"; return; fi
 "$@" >"$DWORK/out" 2>&1 & read_pid=$!
 (sleep 2; kill -TERM "$read_pid" 2>/dev/null; sleep 1; kill -KILL "$read_pid" 2>/dev/null) & timer_pid=$!
 wait "$read_pid"; rc=$?
 kill "$timer_pid" 2>/dev/null; wait "$timer_pid" 2>/dev/null
 [ "$rc" = 0 ] || printf '\nREAD_ERROR rc=%s\n' "$rc" >>"$DWORK/out"
}
diag_read() {
 label=$1; shift
 diag_run "$@"
 output=$(awk 'NR<=160 {if(length($0)>600)$0=substr($0,1,600);print}NR==161{print "[output truncated]"}' "$DWORK/out" | diag_redact)
 emit "$label" "$output"
}
diag_mib() {
 me=$1
 diag_run /bin/omcicli mib get "$me"
 cp "$DWORK/out" "$DWORK/mib"
 # This firmware lists entities first; attributes require a second read per entity.
 awk 'tolower($1)=="entityid:" && $2~/^0x[0-9A-Fa-f]+$/{if(!seen[$2]++)print $2}' "$DWORK/mib" >"$DWORK/entities"
 entity_count=0
 : >"$DWORK/details"
 while IFS= read -r entity; do
  entity_count=$((entity_count+1))
  if [ "$entity_count" -gt 12 ]; then printf '[entity list truncated after 12]\n' >>"$DWORK/details"; break; fi
  [ "${#entity}" -le 6 ] || continue
  diag_run /bin/omcicli mib get "$me" "$entity"
  printf '\nEntityID: %s\n' "$entity" >>"$DWORK/details"
  # Some versions repeat the ID in the detail read. Keep one record delimiter.
  awk 'tolower($1)!="entityid:"' "$DWORK/out" >>"$DWORK/details"
 done <"$DWORK/entities"
 [ ! -s "$DWORK/details" ] || cp "$DWORK/details" "$DWORK/mib"
 emit "me_$me" "$(awk 'NR<=350{if(length($0)>600)$0=substr($0,1,600);print}NR==351{print "[output truncated]"}' "$DWORK/mib" | diag_redact)"
}
diag_collect() {
 [ ! -d "$STATE/write.lock" ] || return 1
 mkdir "$STATE/read.lock" 2>/dev/null || return 1
 DWORK=$STATE/read.lock
 diag_started=$(diag_now)
 trap 'rm -r "$DWORK"' 0
 trap 'exit 1' 1 2 15
 headers
 emit panel_version "$PANEL_VERSION"
 emit sampled_uptime "$(diag_now)"
 emit uptime "$(cat /proc/uptime)"
 emit memory "$(awk '/MemTotal:|MemAvailable:|MemFree:/{print}' /proc/meminfo)"
 emit firmware_status "$(cat "$STATE/firmware-status" 2>/dev/null)"
 emit firmware_phase "$(cat "$STATE/firmware-phase" 2>/dev/null)"
 emit firmware_error "$(cat "$STATE/firmware-error" 2>/dev/null)"
 emit link_actual "$(cat /proc/lan_sds/lan_sds_cfg 2>/dev/null)"
 for key in PON_MODE VLAN_CFG_TYPE VLAN_MANU_MODE; do emit "$key" "$(get_flash "$key")"; done
 diag_read pon_state /bin/diag gpon get onu-state
 for metric in rx-power tx-power temperature voltage bias-current; do
  diag_read "optic_$metric" /bin/diag pon get transceiver "$metric"
 done
 diag_read runtime_sn /bin/omcicli get sn
 diag_read loid_auth /bin/omcicli get loidauth
 diag_read auth_uptime /bin/omcicli get authuptime
 emit mods_status "$(cat "$STATE/mods-status" 2>/dev/null)"
 emit mods_log "$(cat "$STATE/mods.log" 2>/dev/null | diag_redact)"
 if [ "$QUERY_STRING" = diagnostics ]; then
  for class in 84 171 78 79 268 262 277 7 257; do diag_mib "$class"; done
  diag_read connections /bin/omcicli dump conn
  for class in 84 171; do emit "baseline_$class" "$(cat "$STATE/baseline-$class" 2>/dev/null | diag_redact)"; done
  emit baseline_uptime "$(cat "$STATE/baseline-uptime" 2>/dev/null)"
  emit firmware_log "$(cat "$STATE/firmware-update.log" 2>/dev/null | diag_redact | awk 'NR<=100{print}')"
 fi
 emit collection_seconds "$(($(diag_now) - diag_started))"
 emit ok 1
 rm -r "$DWORK"; trap - 0 1 2 15
}
