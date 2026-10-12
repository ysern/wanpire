#!/usr/bin/env bash
# delay.sh: ask for a round trip, measure it with ping through the bridge.
# Prints: label asked_rtt_ms min avg max mdev loss%
set -euo pipefail
cd "$(dirname "$0")"
N=${N:-500}
run() { # label asked netem-args...
  local label=$1 asked=$2; shift 2
  ./netem.sh clear
  if [ $# -gt 0 ]; then ./netem.sh both "$@"; fi
  out=$(ip netns exec wp-a ping -c "$N" -i 0.01 -q 10.99.0.2 | tail -2)
  loss=$(echo "$out" | grep -o '[0-9.]*% packet loss' | cut -d% -f1)
  rtt=$(echo "$out" | awk -F'= ' '/rtt/{print $2}' | cut -d' ' -f1 | tr / ' ')
  printf '%-28s %6s  %s  loss=%s%%\n' "$label" "$asked" "$rtt" "$loss"
}
echo "label                       asked  min avg max mdev (ms)"
run none 0
for rtt in 20 100 200 300; do run "delay ${rtt}" "$rtt" delay "$((rtt/2))ms"; done
run "jit 100 +-10 uniform" 100 delay 50ms 10ms
run "jit 100 +-10 normal" 100 delay 50ms 10ms distribution normal
run "jit 100 +-10 pareto" 100 delay 50ms 10ms distribution paretonormal
run "jit 100 +-10 normal, rate" 100 delay 50ms 10ms distribution normal rate 1gbit
./netem.sh clear
