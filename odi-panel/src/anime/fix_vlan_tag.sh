#!/bin/sh
# Adapted from inyourgroove/rajkosto via Anime4000: one pass, managed 30s loop.
# Filters are mandatory in Panel; no implicit all-entity mode or sourced config.
[ -n "$MOD_VLANS$MOD_ENTITIES" ] || exit 1
for entity in $(omcicli mib get 84 | awk '/^EntityID:/ {print $2}'); do
 case "$entity" in 0x*) ;; *) continue;; esac
 echo "$entity" | grep -Eq '^0x[0-9a-fA-F]{1,4}$' || continue
 data=$(omcicli mib get 84 "$entity")
 match=0
 for wanted in $MOD_ENTITIES;do [ "$((wanted))" = "$((entity))" ] && match=1;done
 if [ "$match" = 0 ];then
  for vid in $(printf '%s\n' "$data" | grep -o ' VID [0-9]*' | awk '{print $2}'); do
   for wanted in $MOD_VLANS;do [ "$wanted" = "$vid" ] && match=1;done
  done
 fi
 [ "$match" = 1 ] || continue
 active=$(printf '%s\n' "$data" | awk '/^FwdOp:/ {print $2;exit}')
 echo "$active" | grep -Eq '^(0x[0-9a-fA-F]{1,2}|[0-9]{1,3})$' || continue
 [ "$((active))" = "$((MOD_FWDOP))" ] && continue
 omcicli mib set 84 "$entity" FwdOp "$MOD_FWDOP" || exit 1
done

exit 0
