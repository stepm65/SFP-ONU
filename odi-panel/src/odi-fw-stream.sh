#!/bin/sh
# Fixed worker-owned archive/member paths; report extraction status before EOF.
tar -xf "$1" "$2" -O
result=$?
printf '%s' "$result" >"$3"
exit "$result"
