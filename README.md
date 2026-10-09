# wanpire

**A small box on your Ethernet line that makes it behave like a long internet link.**

wanpire sits between your device and the rest of the network and adds what a long
link adds: delay, jitter, loss (also in bursts), a bandwidth cap, reordering and
duplication, set separately for each direction. Describe the link by its two ends,
for example *London on consumer fibre* to *Los Angeles on 4G*, and wanpire works out
the rest. Drive it from a web page, a REST API, or any MCP-capable AI agent.

The reference build is a Raspberry Pi 4 with Ubuntu Server 24.04 LTS, its on-board
Ethernet port as the link in and a USB 3 gigabit Ethernet adapter as the link out,
controlled over its Wi-Fi. Any Debian-like Linux box with two Ethernet ports should do.

## Status

Early. The engine and its command line work; presets, the web UI, the REST API and the MCP do not exist yet. What there is:

- the design and the first measurements: [`openspec/changes/design-the-link-emulator/`](openspec/changes/design-the-link-emulator/)
- how the box was built, step by step: [`docs/build-journal.md`](docs/build-journal.md)
- what is assumed and what is still open: [`docs/open-questions.md`](docs/open-questions.md)

What works today, on Linux as root: the engine and a command line, on raw figures.

```sh
python3 -m venv .venv && .venv/bin/pip install -e ".[test]"
sudo .venv/bin/wanpire apply --adapter <outbound> --down delay_ms=150,jitter_ms=5 --up delay_ms=150,loss_pct=1
sudo .venv/bin/wanpire show  --adapter <outbound>
sudo .venv/bin/wanpire clear --adapter <outbound>
```

A link is cleared by itself after two minutes unless renewed (`wanpire renew`), so a
forgotten one never lingers. Tests: `.venv/bin/pytest` (no root needed), and with real packets
in network namespaces, `sudo .venv/bin/python -m pytest tests/netns`.

The project is planned with [OpenSpec](https://github.com/Fission-AI/OpenSpec):
`openspec/specs/` says what must be true, `openspec/changes/` holds the work in progress.

## Licence

MIT, see [LICENSE](LICENSE).
