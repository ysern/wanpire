#!/bin/sh
# A three-namespace bed for trying wanpire by hand, the same as tests/netns builds:
#
#   wp-dut (10.99.0.1) --veth-- [wp-box: bridge br0 over o1 and n1] --veth-- wp-net (10.99.0.2)
#
# o1 is the outbound adapter. Touches no real interface. Needs root.
#   sudo tools/testbed.sh up      build it (and write /tmp/wanpire-bed.json, a config for it)
#   sudo tools/testbed.sh down    take it away
set -eu
down() {
    for n in wp-dut wp-net wp-box; do
        ip netns del "$n" 2>/dev/null || true
    done
    rm -f /tmp/wanpire-bed.json
}
case "${1:-}" in
up)
    down
    for n in wp-dut wp-net wp-box; do ip netns add "$n"; done
    ip link add d0 netns wp-dut type veth peer name o1 netns wp-box
    ip link add n0 netns wp-net type veth peer name n1 netns wp-box
    ip -n wp-box link add br0 type bridge
    for i in o1 n1; do ip -n wp-box link set "$i" master br0; done
    for i in o1 n1 br0 lo; do ip -n wp-box link set "$i" up; done
    ip -n wp-dut addr add 10.99.0.1/24 dev d0
    ip -n wp-net addr add 10.99.0.2/24 dev n0
    for n in wp-dut wp-net; do
        ip -n "$n" link set lo up
        ip -n "$n" link set "$( [ "$n" = wp-dut ] && echo d0 || echo n0 )" up
    done
    printf '%s\n' '{"schema": "wanpire-config/1", "mode": "bridge",' \
        ' "adapters": {"control": "ctl0", "inbound": "n1", "outbound": ["o1"]}}' \
        > /tmp/wanpire-bed.json
    ip netns exec wp-dut ping -c 2 -i 0.2 -W 1 10.99.0.2 >/dev/null
    echo "bed up: wanpire serve --netns wp-box --config /tmp/wanpire-bed.json --host 127.0.0.1"
    ;;
down) down; echo "bed down" ;;
*) echo "usage: $0 up|down" >&2; exit 2 ;;
esac
