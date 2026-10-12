#!/usr/bin/env bash
# Build or remove a three-namespace test bed: wp-a <-> wp-br (bridge) <-> wp-b.
# Nothing here touches the host's real interfaces.
#   wp-a: 10.99.0.1/24 on veth a0      wp-b: 10.99.0.2/24 on veth b0
#   wp-br: bridge br0 over a1 and b1, no address (transparent)
# Impairment a->b is netem on b1's egress; b->a is netem on a1's egress.
set -euo pipefail
cmd=${1:-up}
down() {
  for ns in wp-a wp-b wp-br; do
    ip netns pids "$ns" 2>/dev/null | xargs -r kill 2>/dev/null || true
    ip netns del "$ns" 2>/dev/null || true
  done
}
up() {
  down
  for ns in wp-a wp-b wp-br; do ip netns add "$ns"; done
  ip link add a0 netns wp-a type veth peer name a1 netns wp-br
  ip link add b0 netns wp-b type veth peer name b1 netns wp-br
  ip -n wp-br link add br0 type bridge
  ip -n wp-br link set a1 master br0
  ip -n wp-br link set b1 master br0
  for i in a1 b1 br0 lo; do ip -n wp-br link set "$i" up; done
  ip -n wp-a addr add 10.99.0.1/24 dev a0; ip -n wp-a link set a0 up; ip -n wp-a link set lo up
  ip -n wp-b addr add 10.99.0.2/24 dev b0; ip -n wp-b link set b0 up; ip -n wp-b link set lo up
  # Let the bridge settle (no STP, so forwarding is immediate; this is just the link-up).
  sleep 1
  ip netns exec wp-a ping -c 2 -W 1 10.99.0.2 >/dev/null
}
"$cmd"
