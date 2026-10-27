#!/bin/sh
# Fixed uplink operations. No port, command or rate is accepted from HTTP input.
PATH=/bin:/sbin:/usr/bin:/usr/sbin
export PATH
LC_ALL=C
export LC_ALL
umask 077
. /etc/scripts/odi-mods-lib.sh
STATE=/tmp/odi-panel
case "$1:$2" in apply:api|check:api|apply:boot|check:boot|maintain:boot) ;; *) exit 2;; esac
operation=$1; source=$2
mkdir -p "$STATE" || exit 1
own_write=0; UWORK=''; sdk_pid=''; timer_pid=''
if [ "$source" = api ] && [ ! -d "$STATE/write.lock" ]; then exit 75; fi
if [ "$source" = boot ]; then
 mkdir "$STATE/write.lock" 2>/dev/null || exit 75
 own_write=1
fi
cleanup() {
 [ -z "$sdk_pid" ] || kill -TERM "$sdk_pid" 2>/dev/null
 [ -z "$timer_pid" ] || kill "$timer_pid" 2>/dev/null
 [ "$own_write" = 0 ] || rm -r "$STATE/write.lock"
 [ -z "$UWORK" ] || rm -r "$UWORK"
}
trap cleanup 0
trap 'exit 1' 1 2 15
[ ! -d "$STATE/read.lock" ] || exit 75
mkdir "$STATE/uplink.lock" 2>/dev/null || exit 75
UWORK=$STATE/uplink.lock
started=$(mod_stamp)
speed_cfg=$(mod_get MOD_SPEED); flow_cfg=$(mod_get MOD_FLOWCONTROL)
mod_valid MOD_SPEED "$speed_cfg" && mod_valid MOD_FLOWCONTROL "$flow_cfg" || exit 2
selected=$(/etc/scripts/flash get LAN_SPEED_MODE 2>/dev/null); selected=${selected#LAN_SPEED_MODE=}
actual=$(sed -n 's/.*lan_sds_mode *= *\([0-7]\).*/\1/p' /proc/lan_sds/lan_sds_cfg 2>/dev/null)
speed=off; flow=unchanged; error=none; rates_match=0; flow_rc=unknown
run_diag() {
 output=$1; shift
 [ $(($(mod_stamp) - started)) -lt 20 ] || { printf 'READ_ERROR deadline\n' >"$UWORK/$output"; return 1; }
 /bin/diag "$@" >"$UWORK/$output" 2>&1 & sdk_pid=$!
 (sleep 3; kill -TERM "$sdk_pid" 2>/dev/null; sleep 1; kill -KILL "$sdk_pid" 2>/dev/null) & timer_pid=$!
 wait "$sdk_pid"; result=$?
 kill "$timer_pid" 2>/dev/null; wait "$timer_pid" 2>/dev/null
 sdk_pid=''; timer_pid=''
 return "$result"
}
rates_ok() {
 # Ignore echoed SDK commands/queue lines; require BOTH real RTL9601D ports.
 awk '{gsub(/:/," ");if($1=="port" && $3=="rate"){
  if($2=="0")p0++;if($2=="2")p2++;
  if(($2!="0" && $2!="2") || $4!="4194296" || NF!=4)bad=1;
 }}END{exit !(p0==1 && p2==1 && !bad)}' "$1"
}
read_rates() {
 run_diag ingress bandwidth get ingress port all; in_rc=$?
 run_diag egress bandwidth get egress port all; out_rc=$?
 [ "$in_rc:$out_rc" = 0:0 ] && rates_ok "$UWORK/ingress" && rates_ok "$UWORK/egress"
}
if read_rates; then rates_match=1; fi
if [ "$speed_cfg" = 1 ]; then
 case "$actual" in
 4|5|6)
  if [ "$rates_match" = 1 ]; then speed=verified
  elif [ "$operation" != check ]; then
   run_diag set-egress bandwidth set egress port all rate 4194296; set_out=$?
   run_diag set-ingress bandwidth set ingress port all rate 4194296; set_in=$?
   if read_rates && [ "$set_out:$set_in" = 0:0 ]; then rates_match=1; speed=verified
   else speed=failed; error=bandwidth_readback; fi
  else speed=not-applied; fi;;
 *) speed=waiting-2.5g;;
 esac
fi
if [ "$flow_cfg" = 1 ]; then
 if [ "$operation" = apply ]; then
  case "$actual" in 4|5|6)
  if run_diag set-flow port set auto-nego port all ability asy-flow-control; then flow=command-ok; flow_rc=0
  else flow=failed; flow_rc=1; error=flow_command; fi;;
  *) flow=waiting-2.5g;; esac
 else flow=not-checked; fi
fi
# Ability readback is raw evidence, not proof that PAUSE was negotiated.
run_diag ability port get auto-nego port all ability || :
run_diag ports port get status port all || :
if [ "$in_rc:$out_rc" != 0:0 ] && [ "$error" = none ]; then error=bandwidth_read; fi
for item in ingress egress ability ports; do
 [ ! -f "$UWORK/$item" ] || cp "$UWORK/$item" "$STATE/uplink-$item"
done
{
 printf 'source=%s\noperation=%s\nconfigured_speed=%s\nconfigured_flow=%s\nselected_mode=%s\nactual_mode=%s\n' "$source" "$operation" "$speed_cfg" "$flow_cfg" "$selected" "$actual"
 printf 'speed=%s\nrates_match=%s\nflow=%s\nflow_rc=%s\nerror=%s\nchecked_uptime=%s\n' "$speed" "$rates_match" "$flow" "$flow_rc" "$error" "$(mod_stamp)"
} >"$UWORK/status"
cp "$UWORK/status" "$STATE/uplink-status" || exit 1
mod_log "UPLINK source=$source speed=$speed flow=$flow error=$error"
[ "$error" = none ] || exit 1
if [ "$operation" != check ] && { [ "$speed" = waiting-2.5g ] || [ "$flow" = waiting-2.5g ]; }; then exit 3; fi
exit 0
