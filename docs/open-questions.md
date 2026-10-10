# Open questions

Everything still open about wanpire, and every assumption made in the owner's place.

Tags: **👤 needs the owner** (money, accounts, licences, hardware in hand, publishing);
**⚪ assumed** (decided by the agent; says what was chosen and what was not, so it can be
reversed). Answered questions stay, marked answered.

## Needs the owner

| Id | Question | Options and recommendation |
|---|---|---|
| O1 👤 | **The USB 3 gigabit Ethernet adapter**: plugged into a blue USB 3 port, and its model, so the hardware run can measure it in bridge mode | **Answered, 2026-10-10:** an ASIX AX88179B on the USB 3 bus, plugged in; the hardware run is done (README, "Measured on the reference build") |
| O2 👤 | **The GitHub account `wanpire` exists** (created 2023, one repository, no description). Not a project, not on PyPI or npm; the PyPI name `wanpire` is free | Keep the name; optionally reserve `wanpire` on PyPI before the first release. Recommendation: keep |
| O3 👤 | **Ask RIPE NCC and WonderNetwork for permission to ship derived figures?** Their data may be read, not shipped (RIPE Atlas: commercial use needs prior permission, and MIT allows commercial use; WonderNetwork: "please reach out") | Not asking: they calibrate the formula only, which is what the design does now. Asking: a much wider shipped table. Recommendation: not now; the CC BY and CC0 sources suffice to start. **Answered, 2026-10-10: not now, as recommended** |
| O4 👤 | **Ookla Open Data is CC BY-NC-SA 4.0**: redistributable, but not under MIT | Read only (the design's choice); or ship it as a separate, separately licensed data package. Recommendation: read only. **Answered, 2026-10-10: read only, as recommended** |
| O5 👤 | **Pick the logo** from the three proposals in `docs/logo-proposals/` (A: the case biting a cable; B: the same with a cape's collar; C: a minimal head biting a plug), or ask for changes | Recommendation: B for the README and the article, its favicon for the page; A if the collar is too much. **2026-10-10: the owner sent a sketch; drawn as D, the emblem (green board, red cape, blue ring and cables), without the sketch's maker's mark.** **Answered, 2026-10-10: D**, its favicon on the web page (tab and header mark), its full form at the top of the README |

## Assumed

| Id | Assumption | Not taken |
|---|---|---|
| A1 ⚪ | All impairment on the outbound adapter: *down* on its egress, *up* on its ingress through an `ifb`, so the inbound adapter (which may carry control) is never touched | netem on each port's egress, which the spike measured: kept as a fallback if `ifb` costs too much |
| A2 ⚪ | Jitter keeps packet order by default (netem `rate` set), and its default distribution is `normal`; reordering is an explicit setting | netem's defaults (uniform jitter that reorders most packets) |
| A3 ⚪ | Burst loss uses the Gilbert-Elliott model, from a mean loss and a mean burst length; netem's loss correlation is never used (the spike found it broken) | netem's `loss p corr` |
| A4 ⚪ | Netem's queue is sized as 1.5 × (delay + 3 × jitter) × rate / 1,500 bytes, at least 1,000, capped at 64 MB per direction | netem's fixed default of 1,000 packets |
| A5 ⚪ | Bandwidth through netem's `rate` first; `tbf` compared in B2 | `tbf`/`htb` from the start |
| A6 ⚪ | How two endpoints combine: delays add (path split evenly), jitters add in quadrature, losses compound, bandwidth is the narrower end | Jitters adding linearly; a per-pair table only |
| A7 ⚪ | Formula: `2 × great-circle × route factor / 200 km per ms + router term`, route factor 1.6 to start, fitted per region pair | A single global factor |
| A8 ⚪ | The shipped city-pair table starts from a CC BY 4.0 cloud-region table; naming that provider as a *data source* is allowed (the "no provider named" rule is about channels in presets, and CC BY requires the attribution) | Leaving that source out to avoid the name |
| A9 ⚪ | The MCP tools call the REST API over HTTP, even in process, so one token check and one broker apply | MCP tools calling the core directly |
| A10 ⚪ | The server runs as root under systemd, listening on the control address only, behind one bearer token generated at install | An unprivileged user with `CAP_NET_ADMIN` (later, perhaps) |
| A11 ⚪ | The skill lives at `skills/wanpire/SKILL.md` (the plan said `skills/piwan/`, the project's earlier name) | `skills/piwan/` |
| A12 ⚪ | The project is planned with OpenSpec's default `spec-driven` schema; decisions are recorded in each change's `design.md` (Decisions, with what was not taken) rather than in separate ADR files | A separate ADR directory |
| A13 ⚪ | The spike's scripts are kept in the repository, in the design change's `spikes/scripts/`, so anyone can repeat the measurements | Leaving them out as throwaway code |
| A14 ⚪ | The on-board port's test, before the second wired port exists, used router-with-NAT with a port-forward to a namespace on the box, so the workstation needed no route and no inbound firewall rule | A host route on the workstation through the box (needs administrator rights there) |
| A15 ⚪ | Endpoint and channel figures are typical, with every figure's source in the file; the first set: London, Los Angeles, New York, Vancouver, Sydney, Mumbai, Tokyo | A larger first set |
| A16 ⚪ | netem is driven through `tc` argument lists, not pyroute2: pyroute2 0.9.6 cannot express a delay distribution or the Gilbert-Elliott loss model. pyroute2 stays for adapters and bridges | Patching pyroute2 first (worth contributing later); netlink by hand |
| A17 ⚪ | The dead-man is a transient systemd timer per adapter (`wanpire-deadman-<adapter>`), default lifetime 120 s, the lease's TTL | An in-process timer, which dies with the process it should guard against |
| A18 ⚪ | B2 was split: this change is the engine, its dead-man and a CLI on raw figures; presets and the city table, the two modes' setup, the broker and the server are changes of their own | One change for all of B2 |
| A19 ⚪ | The presets, the path table and the fitted factors ship inside the package (`src/wanpire/data/`), so an installed wanpire finds them | A top-level `presets/` as the design sketched (lost once installed); `/usr/share/wanpire` |
| A20 ⚪ | A path between two table sites is the mean of its two directions; a city is anchored at its nearest site within 1,000 km, corrected by the formula's difference between the city and the site | The faster direction; anchoring without the correction; a smaller radius |
| A21 ⚪ | Nine world regions for the route factor, south-east Asia apart from east Asia (it cut the Europe/east-Asia error from 19.5% to 9.4%) | Eight regions; a factor per country |
| A22 ⚪ | The formula is fitted on the shipped CC BY table only; checking it against RIPE Atlas and WonderNetwork (read only, nothing copied) is a later change | Fitting on the read-only sources now |
| A23 ⚪ | Each city's *generic* channel is M-Lab's (CC0) median download, upload and half the minimum round trip, Jan–Mar 2024; its jitter (30% of the delay) and loss (0.1%) are estimates. The other eleven kinds are wanpire's own typical figures, the same in every city, each with its reasoning in the file | Per-city figures per kind (no redistributable source splits by kind); calling M-Lab's mix *consumer-fibre* |
| A24 ⚪ | A channel carries only access figures (delay, jitter, loss, bandwidth); reordering and duplication stay raw figures | Allowing every link setting in a channel |
| A25 ⚪ | A bandwidth is a `tbf` under netem with a bounded queue (`queue_ms`, default 50 ms); netem's own `rate` stays only at the line rate to keep order under jitter. Measured: netem's rate let one TCP flow queue 718 ms; tbf held it to the queue asked at the same throughput | netem's `rate` (A5's first choice); `htb`; an AQM such as `cake` as the default |
| A26 ⚪ | In bridge mode the control adapter may not be a bridge port (moving its address onto the bridge is not built); router mode lets control and inbound share | Moving the control address to the bridge automatically |
| A27 ⚪ | A Wi-Fi outbound adapter (the Pi as an access point) is refused as not built yet | Building hostapd support now |
| A28 ⚪ | Router mode's network defaults to `10.77.0.1/24`, DHCP `.100`–`.199`, dnsmasq bound to outbound only and run as root (its lease file lives in the root-owned `/run/wanpire`); unsolicited traffic from inbound to outbound is dropped, like a home router | `192.168.x` (likelier to clash with the line's own network); dnsmasq as its own user |
| A29 ⚪ | A bridge port that carries an address is refused, never stripped; the install (B4) brings the ports up address-less | Removing the address at setup |
| A30 ⚪ | The broker hands out an opaque random ticket; `who` and `purpose` are labels shown in the status, not identities | The client choosing its own id (two agents both called "agent" would share a lease) |
| A31 ⚪ | When the link frees, the head of the queue holds the lease at once and its TTL starts then | Granting on its next poll (a second rule for the same thing) |
| A32 ⚪ | The broker's state is in memory: a server restart ends every lease, and the boot-time clear leaves the line clean | Persisting leases to disk |
| A33 ⚪ | If clearing the link fails when a lease ends, the lease still passes on and the error shows in the status; the dead-man still clears the line | Keeping the lease until the clear succeeds |
| A34 ⚪ | The broker's ticket travels in an `X-Wanpire-Ticket` header; errors are JSON `{"error": ...}` with 401, 400 (no ticket), 404 (unknown ticket), 409 (not the holder), 410 (lease ended, said once), 422 (invalid), 500 (the engine failed) | The ticket as the bearer token; a cookie |
| A35 ⚪ | A link is applied with the lease's TTL as its dead-man lifetime; each poll by the holder renews both, and a 5 s tick settles expired leases | A separate renew call for the dead-man |
| A36 ⚪ | `wanpire serve` listens on port 8080 of the control adapter's IPv4 address, one worker, plain HTTP; TLS is left to a reverse proxy | Port 80 (needs nothing more as root, but clashes more often); TLS built in |
| A37 ⚪ | The web UI's static files, `/docs` and `/openapi.json` are served without the token: they hold no data and describe a published API; every `/api/v1` route needs it | Guarding `/docs` too (it hides nothing that is not in the source) |
| A38 ⚪ | The web page keeps the token in the browser's local storage once given ("Forget token" removes it), and its lease's ticket per tab; closing or reloading the page releases its lease | A login cookie; keeping the lease across a reload |
| A39 ⚪ | The web page shows no scenarios, raw-figure form, mode or adapter mapping yet: the engine has no scenarios, and the API cannot change the mapping | Building them into this change |
| A40 ⚪ | The MCP's agent carries its ticket (returned by `wanpire_lease`, passed to every change); the MCP runs stateless with JSON answers | A ticket kept per MCP session |
| A41 ⚪ | On the box the MCP's tools reach the REST API through an HTTP transport bound to the app itself (no socket), so the token check and the broker are the REST API's whatever address the server listens on | A loopback socket (the server listens on the control address only) |
| A42 ⚪ | `/mcp` needs the box's bearer token; the SDK's DNS-rebinding check is off because the token already stops a browser without it | Keeping the check, which would refuse the box's own name and addresses |
| A43 ⚪ | The MCP offers no tool to end another client's lease: that is a person's decision, at the web page | A tool with a confirmation argument |
| A44 ⚪ | The MCP SDK is pinned to its 2.x line (`mcp>=2.3,<3`), where the server class is `MCPServer` | The 1.x line (`FastMCP`) |
| A45 ⚪ | The skill is instructions only (no scripts), assumes the MCP is registered as `wanpire`, and tells an agent that cannot wait between polls to leave the queue and say the link is busy | A polling script in the skill; holding a queue place it will not poll |
| A46 ⚪ | The install writes and validates the netplan drop-in but applies it only with `--apply-netplan` (else at the next boot): applying restarts networking, the Wi-Fi control path included | Applying by default |
| A47 ⚪ | The install never overwrites `/etc/wanpire/wanpire.json`; other roles on an installed box are refused, saying how to change them | Rewriting the file with the new roles |
| A48 ⚪ | The service runs `wanpire reset` (clear every outbound adapter) and `wanpire up` before serving, `reset` again after stopping, and restarts on failure | Clearing at boot from a separate oneshot unit |
| A49 ⚪ | The install needs Python 3.12 or later and says so on an older system (Debian 12 has 3.11) | Supporting 3.11 now |
| A50 ⚪ | The web page's palette is wanpire's own: a wine-red primary (`#a0213a` to `#6e1022`, white text 7.6:1 and 11.9:1) and a warm amber accent (`#f2b134`) for what is active, light and dark | A crimson brighter than AA allows for white text; a blue or teal primary |
| A51 ⚪ | The grey sentence under each section title is `#646c71` (5.4:1 on white), not the style rules' `#a7a9ac` (2.4:1, below WCAG AA) | The rules' grey as written |
| A52 ⚪ | The page's sections: Link (set the link, counters), Endpoints (places), Broker (holder and queue), Adapters (roles), Settings (access); from 720 px the side menu sits left, below it on top | Fewer sections; a settings page that changes the box (the API cannot yet) |
| A53 ⚪ | Three logo proposals, hand-drawn SVG in the web page's palette, each in full colour, one colour (one ink, details cut out) and a favicon redrawn on a 32 px grid | More proposals; a raster contact sheet only |
| A54 ⚪ | The bridge carries no address of any kind: IPv6 is switched off on it (`disable_ipv6`) when it is set up, which still forwards IPv6 frames. The hardware run found it taking a link-local and two global addresses from the line | A bridge reachable on the line over IPv6 (the box would be visible where it emulates a wire); `addr_gen_mode` none with `accept_ra` 0 (two settings for the same result) |
| A55 ⚪ | **The *up* direction's ceiling, about 600 Mbit/s under 150 ms each way, is left as it is and documented.** Above it the inbound port's default `fq_codel` drops what netem releases from the `ifb`; *down* reaches 760 Mbit/s clean. It is twelve times a 50 Mbit/s video stream. Not yet proven why. **The owner, 2026-10-10: leave it** | Replacing the inbound port's root qdisc while a link is applied (touches the port A1 keeps untouched, and control may share it in router mode); netem on each port's egress (A1's fallback); spreading the forwarding over cores with RPS |
