#!/bin/sh
# wanpire's install, for Ubuntu Server and other Debian-like Linux with two Ethernet ports.
#
#   sudo install/install.sh [install] [--control IF] [--inbound IF] [--outbound IF]
#                           [--mode bridge|router] [--apply-netplan] [--no-start] [--user NAME]
#   sudo install/install.sh uninstall [--purge]
#
# No credential is written: the first visit to the box's web page makes its account, a user
# name and a password. --user NAME sets it here instead, the password read from standard input.
# A forgotten password: `sudo wanpire account set <user>` on the box, over SSH.
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
#
# Wi-Fi: a Wi-Fi adapter picked as inbound or outbound (on the web page) is an access point.
#   --wifi-country CC   the regulatory country an access point needs (else the box's own, if set)
#   --wifi-driver       build and install, through DKMS, the out-of-tree rtw89 driver for a USB
#                       Wi-Fi adapter the kernel does not drive (fetched from its repository;
#                       wanpire ships none of it). Without it, such an adapter is only named.
# Other options: --sysfs DIR (where to read the adapters, default /sys/class/net),
#   --usb-sysfs DIR (the USB devices, default /sys/bus/usb/devices),
#   --source DIR (the wanpire checkout, default this script's parent), --no-apt, --no-venv.
set -eu

ACTION=install
ROOT=""
SYSFS=/sys/class/net
USB_SYSFS=/sys/bus/usb/devices
WIFI_DRIVER=0
WIFI_COUNTRY=""
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
ACCOUNT_USER=""
HERE=$(cd "$(dirname "$0")" && pwd)
SOURCE=$(dirname "$HERE")

die() { echo "install.sh: $*" >&2; exit 1; }
need() { [ $# -ge 2 ] || die "$1 needs a value"; }

while [ $# -gt 0 ]; do
    case "$1" in
        install|uninstall) ACTION=$1 ;;
        --root) need "$@"; ROOT=${2%/}; shift ;;
        --sysfs) need "$@"; SYSFS=$2; shift ;;
        --usb-sysfs) need "$@"; USB_SYSFS=$2; shift ;;
        --wifi-driver) WIFI_DRIVER=1 ;;
        --wifi-country) need "$@"; WIFI_COUNTRY=$2; shift ;;
        --source) need "$@"; SOURCE=$2; shift ;;
        --control) need "$@"; CONTROL=$2; GIVEN=1; shift ;;
        --inbound) need "$@"; INBOUND=$2; GIVEN=1; shift ;;
        --outbound) need "$@"; OUTBOUND=$2; GIVEN=1; shift ;;
        --mode) need "$@"; MODE=$2; GIVEN=1; shift ;;
        --user) need "$@"; ACCOUNT_USER=$2; shift ;;
        --dry-run) DRY=1 ;;
        --no-apt) APT=0 ;;
        --no-venv) VENV=0 ;;
        --no-start) START=0 ;;
        --no-check) CHECK=0 ;;
        --apply-netplan) APPLY_NETPLAN=1 ;;
        --purge) PURGE=1 ;;
        -h|--help) sed -n '2,31p' "$0"; exit 0 ;;
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

case "$WIFI_COUNTRY" in
    "") ;;
    00) die "--wifi-country is a country, not 00" ;;
    [A-Z][A-Z]) ;;
    *) die "--wifi-country is two capital letters, an ISO 3166-1 code such as GB, not $WIFI_COUNTRY" ;;
esac

# The out-of-tree driver for Realtek's Wi-Fi 6 USB chips (RTL8832AU and kin): the upstream
# rtw89 backported, Dual BSD/GPL. Fetched at the commit proven on the reference build.
RTW89_REPO=https://github.com/morrownr/rtw89
RTW89_COMMIT=8bbbacadf6fa73c3a3195aefbd4b2ec2422ae356

P() { printf '%s%s' "$ROOT" "$1"; }  # a path on the box, under the staging root if any
VENV_DIR=/opt/wanpire/venv
WANPIRE=$VENV_DIR/bin/wanpire
CONFIG=/etc/wanpire/wanpire.json
FACTORY=/etc/wanpire/factory.json  # the configuration as installed: what `wanpire factory-reset` restores
ACCOUNT=/etc/wanpire/account
OLD_TOKEN=/etc/wanpire/token  # the first version's; nothing reads it any more
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
    if [ -d "$d/wireless" ]; then
        case "$(readlink -f "$d/device")" in */usb*) echo usb-wifi ;; *) echo wifi ;; esac
        return
    fi
    if [ ! -e "$d/device" ]; then echo virtual; return; fi
    case "$(readlink -f "$d/device")" in
        */usb*) echo usb ;;
        *) echo onboard ;;
    esac
}

USB_WIFI=""
detect() {
    for d in "$SYSFS"/*; do
        [ -e "$d" ] || continue
        name=$(basename "$d")
        case "$(kind_of "$name")" in
            wifi) [ -n "$CONTROL" ] || CONTROL=$name ;;
            usb-wifi) [ -n "$USB_WIFI" ] || USB_WIFI=$name ;;
            onboard) [ -n "$INBOUND" ] || INBOUND=$name ;;
            usb) [ -n "$OUTBOUND" ] || OUTBOUND=$name ;;
        esac
    done
    # a USB radio is control only when it is the only one: the built-in one stays control
    [ -n "$CONTROL" ] || CONTROL=$USB_WIFI
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
    printf '{"schema": "wanpire-config/1", "mode": "%s",\n "adapters": {"control": "%s", "inbound": "%s", "outbound": ["%s"]}' \
        "$MODE" "$CONTROL" "$INBOUND" "$OUTBOUND"
    [ -z "$WIFI_COUNTRY" ] || printf ',\n "wifi": {"country": "%s"}' "$WIFI_COUNTRY"
    printf '}\n'
}

# an installed configuration with the country added, unless it has one: on standard output
with_country() {
    "${PYTHON:-python3}" - "$1" "$2" <<'EOF'
import json, sys
c = json.load(open(sys.argv[1], encoding="utf-8"))
if not (c.get("wifi") or {}).get("country"):
    c.setdefault("wifi", {})["country"] = sys.argv[2]
print(json.dumps(c, indent=1, ensure_ascii=False))
EOF
}

# USB devices that look like Wi-Fi adapters and that no driver has taken: "id product" lines
undriven_wifi() {
    for d in "$USB_SYSFS"/*; do
        [ -f "$d/product" ] && [ -f "$d/idVendor" ] || continue
        case "$(cat "$d/product")" in
            *802.11*|*WLAN*|*Wireless*|*Wi-Fi*|*WiFi*) ;;
            *) continue ;;
        esac
        driven=0
        for i in "$d"/*:*; do
            if [ -e "$i/driver" ]; then driven=1; fi
        done
        [ "$driven" = 1 ] || echo "$(cat "$d/idVendor"):$(cat "$d/idProduct") $(cat "$d/product")"
    done
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
        step keep "kept /etc/wanpire (the configuration and the account); --purge removes it"
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
    # hostapd: a Wi-Fi outbound access point; wpasupplicant and dhcpcd-base: a Wi-Fi inbound client
    for pkg in python3-venv iproute2 nftables dnsmasq-base ethtool iw hostapd wpasupplicant dhcpcd-base; do
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

# The box's own regulatory country, when the option gives none and the box has one set
if [ -z "$WIFI_COUNTRY" ] && [ "$STAGING" = 0 ] && command -v iw >/dev/null 2>&1; then
    c=$(iw reg get 2>/dev/null | sed -n 's/^country \([A-Z][A-Z]\):.*/\1/p' | head -n 1)
    # A Pi's built-in radio may show a code of its own ("country 98") as the global domain;
    # the country the system asked for (netplan's regulatory-domain) is then the kernel's hint.
    case $c in
        [A-Z][A-Z]) ;;
        *) c=$(cat /sys/module/cfg80211/parameters/ieee80211_regdom 2>/dev/null) ;;
    esac
    case $c in 00|"") ;; [A-Z][A-Z]) WIFI_COUNTRY=$c ;; esac
fi

# Written once: afterwards the page changes it (the roles, the access points), and a second
# install keeps it, adding only a country it lacks. Root only: it holds the access points'
# passwords.
if [ -f "$(P "$CONFIG")" ]; then
    if [ -n "$WIFI_COUNTRY" ]; then
        with_country "$(P "$CONFIG")" "$WIFI_COUNTRY" | write_file "$CONFIG" 600 config || true
    elif [ "$(stat -c %a "$(P "$CONFIG")")" != 600 ]; then
        run chmod 600 "$(P "$CONFIG")"
        step config "made $CONFIG readable by root only"
    else
        step config "unchanged: $CONFIG"
    fi
    # a box installed before the factory copy existed: its install state is what it has now
    if [ ! -f "$(P "$FACTORY")" ]; then
        write_file "$FACTORY" 600 factory < "$(P "$CONFIG")" && \
            step factory "copied from $CONFIG: the box's install state, which 'wanpire factory-reset' restores"
    fi
else
    config_json | write_file "$CONFIG" 600 config || true
    config_json | write_file "$FACTORY" 600 factory || true
fi
[ -n "$WIFI_COUNTRY" ] || \
    step wifi "no regulatory country: an access point needs one (--wifi-country CC, or wifi.country in $CONFIG)"
if [ "$VENV" = 1 ] && [ "$STAGING" = 0 ] && [ "$DRY" = 0 ] && [ "$CHECK" = 1 ]; then
    "$WANPIRE" adapters --config "$CONFIG" >/dev/null || \
        die "wanpire refused $CONFIG (above); fix it and run this again"
fi

remove "$OLD_TOKEN"

# -- the access point's driver (--wifi-driver) ------------------------------------------------

undriven=$(undriven_wifi)
if [ -n "$undriven" ] && [ "$WIFI_DRIVER" = 0 ]; then
    echo "$undriven" | while read -r id product; do
        step wifi "$id ($product) has no driver; --wifi-driver builds the out-of-tree rtw89 for it ($RTW89_REPO)"
    done
fi
if [ "$WIFI_DRIVER" = 1 ]; then
    if [ "$STAGING" = 1 ] && [ "$DRY" = 0 ]; then
        step wifi "--wifi-driver skipped under --root: it builds a kernel module for this box"
    else
        kver=$(uname -r)
        run env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
            "linux-headers-$kver" dkms git build-essential
        src=/usr/src/rtw89-wanpire
        if [ "$DRY" = 1 ] || [ ! -d "$src/.git" ]; then
            run git clone --quiet "$RTW89_REPO" "$src"
        else
            run git -C "$src" fetch --quiet origin
        fi
        run git -C "$src" -c advice.detachedHead=false checkout --quiet "$RTW89_COMMIT"
        if [ "$DRY" = 1 ]; then
            ver=VERSION
        else
            ver=$(sed -n 's/^PACKAGE_VERSION="\(.*\)"/\1/p' "$src/dkms.conf")
        fi
        # dkms wants its source at /usr/src/<name>-<version>
        [ -e "/usr/src/rtw89-$ver" ] || run ln -s "$src" "/usr/src/rtw89-$ver"
        # One compiler at a time on a small box: three at once starved a 1 GB Pi of memory.
        # Kept in DKMS's own override, so the rebuild after a kernel update does the same.
        mem=$(sed -n 's/^MemTotal: *\([0-9]*\).*/\1/p' /proc/meminfo)
        jobs=1
        [ "${mem:-0}" -lt 3000000 ] || jobs=$(( $(nproc) - 1 ))
        # shellcheck disable=SC2016
        printf '# written by wanpire install.sh: %s compiler(s) at a time\nMAKE="KVER=${kernelver} NPROC=%s '"'"'make'"'"' modules"\n' \
            "$jobs" "$jobs" | write_file /etc/dkms/rtw89.conf 644 dkms || true
        run env NPROC=$jobs dkms install "rtw89/$ver" -k "$kver"
        run make -C "$src" install_fw
        run cp "$src/rtw89.conf" /etc/modprobe.d/rtw89.conf
        step wifi "the rtw89 driver is installed; unplug the adapter and plug it in again, or reboot"
    fi
fi

# wanpire's own command sets the account: the venv's, or (--no-venv) the checkout's
account_tool() {
    if [ "$VENV" = 1 ]; then
        "$(P $VENV_DIR)/bin/wanpire" account "$@"
    else
        PYTHONPATH="$SOURCE/src" "${PYTHON:-python3}" -m wanpire.cli account "$@"
    fi
}

HAS_ACCOUNT=0
if [ -s "$(P "$ACCOUNT")" ]; then
    HAS_ACCOUNT=1
    step account "unchanged: $ACCOUNT"
    [ -z "$ACCOUNT_USER" ] || \
        step account "--user ignored: the box has an account; to change it: sudo wanpire account set <user>"
elif [ -n "$ACCOUNT_USER" ]; then
    if [ "$DRY" = 1 ]; then
        step account "would set the account $ACCOUNT_USER, the password from standard input"
    else
        account_tool set "$ACCOUNT_USER" --file "$(P "$ACCOUNT")" >/dev/null || \
            die "the account was not set (above); run this again, or make it on the first visit"
        HAS_ACCOUNT=1
        step account "set: $ACCOUNT_USER, in $ACCOUNT (mode 0600, the password hashed)"
    fi
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

if [ "$HAS_ACCOUNT" = 0 ]; then
    step account "none yet: open http://<control address>:8080/ now to make it (until then, anyone on the control network can), or: sudo wanpire account set <user>"
fi
