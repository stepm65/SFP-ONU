# ODI Panel terminal. Sourced by api.cgi after the admin session and CSRF checks.
# This is the only place where the panel runs operator-supplied shell commands.
# Safeguards: off by default; enabled for TERM_TTL seconds and then refused until
# re-enabled; local (RFC 1918 / loopback / link-local) clients only; one command
# at a time; TERM_TIMEOUT seconds per command; output capped by ulimit -f.
# BusyBox on the stick has no timeout/setsid/head, so limits are done in ash.
TERMROOT=$STATE/terminal
TERM_TTL=900
TERM_TIMEOUT=20
TERM_MAX_BYTES=65536

term_client() { printf '%s' "${REMOTE_ADDR#::ffff:}"; }
term_lan() {
 ta=$(term_client)
 case "$ta" in
  10.*|192.168.*|127.*|169.254.*) ;;
  172.*) to=${ta#172.}; to=${to%%.*}; case "$to" in ''|*[!0-9]*) return 1;; esac; [ "$to" -ge 16 ] && [ "$to" -le 31 ] || return 1;;
  *) return 1;;
 esac
 case "$ta" in *[!0-9.]*) return 1;; esac
}
term_remaining() {
 tu=$(cat "$TERMROOT/until" 2>/dev/null)
 case "$tu" in ''|*[!0-9]*) printf 0; return;; esac
 tn=$(log_tick)
 if [ "$tu" -gt "$tn" ]; then printf '%s' $((tu-tn)); else printf 0; fi
}
# Print a process and all of its descendants (from /proc), the root first.
term_tree() {
 cat /proc/[0-9]*/stat 2>/dev/null | awk -v root="$1" '
  { p=$1; s=$0; i=0; while((j=index(s,")"))>0){i+=j; s=substr(s,j+1)}
    split(substr($0,i+2),f," "); kids[f[2]]=kids[f[2]] " " p }
  END { n=1; q[1]=root; for(k=1;k<=n;k++){ print q[k]; m=split(kids[q[k]],c," "); for(x=1;x<=m;x++) q[++n]=c[x] } }'
}
term_kill() {
 case "$1" in ''|*[!0-9]*) return 0;; esac
 tk=$(term_tree "$1")
 for tp in $tk; do kill -TERM "$tp" 2>/dev/null; done
 sleep 1
 for tp in $tk; do kill -KILL "$tp" 2>/dev/null; done
}
term_tick() { sleep 0.2 2>/dev/null || sleep 1; }
term_lock() {
 mkdir -p "$TERMROOT" || fail '500 Internal Server Error' 'Cannot initialize terminal directory'
 if ! mkdir "$TERMROOT/run.lock" 2>/dev/null; then
  owner=$(cat "$TERMROOT/run.lock/owner" 2>/dev/null)
  case "$owner" in ''|*[!0-9]*) fail '409 Conflict' 'Another command is running';; esac
  kill -0 "$owner" 2>/dev/null && fail '409 Conflict' 'Another command is running'
  # The previous request died without cleanup: stop what it left running.
  term_kill "$(cat "$TERMROOT/pid" 2>/dev/null)"
  rm -r "$TERMROOT/run.lock"
  mkdir "$TERMROOT/run.lock" 2>/dev/null || fail '409 Conflict' 'Another command is running'
 fi
 printf '%s\n' $$ >"$TERMROOT/run.lock/owner"
}
term_decode() {
 tdec=''; trest=$1
 case "$trest" in ''|*[!0-9a-fA-F]*) return 1;; esac
 [ "${#trest}" -le 2048 ] || return 1
 while [ -n "$trest" ]; do
  [ "${#trest}" -ge 2 ] || return 1
  tpair=${trest%"${trest#??}"}; trest=${trest#??}
  tn=$((0x$tpair)); [ "$tn" -ge 32 ] && [ "$tn" -le 126 ] || return 1
  tdec=$tdec$(printf "\\$(printf '%03o' "$tn")")
 done
}
term_history() {
 # RAM only (/tmp), never sent to syslog: commands may contain credentials.
 printf 'uptime=%s from=%s rc=%s %s\n' "$(log_tick)" "$(term_client)" "$1" "$2" >>"$TERMROOT/history"
 awk '{l[NR]=$0} END{s=NR>200?NR-199:1; for(i=s;i<=NR;i++)print l[i]}' "$TERMROOT/history" >"$TERMROOT/history.tmp" && cat "$TERMROOT/history.tmp" >"$TERMROOT/history"
 rm -f "$TERMROOT/history.tmp"
}
term_status() {
 emit terminal_remaining "$(term_remaining)"
 emit terminal_ttl "$TERM_TTL"
 emit terminal_timeout "$TERM_TIMEOUT"
 emit terminal_lan "$(term_lan && printf 1 || printf 0)"
 emit terminal_cwd "$(cat "$TERMROOT/cwd" 2>/dev/null || printf /)"
}
terminal_request() {
 term_lan || fail '403 Forbidden' 'The terminal accepts only local network addresses'
 mkdir -p "$TERMROOT" || fail '500 Internal Server Error' 'Cannot initialize terminal directory'
 case "$1" in
 terminal_enable|terminal_disable|terminal_kill)
  while IFS= read -r extra; do [ -z "$extra" ] || fail '400 Bad Request' 'Terminal action accepts no parameters'; done
  case "$1" in
  terminal_enable)
   printf '%s\n' $(( $(log_tick) + TERM_TTL )) >"$TERMROOT/until"
   log_event "terminal=enabled seconds=$TERM_TTL from=$(term_client)" || :;;
  terminal_disable)
   rm -f "$TERMROOT/until"
   : >"$TERMROOT/abort"; term_kill "$(cat "$TERMROOT/pid" 2>/dev/null)"
   log_event "terminal=disabled from=$(term_client)" || :;;
  terminal_kill)
   : >"$TERMROOT/abort"; term_kill "$(cat "$TERMROOT/pid" 2>/dev/null)";;
  esac
  headers; term_status; emit ok 1; exit 0;;
 terminal_run)
  tcmd=''; seen=0
  while IFS='=' read -r key value; do
   [ -n "$key" ] || continue
   [ "$key" = command ] && [ "$seen" = 0 ] || fail '400 Bad Request' 'Unknown terminal field'
   term_decode "$value" || fail '400 Bad Request' 'The command must be printable ASCII, up to 1024 characters'
   tcmd=$tdec; seen=1
  done
  [ -n "$tcmd" ] || fail '400 Bad Request' 'Empty command'
  [ "$(term_remaining)" -gt 0 ] || fail '403 Forbidden' 'The terminal is off. Enable it first.'
  term_lock
  trap 'term_kill "$(cat "$TERMROOT/pid" 2>/dev/null)"; rm -f "$TERMROOT/pid"; rm -r "$TERMROOT/run.lock"' 0
  rm -f "$TERMROOT/abort" "$TERMROOT/next-cwd"
  tcwd=$(cat "$TERMROOT/cwd" 2>/dev/null); [ -n "$tcwd" ] || tcwd=/
  tout=$TERMROOT/out
  : >"$tout"
  (
   ulimit -f $((TERM_MAX_BYTES/512))
   cd "$tcwd" 2>/dev/null || cd /
   exec /bin/sh -c 'eval "$1"; rc=$?; pwd >"$2" 2>/dev/null; exit $rc' odi-terminal "$tcmd" "$TERMROOT/next-cwd"
  ) </dev/null >"$tout" 2>&1 &
  tpid=$!
  printf '%s\n' "$tpid" >"$TERMROOT/pid"
  tstate=done; tstart=$(log_tick)
  while kill -0 "$tpid" 2>/dev/null; do
   if [ -f "$TERMROOT/abort" ]; then tstate=aborted; break; fi
   if [ $(( $(log_tick) - tstart )) -ge "$TERM_TIMEOUT" ]; then tstate=timeout; break; fi
   term_tick
  done
  [ "$tstate" = done ] || term_kill "$tpid"
  wait "$tpid"; trc=$?
  # terminal_kill may stop the process before this loop sees the abort flag.
  if [ "$tstate" = done ] && [ -f "$TERMROOT/abort" ]; then tstate=aborted; fi
  rm -f "$TERMROOT/pid"
  if [ -s "$TERMROOT/next-cwd" ]; then cat "$TERMROOT/next-cwd" >"$TERMROOT/cwd"; fi
  tsize=$(ls -l "$tout" 2>/dev/null | awk '{print $5}')
  ttrunc=0; case "$tsize" in ''|*[!0-9]*) ;; *) [ "$tsize" -lt "$TERM_MAX_BYTES" ] || ttrunc=1;; esac
  term_history "$trc" "$tcmd"
  headers
  emit terminal_rc "$trc"
  emit terminal_state "$tstate"
  emit terminal_truncated "$ttrunc"
  emit terminal_output "$(cat "$tout")"
  : >"$tout"
  term_status; emit ok 1; exit 0;;
 esac
 fail '400 Bad Request' 'Unknown terminal action'
}
