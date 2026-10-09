#!/usr/bin/env python3
"""Sequenced UDP probe: count loss, loss bursts, duplicates and reordering.

  seq.py rx <bind-ip> <port> <seconds>        (prints a JSON summary)
  seq.py tx <dst-ip>  <port> <pps> <count> <size>
"""
import json, socket, struct, sys, time

def rx(ip, port, seconds):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 8 << 20)
    s.bind((ip, int(port))); s.settimeout(0.5)
    seen = set(); dup = ooo = 0; top = -1; total = None
    end = time.time() + float(seconds)
    while time.time() < end:
        try: d = s.recv(65535)
        except socket.timeout: continue
        n, total = struct.unpack("!II", d[:8])
        if n in seen: dup += 1; continue
        seen.add(n)
        if n < top: ooo += 1
        top = max(top, n)
    total = total or 0
    bursts = []; run = 0
    for i in range(total):
        if i in seen:
            if run: bursts.append(run); run = 0
        else: run += 1
    if run: bursts.append(run)
    lost = total - len(seen)
    print(json.dumps({"sent": total, "received": len(seen), "lost": lost,
        "loss_pct": round(100 * lost / total, 3) if total else None,
        "duplicates": dup, "out_of_order": ooo,
        "loss_bursts": len(bursts),
        "mean_burst": round(sum(bursts) / len(bursts), 2) if bursts else 0,
        "max_burst": max(bursts) if bursts else 0}))

def tx(ip, port, pps, count, size):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    pps, count, size = float(pps), int(count), int(size)
    pad = b"\0" * max(0, size - 8); t0 = time.perf_counter()
    for i in range(count):
        s.sendto(struct.pack("!II", i, count) + pad, (ip, int(port)))
        wait = t0 + (i + 1) / pps - time.perf_counter()
        if wait > 0: time.sleep(wait)

if __name__ == "__main__":
    {"rx": rx, "tx": tx}[sys.argv[1]](*sys.argv[2:])
