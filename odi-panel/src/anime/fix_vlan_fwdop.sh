#!/bin/sh
# Adapted from Anime4000/inyourgroove/rajkosto: dedicated settings, exact ID matching.
# Do not overload RTK_DEVINFO_SPECVER, an unrelated ONU identity parameter.
for pair in $(printf '%s' "$MOD_PAIRS" | sed 's/,/ /g'); do
 entity=${pair%:*}; op=${pair#*:}
 for active_entity in $(omcicli mib get 84 | awk '/^EntityID:/ {print $2}'); do
  echo "$active_entity" | grep -Eq '^0x[0-9a-fA-F]{1,4}$' || continue
  [ "$((active_entity))" = "$((entity))" ] || continue
  active=$(omcicli mib get 84 "$active_entity" | awk '/^FwdOp:/ {print $2;exit}')
  echo "$active" | grep -Eq '^(0x[0-9a-fA-F]{1,2}|[0-9]{1,3})$' || continue
  if [ "$((active))" != "$((op))" ]; then
   omcicli mib set 84 "$active_entity" FwdOp "$op" || exit 1
  fi
 done
done

exit 0
