#!/bin/sh
umask 077
PATH=/bin:/sbin:/usr/bin:/usr/sbin
export PATH
. /etc/scripts/odi-mods-lib.sh
MOD_SPEED=$(mod_get MOD_SPEED);MOD_VLAN=$(mod_get MOD_VLAN)
MOD_VLANS=$(mod_get MOD_VLANS);MOD_ENTITIES=$(mod_get MOD_ENTITIES)
MOD_FWDOP=$(mod_get MOD_FWDOP);MOD_PAIRS=$(mod_get MOD_PAIRS)
mod_valid MOD_SPEED "$MOD_SPEED" || exit 1
export MOD_VLANS MOD_ENTITIES MOD_FWDOP MOD_PAIRS
mkdir /tmp/odi-mods-running 2>/dev/null || exit 0
trap 'rm -r /tmp/odi-mods-running' 0
trap 'exit 0' 1 2 15
mkdir -p /tmp/odi-panel
mod_log "Runner started"
sleep 5
if [ "$MOD_SPEED" = 1 ]; then
 /etc/scripts/fix_speed.sh >/tmp/odi-panel/speed-result 2>&1
 speed_rc=$?; mod_log "SPEED rc=$speed_rc"
else speed_rc=off; fi
printf 'pid=%s\nspeed=%s\nvlan=%s\nheartbeat=%s\n' "$$" "$speed_rc" "$MOD_VLAN" "$(mod_stamp)" >/tmp/odi-panel/mods-status
case "$MOD_VLAN" in
 tag) mod_valid MOD_VLANS "$MOD_VLANS" && mod_valid MOD_ENTITIES "$MOD_ENTITIES" && mod_valid MOD_FWDOP "$MOD_FWDOP" && [ -n "$MOD_VLANS$MOD_ENTITIES" ] || exit 1;script=/etc/scripts/fix_vlan_tag.sh;;
 fwdop) mod_valid MOD_PAIRS "$MOD_PAIRS" && [ -n "$MOD_PAIRS" ] || exit 1;script=/etc/scripts/fix_vlan_fwdop.sh;;
 *) exit 0;;
esac
while :;do
 # Capture an actual MIB snapshot before the first local VLAN mutation.
 if [ ! -f /tmp/odi-panel/baseline-84 ]; then
  if mod_snapshot 84 /tmp/odi-panel/baseline-84; then
   mod_snapshot 171 /tmp/odi-panel/baseline-171
   mod_stamp >/tmp/odi-panel/baseline-uptime
  fi
 fi
 "$script" >/tmp/odi-panel/vlan-result 2>&1
 rc=$?; mod_log "VLAN algorithm=$MOD_VLAN rc=$rc"
 printf 'pid=%s\nspeed=%s\nvlan=%s\nlast_rc=%s\nheartbeat=%s\n' "$$" "$speed_rc" "$MOD_VLAN" "$rc" "$(mod_stamp)" >/tmp/odi-panel/mods-status
 sleep 30
done
