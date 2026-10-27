#!/bin/sh
umask 077
PATH=/bin:/sbin:/usr/bin:/usr/sbin
export PATH
. /etc/scripts/odi-mods-lib.sh
case "$1" in ''|once) ;; *) exit 2;; esac
mkdir /tmp/odi-mods-running 2>/dev/null || exit 0
owned=0
trap '[ "$owned" = 0 ] || rm -r /tmp/odi-panel/write.lock; rm -r /tmp/odi-mods-running' 0
trap 'exit 0' 1 2 15
mkdir -p /tmp/odi-panel
mod_log "Runner started"
sleep 5
first=1; attempts=0; speed_rc=off; previous_uplink=''
while :; do
 # Read AFTER SDK startup, and again on each tick. Settings are never shell code.
 MOD_SPEED=$(mod_get MOD_SPEED); MOD_FLOWCONTROL=$(mod_get MOD_FLOWCONTROL); MOD_SPEED_WATCH=$(mod_get MOD_SPEED_WATCH)
 MOD_VLAN=$(mod_get MOD_VLAN); MOD_VLANS=$(mod_get MOD_VLANS); MOD_ENTITIES=$(mod_get MOD_ENTITIES)
 MOD_FWDOP=$(mod_get MOD_FWDOP); MOD_PAIRS=$(mod_get MOD_PAIRS)
 current_uplink=$MOD_SPEED:$MOD_FLOWCONTROL
 if [ "$current_uplink" != "$previous_uplink" ]; then
  first=1; attempts=0; previous_uplink=$current_uplink
 fi
 for key in MOD_SPEED MOD_FLOWCONTROL MOD_SPEED_WATCH; do
  case "$key" in MOD_SPEED) val=$MOD_SPEED;; MOD_FLOWCONTROL) val=$MOD_FLOWCONTROL;; MOD_SPEED_WATCH) val=$MOD_SPEED_WATCH;; *) val=$MOD_VLAN;; esac
  mod_valid "$key" "$val" || exit 1
 done
 export MOD_VLANS MOD_ENTITIES MOD_FWDOP MOD_PAIRS
 if [ ! -d /tmp/odi-panel/write.lock ] && [ ! -d /tmp/odi-panel/read.lock ]; then
  if [ "$first" = 1 ] || [ "$MOD_SPEED_WATCH" = 1 ]; then
   if [ "$MOD_SPEED$MOD_FLOWCONTROL" != 00 ]; then
    job=maintain; [ "$first" = 0 ] || job=apply
    /etc/scripts/odi-uplink.sh "$job" boot >/tmp/odi-panel/speed-result 2>&1
    speed_rc=$?; mod_log "SPEED rc=$speed_rc"
    # Three startup attempts; continuous rechecking requires an explicit switch.
    if [ "$first" = 1 ] && [ "$speed_rc" != 75 ]; then attempts=$((attempts+1)); fi
    if [ "$speed_rc" = 0 ] || [ "$attempts" -ge 3 ]; then first=0; fi
   else speed_rc=off; first=0; fi
  fi
  mod_valid MOD_VLAN "$MOD_VLAN" || exit 1
  case "$MOD_VLAN" in
  tag) mod_valid MOD_VLANS "$MOD_VLANS" && mod_valid MOD_ENTITIES "$MOD_ENTITIES" && mod_valid MOD_FWDOP "$MOD_FWDOP" && [ -n "$MOD_VLANS$MOD_ENTITIES" ] || exit 1;script=/etc/scripts/fix_vlan_tag.sh;;
  fwdop) mod_valid MOD_PAIRS "$MOD_PAIRS" && [ -n "$MOD_PAIRS" ] || exit 1;script=/etc/scripts/fix_vlan_fwdop.sh;;
  *) script='';;
  esac
  if [ -n "$script" ] && mkdir /tmp/odi-panel/write.lock 2>/dev/null; then
   owned=1
   if [ ! -d /tmp/odi-panel/read.lock ]; then
    if [ ! -f /tmp/odi-panel/baseline-84 ] && mod_snapshot 84 /tmp/odi-panel/baseline-84; then
     mod_snapshot 171 /tmp/odi-panel/baseline-171; mod_stamp >/tmp/odi-panel/baseline-uptime
    fi
    "$script" >/tmp/odi-panel/vlan-result 2>&1
    rc=$?; mod_log "VLAN algorithm=$MOD_VLAN rc=$rc"
   fi
   rm -r /tmp/odi-panel/write.lock
   owned=0
  fi
 fi
 printf 'pid=%s\nspeed=%s\nvlan=%s\nwatch=%s\nheartbeat=%s\n' "$$" "$speed_rc" "$MOD_VLAN" "$MOD_SPEED_WATCH" "$(mod_stamp)" >/tmp/odi-panel/mods-status
 [ "$1" != once ] || exit 0
 sleep 30
done
