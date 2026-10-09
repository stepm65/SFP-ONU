#!/bin/sh
# Adapted from Anime4000/stich86 fix_sw_ver.sh for ODI Panel: quote and verify writes.
FLASH=/etc/scripts/flash
[ "$($FLASH get OMCI_OLT_MODE)" = OMCI_OLT_MODE=3 ] || exit 0
for bank in 0 1; do
 raw=$(/bin/nv getenv sw_custom_version$bank);ver=${raw#*=}
 case "$raw" in sw_custom_version$bank=*) ;; *) ver='';; esac
 if [ -z "$ver" ];then
  raw=$(/bin/nv getenv sw_version$bank)
  case "$raw" in sw_version$bank=*) ver=${raw#*=};; *) continue;; esac
 fi
 [ -n "$ver" ] && [ "${#ver}" -le 14 ] || continue
 case "$ver" in *[!a-zA-Z0-9._:/+@\ -]*) continue;; esac
 if [ "$bank" = 0 ];then key=OMCI_SW_VER1;else key=OMCI_SW_VER2;fi
 [ "$($FLASH get "$key")" = "$key=$ver" ] && continue
 $FLASH set "$key" "$ver" >/dev/null || exit 1
 [ "$($FLASH get "$key")" = "$key=$ver" ] || exit 1
done
