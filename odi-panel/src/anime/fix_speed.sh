#!/bin/sh
# HiSGMII Speed: Fix upload speed when using HiSGMII mode
# By stich86

SPEED=$(/etc/scripts/flash get LAN_SPEED_MODE | awk -F'=' '{print $2}')

if [ "$SPEED" = "4" ] || [ "$SPEED" = "5" ] || [ "$SPEED" = "6" ]; then
	rc=0
	/bin/diag bandwidth set egress port all rate 4194296 || rc=1
	/bin/diag bandwidth set ingress port all rate 4194296 || rc=1
	exit "$rc"
fi
