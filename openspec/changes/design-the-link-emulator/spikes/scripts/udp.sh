#!/usr/bin/env bash
# udp.sh: one-way UDP through the bridge a->b with iperf3, netem on a->b only.
# Prints: label  sent  lost  loss%  out-of-order  receiver Mbit/s
set -euo pipefail
cd "$(dirname "$0")"
RATE=${RATE:-10M}; LEN=${LEN:-1200}; T=${T:-20}
ip netns exec wp-b iperf3 -s -D -1 -p 5201 --logfile /tmp/iperf3-s.log; sleep 0.5
label=$1; shift
./netem.sh clear
if [ $# -gt 0 ]; then ./netem.sh ab "$@"; fi
j=$(ip netns exec wp-a iperf3 -c 10.99.0.2 -u -b "$RATE" -l "$LEN" -t "$T" -J 2>/dev/null)
echo "$j" | jq -r --arg l "$label" '.end.sum as $s | "\($l)\tsent=\($s.packets) lost=\($s.lost_packets) loss=\($s.lost_percent|.*1000|round/1000)% ooo=\(.end.streams[0].udp.out_of_order // "?") rx=\(.end.sum.bits_per_second/1e6|.*10|round/10)Mbit/s"'
s=$(ip netns exec wp-br tc -s qdisc show dev b1 | grep -o 'dropped [0-9]*' | head -1)
echo "    netem $s"
./netem.sh clear
