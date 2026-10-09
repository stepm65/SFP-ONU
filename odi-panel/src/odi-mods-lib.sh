#!/bin/sh
# Target BusyBox (SFU 240408) has no mv, tr, head, tail, od, cut, wc, rmdir or touch.
# Trusted parser: the persistent configuration is data, never shell source.
MODCONF=/var/config/odi-panel-mods.conf
MODKEYS='MOD_SPEED MOD_SWVER MOD_VLAN MOD_VLANS MOD_ENTITIES MOD_FWDOP MOD_PAIRS'
mod_default() {
 case "$1" in MOD_SPEED|MOD_SWVER) printf 0;; MOD_VLAN) printf off;; MOD_FWDOP) printf 0x02;; esac
}
mod_get() {
 mg=$(sed -n "s/^$1=//p" "$MODCONF" 2>/dev/null)
 [ -n "$mg" ] || mg=$(mod_default "$1")
 printf '%s' "$mg"
}
mod_valid() {
 case "$1" in
 MOD_SPEED|MOD_SWVER) case "$2" in 0|1) return 0;; esac;;
 MOD_VLAN) case "$2" in off|tag|fwdop) return 0;; esac;;
 MOD_FWDOP) echo "$2" | grep -Eq '^0x[0-9A-Fa-f]{2}$';return $?;;
 MOD_ENTITIES) [ -z "$2" ] && return 0;[ "${#2}" -le 120 ] && echo "$2" | grep -Eq '^0x[0-9A-Fa-f]{1,4}( 0x[0-9A-Fa-f]{1,4})*$';return $?;;
 MOD_PAIRS) [ -z "$2" ] && return 0;[ "${#2}" -le 120 ] && echo "$2" | grep -Eq '^0x[0-9A-Fa-f]{1,4}:0x[0-9A-Fa-f]{2}(,0x[0-9A-Fa-f]{1,4}:0x[0-9A-Fa-f]{2})*$';return $?;;
 MOD_VLANS)
  [ -z "$2" ] && return 0
  [ "${#2}" -le 120 ] && echo "$2" | grep -Eq '^[1-9][0-9]{0,3}( [1-9][0-9]{0,3})*$' || return 1
  for mv in $2; do [ "$mv" -le 4094 ] || return 1;done;return 0;;
 esac
 return 1
}

mod_stamp() { IFS=' ' read -r ms rest </proc/uptime; printf '%s' "${ms%%.*}"; }
mod_log() {
 mkdir -p /tmp/odi-panel
 printf 'uptime=%s %s\n' "$(mod_stamp)" "$1" >>/tmp/odi-panel/mods.log
 awk '{line[NR%40]=$0}END{start=NR>40?NR-39:1;for(i=start;i<=NR;i++)print line[i%40]}' /tmp/odi-panel/mods.log >/tmp/odi-panel/mods.log.new
 cp /tmp/odi-panel/mods.log.new /tmp/odi-panel/mods.log && rm -f /tmp/odi-panel/mods.log.new
}
mod_backup_versions() {
 [ -f /var/config/odi-original-omci.conf ] && return 0
 mb_tmp=/var/config/odi-original-omci.conf.new
 for mb_key in OMCI_SW_VER1 OMCI_SW_VER2; do
  mb_raw=$(/etc/scripts/flash get "$mb_key")
  case "$mb_raw" in "$mb_key="*) printf '%s\n' "$mb_raw";; *) return 1;; esac
 done >"$mb_tmp" || return 1
 cp "$mb_tmp" /var/config/odi-original-omci.conf || return 1
 rm -f "$mb_tmp"
}
mod_snapshot() {
 # These two classes contain the VLAN rules. Never accept an arbitrary ME ID.
 case "$1" in 84|171) ;; *) return 1;; esac
 ms_class=$1;ms_file=$2
 omcicli mib get "$ms_class" >"$ms_file.list" 2>/dev/null || return 1
 grep -qi 'EntityID:' "$ms_file.list" || return 1
 : >"$ms_file.new"
 for ms_entity in $(awk 'tolower($1)=="entityid:" && $2~/^0x[0-9A-Fa-f]+$/{if(!seen[$2]++ && ++n<=12)print $2}' "$ms_file.list"); do
  [ "${#ms_entity}" -le 6 ] || continue
  printf '\nEntityID: %s\n' "$ms_entity" >>"$ms_file.new"
  omcicli mib get "$ms_class" "$ms_entity" 2>/dev/null | awk 'NR<=150 && tolower($1)!="entityid:"{print}' >>"$ms_file.new"
 done
 [ -s "$ms_file.new" ] || return 1
 cp "$ms_file.new" "$ms_file" || return 1
 rm -f "$ms_file.new"
 rm -f "$ms_file.list"
}
