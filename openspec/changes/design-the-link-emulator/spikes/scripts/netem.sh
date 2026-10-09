#!/usr/bin/env bash
# netem.sh <dir: ab|ba|both|clear> [netem args...]
set -euo pipefail
dir=$1; shift
apply() { ip netns exec wp-br tc qdisc replace dev "$1" root netem "$@" ; }
clr() { ip netns exec wp-br tc qdisc del dev "$1" root 2>/dev/null || true; }
case $dir in
  ab) ip netns exec wp-br tc qdisc replace dev b1 root netem "$@";;
  ba) ip netns exec wp-br tc qdisc replace dev a1 root netem "$@";;
  both) ip netns exec wp-br tc qdisc replace dev b1 root netem "$@"; ip netns exec wp-br tc qdisc replace dev a1 root netem "$@";;
  clear) clr a1; clr b1;;
esac
