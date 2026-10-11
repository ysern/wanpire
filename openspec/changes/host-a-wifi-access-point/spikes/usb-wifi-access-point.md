# Spike: the USB Wi-Fi adapter as an access point

**Status:** in progress, 2026-10-11.

## Question

Can the owner's USB Wi-Fi adapter, a TP-Link Archer TX20U Plus (USB `2357:013f`), run a 5 GHz
WPA2/WPA3 access point with `hostapd` on the reference box (Raspberry Pi 4, 1 GB, Ubuntu 24.04,
kernel 6.8.0-raspi), steadily, through an out-of-tree driver?

## Why it matters

The change's access point rests on it. If it fails, the change stops here and recommends an
adapter whose driver is in the kernel and does AP mode.

## Rests on

- The kernel's `rtw89` on this box has PCIe modules only: no network interface appears for the
  adapter.
- The box is controlled over its built-in Wi-Fi: nothing in the spike may touch that radio's
  configuration, and the bridged line is left alone.

## Method

1. Find the chip from the USB id tables of the candidate drivers, and the licence.
2. Install the kernel headers, `dkms` and `hostapd`; build and install the driver by DKMS; check
   the adapter gets an interface and its radio lists AP mode.
3. Start `hostapd` by hand on the USB adapter only, with a generated test name and password, 5 GHz
   channel 36 at 80 MHz, WPA2 and WPA3; check it with `iw` and look for its beacon from the
   box's other radio.
4. Leave it up for an hour or more, checking every minute.
5. Take it down; keep the driver if it works.

## Kill or pivot signal

No interface, no AP mode in the radio's modes, `hostapd` failing to start on 5 GHz, or the
access point falling over within the hour: the out-of-tree route is dropped, and the change
recommends a MediaTek MT7612U or MT7921AU adapter (in-kernel `mt76`, AP mode proven).

## Findings

(Written when the spike ends.)

## Findings in full

### The chip is an RTL8832AU, not an RTL8852BU

The guess was morrownr's `rtl8852bu` (Realtek's vendor driver). Its supported-ids list and its
USB table do not carry `2357:013f`; nor do those of `rtl8852cu`. Upstream Linux's
`drivers/net/wireless/realtek/rtw89/rtw8852au.c` does, beside `2357:0140` and `2357:0141`: the
adapter is an RTL8832AU (the 2x2 Wi-Fi 6 chip of the 8852A family, on USB). Upstream's rtw89 has
had USB support only since kernels well after 6.8.

The backport of upstream's rtw89 (github.com/morrownr/rtw89) builds for kernels 6.6 and newer,
lists the RTL8832AU among its USB chips, carries the same `2357:013f` entry, and installs by DKMS.
Its modules are `MODULE_LICENSE("Dual BSD/GPL")`; the firmware is under Realtek's
redistribution licence (`LICENCE.rtlwifi_firmware.txt`). Installing it on a box is fine; copying
it into wanpire is not, and wanpire does not.

The adapter enumerates on the Pi as a USB 2.0 device (480 Mbit/s, vendor-specific class, 500 mA),
after its own switch out of its driver-disc mode.
