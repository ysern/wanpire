// wanpire's web page: a client of the REST API under /api/v1, and nothing more.
// The token is kept in localStorage (asked once), the lease's ticket in sessionStorage
// (one tab, one client). Plain JS, no build step.
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

let token = store.get("localStorage", "wanpire.token");
let name = store.get("localStorage", "wanpire.name") || "";
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

async function call(method, path, body, withTicket) {
  const headers = { Authorization: `Bearer ${token}` };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (withTicket && ticket) headers["X-Wanpire-Ticket"] = ticket;
  const r = await fetch(`${API}/${path}`, {
    method, headers, body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (r.status === 401) {
    signOut("The token was refused. Give it again.");
    throw new Refused();
  }
  const data = r.status === 204 ? null : await r.json().catch(() => null);
  return { status: r.status, ok: r.ok, data };
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

// -- signing in -----------------------------------------------------------------------------

function signOut(why) {
  token = null;
  store.set("localStorage", "wanpire.token", null);
  clearInterval(statusTimer);
  statusTimer = null;
  $("app").hidden = true;
  $("forget").hidden = true;
  $("signin").hidden = false;
  $("name").value = name;
  $("token").value = "";
  $("token-error").textContent = why || "";
}

async function signIn() {
  $("signin").hidden = true;
  $("app").hidden = false;
  $("forget").hidden = false;
  try {
    await refresh();
    await loadEndpoints();
  } catch (e) {
    if (!(e instanceof Refused)) say(`Cannot reach the box: ${e.message}`, "bad");
    return;
  }
  clearInterval(statusTimer);
  statusTimer = setInterval(() => refresh().catch(() => {}), STATUS_EVERY_MS);
  if (ticket) await pollOnce();
  showLease();
}

$("token-form").addEventListener("submit", (ev) => {
  ev.preventDefault();
  token = $("token").value.trim();
  name = $("name").value.trim();
  store.set("localStorage", "wanpire.token", token);
  store.set("localStorage", "wanpire.name", name);
  $("token-error").textContent = "";
  signIn();
});

$("forget").addEventListener("click", () => signOut(""));

// -- the status, the counters and who uses the box -------------------------------------------

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
  const res = await call("POST", "lease", { who: `web: ${name}`, purpose });
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
  change("PUT", e, `Applied: ${e.near} to ${e.far}.`);
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
  if (!ticket || !token) return;
  // a closed page gives the link back; a browser that dies is covered by the TTL
  fetch(`${API}/lease`, {
    method: "DELETE", keepalive: true,
    headers: { Authorization: `Bearer ${token}`, "X-Wanpire-Ticket": ticket },
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

if (token) signIn(); else signOut("");
