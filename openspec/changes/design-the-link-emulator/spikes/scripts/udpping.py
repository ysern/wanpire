#!/usr/bin/env python3
"""UDP round-trip probe that works where ICMP cannot be port-forwarded.

  udpping.py echo <bind-ip> <port>
  udpping.py ping <host> <port> <count> <interval-s>   (prints a JSON summary)
"""
import json, socket, statistics, struct, sys, time

def echo(ip, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind((ip, int(port)))
    while True:
        d, a = s.recvfrom(2048)
        s.sendto(d, a)

def ping(host, port, count, interval):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setblocking(False)
    count, interval = int(count), float(interval)
    sent = {}; rtts = {}; t0 = time.perf_counter(); i = 0
    deadline = None
    while True:
        now = time.perf_counter()
        if i < count and now >= t0 + i * interval:
            s.sendto(struct.pack("!Id", i, now) + b"\0" * 52, (host, int(port)))
            i += 1
            if i == count: deadline = now + 3.0
        try:
            while True:
                d = s.recv(2048)
                n, ts = struct.unpack("!Id", d[:12])
                if n not in rtts: rtts[n] = (time.perf_counter() - ts) * 1000
        except (BlockingIOError, ConnectionResetError):
            pass
        if deadline and time.perf_counter() > deadline: break
        time.sleep(0.0005)
    v = list(rtts.values())
    out = {"sent": count, "received": len(v),
           "loss_pct": round(100 * (count - len(v)) / count, 3)}
    if v:
        q = statistics.quantiles(v, n=100)
        out.update(min=round(min(v), 3), avg=round(statistics.mean(v), 3),
                   p50=round(q[49], 3), p99=round(q[98], 3), max=round(max(v), 3),
                   stdev=round(statistics.pstdev(v), 3))
    print(json.dumps(out))

if __name__ == "__main__":
    {"echo": echo, "ping": ping}[sys.argv[1]](*sys.argv[2:])
