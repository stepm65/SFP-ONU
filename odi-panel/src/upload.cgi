#!/bin/sh
# Explicit inactive-bank update. Only the exact reviewed SFU 240408 kernel and safe installer are accepted.
PATH=/bin:/sbin:/usr/bin:/usr/sbin
export PATH
LC_ALL=C
export LC_ALL
umask 077
STATE=/tmp/odi-panel
NV=/bin/nv
MTD=/proc/mtd
DEV=/dev
CONFIG=/var/config
STARTER=/etc/scripts/fwu_starter.sh
streaming=0
# A closed browser must not interrupt an already started flash operation.
trap '' PIPE
headers(){ printf 'Content-Type: text/plain; charset=utf-8\r\nCache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\n\r\n'; }
send(){ printf '%s=%s\n' "$1" "$2" 2>/dev/null || :; }
phase(){ printf '%s' "$1" >"$STATE/firmware-phase"; [ "$streaming" = 0 ] || send phase "$1"; }
sendlog(){
 [ "$streaming" = 1 ] || return 0
 # Target BusyBox has no head/od/tr: hex-encode the first 100 lines (max 20000 bytes) with awk.
 log=$(awk 'BEGIN{for(i=1;i<256;i++)ord[sprintf("%c",i)]=i} NR<=100{s=$0 "\n";for(i=1;i<=length(s)&&n<20000;i++){printf "%02x",ord[substr(s,i,1)];n++}}' "$STATE/firmware-update.log" 2>/dev/null)
 send log "$log"
}
fail(){
 if [ "$streaming" = 1 ]; then
  printf '%s' "$2" >"$STATE/firmware-error"
  sendlog; phase failed; send error "$2"
 else
  printf 'Status: %s\r\n' "$1"; headers; send error "$2"
 fi
 exit 1
}
size(){ ls -ln "$1" | awk '{print $5}'; }
md5(){ md5sum "$1" | awk '{print $1}'; }
getnv(){ value=$($NV getenv "$1") || return 1; case "$value" in "$1="*) printf '%s' "${value#*=}";; *) return 1;; esac; }
# BusyBox in the supplied image reports an equal prefix as this exact EOF diagnostic.
# Any mismatch, I/O error or unknown diagnostic fails closed.
prefix_equal(){
 cmp "$1" "$2" >"$WORK/cmp.out" 2>"$WORK/cmp.err"; rc=$?
 [ "$rc" = 0 ] && return 0
 [ "$rc" = 1 ] && [ ! -s "$WORK/cmp.out" ] && [ "$(cat "$WORK/cmp.err")" = "cmp: EOF on $1" ]
}
[ -n "$REMOTE_USER" ] || fail '403 Forbidden' AUTH
[ "$REQUEST_METHOD" = POST ] || fail '405 Method Not Allowed' METHOD
[ "$CONTENT_TYPE" = application/octet-stream ] || fail '415 Unsupported Media Type' TYPE
case "$CONTENT_LENGTH" in ''|*[!0-9]*) fail '400 Bad Request' LENGTH;; esac
[ "${#CONTENT_LENGTH}" -le 7 ] && [ "$CONTENT_LENGTH" -ge 10240 ] && [ "$CONTENT_LENGTH" -le 8388608 ] || fail '413 Payload Too Large' LENGTH
[ -s "$STATE/token" ] || fail '403 Forbidden' CSRF
IFS= read -r supplied || fail '400 Bad Request' ENVELOPE
[ "$supplied" = "csrf=$(cat "$STATE/token")" ] || fail '403 Forbidden' CSRF
IFS= read -r bankline || fail '400 Bad Request' ENVELOPE
case "$bankline" in bank=0|bank=1) bank=${bankline#bank=};; *) fail '400 Bad Request' BANK;; esac
[ ! -d "$STATE/read.lock" ] || fail '409 Conflict' BUSY
mkdir "$STATE/write.lock" 2>/dev/null || fail '409 Conflict' BUSY
WORK=$STATE/write.lock
started=0
completed=0
cleanup(){ if [ "$started" = 1 ]; then printf 'FAILED bank=%s\n' "$bank" >"$STATE/firmware-status"; fi; [ "$completed" = 1 ] || printf failed >"$STATE/firmware-phase"; rm -r "$WORK"; }
trap cleanup 0
trap 'exit 1' 1 2 15
active=$(getnv sw_active); commit=$(getnv sw_commit)
case "$active:$commit" in 0:0|1:1) ;; *) fail '409 Conflict' BOOT_STATE;; esac
[ "$bank" != "$active" ] || fail '409 Conflict' ACTIVE_BANK
# Require the reviewed dual-bank geometry, unique names, distinct character devices.
for pair in k0:0014c000 r0:00274000 k1:0014c000 r1:00274000; do
 name=${pair%:*}; expected=${pair#*:}
 rows=$(awk -v n="\"$name\"" '$4==n{print $1 " " $2 " " $3}' "$MTD")
 set -- $rows
 [ "$#" = 3 ] && [ "$2" = "$expected" ] && [ "$3" = 00001000 ] || fail '409 Conflict' PARTITIONS
 dev=${1%:}; case "$dev" in mtd[0-9]|mtd[0-9][0-9]) ;; *) fail '409 Conflict' PARTITIONS;; esac
 [ -c "$DEV/$dev" ] || fail '409 Conflict' PARTITIONS
 printf '%s\n' "$dev" >>"$WORK/devices"
 [ "$name" = "k$bank" ] && kerneldev=$DEV/$dev
 [ "$name" = "r$bank" ] && rootdev=$DEV/$dev
done
awk 'seen[$0]++{bad=1}END{exit bad}' "$WORK/devices" || fail '409 Conflict' PARTITIONS
printf 'RECEIVING bank=%s\n' "$bank" >"$STATE/firmware-status"
: >"$STATE/firmware-update.log"
: >"$STATE/firmware-error"
# Stream actual milestones over the same request; no second CGI is needed.
headers
streaming=1
send protocol 2
phase receiving
# stdin is the TAR after the two ASCII envelope lines. No uploaded pathname is used.
cat >"$WORK/image.tar" || fail '500 Internal Server Error' RECEIVE
phase checking
expected_length=$((CONTENT_LENGTH - ${#supplied} - ${#bankline} - 2))
[ "$(size "$WORK/image.tar")" = "$expected_length" ] || fail '400 Bad Request' TRUNCATED
[ $((expected_length % 512)) = 0 ] || fail '400 Bad Request' ARCHIVE
tar -tf "$WORK/image.tar" >"$WORK/list" 2>/dev/null || fail '400 Bad Request' ARCHIVE
awk 'BEGIN{split("fwu.sh rootfs uImage fwu_ver hw_ver md5.txt",a);for(i in a)need[a[i]]=1} !($0 in need)||seen[$0]++{bad=1} END{if(NR!=6)bad=1;exit bad}' "$WORK/list" || fail '400 Bad Request' ARCHIVE
tar -tvf "$WORK/image.tar" >"$WORK/types" 2>/dev/null || fail '400 Bad Request' ARCHIVE
awk 'substr($0,1,1)!="-"{bad=1} END{if(NR!=6)bad=1;exit bad}' "$WORK/types" || fail '400 Bad Request' ARCHIVE
for file in fwu.sh rootfs uImage fwu_ver hw_ver md5.txt; do
 tar -xf "$WORK/image.tar" "$file" -O >"$WORK/$file" 2>/dev/null || fail '400 Bad Request' ARCHIVE
done
case "$(size "$WORK/uImage"):$(md5 "$WORK/uImage")" in
 876153:65bf05eb8609c6629f368f1e1f19b588) ;;
 *) fail '400 Bad Request' KERNEL;;
esac
[ "$(md5 "$WORK/fwu.sh")" = aff0174cbba7b029b61259777f3d7196 ] || fail '400 Bad Request' UPDATER
[ "$(cat "$WORK/hw_ver")" = X100SFP ] || fail '400 Bad Request' HARDWARE
root_size=$(size "$WORK/rootfs")
[ "$root_size" -ge 96 ] && [ "$root_size" -le 2572288 ] || fail '400 Bad Request' ROOTFS
printf hsqs >"$WORK/magic"
prefix_equal "$WORK/magic" "$WORK/rootfs" || fail '400 Bad Request' ROOTFS
[ "$(size "$WORK/fwu_ver")" -le 80 ] && [ -s "$WORK/fwu_ver" ] || fail '400 Bad Request' VERSION
version=$(cat "$WORK/fwu_ver")
case "$version" in ''|*[!A-Za-z0-9._+-]*) fail '400 Bad Request' VERSION;; esac
awk 'BEGIN{split("fwu.sh rootfs uImage fwu_ver hw_ver",a);for(i in a)need[a[i]]=1} NF!=2||!($2 in need)||seen[$2]++||length($1)!=32||$1~/[^0-9a-f]/{bad=1} END{if(NR!=5)bad=1;exit bad}' "$WORK/md5.txt" || fail '400 Bad Request' CHECKSUM
for file in fwu.sh rootfs uImage fwu_ver hw_ver; do
 digest=$(awk -v n="$file" '$2==n{print $1}' "$WORK/md5.txt")
 [ "$(md5 "$WORK/$file")" = "$digest" ] || fail '400 Bad Request' CHECKSUM
done
# Recheck boot state immediately before the destructive operation.
[ "$(getnv sw_active)" = "$active" ] && [ "$(getnv sw_commit)" = "$active" ] || fail '409 Conflict' BOOT_STATE
printf 'Update not verified\n' >"$CONFIG/odi-invalid-bank$bank" || fail '500 Internal Server Error' MARKER
started=1
printf 'WRITING bank=%s\n' "$bank" >"$STATE/firmware-status"
phase writing
sh "$STARTER" "$bank" "$WORK/image.tar" >"$STATE/firmware-update.log" 2>&1 || fail '500 Internal Server Error' WRITE
sendlog
phase readback
prefix_equal "$WORK/uImage" "$kerneldev" && prefix_equal "$WORK/rootfs" "$rootdev" || fail '500 Internal Server Error' READBACK
[ "$(getnv sw_commit)" = "$active" ] && [ "$(getnv sw_active)" = "$active" ] || fail '500 Internal Server Error' BOOT_CHANGED
[ "$(getnv sw_version$bank)" = "$(cat "$WORK/fwu_ver")" ] || fail '500 Internal Server Error' VERSION
rm "$CONFIG/odi-invalid-bank$bank" || fail '500 Internal Server Error' MARKER
started=0
printf 'VERIFIED bank=%s\n' "$bank" >"$STATE/firmware-status"
completed=1
phase verified
send bank "$bank"
send ok 1
