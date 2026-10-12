#!/usr/bin/env bash
# tput.sh <label> <udp|tcp> <rate|-> <len> [netem args a->b]
# One-way a->b for T seconds; prints delivered rate, loss, netem drops and CPU
# (whole Pi, all four cores: user/sys/softirq/idle averaged over the run).
set -euo pipefail
cd "$(dirname "$0")"
T=${T:-15}
label=$1 proto=$2 rate=$3 len=$4; shift 4
./netem.sh clear; if [ $# -gt 0 ]; then ./netem.sh ab "$@"; fi
pkill -x iperf3 2>/dev/null || true; sleep 1
ip netns exec wp-b iperf3 -s -D -1 -p 5201 --logfile /tmp/iperf3-s.log; sleep 0.5
mpstat -P ALL 1 $((T-2)) > /tmp/mpstat.txt &
args=(-c 10.99.0.2 -t "$T" -J -l "$len")
if [ "$proto" = udp ]; then args+=(-u -b "$rate"); fi
j=$(ip netns exec wp-a iperf3 "${args[@]}" 2>/dev/null || true)
wait
cpu=$(awk '/Average:/ && $2=="all"{printf "usr=%s sys=%s soft=%s idle=%s", $3,$5,$8,$12}' /tmp/mpstat.txt)
busiest=$(awk '/Average:/ && $2 ~ /^[0-9]$/ {b=100-$12; if (b>m) m=b} END{printf "busiest-core=%.0f%%", m}' /tmp/mpstat.txt)
drops=$(ip netns exec wp-br tc -s qdisc show dev b1 | grep -o 'dropped [0-9]*' | head -1 || true)
if [ "$proto" = udp ]; then
  r=$(echo "$j" | jq -r 'if .error then "error: \(.error)" else (.end.sum | "rx=\(.bits_per_second/1e6|round)Mbit/s loss=\(.lost_percent|.*100|round/100)% pkts=\(.packets)") end')
else
  r=$(echo "$j" | jq -r '.end | "rx=\(.sum_received.bits_per_second/1e6|round)Mbit/s retr=\(.sum_sent.retransmits)"')
fi
printf '%-30s %s netem:%s | %s %s\n' "$label" "$r" "${drops:-none}" "$cpu" "$busiest"
./netem.sh clear
