"use strict";
/* Jarvis dashboard. No framework: small render functions + fetch. */

// ---------- icons (hand-drawn line icons, 24x24) ----------
const ICONS = {
  grid: '<rect x="4" y="4" width="6.5" height="6.5" rx="1.5"/><rect x="13.5" y="4" width="6.5" height="6.5" rx="1.5"/><rect x="4" y="13.5" width="6.5" height="6.5" rx="1.5"/><rect x="13.5" y="13.5" width="6.5" height="6.5" rx="1.5"/>',
  chat: '<path d="M5 5h14a1.5 1.5 0 0 1 1.5 1.5v9A1.5 1.5 0 0 1 19 17H10l-4.5 3.5V17H5a1.5 1.5 0 0 1-1.5-1.5v-9A1.5 1.5 0 0 1 5 5z"/>',
  check: '<rect x="4" y="4" width="16" height="16" rx="3"/><path d="M8.5 12.2l2.4 2.4 4.8-5"/>',
  tick: '<path d="M6 12.5l4 4 8-9"/>',
  calendar: '<rect x="4" y="5.5" width="16" height="14.5" rx="2"/><path d="M4 10h16M8.5 3.5v4M15.5 3.5v4"/>',
  mail: '<rect x="3.5" y="5.5" width="17" height="13" rx="2"/><path d="M4 7l8 6 8-6"/>',
  doc: '<path d="M7 3.5h7l4 4V20a.5.5 0 0 1-.5.5h-10.5a.5.5 0 0 1-.5-.5V4a.5.5 0 0 1 .5-.5z"/><path d="M14 3.5V8h4M9 12h6M9 15.5h6"/>',
  pulse: '<path d="M3 12h4l2.5-6 5 12 2.5-6h4"/>',
  mic: '<rect x="9" y="3.5" width="6" height="11" rx="3"/><path d="M6 11.5a6 6 0 0 0 12 0M12 17.5v3"/>',
  send: '<path d="M4.5 12l15-7-5.5 15-2.5-6.5z"/><path d="M11.5 13.5l8-8.5"/>',
  plus: '<circle cx="12" cy="12" r="8.5"/><path d="M12 8v8M8 12h8"/>',
  clock: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
  play: '<path d="M8 5.5v13l10-6.5z"/>',
  user: '<circle cx="12" cy="9" r="3.5"/><path d="M5.5 19.5c1.2-3.2 3.6-4.8 6.5-4.8s5.3 1.6 6.5 4.8"/>',
  globe: '<circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17M12 3.5c2.6 2.6 2.6 14.4 0 17M12 3.5c-2.6 2.6-2.6 14.4 0 17"/>',
  chip: '<rect x="7" y="7" width="10" height="10" rx="2"/><path d="M10 3.5V7M14 3.5V7M10 17v3.5M14 17v3.5M3.5 10H7M3.5 14H7M17 10h3.5M17 14h3.5"/>',
  link: '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
  bolt: '<path d="M13 3.5L5.5 13.5h6l-1 7 7.5-10h-6z"/>',
  alert: '<path d="M12 4l9 15.5H3z"/><path d="M12 10v4M12 17v.01"/>',
  bot: '<rect x="5" y="8" width="14" height="11" rx="3"/><path d="M12 4.5V8M9.5 13v.01M14.5 13v.01M9.5 16h5"/>',
  brain: '<circle cx="12" cy="12" r="3"/><path d="M12 3.5v3M12 17.5v3M3.5 12h3M17.5 12h3M6 6l2.1 2.1M15.9 15.9L18 18M6 18l2.1-2.1M15.9 8.1L18 6"/>',
  power: '<path d="M12 3.5v8"/><path d="M7 6.5a7 7 0 1 0 10 0"/>',
  refresh: '<path d="M19.5 12a7.5 7.5 0 1 1-2.2-5.3"/><path d="M19.5 4.5v4h-4"/>',
  empty: '<circle cx="12" cy="12" r="8.5"/><path d="M8.5 12h7"/>',
};
const icon = (name) => `<svg class="i" viewBox="0 0 24 24" aria-hidden="true">${ICONS[name] || ""}</svg>`;
const hydrateIcons = (root = document) =>
  root.querySelectorAll("[data-icon]").forEach((el) => {
    if (!el.querySelector(":scope > svg.i")) el.insertAdjacentHTML("afterbegin", icon(el.dataset.icon));
  });

// ---------- helpers ----------
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
let TZ = Intl.DateTimeFormat().resolvedOptions().timeZone;
const fmt = (d, opts) => new Intl.DateTimeFormat("en-AU", { timeZone: TZ, ...opts }).format(new Date(d));
const hm = (d) => fmt(d, { hour: "2-digit", minute: "2-digit", hour12: false });
const ymd = (d) => fmt(d, { year: "numeric", month: "2-digit", day: "2-digit" }).split("/").reverse().join("-");

function store(key, value) {
  try { value === undefined ? localStorage.removeItem(key) : localStorage.setItem(key, value); } catch {}
}
function recall(key) { try { return localStorage.getItem(key); } catch { return null; } }

let TOKEN = null;
(function readToken() {
  const m = location.hash.match(/token=([^&]+)/);
  if (m) {
    TOKEN = decodeURIComponent(m[1]);
    store("jarvis_token", TOKEN);
    history.replaceState(null, "", location.pathname);
  } else TOKEN = recall("jarvis_token");
})();

class ApiError extends Error {}

async function api(path, opts = {}) {
  let res;
  try {
    res = await fetch(path, {
      ...opts,
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${TOKEN || ""}`, ...(opts.headers || {}) },
    });
  } catch {
    throw new ApiError("Can't reach Jarvis. Is `python -m jarvis.web` running?");
  }
  if (res.status === 401) { showGate(); throw new ApiError("Dashboard token required."); }
  if (!res.ok) {
    let msg = `Error ${res.status}`;
    try { const j = await res.json(); msg = typeof j.detail === "string" ? j.detail : msg; } catch {}
    throw new ApiError(msg);
  }
  return opts.raw ? res : res.json();
}

// ---------- panel states ----------
const loading = (n = 3) => Array.from({ length: n }, () => '<div class="skel"></div>').join("");
const empty = (msg, ico = "empty") => `<div class="state">${icon(ico)}<span>${esc(msg)}</span></div>`;
const failed = (msg, retry) =>
  `<div class="state error">${icon("alert")}<span>${esc(msg)}</span>` +
  (retry ? `<button class="btn" type="button" data-retry="${retry}">${icon("refresh")}Retry</button>` : "") + "</div>";

const loaders = {};
async function panel(name, el, fetcher, render, { quiet = false } = {}) {
  loaders[name] = () => panel(name, el, fetcher, render);
  if (!quiet) el.innerHTML = loading();
  try {
    el.innerHTML = render(await fetcher());
  } catch (e) {
    if (!quiet || !el.innerHTML.trim()) el.innerHTML = failed(e.message, name);
  }
}
document.addEventListener("click", (e) => {
  const r = e.target.closest("[data-retry], [data-refresh]");
  if (r) loaders[r.dataset.retry || r.dataset.refresh]?.();
});

// ---------- status ----------
let status = null;
async function loadStatus() {
  const body = $("#status-body");
  if (!status) body.innerHTML = loading(5);
  try {
    status = await api("/api/status");
  } catch (e) {
    status = null;
    $("#sys-pill").innerHTML = `SYSTEM STATUS <span class="bad"><span class="dot"></span> OFFLINE</span>`;
    body.innerHTML = failed(e.message, "status");
    return;
  }
  TZ = status.timezone;
  const s = status;
  const ok = s.bot_online && s.google_connected;
  $("#sys-pill").innerHTML = `SYSTEM STATUS <span class="${ok ? "ok" : "warn"}"><span class="dot"></span> ${ok ? "OPTIMAL" : "DEGRADED"}</span>`;
  $("#last-run").textContent = s.last_briefing_at ? `${fmt(s.last_briefing_at, { weekday: "short" })} ${hm(s.last_briefing_at)}` : "Never";
  $("#next-run").textContent = s.next_briefing_at ? `${fmt(s.next_briefing_at, { weekday: "short" })} ${hm(s.next_briefing_at)}` : "–";
  $("#owner-sub").textContent = s.owner_set ? "Telegram linked" : "Unclaimed";
  $("#f-tz").textContent = s.timezone;
  $("#f-model").textContent = s.model;
  $("#f-google").textContent = s.google_connected ? "Read-only" : "Not linked";
  $("#nav-tasks").textContent = s.open_tasks;
  const rows = [
    ["brain", "Brain", s.model, "c-cyan"],
    ["bot", "Telegram Bot", s.bot_online ? "Online" : "Offline", s.bot_online ? "c-green" : "c-red"],
    ["mail", "Gmail", s.google_connected ? "Connected · read-only" : "Not linked", s.google_connected ? "c-green" : "c-amber"],
    ["calendar", "Calendar", s.google_connected ? "Connected · read-only" : "Not linked", s.google_connected ? "c-purple" : "c-amber"],
    ["check", "Tasks", `${s.open_tasks} open`, "c-orange"],
    ["clock", "Briefing", s.next_briefing_at ? `Next ${hm(s.next_briefing_at)}` : "Not scheduled", "c-blue"],
  ];
  body.innerHTML = rows.map(([ico, t, sub, c]) =>
    `<div class="tile ${c}"><span class="ico">${icon(ico)}</span><div class="body"><div class="t">${esc(t)}</div><div class="s">${esc(sub)}</div></div></div>`).join("");
}
loaders.status = loadStatus;

// ---------- activity ----------
const KIND = {
  tool: ["bolt", "c-cyan", "TOOL"], tool_error: ["alert", "c-amber", "WARN"], error: ["alert", "c-red", "ERR"],
  briefing: ["doc", "c-purple", "BRIEF"], dashboard: ["grid", "c-blue", "WEB"], owner: ["user", "c-green", "INFO"],
  startup: ["power", "c-green", "INFO"],
};
const loadActivity = (quiet) => panel("activity", $("#activity-body"), () => api("/api/activity?limit=40"), (rows) =>
  rows.length ? rows.map((r) => {
    const [ico, c, tag] = KIND[r.kind] || ["pulse", "c-cyan", r.kind.toUpperCase()];
    return `<div class="tile ${c}"><span class="ico">${icon(ico)}</span><div class="body"><div class="t" title="${esc(r.summary)}">${esc(r.summary)}</div>` +
      `<div class="s">${esc(fmt(r.timestamp, { weekday: "short" }))} ${hm(r.timestamp)}</div></div><span class="tag">${esc(tag)}</span></div>`;
  }).join("") : empty("Nothing logged yet. Jarvis's actions will appear here.", "pulse"), { quiet });

// ---------- tasks ----------
let showDone = false;
function dueLabel(d) {
  if (!d) return "";
  const today = ymd(Date.now());
  const cls = d < today ? "overdue" : d === today ? "today" : "";
  const txt = d < today ? `Overdue · ${d}` : d === today ? "Due today" : `Due ${d}`;
  return `<span class="due ${cls}">${esc(txt)}</span>`;
}
const loadTasks = (quiet) => panel("tasks", $("#tasks-body"), () => api(`/api/tasks?status=${showDone ? "all" : "open"}`), (tasks) =>
  tasks.length ? `<div class="tasks">${tasks.map((t) => `
    <div class="task ${t.status === "done" ? "done" : ""}" data-id="${t.id}">
      <button class="check" type="button" data-toggle="${t.status === "done" ? "open" : "done"}"
        aria-label="${t.status === "done" ? "Reopen" : "Complete"} ${esc(t.title)}">${t.status === "done" ? icon("tick") : ""}</button>
      <div class="body"><div class="t" title="${esc(t.notes || t.title)}">${esc(t.title)}</div>
        <button class="due-edit" type="button" data-due="${esc(t.due_date || "")}" aria-label="Change due date">${dueLabel(t.due_date) || '<span class="due">+ due date</span>'}</button></div>
    </div>`).join("")}</div>` : empty(showDone ? "No tasks at all." : "No open tasks. Enviable.", "check"), { quiet });

$("#tasks-toggle").addEventListener("click", (e) => {
  showDone = !showDone;
  e.target.textContent = showDone ? "Hide done" : "Show done";
  loadTasks();
});
$("#task-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = e.target, btn = f.querySelector("button");
  const title = f.title.value.trim();
  if (!title) return;
  btn.disabled = true;
  try {
    await api("/api/tasks", { method: "POST", body: JSON.stringify({ title, due_date: f.due_date.value || null }) });
    f.reset();
    loadTasks(true); loadStatus(); loadActivity(true);
  } catch (err) {
    $("#tasks-body").insertAdjacentHTML("afterbegin", failed(err.message));
  } finally { btn.disabled = false; }
});
$("#tasks-body").addEventListener("click", async (e) => {
  const task = e.target.closest(".task");
  if (!task) return;
  const id = task.dataset.id;
  const toggle = e.target.closest("[data-toggle]");
  const dueBtn = e.target.closest("[data-due]");
  if (toggle) {
    toggle.disabled = true;
    await patchTask(id, { status: toggle.dataset.toggle });
  } else if (dueBtn) {
    const input = document.createElement("input");
    input.type = "date"; input.className = "due-input"; input.value = dueBtn.dataset.due;
    input.setAttribute("aria-label", "Due date");
    dueBtn.replaceWith(input);
    input.focus();
    input.showPicker?.();
    const done = () => patchTask(id, { due_date: input.value || "" });
    input.addEventListener("change", done, { once: true });
    input.addEventListener("blur", () => loadTasks(true), { once: true });
  }
});
async function patchTask(id, body) {
  try {
    await api(`/api/tasks/${id}`, { method: "PATCH", body: JSON.stringify(body) });
  } catch (err) { alert(err.message); }
  loadTasks(true); loadStatus(); loadActivity(true);
}

// ---------- calendar ----------
function relative(ev) {
  const now = Date.now(), s = +new Date(ev.start), f = +new Date(ev.end);
  if (ev.all_day) return "All day";
  if (f <= now) return "Done";
  if (s <= now) return "Now";
  const mins = Math.round((s - now) / 60000);
  return mins < 60 ? `In ${mins}m` : `In ${Math.floor(mins / 60)}h ${mins % 60}m`;
}
const loadCalendar = () => panel("calendar", $("#calendar-body"), () => api("/api/calendar/today"), ({ events, gaps }) => {
  if (!events.length) return empty("Nothing on the calendar today. A rare luxury.", "calendar");
  const now = Date.now();
  const items = events.map((e) => ({ at: +new Date(e.start), html:
    `<div class="ev ${+new Date(e.end) <= now ? "past" : ""} ${e.clash ? "clash" : ""}">
      <div class="when">${e.all_day ? "All<br>day" : hm(e.start)}</div><span class="pt"></span>
      <div class="what"><div class="name" title="${esc(e.location)}">${esc(e.summary)}</div><div class="bar"></div></div>
      <div class="rel">${e.clash ? "Clash · " : ""}${relative(e)}</div></div>` }));
  gaps.forEach((g) => items.push({ at: +new Date(g.start) + 1, html: `<div class="gap">Free ${hm(g.start)}–${hm(g.end)}</div>` }));
  return `<div class="timeline">${items.sort((a, b) => a.at - b.at).map((i) => i.html).join("")}</div>`;
});

// ---------- inbox ----------
const COLORS = ["c-cyan", "c-purple", "c-amber", "c-green", "c-orange", "c-blue"];
function senderName(s) { return (s.match(/^\s*"?([^"<]+?)"?\s*</) || [, s])[1].trim(); }
const loadInbox = () => panel("inbox", $("#inbox-body"), () => api("/api/inbox/needs-reply"), (mails) => {
  $("#inbox-count").textContent = mails.length ? `${mails.length} WAITING` : "";
  $("#nav-inbox").textContent = mails.length;
  if (!mails.length) return empty("No unread mail from real people in the last 24 hours.", "mail");
  return `<div class="inbox">${mails.map((m, i) => {
    const name = senderName(m.sender);
    return `<div class="tile mail ${COLORS[i % COLORS.length]}"><span class="avatar">${esc(name.slice(0, 1).toUpperCase())}</span>
      <div class="body"><div class="t" title="${esc(m.subject)}">${esc(m.subject)}</div><div class="from">${esc(name)}</div>
      <div class="snip">${esc(m.snippet)}</div></div></div>`;
  }).join("")}</div>`;
});

// ---------- briefing ----------
function renderBriefing(b) {
  $("#briefing-meta").textContent = b.at ? `${fmt(b.at, { weekday: "short", day: "numeric", month: "short" })} ${hm(b.at)}` : "";
  return b.text ? `<div class="briefing-text">${esc(b.text)}</div>`
    : empty("No briefing yet. Run one now, or wait for the morning.", "doc");
}
const loadBriefing = () => panel("briefing", $("#briefing-body"), () => api("/api/briefing/latest"), renderBriefing);
let briefingBusy = false;
async function runBriefing() {
  if (briefingBusy) return;
  briefingBusy = true;
  document.querySelectorAll('[data-cmd="briefing"]').forEach((b) => (b.disabled = true));
  $("#briefing-body").innerHTML = `<div class="state">${icon("doc")}<span>Composing your briefing…</span></div>${loading(2)}`;
  $("#briefing").scrollIntoView({ behavior: "smooth", block: "nearest" });
  try {
    $("#briefing-body").innerHTML = renderBriefing(await api("/api/briefing/run", { method: "POST" }));
  } catch (e) {
    $("#briefing-body").innerHTML = failed(e.message, "briefing");
  } finally {
    briefingBusy = false;
    document.querySelectorAll('[data-cmd="briefing"]').forEach((b) => (b.disabled = false));
    loadStatus(); loadActivity(true);
  }
}

// ---------- chat ----------
const TOOL_LABEL = {
  add_task: "Adding a task", list_tasks: "Checking your tasks", update_task: "Updating a task",
  complete_task: "Ticking that off", get_unread_emails: "Reading your inbox", get_calendar: "Consulting the calendar",
};
const msgs = $("#msgs"), chatPanel = $("#chat"), input = $("#chat-input");
function addMsg(who, text, extra = "") {
  chatPanel.classList.add("has-messages");
  const el = document.createElement("div");
  el.className = `msg ${who} ${extra}`;
  el.textContent = text;
  msgs.append(el);
  msgs.scrollTop = msgs.scrollHeight;
  return el;
}
let chatBusy = false;
async function sendChat(text) {
  if (chatBusy || !text.trim()) return;
  chatBusy = true;
  input.value = "";
  addMsg("user", text);
  chatPanel.classList.add("thinking");
  $("#talk-sub").textContent = "Thinking…";
  const thinking = document.createElement("div");
  thinking.className = "thinking-line";
  thinking.innerHTML = '<i></i><i></i><i></i><span>Jarvis is thinking</span>';
  msgs.append(thinking);
  msgs.scrollTop = msgs.scrollHeight;
  let bubble = null;
  try {
    const res = await api("/api/chat", { method: "POST", body: JSON.stringify({ message: text }), raw: true });
    const reader = res.body.getReader(), dec = new TextDecoder();
    let buf = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let nl;
      while ((nl = buf.indexOf("\n")) >= 0) {
        const ev = JSON.parse(buf.slice(0, nl));
        buf = buf.slice(nl + 1);
        if (ev.type === "tool") thinking.querySelector("span").textContent = `${TOOL_LABEL[ev.name] || ev.name}…`;
        else if (ev.type === "text") {
          bubble ??= addMsg("jarvis", "");
          bubble.textContent += ev.delta;
          msgs.append(thinking);
        } else if (ev.type === "done") {
          bubble ??= addMsg("jarvis", "");
          bubble.textContent = ev.text;  // final reply replaces any pre-tool chatter
        }
        msgs.scrollTop = msgs.scrollHeight;
      }
    }
  } catch (e) {
    addMsg("jarvis", e.message, "error");
  } finally {
    thinking.remove();
    chatPanel.classList.remove("thinking");
    $("#talk-sub").textContent = "At your service";
    chatBusy = false;
    loadActivity(true); loadTasks(true); loadStatus();
  }
}
$("#chat-form").addEventListener("submit", (e) => { e.preventDefault(); sendChat(input.value); });
$("#chat-clear").addEventListener("click", () => { msgs.innerHTML = ""; chatPanel.classList.remove("has-messages"); });
$("#talk").addEventListener("click", () => { $("#chat").scrollIntoView({ behavior: "smooth", block: "center" }); input.focus(); });
document.addEventListener("click", (e) => {
  const b = e.target.closest("[data-cmd], [data-ask]");
  if (!b) return;
  if (b.dataset.ask) { input.focus(); sendChat(b.dataset.ask); }
  else if (b.dataset.cmd === "briefing") runBriefing();
  else if (b.dataset.cmd === "focus-task") { $("#tasks").scrollIntoView({ behavior: "smooth", block: "nearest" }); $("#task-title").focus(); }
});

// ---------- orb (procedural SVG) ----------
function buildOrb() {
  const W = 900, H = 400, cx = 450, cy = 178, r = 140;
  let seed = 7;
  const rand = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
  const pts = [];
  for (let i = 0; i < 70; i++) {  // points on a sphere, orthographic projection
    const u = rand() * 2 - 1, th = rand() * Math.PI * 2, s = Math.sqrt(1 - u * u);
    pts.push([cx + r * s * Math.cos(th) * 0.97, cy + r * u * 0.97, s * Math.sin(th)]);
  }
  let net = "";
  pts.forEach((a, i) => pts.slice(i + 1).forEach((b) => {
    const d = Math.hypot(a[0] - b[0], a[1] - b[1]);
    if (d < 48) net += `<line x1="${a[0].toFixed(1)}" y1="${a[1].toFixed(1)}" x2="${b[0].toFixed(1)}" y2="${b[1].toFixed(1)}" stroke-opacity="${(0.18 + 0.3 * Math.max(a[2], b[2], 0)).toFixed(2)}"/>`;
  }));
  const dots = pts.map((p) => `<circle cx="${p[0].toFixed(1)}" cy="${p[1].toFixed(1)}" r="${p[2] > 0 ? 1.8 : 1.1}" fill="#bff3ff" fill-opacity="${p[2] > 0 ? 0.9 : 0.4}"/>`).join("");
  const lat = [-0.75, -0.45, -0.15, 0.15, 0.45, 0.75].map((k) =>
    `<ellipse cx="${cx}" cy="${cy + k * r}" rx="${r * Math.sqrt(1 - k * k)}" ry="${r * Math.sqrt(1 - k * k) * 0.22}"/>`).join("");
  const lon = [0.15, 0.45, 0.75, 0.95].map((k) => `<ellipse cx="${cx}" cy="${cy}" rx="${r * k}" ry="${r}"/>`).join("");
  const halo = [0, 1, 2, 3, 4, 5].map((i) =>
    `<ellipse cx="${cx}" cy="${cy + r + 14}" rx="${170 + i * 26}" ry="${16 + i * 4}" stroke-dasharray="${i % 2 ? "1 5" : "2 3"}" stroke-opacity="${0.55 - i * 0.07}"/>`).join("");
  const stars = Array.from({ length: 40 }, () => `<circle cx="${(rand() * W).toFixed(0)}" cy="${(rand() * H).toFixed(0)}" r="${(rand() * 1.1 + 0.3).toFixed(1)}" fill="#9fdcff" fill-opacity="${(rand() * 0.5 + 0.15).toFixed(2)}"/>`).join("");
  const node = (x, y, s = 1) => `<circle cx="${x}" cy="${y}" r="${9 * s}" fill="url(#nodeGlow)"/><circle cx="${x}" cy="${y}" r="${2.6 * s}" fill="#fff"/>`;
  $("#orb").innerHTML = `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet">
    <defs>
      <radialGradient id="sphere" cx="45%" cy="40%" r="65%"><stop offset="0" stop-color="#1f6fa8" stop-opacity=".55"/><stop offset=".7" stop-color="#0b3558" stop-opacity=".45"/><stop offset="1" stop-color="#2fd8ff" stop-opacity=".35"/></radialGradient>
      <radialGradient id="aura"><stop offset=".55" stop-color="#2fd8ff" stop-opacity=".18"/><stop offset="1" stop-color="#2fd8ff" stop-opacity="0"/></radialGradient>
      <radialGradient id="nodeGlow"><stop offset="0" stop-color="#e8fbff"/><stop offset=".3" stop-color="#2fd8ff" stop-opacity=".7"/><stop offset="1" stop-color="#2fd8ff" stop-opacity="0"/></radialGradient>
    </defs>
    <g>${stars}</g>
    <g fill="none" stroke="#2fd8ff" stroke-width="1">${halo}</g>
    <circle cx="${cx}" cy="${cy}" r="${r * 1.45}" fill="url(#aura)"/>
    <g class="spin slow" fill="none" stroke="#5cc8f5" stroke-opacity=".35" stroke-width="1">
      <ellipse cx="${cx}" cy="${cy}" rx="350" ry="90" transform="rotate(-7 ${cx} ${cy})"/>
    </g>
    <g fill="none" stroke="#5cc8f5" stroke-opacity=".45" stroke-width="1.1">
      <ellipse cx="${cx}" cy="${cy}" rx="300" ry="62" transform="rotate(-4 ${cx} ${cy})"/>
      <ellipse cx="${cx}" cy="${cy}" rx="235" ry="125" transform="rotate(14 ${cx} ${cy})" stroke-opacity=".3"/>
    </g>
    <g class="orb-core">
      <circle cx="${cx}" cy="${cy}" r="${r}" fill="url(#sphere)" stroke="#6fe3ff" stroke-width="2" stroke-opacity=".85"/>
      <g fill="none" stroke="#5cc8f5" stroke-opacity=".28" stroke-width=".8">${lat}${lon}</g>
      <g stroke="#9fe6ff" stroke-width=".7">${net}</g>${dots}
    </g>
    <g class="twinkle">${node(cx - 300, cy + 8, 1.3)}${node(cx + 288, cy + 16, 1.5)}${node(cx - 120, cy - 118)}${node(cx - 245, cy + 98, 1.1)}</g>
    <text class="orb-title" x="${cx + 10}" y="${cy + 12}" text-anchor="middle">JARVIS</text>
    <text class="orb-sub" x="${cx + 5}" y="${cy + 62}" text-anchor="middle">AI CORE</text>
    <text class="orb-ver" x="${cx}" y="${cy + 92}" text-anchor="middle">v0.1</text>
  </svg>`;
}

function buildWaves() {
  const hs = [3, 6, 4, 9, 14, 8, 18, 11, 22, 15, 9, 19, 12, 7, 15, 10, 6, 9, 5, 3];
  $("#wave-l").innerHTML = hs.map((h, i) =>
    `<rect x="${i * 3.2}" y="${13 - h / 2}" width="1.8" height="${h}" rx=".9" fill="currentColor" opacity="${0.4 + (i / hs.length) * 0.6}"/>`).join("");
  $("#side-wave").innerHTML = Array.from({ length: 40 }, (_, i) => `<span style="height:${i < 20 ? 6 + ((i * 7) % 20) : 3}px"></span>`).join("");
}

// ---------- clock / nav / gate ----------
function tick() {
  const now = Date.now();
  $("#date").textContent = fmt(now, { weekday: "long", day: "numeric", month: "long", year: "numeric" });
  $("#time").textContent = fmt(now, { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: true }).replace(/\s?(am|pm)/i, " $1").toLowerCase();
}
document.querySelectorAll("#nav a").forEach((a) => a.addEventListener("click", () => {
  document.querySelectorAll("#nav a").forEach((x) => x.classList.toggle("active", x === a));
}));
function showGate() { $("#gate").hidden = false; $("#gate-input").focus(); }
$("#gate-form").addEventListener("submit", (e) => {
  e.preventDefault();
  TOKEN = $("#gate-input").value.trim();
  store("jarvis_token", TOKEN);
  $("#gate").hidden = true;
  boot();
});

function boot() {
  // Everything renders dates in Jarvis's timezone, which comes from /api/status.
  loadStatus().then(() => { tick(); loadActivity(); loadTasks(); loadBriefing(); loadCalendar(); loadInbox(); });
}

hydrateIcons();
buildOrb();
buildWaves();
tick();
setInterval(tick, 1000);
if (!TOKEN) showGate(); else boot();
setInterval(() => { if (!document.hidden) { loadStatus(); loadActivity(true); } }, 30000);
setInterval(() => { if (!document.hidden) { loadCalendar(); loadInbox(); } }, 5 * 60000);
