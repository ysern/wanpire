#!/bin/sh
# wanpire's install, for Ubuntu Server and other Debian-like Linux with two Ethernet ports.
#
#   sudo install/install.sh [install] [--control IF] [--inbound IF] [--outbound IF]
#                           [--mode bridge|router] [--apply-netplan] [--no-start]
#   sudo install/install.sh uninstall [--purge]
#
# Idempotent: run it again and it changes only what differs. Without roles it proposes the
# Wi-Fi adapter as control, the on-board Ethernet port as inbound and a USB Ethernet port as
# outbound, and stops if one is missing. The netplan drop-in giving the line's ports no address
# is written and validated, and applied at the next boot (or now, with --apply-netplan).
#
# To try it without changing the system:
#   install/install.sh --dry-run                print each step, change nothing
#   install/install.sh --root DIR --no-venv     write the files under DIR instead of /
#                                                (no apt, systemctl or netplan there)
# Not plugged in yet? --no-check with all three roles named installs without looking for them.
# Other options: --sysfs DIR (where to read the adapters, default /sys/class/net),
#   --source DIR (the wanpire checkout, default this script's parent), --no-apt, --no-venv.
set -eu

ACTION=install
ROOT=""
SYSFS=/sys/class/net
DRY=0
APT=1
VENV=1
START=1
CHECK=1
APPLY_NETPLAN=0
PURGE=0
CONTROL=""
INBOUND=""
OUTBOUND=""
MODE=""
GIVEN=0
HERE=$(cd "$(dirname "$0")" && pwd)
SOURCE=$(dirname "$HERE")

die() { echo "install.sh: $*" >&2; exit 1; }
need() { [ $# -ge 2 ] || die "$1 needs a value"; }

while [ $# -gt 0 ]; do
    case "$1" in
        install|uninstall) ACTION=$1 ;;
        --root) need "$@"; ROOT=${2%/}; shift ;;
        --sysfs) need "$@"; SYSFS=$2; shift ;;
        --source) need "$@"; SOURCE=$2; shift ;;
        --control) need "$@"; CONTROL=$2; GIVEN=1; shift ;;
        --inbound) need "$@"; INBOUND=$2; GIVEN=1; shift ;;
        --outbound) need "$@"; OUTBOUND=$2; GIVEN=1; shift ;;
        --mode) need "$@"; MODE=$2; GIVEN=1; shift ;;
        --dry-run) DRY=1 ;;
        --no-apt) APT=0 ;;
        --no-venv) VENV=0 ;;
        --no-start) START=0 ;;
        --no-check) CHECK=0 ;;
        --apply-netplan) APPLY_NETPLAN=1 ;;
        --purge) PURGE=1 ;;
        -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
        *) die "unknown argument: $1 (see --help)" ;;
    esac
    shift
done

if [ -n "$ROOT" ]; then
    STAGING=1
    APT=0
else
    STAGING=0
fi
if [ "$(id -u)" != 0 ] && [ "$STAGING" = 0 ] && [ "$DRY" = 0 ]; then
    die "run as root (sudo), or try it first with --dry-run or --root DIR"
fi

P() { printf '%s%s' "$ROOT" "$1"; }  # a path on the box, under the staging root if any
VENV_DIR=/opt/wanpire/venv
WANPIRE=$VENV_DIR/bin/wanpire
CONFIG=/etc/wanpire/wanpire.json
TOKEN=/etc/wanpire/token
NETPLAN=/etc/netplan/60-wanpire.yaml
UNIT=/etc/systemd/system/wanpire.service
WANTS=/etc/systemd/system/multi-user.target.wants/wanpire.service

step() { printf '%-10s %s\n' "$1" "$2"; }

# write_file PATH MODE < content: writes only when the content or the mode differs
write_file() {
    tmp=$(mktemp)
    cat > "$tmp"
    dest=$(P "$1")
    if [ -f "$dest" ] && cmp -s "$tmp" "$dest" && \
       [ "$(stat -c %a "$dest")" = "$(printf '%o' "0$2")" ]; then
        rm -f "$tmp"
        step "$3" "unchanged: $1"
        return 1
    fi
    if [ "$DRY" = 1 ]; then
        rm -f "$tmp"
        step "$3" "would write $1"
        return 0
    fi
    mkdir -p "$(dirname "$dest")"
    chmod "$2" "$tmp"
    mv "$tmp" "$dest"
    step "$3" "wrote $1"
    return 0
}

remove() {
    dest=$(P "$1")
    if [ ! -e "$dest" ] && [ ! -L "$dest" ]; then
        return 0
    fi
    if [ "$DRY" = 1 ]; then
        step remove "would remove $1"
    else
        rm -rf "$dest"
        step remove "removed $1"
    fi
}

run() {
    if [ "$DRY" = 1 ]; then
        step run "would run: $*"
    else
        "$@"
    fi
}

# -- the adapters ---------------------------------------------------------------------------

kind_of() {
    d=$SYSFS/$1
    if [ -d "$d/wireless" ]; then echo wifi; return; fi
    if [ ! -e "$d/device" ]; then echo virtual; return; fi
    case "$(readlink -f "$d/device")" in
        */usb*) echo usb ;;
        *) echo onboard ;;
    esac
}

detect() {
    for d in "$SYSFS"/*; do
        [ -e "$d" ] || continue
        name=$(basename "$d")
        case "$(kind_of "$name")" in
            wifi) [ -n "$CONTROL" ] || CONTROL=$name ;;
            onboard) [ -n "$INBOUND" ] || INBOUND=$name ;;
            usb) [ -n "$OUTBOUND" ] || OUTBOUND=$name ;;
        esac
    done
    [ -n "$CONTROL" ] || die "no Wi-Fi adapter found for control; name one with --control <adapter>"
    [ -n "$INBOUND" ] || die "no on-board Ethernet port found for inbound; name one with --inbound <adapter>"
    [ -n "$OUTBOUND" ] || die "no USB Ethernet port found for outbound: plug one in, or name one with --outbound <adapter>"
}

# roles in an existing configuration: "mode control inbound outbound"
roles_of() {
    python3 - "$1" <<'EOF'
import json, sys
c = json.load(open(sys.argv[1], encoding="utf-8"))
a = c["adapters"]
print(c.get("mode", "bridge"), a["control"], a["inbound"], a["outbound"][0])
EOF
}

config_json() {
    printf '{"schema": "wanpire-config/1", "mode": "%s",\n "adapters": {"control": "%s", "inbound": "%s", "outbound": ["%s"]}}\n' \
        "$MODE" "$CONTROL" "$INBOUND" "$OUTBOUND"
}

netplan_yaml() {
    echo "# wanpire: the line's ports carry no address (written by install/install.sh)."
    echo "# The control adapter is not named here: its own configuration is left alone."
    echo "network:"
    echo "  version: 2"
    echo "  ethernets:"
    if [ "$MODE" = bridge ]; then ports="$INBOUND $OUTBOUND"; else ports=$OUTBOUND; fi
    for p in $ports; do
        echo "    $p:"
        echo "      dhcp4: false"
        echo "      dhcp6: false"
        echo "      accept-ra: false"
        echo "      link-local: []"
        echo "      optional: true"
    done
}

# -- uninstall ------------------------------------------------------------------------------

if [ "$ACTION" = uninstall ]; then
    if [ "$STAGING" = 0 ] && command -v systemctl >/dev/null 2>&1 && [ -f "$UNIT" ]; then
        run systemctl disable --now wanpire.service || true
    fi
    if [ "$STAGING" = 0 ] && [ -x "$WANPIRE" ] && [ -f "$CONFIG" ]; then
        run "$WANPIRE" reset || true
        run "$WANPIRE" down || true
    fi
    remove "$WANTS"
    remove "$UNIT"
    if [ "$STAGING" = 0 ] && command -v systemctl >/dev/null 2>&1; then
        run systemctl daemon-reload
    fi
    if [ -e "$(P "$NETPLAN")" ]; then
        remove "$NETPLAN"
        if [ "$STAGING" = 0 ] && [ "$APPLY_NETPLAN" = 1 ]; then
            run netplan apply
        elif [ "$STAGING" = 0 ]; then
            step netplan "the ports get their old configuration at the next boot, or: sudo netplan apply"
        fi
    fi
    remove /opt/wanpire
    if [ "$PURGE" = 1 ]; then
        remove /etc/wanpire
    else
        step keep "kept /etc/wanpire (the configuration and the token); --purge removes it"
    fi
    exit 0
fi

# -- install: every check before any change -------------------------------------------------

if [ -f "$(P "$CONFIG")" ]; then
    # shellcheck disable=SC2046
    set -- $(roles_of "$(P "$CONFIG")")
    if [ "$GIVEN" = 1 ]; then
        for pair in "$1:${MODE:-$1}" "$2:${CONTROL:-$2}" "$3:${INBOUND:-$3}" "$4:${OUTBOUND:-$4}"; do
            if [ "${pair%%:*}" != "${pair#*:}" ]; then
                die "$CONFIG exists with other roles ($1: control $2, inbound $3, outbound $4). To change them, run 'wanpire down', edit $CONFIG and run this again; or start over with 'install.sh uninstall --purge'"
            fi
        done
    fi
    MODE=$1 CONTROL=$2 INBOUND=$3 OUTBOUND=$4
    step roles "kept from $CONFIG: $MODE mode, control $CONTROL, inbound $INBOUND, outbound $OUTBOUND"
else
    MODE=${MODE:-bridge}
    case "$MODE" in bridge|router) ;; *) die "--mode is bridge or router, not $MODE" ;; esac
    if [ "$CHECK" = 1 ]; then
        detect
        for a in "$CONTROL" "$INBOUND" "$OUTBOUND"; do
            [ -e "$SYSFS/$a" ] || die "no adapter named $a (the adapters are in $SYSFS)"
        done
    elif [ -z "$CONTROL" ] || [ -z "$INBOUND" ] || [ -z "$OUTBOUND" ]; then
        die "--no-check needs all three roles: --control, --inbound and --outbound"
    fi
    [ "$OUTBOUND" != "$CONTROL" ] || die "the outbound adapter shares nothing: $OUTBOUND is also control"
    [ "$OUTBOUND" != "$INBOUND" ] || die "the outbound adapter shares nothing: $OUTBOUND is also inbound"
    if [ "$MODE" = bridge ] && [ "$CONTROL" = "$INBOUND" ]; then
        die "in bridge mode the control adapter cannot be a bridge port; use router mode, or another control adapter"
    fi
    step roles "$MODE mode, control $CONTROL, inbound $INBOUND, outbound $OUTBOUND"
fi

if [ "$VENV" = 1 ]; then
    command -v python3 >/dev/null 2>&1 || die "python3 is needed (apt install python3)"
    python3 -c 'import sys; sys.exit(sys.version_info < (3, 12))' || \
        die "wanpire needs Python 3.12 or later; this system has $(python3 -V 2>&1)"
fi

# -- install: the steps ---------------------------------------------------------------------

if [ "$APT" = 1 ]; then
    missing=""
    for pkg in python3-venv iproute2 nftables dnsmasq-base ethtool iw; do
        dpkg -s "$pkg" >/dev/null 2>&1 || missing="$missing $pkg"
    done
    if [ -n "$missing" ]; then
        run apt-get update
        # shellcheck disable=SC2086
        run env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends $missing
    else
        step packages "unchanged: all installed"
    fi
fi

if [ "$VENV" = 1 ]; then
    if [ ! -x "$(P $VENV_DIR)/bin/python" ]; then
        run python3 -m venv "$(P $VENV_DIR)"
    fi
    run "$(P $VENV_DIR)/bin/pip" install --quiet --upgrade "$SOURCE"
    step venv "wanpire in $VENV_DIR"
fi

config_json | write_file "$CONFIG" 644 config || true
if [ "$VENV" = 1 ] && [ "$STAGING" = 0 ] && [ "$DRY" = 0 ] && [ "$CHECK" = 1 ]; then
    "$WANPIRE" adapters --config "$CONFIG" >/dev/null || \
        die "wanpire refused $CONFIG (above); fix it and run this again"
fi

if [ -s "$(P "$TOKEN")" ]; then
    step token "unchanged: $TOKEN"
elif [ "$DRY" = 1 ]; then
    step token "would generate $TOKEN (mode 0600)"
else
    mkdir -p "$(dirname "$(P "$TOKEN")")"
    (umask 077 && od -An -tx1 -N32 /dev/urandom | tr -d ' \n' > "$(P "$TOKEN")" && echo >> "$(P "$TOKEN")")
    chmod 600 "$(P "$TOKEN")"
    step token "generated $TOKEN (mode 0600): give it to the web page and your MCP host"
fi

if [ "$STAGING" = 1 ] || [ -d /etc/netplan ]; then
    if netplan_yaml | write_file "$NETPLAN" 600 netplan && [ "$STAGING" = 0 ]; then
        run netplan generate
        if [ "$APPLY_NETPLAN" = 1 ]; then
            run netplan apply
        else
            step netplan "takes effect at the next boot, or now: sudo netplan apply"
        fi
    fi
else
    step netplan "no netplan here: give $([ "$MODE" = bridge ] && echo "$INBOUND and ")$OUTBOUND no address (no DHCP, no IPv6 autoconfiguration) in your network configuration"
fi

unit_changed=0
write_file "$UNIT" 644 unit < "$HERE/wanpire.service" && unit_changed=1
if [ "$STAGING" = 1 ]; then
    if [ ! -L "$(P "$WANTS")" ]; then
        if [ "$DRY" = 1 ]; then
            step enable "would enable wanpire.service"
        else
            mkdir -p "$(dirname "$(P "$WANTS")")"
            ln -s "$UNIT" "$(P "$WANTS")"
            step enable "enabled wanpire.service"
        fi
    else
        step enable "unchanged: wanpire.service enabled"
    fi
else
    [ "$unit_changed" = 0 ] || run systemctl daemon-reload
    run systemctl enable --quiet wanpire.service
    if [ "$START" = 1 ]; then
        if [ "$unit_changed" = 1 ] || [ "$VENV" = 1 ]; then
            run systemctl restart wanpire.service
        else
            run systemctl start wanpire.service
        fi
        step service "wanpire.service started; the web page is at http://<control address>:8080/"
    else
        step service "enabled, not started (--no-start)"
    fi
fi
