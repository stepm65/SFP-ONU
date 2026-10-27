#!/bin/sh
# Exact target BusyBox cmp equal-prefix diagnostic. Unknown errors fail closed.
cmp "$2" "$3" >"$1/cmp.out" 2>"$1/cmp.err";rc=$?
[ "$rc" = 0 ] && exit 0
[ "$rc" = 1 ] && [ ! -s "$1/cmp.out" ] && [ "$(cat "$1/cmp.err")" = "cmp: EOF on $2" ]
