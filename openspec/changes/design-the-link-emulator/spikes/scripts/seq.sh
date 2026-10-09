#!/usr/bin/env bash
# seq.sh <label> [netem args for a->b]: 10000 packets at 1000 pps, 200 bytes.
set -euo pipefail
cd "$(dirname "$0")"
label=$1; shift
./netem.sh clear; if [ $# -gt 0 ]; then ./netem.sh ab "$@"; fi
ip netns exec wp-b python3 seq.py rx 10.99.0.2 7000 13 > /tmp/seq.json &
sleep 0.5
ip netns exec wp-a python3 seq.py tx 10.99.0.2 7000 1000 10000 200
wait
printf '%-34s %s\n' "$label" "$(cat /tmp/seq.json)"
./netem.sh clear
