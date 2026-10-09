#!/bin/sh
umask 077
# Apply explicitly configured OMCI software identity after vendor checkomci.
# Hooked after insdrv.sh, before runsdk.sh / runomci.sh.
. /etc/scripts/odi-mods-lib.sh
mkdir -p /tmp/odi-panel
if [ "$(mod_get MOD_SWVER)" = 1 ];then
 mod_backup_versions || exit 1
 /etc/scripts/fix_sw_ver.sh
 rc=$?; mod_log "SWVER rc=$rc source=bank-fallback"; exit "$rc"
fi
FLASH=/etc/scripts/flash
mode=$($FLASH get OMCI_OLT_MODE 2>/dev/null)
[ "$mode" = OMCI_OLT_MODE=3 ] || exit 0
for bank in 0 1; do
 raw=$(/bin/nv getenv sw_custom_version$bank 2>/dev/null)
 case "$raw" in sw_custom_version$bank=*) ver=${raw#*=};; *) continue;; esac
 [ -n "$ver" ] && [ "${#ver}" -le 14 ] || continue
 case "$ver" in *[!a-zA-Z0-9._:/+@\ -]*) continue;; esac
 if [ "$bank" = 0 ]; then key=OMCI_SW_VER1; else key=OMCI_SW_VER2; fi
 current=$($FLASH get "$key" 2>/dev/null)
 if [ "$current" != "$key=$ver" ]; then
  mod_backup_versions || exit 1
  $FLASH set "$key" "$ver" >/dev/null 2>&1
  current=$($FLASH get "$key" 2>/dev/null)
  [ "$current" = "$key=$ver" ] || printf 'ODI Panel: %s read-back failed\n' "$key" >>/tmp/odi-panel-boot.log
 fi
done
mod_log "SWVER explicit-version pass completed"
exit 0
