#!/bin/sh
PATH=/bin:/sbin:/usr/bin:/usr/sbin
export PATH
LC_ALL=C
export LC_ALL
umask 077
. /etc/scripts/odi-fw-lib.sh
STARTER=/etc/scripts/fwu_starter.sh
STREAM=/etc/scripts/odi-fw-stream.sh
COMPARE=/etc/scripts/odi-fw-compare.sh
trap '' PIPE HUP
[ -d "$WORK" ] && [ -f "$WORK/image.tar" ] || exit 2
IFS= read -r bank <"$WORK/bank"
case "$bank" in 0|1);;*)exit 2;;esac
completed=0;started=0
cleanup(){
 if [ "$completed" != 1 ];then
  [ -s "$STATE/firmware-error" ] || printf WORKER_STOPPED >"$STATE/firmware-error"
  fw_phase failed;printf 'FAILED bank=%s\n' "$bank" >"$STATE/firmware-status"
 fi
 rm -f "$STATE/firmware-worker.pid"
 rm -r "$WORK"
}
trap cleanup 0
trap 'exit 1' 2 15
printf '%s\n' "$$" >"$STATE/firmware-worker.pid"
printf 'CHECKING bank=%s\n' "$bank" >"$STATE/firmware-status";fw_phase checking
active=$(getnv sw_active);commit=$(getnv sw_commit)
case "$active:$commit" in 0:0|1:1);;*)fw_error BOOT_STATE;;esac
[ "$bank" != "$active" ] || fw_error ACTIVE_BANK
: >"$WORK/devices";fw_geometry || fw_error PARTITIONS
image=$WORK/image.tar
tar -tf "$image" >"$WORK/list" 2>/dev/null || fw_error ARCHIVE
awk 'BEGIN{split("fwu.sh rootfs uImage fwu_ver hw_ver md5.txt",a);for(i in a)need[a[i]]=1} !($0 in need)||seen[$0]++{bad=1} END{if(NR!=6)bad=1;exit bad}' "$WORK/list" || fw_error ARCHIVE
tar -tvf "$image" >"$WORK/types" 2>/dev/null || fw_error ARCHIVE
awk 'substr($0,1,1)!="-"{bad=1}END{if(NR!=6)bad=1;exit bad}' "$WORK/types" || fw_error ARCHIVE
stream(){ rm -f "$WORK/stream-rc";sh "$STREAM" "$image" "$1" "$WORK/stream-rc"; }
stream_ok(){ [ "$(cat "$WORK/stream-rc" 2>/dev/null)" = 0 ]; }
member_size(){ stream "$1" | cksum >"$WORK/member-size";stream_ok || return 1;awk '{print $2}' "$WORK/member-size"; }
member_md5(){ stream "$1" | md5sum >"$WORK/member-md5";stream_ok || return 1;awk '{print $1}' "$WORK/member-md5"; }
# Extract only tiny metadata files. Kernel/rootfs stay in the TAR throughout.
for file in fwu.sh fwu_ver hw_ver md5.txt;do
 amount=$(member_size "$file") || fw_error ARCHIVE
 [ "$amount" -le 8192 ] || fw_error ARCHIVE
 stream "$file" >"$WORK/$file";stream_ok || fw_error ARCHIVE
done
[ "$(member_size uImage)" = 876153 ] && [ "$(member_md5 uImage)" = 65bf05eb8609c6629f368f1e1f19b588 ] || fw_error KERNEL
[ "$(md5sum "$WORK/fwu.sh" | awk '{print $1}')" = aff0174cbba7b029b61259777f3d7196 ] || fw_error UPDATER
[ "$(cat "$WORK/hw_ver")" = X100SFP ] || fw_error HARDWARE
root_size=$(member_size rootfs) || fw_error ROOTFS
[ "$root_size" -ge 96 ] && [ "$root_size" -le 2572288 ] || fw_error ROOTFS
printf hsqs >"$WORK/magic"
stream rootfs | sh "$COMPARE" "$WORK" "$WORK/magic" - || fw_error ROOTFS
# The magic comparison intentionally ends early; whole-member checks follow.
[ "$(ls -ln "$WORK/fwu_ver" | awk '{print $5}')" -le 80 ] && [ -s "$WORK/fwu_ver" ] || fw_error VERSION
version=$(cat "$WORK/fwu_ver");case "$version" in ''|*[!A-Za-z0-9._+-]*)fw_error VERSION;;esac
awk 'BEGIN{split("fwu.sh rootfs uImage fwu_ver hw_ver",a);for(i in a)need[a[i]]=1} NF!=2||!($2 in need)||seen[$2]++||length($1)!=32||$1~/[^0-9a-f]/{bad=1}END{if(NR!=5)bad=1;exit bad}' "$WORK/md5.txt" || fw_error CHECKSUM
for file in fwu.sh rootfs uImage fwu_ver hw_ver;do
 expected=$(awk -v n="$file" '$2==n{print $1}' "$WORK/md5.txt")
 [ "$(member_md5 "$file")" = "$expected" ] || fw_error CHECKSUM
done
[ "$(getnv sw_active)" = "$active" ] && [ "$(getnv sw_commit)" = "$active" ] || fw_error BOOT_STATE
# The reviewed factory fwu.sh unlinks its input TAR after writing. Retain the
# open inode for readback without storing another complete archive in RAM.
exec 9<"$image" || fw_error ARCHIVE_HANDLE
retained_image=/proc/$$/fd/9
tar -tf "$retained_image" >"$WORK/retained-list" 2>/dev/null || fw_error ARCHIVE_HANDLE
cmp "$WORK/list" "$WORK/retained-list" >/dev/null 2>&1 || fw_error ARCHIVE_HANDLE
printf 'Update not verified\n' >"$CONFIG/odi-invalid-bank$bank" || fw_error MARKER
started=1;printf 'WRITING bank=%s\n' "$bank" >"$STATE/firmware-status";fw_phase writing
sh "$STARTER" "$bank" "$image" >"$STATE/firmware-update.log" 2>&1 || fw_error WRITE
image=$retained_image
fw_phase readback
stream uImage | sh "$COMPARE" "$WORK" - "$kerneldev" || fw_error READBACK
stream_ok || fw_error READBACK
stream rootfs | sh "$COMPARE" "$WORK" - "$rootdev" || fw_error READBACK
stream_ok || fw_error READBACK
[ "$(getnv sw_active)" = "$active" ] && [ "$(getnv sw_commit)" = "$active" ] || fw_error BOOT_CHANGED
[ "$(getnv sw_version$bank)" = "$version" ] || fw_error VERSION
rm "$CONFIG/odi-invalid-bank$bank" || fw_error MARKER
completed=1;fw_phase verified;printf 'VERIFIED bank=%s\n' "$bank" >"$STATE/firmware-status"
exit 0
