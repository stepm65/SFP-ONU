#!/bin/sh
STATE=/tmp/odi-panel
NV=/bin/nv
MTD=/proc/mtd
DEV=/dev
CONFIG=/var/config
WORK=$STATE/write.lock
getnv(){ value=$($NV getenv "$1") || return 1;case "$value" in "$1="*)printf '%s' "${value#*=}";;*)return 1;;esac; }
fw_phase(){ printf '%s' "$1" >"$STATE/firmware-phase"; }
fw_error(){ printf '%s' "$1" >"$STATE/firmware-error";fw_phase failed;printf 'FAILED bank=%s\n' "${bank:-unknown}" >"$STATE/firmware-status";exit 1; }
fw_geometry(){
 for pair in k0:0014c000 r0:00274000 k1:0014c000 r1:00274000;do
  name=${pair%:*};expected=${pair#*:}
  rows=$(awk -v n="\"$name\"" '$4==n{print $1 " " $2 " " $3}' "$MTD");set -- $rows
  [ "$#" = 3 ] && [ "$2" = "$expected" ] && [ "$3" = 00001000 ] || return 1
  dev=${1%:};case "$dev" in mtd[0-9]|mtd[0-9][0-9]);;*)return 1;;esac
  [ -c "$DEV/$dev" ] || return 1
  printf '%s\n' "$dev" >>"$WORK/devices"
  [ "$name" != "k$bank" ] || kerneldev=$DEV/$dev
  [ "$name" != "r$bank" ] || rootdev=$DEV/$dev
 done
 awk 'seen[$0]++{bad=1}END{exit bad}' "$WORK/devices"
}
