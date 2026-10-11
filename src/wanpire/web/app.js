// wanpire's web page: a client of the REST API under /api/v1, and nothing more.
// The first visit makes the box's account; afterwards the page signs in with it and holds a
// session cookie it cannot read, so the browser's storage keeps no credential. The lease's
// ticket is in sessionStorage (one tab, one client). Plain JS, no build step.
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
let ticket = store.get("sessionStorage", "wanpire.ticket");
let holds = false;
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

function say(text, kind) {
  const m = $("message");
  m.textContent = text;
  m.className = kind || "";
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
    a.name, a.kind, a.role || "none", a.state || "-", a.speed_mbit ? `${a.speed_mbit} Mbit/s` : "-"]));
}

// -- the first visit, signing in and out ------------------------------------------------------

const MIN_PASSWORD = 8;

function leave() {
  user = null;
  clearInterval(statusTimer);
  statusTimer = null;
  setTicket(null);
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
  if (ticket) await send("DELETE", "lease", undefined, true).catch(() => {});
  await send("DELETE", "session").catch(() => {});
  showSignIn("");
});

$("pw-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const m = $("pw-message");
  const problem = passwordProblem($("pw-new").value, $("pw-again").value);
  if (problem) { m.textContent = problem; m.className = "help bad"; return; }
  // sent without `call`: a refused current password is an answer here, not a lost session
  const res = await send("PUT", "account/password",
    { current: $("pw-current").value, new: $("pw-new").value });
  for (const id of ["pw-current", "pw-new", "pw-again"]) $(id).value = "";
  if (res.ok) { m.textContent = "The password was changed."; m.className = "help good"; return; }
  m.textContent = res.status === 401 ? "The current password was refused." : errorOf(res);
  m.className = "help bad";
});

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
  } catch (e) {
    if (!(e instanceof Refused)) say(`Cannot reach the box: ${e.message}`, "bad");
    return;
  }
  clearInterval(statusTimer);
  statusTimer = setInterval(() => refresh().catch(() => {}), STATUS_EVERY_MS);
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
  const row = (place, who, purpose, since) => {
    const tr = document.createElement("tr");
    for (const text of [place, who, purpose, since]) {
      const td = document.createElement("td");
      td.textContent = text;
      tr.append(td);
    }
    rows.append(tr);
  };
  if (b.holder) row("holds", b.holder.who, b.holder.purpose, duration(b.holder.held_s));
  b.queue.forEach((q, i) => row(ordinal(i + 1), q.who, q.purpose, duration(q.waiting_s)));
  if (!rows.children.length) row("", "nobody", "", "");

  $("end-lease").hidden = !b.holder || holds;
  if (b.last_clear_error) say(`The last clear failed: ${b.last_clear_error}`, "bad");

  for (const dir of ["down", "up"]) {
    const c = s.link[dir];
    for (const k of ["packets", "bytes", "dropped", "shaper_dropped", "queued"]) {
      $(`c-${dir}-${k}`).textContent = c.applied ? num(c[k] || 0) : "-";
    }
  }
}

// -- endpoints, channels and the preview ----------------------------------------------------

async function loadEndpoints() {
  const res = await call("GET", "endpoints");
  if (!res.ok) { say(errorOf(res), "bad"); return; }
  endpoints = res.data;
  fillTable("endpoints-table", endpoints.map((e) => [
    e.name, e.country, e.default_channel.replaceAll("-", " "),
    Object.keys(e.channels).length + " kinds"]));
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
  if (!res.ok) { say(errorOf(res), "bad"); return; }
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

function setTicket(t) {
  ticket = t;
  store.set("sessionStorage", "wanpire.ticket", t);
  clearInterval(pollTimer);
  pollTimer = null;
  if (t) pollTimer = setInterval(() => pollOnce().catch(() => {}), (leaseTtl / 3) * 1000);
}

function showLease(text) {
  if (text) $("lease-state").textContent = text;
  else if (!ticket) $("lease-state").textContent = "You do not hold the link.";
  $("ask").disabled = !!ticket;
  $("apply").disabled = !holds;
  $("clear").disabled = !holds;
  $("release").disabled = !ticket;
  $("end-lease").hidden = !lastHolder || holds;
}

function answered(a) {
  const had = holds;
  holds = a.holds;
  showLease(holds
    ? "You hold the link. This page keeps it while it stays open."
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
  else say(errorOf(res), "bad");
}

$("ask").addEventListener("click", async () => {
  const purpose = $("purpose").value.trim() || "testing from the web page";
  const res = await call("POST", "lease", { who: `web: ${user}`, purpose });
  if (!res.ok) { say(errorOf(res), "bad"); return; }
  setTicket(res.data.ticket);
  answered(res.data);
  say("");
});

async function change(method, body, done) {
  const res = await call(method, "link", body, true);
  if (res.ok) { say(done, "good"); refresh().catch(() => {}); return; }
  if (res.status === 410 || res.status === 404) ended(errorOf(res));
  else say(errorOf(res), "bad");
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
  say("Released.");
  refresh().catch(() => {});
});

window.addEventListener("pagehide", () => {
  if (!ticket || !user) return;
  // a closed page gives the link back; a browser that dies is covered by the TTL
  fetch(`${API}/lease`, {
    method: "DELETE", keepalive: true, credentials: "same-origin",
    headers: { "X-Wanpire-Ticket": ticket },
  });
  store.set("sessionStorage", "wanpire.ticket", null);
});

// -- ending another's lease -----------------------------------------------------------------

$("end-lease").addEventListener("click", async () => {
  if (!lastHolder) return;
  const reason = window.prompt(
    `End the lease of ${lastHolder.who} (${lastHolder.purpose})? Its link is cleared, `
    + "and it is told why on its next call. Reason:", "");
  if (reason === null) return; // cancelled
  const res = await call("DELETE", "lease/holder",
    { reason: reason.trim() || "ended by hand at the web page" });
  if (res.ok) say(`Ended the lease of ${lastHolder.who}.`);
  else say(errorOf(res), "bad");
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
