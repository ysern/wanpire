// wanpire's web page: a client of the REST API under /api/v1, and nothing more.
// The first visit makes the box's account; afterwards the page signs in with it and holds a
// session cookie it cannot read, so the browser's storage keeps no credential. The lease's
// ticket is in sessionStorage (one tab, one client), or in localStorage for a lease with a
// length, which outlives the page. Plain JS, no build step.
"use strict";

const API = "api/v1";
const STATUS_EVERY_MS = 5000;

const $ = (id) => document.getElementById(id);
const store = {
  get(area, key) { try { return window[area].getItem(key); } catch { return null; } },
  set(area, key, value) {
    try {
      if (value === null) window[area].removeItem(key); else window[area].setItem(key, value);
    } catch { /* storage blocked: the page still works for this visit */ }
  },
};

let user = null; // the account signed in, from the box
let ticket = null; // loaded on entering (loadTicket)
let kept = false; // the lease has a length and outlives this page (K7)
let holds = false;
let lineUp = true; // the line is down while a configured adapter is not plugged in
let lineReason = "";
let leaseTtl = 120;
let endpoints = [];
let statusTimer = null;
let pollTimer = null;
let previewSeq = 0;
let lastHolder = null;

// -- talking to the box ---------------------------------------------------------------------

class Refused extends Error {}

async function send(method, path, body, withTicket) {
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (withTicket && ticket) headers["X-Wanpire-Ticket"] = ticket;
  const r = await fetch(`${API}/${path}`, {
    method, headers, credentials: "same-origin",
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = r.status === 204 ? null : await r.json().catch(() => null);
  return { status: r.status, ok: r.ok, data };
}

// A call made while signed in: a refusal means the session has gone (signed out elsewhere,
// the password changed, the server restarted, or the account reset on the box).
async function call(method, path, body, withTicket) {
  const res = await send(method, path, body, withTicket);
  if (res.status === 401) { showSignIn("Your session ended. Sign in again."); throw new Refused(); }
  if (res.status === 403) { showSetup(); throw new Refused(); }
  return res;
}

function errorOf(res) {
  return (res.data && res.data.error) || `the box answered ${res.status}`;
}

// -- small helpers --------------------------------------------------------------------------

// A result is said where it belongs: under the button that caused it ("lease-message",
// "link-message", "broker-message"); the line at the top keeps errors reaching the box.
function say(text, kind, place) {
  const m = $(place || "message");
  m.textContent = text;
  m.classList.toggle("bad", kind === "bad");
}

function num(v) {
  if (v === undefined || v === null) return "-";
  return Number(v).toLocaleString("en-US", { maximumFractionDigits: 3 });
}

function duration(s) {
  s = Math.max(0, Math.round(s));
  if (s < 120) return `${s} s`;
  const m = Math.floor(s / 60);
  if (m < 120) return `${m} min ${s % 60} s`;
  return `${Math.floor(m / 60)} h ${m % 60} min`;
}

function ordinal(n) {
  const t = n % 100;
  if (t >= 11 && t <= 13) return `${n}th`;
  return n + ({ 1: "st", 2: "nd", 3: "rd" }[n % 10] || "th");
}

function option(value, text) {
  const o = document.createElement("option");
  o.value = value;
  o.textContent = text;
  return o;
}

// -- sections and pages: #section/page in the address ------------------------------------

const FIRST = {
  link: "link-set", endpoints: "endpoints-places", broker: "broker-queue",
  adapters: "adapters-list", settings: "settings-access",
};

function route() {
  let [section, sub] = location.hash.replace(/^#/, "").split("/");
  if (!FIRST[section]) section = "link";
  if (!sub || !$(`page-${sub}`) || !sub.startsWith(section)) sub = FIRST[section];
  for (const s of Object.keys(FIRST)) {
    const on = s === section;
    if (on) $(`nav-${s}`).setAttribute("aria-current", "page");
    else $(`nav-${s}`).removeAttribute("aria-current");
    $(`side-${s}`).hidden = !on;
  }
  for (const a of document.querySelectorAll(".side a")) {
    if (a.id === `sub-${sub}`) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  }
  for (const p of document.querySelectorAll(".page")) p.hidden = p.id !== `page-${sub}`;
}

window.addEventListener("hashchange", route);

function fillTable(id, rows) {
  const body = $(id).tBodies[0];
  body.replaceChildren(...rows.map((cells) => {
    const tr = document.createElement("tr");
    for (const text of cells) {
      const td = document.createElement("td");
      td.textContent = text;
      tr.append(td);
    }
    return tr;
  }));
}

async function loadAdapters() {
  const res = await call("GET", "adapters");
  if (!res.ok) return;
  fillTable("adapters-table", res.data.map((a) => [
    a.name, a.kind, a.role || "none", a.state || "---", a.speed_mbit ? `${a.speed_mbit} Mbit/s` : "---"]));
}

// -- the roles: inbound and outbound; a Wi-Fi inbound joins a network, a Wi-Fi outbound is an
// access point ----------------------------------------------------------------------------------

const ROLES = ["inbound", "outbound"];
// the fields beside a Wi-Fi adapter: the network to join inbound, the access point outbound
const FIELDS = { inbound: "net-inbound", outbound: "ap-outbound" };
let offered = []; // the adapters the box lets be picked, with their kind
let networks = { inbound: {}, outbound: {} }; // what the box has, by role then adapter
let mode = "bridge";

const isWifi = (name) => (offered.find((a) => a.name === name) || {}).kind === "wifi";

// The general Wi-Fi rules, the same as the box's: it is the authority, this only says it sooner.
function ssidProblem(ssid) {
  const bytes = new TextEncoder().encode(ssid).length;
  return bytes >= 1 && bytes <= 32 ? "" : "A network name has 1 to 32 bytes.";
}

function passProblem(pass) {
  return /^[\x20-\x7e]{8,63}$/.test(pass) ? ""
    : "A password has 8 to 63 printable ASCII characters.";
}

function joinPassProblem(pass) {
  return pass === "" || /^[0-9A-Fa-f]{64}$/.test(pass) || !passProblem(pass) ? ""
    : "A password has 8 to 63 printable ASCII characters, or 64 hexadecimal digits, or is empty for an open network.";
}

// A configured adapter the box does not have stays the drop-down's chosen entry, marked, so
// the page shows the configured truth: the line under it says what to do.
const isMissing = (role) => {
  const o = $(`role-${role}`).selectedOptions[0];
  return !!(o && o.dataset.missing);
};

function showMissing(role) {
  const name = $(`role-${role}`).value;
  $(`role-${role}-missing`).textContent = isMissing(role)
    ? `${name} is not plugged in. Plug it in, or pick another adapter and Save.` : "";
}

function showWifiFields(role) {
  const name = $(`role-${role}`).value;
  const wifi = isWifi(name);
  const f = FIELDS[role];
  $(f).hidden = !wifi;
  if (wifi) {
    const net = networks[role][name] || { ssid: "", passphrase: "" };
    $(`${f}-ssid`).value = net.ssid;
    $(`${f}-pass`).value = net.passphrase;
  }
  $(`${f}-ssid-error`).textContent = "";
  $(`${f}-pass-error`).textContent = "";
}

async function loadRoles() {
  const res = await call("GET", "roles");
  if (!res.ok) return;
  offered = res.data.offered;
  mode = res.data.mode;
  networks = { inbound: res.data.wifi_clients || {}, outbound: res.data.access_points || {} };
  const missing = res.data.missing || [];
  for (const role of ROLES) {
    const sel = $(`role-${role}`);
    const name = res.data[role];
    sel.replaceChildren(...offered.map((a) => option(a.name, `${a.name} (${a.kind})`)));
    if (missing.includes(name)) {
      const o = option(name, `${name} (not plugged in)`);
      o.dataset.missing = "1";
      sel.append(o);
    }
    sel.value = name;
    showWifiFields(role);
    showMissing(role);
  }
}

for (const role of ROLES) {
  $(`role-${role}`).addEventListener("change", () => {
    $("role-error").textContent = "";
    showWifiFields(role);
    showMissing(role);
  });
}

$("roles-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const m = $("roles-message");
  m.textContent = "";
  m.classList.remove("bad");
  const body = { inbound: $("role-inbound").value, outbound: $("role-outbound").value,
    access_points: {}, wifi_clients: {} };
  const problems = [];
  if (body.inbound === body.outbound) {
    problems.push("Inbound and outbound must differ: pick two adapters.");
  }
  if (isWifi(body.inbound) && mode === "bridge") {
    problems.push("A Wi-Fi inbound adapter joins a network as a client, which cannot be a bridge port: it works in router mode only.");
  }
  $("role-error").textContent = problems.join(" ");
  let wrong = problems.length > 0;
  for (const role of ROLES) {
    const name = body[role];
    if (isMissing(role)) { showMissing(role); wrong = true; } // the line under it says why
    if (!isWifi(name)) continue;
    const f = FIELDS[role];
    const ssid = $(`${f}-ssid`).value;
    const passphrase = $(`${f}-pass`).value;
    const pass = role === "inbound" ? joinPassProblem(passphrase) : passProblem(passphrase);
    $(`${f}-ssid-error`).textContent = ssidProblem(ssid);
    $(`${f}-pass-error`).textContent = pass;
    if (ssidProblem(ssid) || pass) wrong = true;
    body[role === "inbound" ? "wifi_clients" : "access_points"][name] = { ssid, passphrase };
  }
  if (wrong) return;
  $("roles-save").disabled = true;
  m.textContent = "Saving: the line is set up again…";
  try {
    const res = await call("PUT", "roles", body);
    if (res.ok) {
      m.textContent = "The roles are saved and the line is set up with them.";
      await loadRoles();
      await loadAdapters();
      refresh().catch(() => {}); // the line may have come up with the new roles
    } else {
      m.textContent = errorOf(res);
      m.classList.add("bad");
    }
  } finally {
    $("roles-save").disabled = false;
  }
});

// -- the first visit, signing in and out ------------------------------------------------------

const MIN_PASSWORD = 8;

function leave() {
  user = null;
  clearInterval(statusTimer);
  statusTimer = null;
  clearInterval(pollTimer); // the stored ticket stays: signing in again finds the lease
  pollTimer = null;
  ticket = null;
  holds = false;
  $("app").hidden = true;
  $("signin-wrap").hidden = false;
}

function showSetup() {
  leave();
  $("signin").hidden = true;
  $("setup").hidden = false;
  $("setup-password").value = "";
  $("setup-again").value = "";
  $("setup-error").textContent = "";
}

function showSignIn(why) {
  leave();
  $("setup").hidden = true;
  $("signin").hidden = false;
  $("password").value = "";
  $("signin-error").textContent = why || "";
}

function passwordProblem(password, again) {
  if (password.length < MIN_PASSWORD) return `A password has at least ${MIN_PASSWORD} characters.`;
  if (password !== again) return "The two passwords differ.";
  return "";
}

$("setup").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const u = $("setup-user").value.trim();
  const problem = passwordProblem($("setup-password").value, $("setup-again").value);
  if (!u) { $("setup-error").textContent = "Give a user name."; return; }
  if (problem) { $("setup-error").textContent = problem; return; }
  const res = await send("POST", "setup", { user: u, password: $("setup-password").value });
  if (res.ok) { enter(res.data.user); return; }
  if (res.status === 409) { showSignIn("The box has an account already. Sign in."); return; }
  $("setup-error").textContent = errorOf(res);
});

$("signin").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const res = await send("POST", "session",
    { user: $("user").value.trim(), password: $("password").value });
  if (res.ok) { enter(res.data.user); return; }
  if (res.status === 403) { showSetup(); return; }
  $("password").value = "";
  $("signin-error").textContent = res.status === 401
    ? "The user name or the password was refused." : errorOf(res);
});

$("signout").addEventListener("click", async () => {
  // a lease held while the page is open ends with it; one with a length is kept
  if (ticket && !kept) {
    await send("DELETE", "lease", undefined, true).catch(() => {});
    setTicket(null);
  }
  await send("DELETE", "session").catch(() => {});
  showSignIn("");
});

$("pw-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const m = $("pw-message");
  const problem = passwordProblem($("pw-new").value, $("pw-again").value);
  m.classList.toggle("bad", !!problem);
  if (problem) { m.textContent = problem; return; }
  // sent without `call`: a refused current password is an answer here, not a lost session
  const res = await send("PUT", "account/password",
    { current: $("pw-current").value, new: $("pw-new").value });
  for (const id of ["pw-current", "pw-new", "pw-again"]) $(id).value = "";
  if (res.ok) { m.textContent = "The password was changed."; return; }
  m.textContent = res.status === 401 ? "The current password was refused." : errorOf(res);
  m.classList.add("bad");
});

// a password field's eye shows what is typed while it is pressed
for (const eye of document.querySelectorAll("button.eye")) {
  eye.addEventListener("click", () => {
    const input = $(eye.getAttribute("aria-controls"));
    const shown = input.type === "text";
    input.type = shown ? "password" : "text";
    eye.setAttribute("aria-pressed", String(!shown));
    eye.setAttribute("aria-label", shown ? "Show the password" : "Hide the password");
  });
}

async function enter(who) {
  user = who;
  $("signin-wrap").hidden = true;
  $("app").hidden = false;
  $("me").textContent = user;
  route();
  try {
    await refresh();
    await loadEndpoints();
    await loadAdapters();
    await loadRoles();
  } catch (e) {
    if (!(e instanceof Refused)) say(`Cannot reach the box: ${e.message}`, "bad");
    return;
  }
  clearInterval(statusTimer);
  statusTimer = setInterval(() => refresh().catch(() => {}), STATUS_EVERY_MS);
  loadTicket();
  if (ticket) await pollOnce();
  showLease();
}

// -- the status, the counters and who uses the box -------------------------------------------

// The band says what the box does to the line, whoever did it: calm with no link, the
// wine red with one (U7).
function bandText(applied, described) {
  if (!applied) return "no link";
  if (described && described.near) return `${described.near} <> ${described.far}`;
  if (described && described.figures) return "set by figures";
  return "link applied"; // applied without the API, e.g. with the CLI on the box
}

function showBand(applied, described) {
  $("band-link").textContent = bandText(applied, described);
  $("band").classList.toggle("live", !!applied);
}

async function refresh() {
  const res = await call("GET", "status");
  if (!res.ok) { say(errorOf(res), "bad"); return; }
  const s = res.data;
  const b = s.broker;
  leaseTtl = b.lease_ttl_s;
  $("mode").textContent = s.mode;

  lineUp = s.line.up;
  lineReason = lineUp ? "" : s.line.reason;
  $("line-state").textContent = lineUp ? "up" : `down: ${lineReason}`;
  $("line-state").className = lineUp ? "good" : "bad";
  showLine();

  const applied = s.link.down.applied || s.link.up.applied;
  $("link-state").textContent = applied ? "impaired" : "no impairment";
  $("link-state").className = applied ? "warn" : "good";
  showBand(applied, s.applied);

  lastHolder = b.holder;
  $("holder").textContent = b.holder
    ? `${b.holder.who}, ${b.holder.purpose}, for ${duration(b.holder.held_s)}`
    : "nobody";
  $("queue-count").textContent = `${b.queue.length} waiting`;

  const rows = $("queue").tBodies[0];
  rows.replaceChildren();
  const row = (place, who, purpose, since, remaining) => {
    const tr = document.createElement("tr");
    for (const text of [place, who, purpose, since, remaining]) {
      const td = document.createElement("td");
      td.textContent = text;
      tr.append(td);
    }
    rows.append(tr);
  };
  const left = (h) => {
    if (h.hold === "until-released") return "until released";
    if (h.hold === null || h.hold === undefined) return "while in use";
    return duration(h.remaining_s);
  };
  const asked = (q) => {
    if (q.hold === "until-released") return "until released";
    if (q.hold === null || q.hold === undefined) return "while in use";
    return `${duration(q.hold)} once granted`;
  };
  if (b.holder) {
    row("holds", b.holder.who, b.holder.purpose, duration(b.holder.held_s), left(b.holder));
  }
  b.queue.forEach((q, i) => row(ordinal(i + 1), q.who, q.purpose, duration(q.waiting_s), asked(q)));
  if (!rows.children.length) {   // the empty state: one pill, one muted line
    const td = el("td", "empty", "Nobody is using the box.");
    td.colSpan = 5;
    const tr = el("tr");
    tr.append(td);
    rows.append(tr);
  }

  $("end-lease").hidden = !b.holder || holds;
  if (b.last_clear_error) say(`The last clear failed: ${b.last_clear_error}`, "bad");

  for (const dir of ["down", "up"]) {
    const c = s.link[dir];
    for (const k of ["packets", "bytes", "dropped", "shaper_dropped", "queued"]) {
      $(`c-${dir}-${k}`).textContent = c.applied ? num(c[k] || 0) : "-";
    }
  }
}

// -- the Endpoints page: places that open to their channels (U9), read-only ------------------

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

function fillPlaces(list) {
  const box = $("places");
  box.replaceChildren(...list.map((e) => {
    const d = el("details", "place");
    d.dataset.id = e.id;
    const s = el("summary");
    const n = Object.keys(e.channels).length;
    s.append(el("span", "place-name", e.name), el("span", "place-facts",
      `${e.country} · ${n} channel${n === 1 ? "" : "s"} · default ${e.default_channel.replaceAll("-", " ")}`));
    d.append(s);
    d.addEventListener("toggle", () => { if (d.open && !d.dataset.loaded) loadPlace(d, e); });
    return d;
  }));
}

function figure(dir, key) {
  const v = dir[key];
  if (key === "rate_mbit") return v ? num(v) : "no cap";
  if (key === "loss_pct" && dir.burst_loss_pct) {
    return `${num(dir.burst_loss_pct)} (bursts of ${num(dir.burst_length)})`;
  }
  return num(v || 0);
}

async function loadPlace(d, e) {
  d.dataset.loaded = "1";
  const res = await call("GET", `endpoints/${encodeURIComponent(e.id)}`);
  if (!res.ok) { d.append(el("p", "bad", errorOf(res))); delete d.dataset.loaded; return; }
  const doc = res.data;
  const ids = Object.keys(doc.channels);
  ids.sort((a, b) => (b === doc.default_channel) - (a === doc.default_channel));
  const list = el("div", "channels");
  for (const id of ids) {
    const c = doc.channels[id];
    const card = el("div", "channel");
    const head = el("div", "channel-head");
    head.append(el("span", "channel-name", id.replaceAll("-", " ")));
    if (id === doc.default_channel) head.append(el("span", "tag", "default"));
    card.append(head);
    if (c.description) card.append(el("p", "channel-desc", c.description));
    const t = el("table", "figures");
    const hr = el("tr");
    hr.append(el("th", "", ""), el("th", "", "Down"), el("th", "", "Up"));
    t.append(el("thead"));
    t.tHead.append(hr);
    const body = el("tbody");
    for (const [label, key] of [["Delay, ms", "delay_ms"], ["Jitter, ms", "jitter_ms"],
      ["Loss, %", "loss_pct"], ["Bandwidth, Mbit/s", "rate_mbit"]]) {
      const tr = el("tr");
      tr.append(el("th", "", label), el("td", "", figure(c.down || {}, key)),
        el("td", "", figure(c.up || {}, key)));
      body.append(tr);
    }
    t.append(body);
    card.append(t);
    list.append(card);
  }
  d.append(list);
}

// -- endpoints, channels and the preview ----------------------------------------------------

async function loadEndpoints() {
  const res = await call("GET", "endpoints");
  if (!res.ok) { say(errorOf(res), "bad"); return; }
  endpoints = res.data;
  fillPlaces(endpoints);
  for (const [end, fallback] of [["near", 0], ["far", 1]]) {
    const sel = $(`${end}-endpoint`);
    const keep = sel.value;
    sel.replaceChildren(...endpoints.map((e) => option(e.id, e.name)));
    const wanted = keep || (end === "far" && endpoints.some((e) => e.id === "los-angeles")
      ? "los-angeles" : endpoints[Math.min(fallback, endpoints.length - 1)].id);
    sel.value = wanted;
    fillChannels(end);
  }
  await preview();
}

function fillChannels(end) {
  const e = endpoints.find((x) => x.id === $(`${end}-endpoint`).value);
  const sel = $(`${end}-channel`);
  if (!e) { sel.replaceChildren(); return; }
  sel.replaceChildren(...Object.entries(e.channels).map(
    ([id, c]) => {
      const o = option(id, id.replaceAll("-", " "));
      o.title = c.description || "";
      return o;
    }));
  sel.value = e.default_channel;
}

function ends() {
  return {
    near: `${$("near-endpoint").value}:${$("near-channel").value}`,
    far: `${$("far-endpoint").value}:${$("far-channel").value}`,
  };
}

function lossText(d) {
  if (d.burst_loss_pct) return `${num(d.burst_loss_pct)} (bursts of ${num(d.burst_length)})`;
  return num(d.loss_pct || 0);
}

async function preview() {
  const seq = ++previewSeq;
  const res = await call("POST", "preview", ends());
  if (seq !== previewSeq) return; // a newer choice is on its way
  if (!res.ok) { say(errorOf(res), "bad", "link-message"); return; }
  const { link, account } = res.data;
  for (const dir of ["down", "up"]) {
    const d = link[dir];
    $(`${dir}-delay_ms`).textContent = num(d.delay_ms || 0);
    $(`${dir}-jitter_ms`).textContent = num(d.jitter_ms || 0);
    $(`${dir}-loss`).textContent = lossText(d);
    $(`${dir}-rate_mbit`).textContent = d.rate_mbit ? num(d.rate_mbit) : "no cap";
  }
  const p = account.path;
  $("path").textContent = `Path round trip ${num(p.rtt_ms)} ms, from the ${p.origin}: ${p.detail}.`
    + (p.attribution ? ` ${p.attribution}` : "");
}

for (const end of ["near", "far"]) {
  $(`${end}-endpoint`).addEventListener("change", () => { fillChannels(end); preview(); });
  $(`${end}-channel`).addEventListener("change", preview);
}

// -- the lease ------------------------------------------------------------------------------

// A lease held while this page is open lives in sessionStorage (one tab, one client) and is
// released when the page closes. A lease with a length (K7) is kept across closing: its ticket
// is in localStorage, so this browser finds it again.
function startPolling() {
  clearInterval(pollTimer);
  pollTimer = null;
  if (ticket) pollTimer = setInterval(() => pollOnce().catch(() => {}), (leaseTtl / 3) * 1000);
}

function setTicket(t, keep) {
  ticket = t;
  kept = !!(t && keep);
  store.set("sessionStorage", "wanpire.ticket", t && !keep ? t : null);
  store.set("localStorage", "wanpire.kept-ticket", t && keep ? t : null);
  startPolling();
}

function loadTicket() {
  const k = store.get("localStorage", "wanpire.kept-ticket");
  ticket = k || store.get("sessionStorage", "wanpire.ticket");
  kept = !!k;
  startPolling();
}

// Apply is offered only with the lease held and the line up. While the line is down the Link
// section says so, muted: it is the box's state, not a mistake of the person's.
function showLine() {
  $("apply").disabled = !holds || !lineUp;
  const m = $("link-message");
  if (!lineUp) {
    say(`The line is down: ${lineReason}. Apply waits for it; the Adapters page sets the roles.`,
      "", "link-message");
    m.dataset.line = "1";
  } else if (m.dataset.line) {
    delete m.dataset.line;
    say("", "", "link-message");
  }
}

function showLease(text) {
  if (text) $("lease-state").textContent = text;
  else if (!ticket) $("lease-state").textContent = "You do not hold the link.";
  $("ask").disabled = !!ticket;
  showLine();
  $("clear").disabled = !holds;
  $("release").disabled = !ticket;
  $("end-lease").hidden = !lastHolder || holds;
}

function answered(a) {
  const had = holds;
  holds = a.holds;
  let held = "You hold the link. This page keeps it while it stays open.";
  if (kept) {
    held = a.expires_in_s === null || a.expires_in_s === undefined
      ? "You hold the link until you release it, whether this page is open or not."
      : `You hold the link for another ${duration(a.expires_in_s)}, whether this page is open or not.`;
  }
  showLease(holds ? held
    : `You are ${ordinal(a.position)} in the queue; waiting while this page is open.`);
  if (holds && !had) refresh().catch(() => {});
}

function ended(why) {
  setTicket(null);
  holds = false;
  showLease(`Your lease ended: ${why}`);
  refresh().catch(() => {});
}

async function pollOnce() {
  if (!ticket) return;
  const res = await call("POST", "lease/poll", undefined, true);
  if (res.ok) answered(res.data);
  else if (res.status === 410 || res.status === 404) ended(errorOf(res));
  else say(errorOf(res), "bad", "lease-message");
}

$("ask").addEventListener("click", async () => {
  const purpose = $("purpose").value.trim() || "testing from the web page";
  const choice = $("hold").value;
  const body = { who: `web: ${user}`, purpose };
  if (choice !== "page") body.hold = choice === "until-released" ? choice : Number(choice);
  const res = await call("POST", "lease", body);
  if (!res.ok) { say(errorOf(res), "bad", "lease-message"); return; }
  setTicket(res.data.ticket, choice !== "page");
  answered(res.data);
  say("", "", "lease-message");
});

async function change(method, body, done) {
  const res = await call(method, "link", body, true);
  if (res.ok) { say(done, "", "link-message"); refresh().catch(() => {}); return; }
  if (res.status === 410 || res.status === 404) ended(errorOf(res));
  else say(errorOf(res), "bad", "link-message");
}

$("apply").addEventListener("click", () => {
  const e = ends();
  change("PUT", e, "Applied."); // the band says which link
});

$("clear").addEventListener("click", () => change("DELETE", undefined, "Cleared: no impairment."));

$("release").addEventListener("click", async () => {
  if (ticket) await call("DELETE", "lease", undefined, true);
  setTicket(null);
  holds = false;
  showLease();
  say("Released.", "", "lease-message");
  say("", "", "link-message");
  refresh().catch(() => {});
});

window.addEventListener("pagehide", () => {
  if (!ticket || !user || kept) return; // a lease with a length outlives the page
  // a closed page gives the link back; a browser that dies is covered by the TTL
  fetch(`${API}/lease`, {
    method: "DELETE", keepalive: true, credentials: "same-origin",
    headers: { "X-Wanpire-Ticket": ticket },
  });
  store.set("sessionStorage", "wanpire.ticket", null);
});

// -- ending another's lease -----------------------------------------------------------------

// The page's own dialog asks for a confirmation and a reason; cancelling does nothing.
const endDialog = $("end-dialog");

$("end-lease").addEventListener("click", () => {
  if (!lastHolder) return;
  $("end-who").textContent = `${lastHolder.who} (${lastHolder.purpose})`;
  $("end-reason").value = "";
  endDialog.showModal();
});

for (const id of ["end-cancel", "end-close"]) {
  $(id).addEventListener("click", () => endDialog.close());
}

$("end-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  endDialog.close();
  const who = lastHolder ? lastHolder.who : "the holder";
  const res = await call("DELETE", "lease/holder",
    { reason: $("end-reason").value.trim() || "ended by hand at the web page" });
  if (res.ok) say(`Ended the lease of ${who}.`, "", "broker-message");
  else say(errorOf(res), "bad", "broker-message");
  refresh().catch(() => {});
});

// -- start ----------------------------------------------------------------------------------

async function start() {
  try {
    const setup = await send("GET", "setup");
    if (setup.ok && setup.data.needed) { showSetup(); return; }
    const session = await send("GET", "session");
    if (session.ok) enter(session.data.user); else showSignIn("");
  } catch (e) {
    showSignIn(`Cannot reach the box: ${e.message}`);
  }
}

start();
