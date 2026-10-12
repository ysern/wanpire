#!/usr/bin/env bash
# rig.sh up|down -- router-with-NAT test rig on the Pi's real Ethernet port.
#
# A workstation on the LAN connects to <pi-eth-address>:5201 (iperf3) or :7001
# (UDP echo). nftables forwards those ports, and only those, to a target in the
# namespace wp-t behind a veth pair. The impairment is netem on the two veth ends
# (t1 towards the target, t0 back towards the workstation), never on the real
# interfaces, so the SSH session and the Pi's own traffic are untouched.
# A dead-man timer clears everything after DEADMAN minutes whatever happens.
set -euo pipefail
cmd=${1:-up}; DEADMAN=${DEADMAN:-20}; IIF=${IIF:-eth0}
SELF=$(readlink -f "$0")
down() {
  # A process outlives its namespace's deletion: stop them first.
  ip netns pids wp-t 2>/dev/null | xargs -r kill 2>/dev/null || true
  ip netns del wp-t 2>/dev/null || true
  ip link del t1 2>/dev/null || true
  nft delete table ip wp_spike 2>/dev/null || true
  sysctl -qw net.ipv4.ip_forward=0
  systemctl stop wp-deadman.timer 2>/dev/null || true
}
up() {
  down
  systemd-run --quiet --unit wp-deadman --on-active="${DEADMAN}m" "$SELF" down
  ip netns add wp-t
  ip link add t1 type veth peer name t0 netns wp-t
  ip addr add 10.98.0.1/24 dev t1; ip link set t1 up
  ip -n wp-t addr add 10.98.0.2/24 dev t0; ip -n wp-t link set t0 up; ip -n wp-t link set lo up
  ip -n wp-t route add default via 10.98.0.1
  sysctl -qw net.ipv4.ip_forward=1
  nft -f - <<NFT
table ip wp_spike {
  chain prerouting_test { type nat hook prerouting priority dstnat;
    iifname "$IIF" meta l4proto { tcp, udp } th dport { 5201, 7001 } dnat to 10.98.0.2; }
  chain forward_test { type filter hook forward priority filter; policy drop;
    ct state established,related accept
    iifname "$IIF" oifname "t1" ip daddr 10.98.0.2 meta l4proto { tcp, udp } th dport { 5201, 7001 } accept; }
}
NFT
  ip netns exec wp-t iperf3 -s -D -p 5201 --logfile /tmp/iperf3-t.log
  ip netns exec wp-t setsid python3 "$(dirname "$SELF")/udpping.py" echo 10.98.0.2 7001 >/dev/null 2>&1 < /dev/null &
}
# netem on the path: rig.sh netem <out|back|both|clear> [args]
#   out  = workstation -> target (t1 egress)   back = target -> workstation (t0 egress)
netem() {
  local d=$1; shift
  case $d in
    out) tc qdisc del dev t1 root 2>/dev/null || true; tc qdisc add dev t1 root netem "$@";;
    back) ip netns exec wp-t tc qdisc del dev t0 root 2>/dev/null || true; ip netns exec wp-t tc qdisc add dev t0 root netem "$@";;
    both) netem out "$@"; netem back "$@";;
    clear) tc qdisc del dev t1 root 2>/dev/null || true; ip netns exec wp-t tc qdisc del dev t0 root 2>/dev/null || true;;
  esac
}
"$cmd" "${@:2}"
