#!/bin/sh
# netem's own rate against a tbf child under netem, on the spike's three-namespace bed.
# Needs root. Touches no real interface. Usage: sudo sh rate-shaper.sh [rate_mbit] [delay_ms]
# For each shaper: idle RTT, then a 15 s TCP transfer towards the device under test with a
# ping running alongside (the queue the transfer builds shows in the ping), then netem/tbf drops.
set -u
RATE=${1:-20}; DELAY=${2:-40}
DUT=wp-dut NET=wp-net BOX=wp-box

down() {
  for n in $DUT $NET $BOX; do
    p=$(ip netns pids $n 2>/dev/null); [ -n "$p" ] && kill $p 2>/dev/null
    ip netns del $n 2>/dev/null
  done
}
trap down EXIT
down
for n in $DUT $NET $BOX; do ip netns add $n; done
ip link add d0 netns $DUT type veth peer name o1 netns $BOX
ip link add n0 netns $NET type veth peer name n1 netns $BOX
ip -n $BOX link add br0 type bridge
for i in o1 n1; do ip -n $BOX link set $i master br0; done
for i in o1 n1 br0 lo; do ip -n $BOX link set $i up; done
ip -n $DUT addr add 10.99.0.1/24 dev d0; ip -n $DUT link set d0 up; ip -n $DUT link set lo up
ip -n $NET addr add 10.99.0.2/24 dev n0; ip -n $NET link set n0 up; ip -n $NET link set lo up
# veths default to no queue; give o1 the hardware's behaviour of a real port
ip netns exec $DUT ping -c 2 -q 10.99.0.2 >/dev/null

run() {
  name=$1
  echo "== $name"
  ip netns exec $DUT ping -q -c 20 -i 0.05 10.99.0.2 | tail -1 | sed 's/^/idle   /'
  ip netns exec $DUT iperf3 -s -1 -D
  sleep 0.5
  ip netns exec $DUT ping -q -c 70 -i 0.2 10.99.0.2 > /tmp/wp-ping.txt &
  pp=$!
  ip netns exec $NET iperf3 -c 10.99.0.1 -t 15 -J > /tmp/wp-iperf.json
  wait $pp
  tail -1 /tmp/wp-ping.txt | sed 's/^/loaded /'
  python3 -c "import json;d=json.load(open('/tmp/wp-iperf.json'));e=d['end'];print('tcp    %.1f Mbit/s, %d retransmits' % (e['sum_received']['bits_per_second']/1e6, e['sum_sent'].get('retransmits',0)))"
  tc -n $BOX -s qdisc show dev o1 | grep -E 'qdisc|dropped' | paste - - | sed 's/^/qdisc  /'
  tc -n $BOX qdisc del dev o1 root 2>/dev/null
}

LIMIT=1000   # wanpire's floor; sizing gives less at this rate and delay
tc -n $BOX qdisc add dev o1 root netem delay ${DELAY}ms rate ${RATE}mbit limit $LIMIT
run "netem rate ${RATE}mbit, delay ${DELAY}ms, limit $LIMIT"

# tbf's queue holds 'latency' worth of bytes at the rate; 20 ms is a modest real bottleneck
tc -n $BOX qdisc add dev o1 root handle 1: netem delay ${DELAY}ms limit $LIMIT
tc -n $BOX qdisc add dev o1 parent 1:1 handle 10: tbf rate ${RATE}mbit burst 32kb latency 20ms
run "netem delay ${DELAY}ms + tbf ${RATE}mbit latency 20ms"

tc -n $BOX qdisc add dev o1 root handle 1: netem delay ${DELAY}ms limit $LIMIT
tc -n $BOX qdisc add dev o1 parent 1:1 handle 10: tbf rate ${RATE}mbit burst 32kb latency 100ms
run "netem delay ${DELAY}ms + tbf ${RATE}mbit latency 100ms"
