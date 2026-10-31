"use strict";
const $ = (id) => document.getElementById(id);
const state = { sid: null, last: 0, busy: false, seen: new Set(), eventTimer: null };

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}
function scrollDown(node) { node.scrollTop = node.scrollHeight; }
function pretty(v) { return JSON.stringify(v, null, 2); }
function compact(v) { const s = JSON.stringify(v); return s.length > 140 ? s.slice(0, 137) + "…" : s; }

async function api(path, method, body) {
  const r = await fetch(path, {
    method: method || "GET",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  let data = null;
  try { data = await r.json(); } catch (_) { /* empty body */ }
  if (!r.ok) {
    const err = new Error((data && (data.message || data.error)) || "HTTP " + r.status);
    err.status = r.status;
    throw err;
  }
  return data;
}

/* ---------- header ---------- */
async function loadClients() {
  const sel = $("client");
  sel.textContent = "";
  try {
    const d = await api("/tenants/" + $("tenant").value);
    d.clients.forEach((c) => {
      const o = el("option", "", c.name + " (" + c.id + ")");
      o.value = c.id;
      sel.appendChild(o);
    });
    const pref = d.clients.find((c) => c.id === "olena");
    if (pref) sel.value = pref.id;
  } catch (e) { addChat("assistant", "Не вдалося завантажити клієнтів: " + e.message); }
}

async function newSession() {
  clearInterval(state.eventTimer);
  $("chat").textContent = "";
  $("feed").textContent = "";
  state.seen.clear();
  state.last = 0;
  try {
    const d = await api("/sessions", "POST", {
      tenant_id: $("tenant").value, client_id: $("client").value, channel: "chat",
    });
    state.sid = d.session_id;
    $("session-id").textContent = "сесія " + d.session_id;
    setBusy(false);
    state.eventTimer = setInterval(pollEvents, 700);
    $("text").focus();
  } catch (e) {
    state.sid = null;
    addChat("assistant", "Не вдалося створити сесію: " + e.message);
  }
  refreshSide();
}

/* ---------- chat ---------- */
function setBusy(b) {
  state.busy = b;
  const off = b || !state.sid;
  $("text").disabled = off;
  $("send").disabled = off;
  $("typing").hidden = !b;
  document.querySelectorAll(".card .opts button").forEach((x) => { x.disabled = off; });
}

function addChat(role, text) {
  const m = el("div", "msg " + role, text);
  $("chat").appendChild(m);
  scrollDown($("chat"));
}

async function send(text) {
  if (!state.sid || state.busy || !text.trim()) return;
  setBusy(true);
  $("text").value = "";
  try {
    await api("/sessions/" + state.sid + "/messages", "POST", { text });
  } catch (e) {
    addChat("assistant", e.status === 409 ? "Агент ще обробляє попереднє повідомлення." : "Помилка: " + e.message);
  } finally {
    setBusy(false);
    pollEvents();
    $("text").focus();
  }
}

function renderCard(c) {
  const card = el("div", "card");
  if (c.type === "slots") {
    card.appendChild(el("h4", "", c.title || "Доступні слоти"));
    const opts = el("div", "opts");
    (c.options || []).forEach((o) => {
      const b = el("button", "ghost", o.label || o.start + " — " + o.staff_name);
      b.addEventListener("click", () => send("Обираю слот " + o.start + " (" + o.staff_name + ")"));
      opts.appendChild(b);
    });
    card.appendChild(opts);
  } else if (c.type === "booking_summary") {
    card.appendChild(el("h4", "", "Запис " + (c.booking_id || "")));
    const t = el("table");
    [["Послуга", c.service], ["Майстер", c.staff], ["Початок", c.start],
     ["Передоплата", c.prepayment], ["Статус", c.status]].forEach(([k, v]) => {
      const tr = el("tr");
      tr.appendChild(el("td", "", k));
      tr.appendChild(el("td", "", v === undefined || v === null ? "—" : String(v)));
      t.appendChild(tr);
    });
    card.appendChild(t);
    if (c.timeline && c.timeline.length) {
      const tl = el("div", "timeline");
      c.timeline.forEach((x) => tl.appendChild(el("div", "", x.ts + " — " + x.event)));
      card.appendChild(tl);
    }
  } else if (c.type === "decision") {
    card.appendChild(el("h4", "", c.title || "Рішення"));
    card.appendChild(el("div", "outcome", c.outcome || ""));
    [["Міркування", c.reasoning], ["Виконані дії", c.actions_taken]].forEach(([h, items]) => {
      if (!items || !items.length) return;
      card.appendChild(el("div", "muted", h));
      const ul = el("ul");
      items.forEach((i) => ul.appendChild(el("li", "", i)));
      card.appendChild(ul);
    });
  } else {
    card.appendChild(el("pre", "", pretty(c)));
  }
  $("chat").appendChild(card);
  scrollDown($("chat"));
}

/* ---------- events ---------- */
function badge(decision) {
  return el("span", "badge b-" + decision, decision);
}

function renderFeed(ev) {
  const p = ev.payload || {};
  const row = el("div", "ev " + ev.type);
  switch (ev.type) {
    case "thinking": row.textContent = "💭 " + (p.text || p.message || pretty(p)); break;
    case "tool_call":
      row.appendChild(el("b", "", p.name + "(" + compact(p.args || {}) + ") → "));
      row.appendChild(badge(p.decision || "read"));
      break;
    case "tool_result": {
      const d = el("details");
      d.appendChild(el("summary", "", "результат: " + p.name));
      d.appendChild(el("pre", "", pretty(p.result)));
      row.appendChild(d);
      break;
    }
    case "error": row.textContent = "⚠ " + (p.message || pretty(p)); break;
    case "approval_created": row.textContent = "🕓 Запит на апрув: " + (p.tool || p.id || ""); break;
    case "approval_decided":
      row.textContent = (p.approve === false || p.status === "rejected" ? "✖ Відхилено" : "✔ Схвалено") +
        (p.by ? " (" + p.by + ")" : "");
      break;
    case "user_message": row.textContent = "👤 " + (p.text || ""); break;
    case "assistant_message": row.textContent = "🤖 " + (p.text || ""); break;
    case "card": row.textContent = "🃏 картка: " + (p.type || ""); break;
    default: row.textContent = ev.type + " " + compact(p);
  }
  $("feed").appendChild(row);
}

function handleEvent(ev) {
  const p = ev.payload || {};
  if (ev.type === "user_message") addChat("user", p.text || "");
  else if (ev.type === "assistant_message") addChat("assistant", p.text || "");
  else if (ev.type === "card") renderCard(p);
  renderFeed(ev);
}

let polling = false;
async function pollEvents() {
  if (!state.sid || polling) return;
  polling = true;
  const sid = state.sid;
  try {
    const d = await api("/sessions/" + sid + "/events?after=" + state.last);
    if (sid !== state.sid) return;
    d.events.forEach((ev) => {
      if (state.seen.has(ev.id)) return;
      state.seen.add(ev.id);
      state.last = Math.max(state.last, ev.id);
      handleEvent(ev);
    });
    if (d.events.length) scrollDown($("feed"));
  } catch (_) { /* transient; retry on next tick */ }
  finally { polling = false; }
}

/* ---------- approvals ---------- */
function approvalCard(a) {
  const box = el("div", "approval");
  box.dataset.id = a.id;
  box.appendChild(el("div", "", ""));
  box.firstChild.appendChild(el("b", "", a.tool));
  box.appendChild(el("pre", "", pretty(a.args)));
  box.appendChild(el("div", "muted", "Причина: " + (a.reason || "—")));
  const row = el("div", "row");
  const note = el("input");
  note.placeholder = "Нотатка (необов'язково)";
  const ok = el("button", "ok", "Схвалити");
  const no = el("button", "no", "Відхилити");
  const decide = async (approve) => {
    ok.disabled = no.disabled = true;
    try {
      await api("/approvals/" + a.id + "/decide", "POST", { approve, note: note.value, by: "Адміністратор" });
      box.remove();
      pollEvents();
      loadApprovals();
    } catch (e) {
      ok.disabled = no.disabled = false;
      if (e.status === 409 || e.status === 404) box.remove();
      else alert("Помилка: " + e.message);
    }
  };
  ok.addEventListener("click", () => decide(true));
  no.addEventListener("click", () => decide(false));
  row.append(note, ok, no);
  box.appendChild(row);
  return box;
}

async function loadApprovals() {
  const box = $("approvals");
  // Do not rebuild while the admin is typing a note.
  if (box.contains(document.activeElement) && document.activeElement.tagName === "INPUT") return;
  try {
    const d = await api("/tenants/" + $("tenant").value + "/approvals?status=pending");
    const ids = d.approvals.map((a) => a.id).join(",");
    $("approvals-count").textContent = d.approvals.length;
    if (box.dataset.ids === ids) return;
    box.dataset.ids = ids;
    box.textContent = "";
    if (!d.approvals.length) box.appendChild(el("div", "empty", "Немає запитів, що очікують."));
    d.approvals.forEach((a) => box.appendChild(approvalCard(a)));
  } catch (_) { /* retry next tick */ }
}

/* ---------- metrics ---------- */
const METRIC_LABELS = {
  sessions: "Сесії", messages: "Повідомлення", tool_calls: "Виклики інструментів",
  auto_actions: "Авто-дії", approvals_pending: "Апруви: очікують", approvals_approved: "Апруви: схвалено",
  approvals_rejected: "Апруви: відхилено", escalations: "Ескалації", money_saved_uah: "Збережено, грн",
};
async function loadMetrics() {
  try {
    const m = await api("/tenants/" + $("tenant").value + "/metrics");
    const grid = $("metrics");
    grid.textContent = "";
    Object.keys(METRIC_LABELS).forEach((k) => {
      if (!(k in m)) return;
      const t = el("div", "tile");
      t.appendChild(el("b", "", String(m[k])));
      t.appendChild(el("span", "", METRIC_LABELS[k]));
      grid.appendChild(t);
    });
  } catch (_) { /* retry next tick */ }
}

function refreshSide() {
  $("approvals").dataset.ids = "";
  loadApprovals();
  loadMetrics();
}

/* ---------- wiring ---------- */
$("composer").addEventListener("submit", (e) => { e.preventDefault(); send($("text").value); });
$("new-session").addEventListener("click", newSession);
$("tenant").addEventListener("change", async () => { await loadClients(); newSession(); });
setInterval(loadApprovals, 1500);
setInterval(loadMetrics, 3000);
loadClients().then(newSession);
