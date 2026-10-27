#!/bin/sh
# Short authenticated upload request; verification/write continue in a worker.
PATH=/bin:/sbin:/usr/bin:/usr/sbin
export PATH
LC_ALL=C
export LC_ALL
umask 077
. /etc/scripts/odi-fw-lib.sh
WORKER=/etc/scripts/odi-firmware-worker.sh
owned=0
headers(){ printf 'Content-Type: text/plain; charset=utf-8\r\nCache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\n\r\n'; }
fail(){ if [ "$owned" = 1 ];then printf '%s' "$2" >"$STATE/firmware-error";fw_phase failed;printf 'FAILED bank=%s\n' "$bank" >"$STATE/firmware-status";fi;printf 'Status: %s\r\n' "$1";headers;printf 'error=%s\n' "$2";exit 1; }
[ -n "$REMOTE_USER" ] || fail '403 Forbidden' AUTH
[ "$REQUEST_METHOD" = POST ] || fail '405 Method Not Allowed' METHOD
[ "$CONTENT_TYPE" = application/octet-stream ] || fail '415 Unsupported Media Type' TYPE
case "$CONTENT_LENGTH" in ''|*[!0-9]*)fail '400 Bad Request' LENGTH;;esac
[ "${#CONTENT_LENGTH}" -le 7 ] && [ "$CONTENT_LENGTH" -ge 10240 ] && [ "$CONTENT_LENGTH" -le 8388608 ] || fail '413 Payload Too Large' LENGTH
[ -s "$STATE/token" ] || fail '403 Forbidden' CSRF
IFS= read -r supplied || fail '400 Bad Request' ENVELOPE
[ "$supplied" = "csrf=$(cat "$STATE/token")" ] || fail '403 Forbidden' CSRF
IFS= read -r bankline || fail '400 Bad Request' ENVELOPE
case "$bankline" in bank=0|bank=1)bank=${bankline#bank=};;*)fail '400 Bad Request' BANK;;esac
[ ! -d "$STATE/read.lock" ] || fail '409 Conflict' BUSY
[ ! -d /tmp/odi-debug/running ] || fail '409 Conflict' DEBUG_ACTIVE
[ ! -d /tmp/odi-debug/starting ] || fail '409 Conflict' DEBUG_ACTIVE
mkdir "$WORK" 2>/dev/null || fail '409 Conflict' BUSY
owned=1
handed=0
cleanup(){ [ "$handed" = 1 ] || rm -r "$WORK"; }
trap cleanup 0
trap 'exit 1' 1 2 15
active=$(getnv sw_active);commit=$(getnv sw_commit)
case "$active:$commit" in 0:0|1:1);;*)fail '409 Conflict' BOOT_STATE;;esac
[ "$bank" != "$active" ] || fail '409 Conflict' ACTIVE_BANK
: >"$WORK/devices";fw_geometry || fail '409 Conflict' PARTITIONS
: >"$STATE/firmware-error";: >"$STATE/firmware-update.log"
printf 'RECEIVING bank=%s\n' "$bank" >"$STATE/firmware-status";fw_phase receiving
cat >"$WORK/image.tar" || fail '500 Internal Server Error' RECEIVE
expected_length=$((CONTENT_LENGTH-${#supplied}-${#bankline}-2))
actual_length=$(cksum "$WORK/image.tar" | awk '{print $2}')
[ "$actual_length" = "$expected_length" ] || fail '400 Bad Request' TRUNCATED
[ $((actual_length%512)) = 0 ] || fail '400 Bad Request' ARCHIVE
printf '%s\n' "$bank" >"$WORK/bank"
printf 'CHECKING bank=%s\n' "$bank" >"$STATE/firmware-status";fw_phase checking
handed=1
sh "$WORKER" </dev/null >"$STATE/firmware-worker.log" 2>&1 &
printf '%s\n' "$!" >"$STATE/firmware-worker.pid"
headers
printf 'protocol=3\naccepted=1\nbank=%s\nok=1\n' "$bank"
