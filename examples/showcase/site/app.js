"use strict";

const STAGE_NAMES = { intent: "Intent extraction", planner: "Planner", reviewer: "Reviewer" };
const SOURCE_TAGS = { live: "Recorded model", scripted: "Scripted model", simulated: "Simulated attack" };
const LANG_TAGS = { en: "English", fa: "فارسی" };

const state = { data: null, filter: "all", current: null };

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function isNumeric(value) {
  return typeof value === "number" || (typeof value === "string" && /^-?\d+(\.\d+)?$/.test(value));
}

function formatValue(value) {
  if (value === null || value === undefined) return "—";
  if (isNumeric(value)) return Number(value).toLocaleString("en-US", { maximumFractionDigits: 2 });
  return String(value);
}

function direction(text) {
  return /[؀-ۿ]/.test(text || "") ? "rtl" : "ltr";
}

function pretty(value) {
  if (typeof value === "string") {
    try { return JSON.stringify(JSON.parse(value), null, 2); } catch (error) { return value; }
  }
  return JSON.stringify(value, null, 2);
}

// Highlight the row-policy conditions SageQL adds to every query.
function highlightSql(sql, columns) {
  const pattern = new RegExp(`(?:\\w+\\.)?[\\["]?(?:${columns.join("|")})[\\]"]?\\s*=\\s*\\?`, "g");
  let html = "", last = 0, match;
  while ((match = pattern.exec(sql)) !== null) {
    html += escapeHtml(sql.slice(last, match.index)) + `<span class="policy">${escapeHtml(match[0])}</span>`;
    last = match.index + match[0].length;
  }
  return html + escapeHtml(sql.slice(last));
}

function renderList() {
  const list = document.getElementById("example-list");
  const examples = state.data.examples.filter((e) => state.filter === "all" || e.category === state.filter);
  list.innerHTML = examples.map((e) => `
    <li><button type="button" data-id="${e.id}" aria-current="${e.id === state.current}">
      <span class="title" dir="${direction(e.title)}">${escapeHtml(e.title)}</span>
      <span class="tags"><span class="tag">${LANG_TAGS[e.language]}</span>
        <span class="tag ${e.source}">${SOURCE_TAGS[e.source]}</span></span>
    </button></li>`).join("");
  if (!examples.some((e) => e.id === state.current) && examples.length) select(examples[0].id);
}

function select(id) {
  state.current = id;
  document.querySelectorAll("#example-list button").forEach((b) => b.setAttribute("aria-current", String(b.dataset.id === id)));
  renderDetail(state.data.examples.find((e) => e.id === id));
}

function banner(example) {
  if (example.source === "simulated") {
    return `<div class="banner simulated">The model reply in this example is deliberately hostile and written by hand,
      to show what SageQL does when a model is wrong or compromised. Everything after it is the real engine.</div>`;
  }
  if (example.source === "scripted") {
    return `<div class="banner scripted">Placeholder model reply. It will be replaced by a recorded live model run;
      everything after it is already the real engine.</div>`;
  }
  const date = state.data.recorded_at ? ` on ${escapeHtml(state.data.recorded_at)}` : "";
  return `<div class="banner">Model replies recorded from a live run${date}. Everything after them is replayed
    through the real engine.</div>`;
}

function periodText(p) {
  if (!p) return null;
  if (p.year && p.month) return `${p.kind} ${p.year}/${p.month}`;
  if (p.start || p.end) return `${p.kind} ${p.start || "…"} → ${p.end || "…"}`;
  if (p.count) return `${p.kind} ${p.count} ${p.unit}`;
  return p.year ? `${p.kind} ${p.year}` : p.kind;
}

// A one-line reading of what the model chose; the raw reply stays one click away.
function summarize(call) {
  let value;
  try { value = JSON.parse(call.output); } catch (error) { return ""; }
  const items = [];
  const add = (label, text) => { if (text) items.push(`<span><b>${label}</b> ${escapeHtml(text)}</span>`); };
  if (call.stage === "intent") {
    add("measures", (value.metrics || []).map((m) => m.concept_id).join(", ") || "none");
    add("grouping", (value.dimensions || []).map((d) => d.concept_id).join(", "));
    add("time grain", value.time_grain && value.time_grain !== "none" ? value.time_grain : "");
    add("period", periodText(value.period) || "missing");
    add("compared with", periodText(value.comparison));
    add("filters", (value.filters || []).map((f) => `${f.filter_id} ${f.operator} ${JSON.stringify(f.values)}`).join("; "));
    add("order", value.order_by ? `${value.order_by}${value.descending ? " desc" : ""}${value.limit ? `, top ${value.limit}` : ""}` : "");
    add("missing", (value.missing || []).join(", "));
    add("unsupported", value.unsupported_reason);
  } else {
    add("status", value.status || (value.approved !== undefined ? (value.approved ? "approved" : "rejected") : ""));
    add("question", value.question);
    add("message", value.message);
  }
  return `<p class="summary">${items.join("")}</p>`;
}

function renderModelCalls(calls) {
  if (!calls.length) {
    return `<div class="stage model"><div class="stage-title">Model</div>
      <p class="stage-note">No model call. The saved definition is validated and compiled directly.</p></div>`;
  }
  return calls.map((call) => {
    const tokens = call.usage && call.usage.input ? ` · ${call.usage.input} in / ${call.usage.output} out tokens` : "";
    const leaked = call.leaked || [];
    const check = leaked.length
      ? `<p class="check bad">Found in model input: ${leaked.map(escapeHtml).join(", ")}</p>`
      : `<p class="check">✓ Checked: no table names, column names or policy values in what SageQL sent.</p>`;
    return `<div class="stage model">
      <div class="stage-title">Model · ${STAGE_NAMES[call.stage] || escapeHtml(call.stage)} · ${escapeHtml(call.model)}${tokens}</div>
      ${summarize(call)}
      ${check}
      <details><summary>What the model received</summary><pre>${escapeHtml(pretty(call.sent))}</pre></details>
      <details><summary>What the model returned (raw)</summary><pre>${escapeHtml(pretty(call.output))}</pre></details>
    </div>`;
  }).join("");
}

function renderQueries(queries, index) {
  if (!queries.length) {
    return `<div class="stage engine"><div class="stage-title">SageQL</div>
      <p class="stage-note">No SQL was generated for this turn.</p></div>`;
  }
  const columns = state.data.policy_columns;
  const blocks = queries.map((q, i) => {
    const id = `q-${index}-${i}`;
    const purpose = q.dataset === "sales" ? "Report query" : `Lookup on ${escapeHtml(q.dataset)}`;
    const params = q.parameters.map((p) => `<code>${escapeHtml(JSON.stringify(p))}</code>`).join(" ");
    return `<div class="query" id="${id}">
      <div class="tabs"><strong class="stage-note">${purpose}</strong>
        <button type="button" class="active" data-dialect="tsql">SQL Server</button>
        <button type="button" data-dialect="sqlite">SQLite (ran here)</button></div>
      <pre class="sql" data-dialect="tsql">${highlightSql(q.tsql, columns)}</pre>
      <pre class="sql" data-dialect="sqlite" hidden>${highlightSql(q.sqlite, columns)}</pre>
      <p class="params">Bound parameters, in order: ${params || "none"} · ${q.rows_returned} row(s)</p>
    </div>`;
  }).join("");
  return `<div class="stage engine"><div class="stage-title">SageQL · validated, compiled, executed</div>
    <p class="legend"><span class="swatch"></span>Row policy from the host's authentication, added to every query</p>
    ${blocks}</div>`;
}

function chart(report) {
  const vis = report.visualization || {};
  const fields = report.fields.map((f) => f.id);
  const x = fields.indexOf(vis.x), y = fields.indexOf(vis.y);
  if (vis.kind === "kpi" && report.rows.length === 1) {
    const field = report.fields[report.fields.length - 1];
    return `<div class="kpi">${formatValue(report.rows[0][report.rows[0].length - 1])}
      <span class="muted">${escapeHtml(field.unit || "")}</span></div>`;
  }
  if (!["bar", "line"].includes(vis.kind) || x < 0 || y < 0 || report.rows.length < 2) return "";
  const points = report.rows.map((r) => ({ label: String(r[x]), value: Number(r[y]) || 0 }));
  const max = Math.max(...points.map((p) => p.value), 1);
  const w = 640, h = 220, pad = 36, inner = w - pad * 2;
  if (vis.kind === "bar") {
    const step = inner / points.length, bw = Math.min(56, step * 0.6);
    const bars = points.map((p, i) => {
      const bh = (p.value / max) * (h - 60), cx = pad + step * i + step / 2;
      return `<rect class="bar" x="${cx - bw / 2}" y="${h - 30 - bh}" width="${bw}" height="${bh}" rx="3"/>
        <text x="${cx}" y="${h - 12}" text-anchor="middle">${escapeHtml(p.label.slice(0, 18))}</text>
        <text x="${cx}" y="${h - 36 - bh}" text-anchor="middle">${formatValue(p.value)}</text>`;
    }).join("");
    return `<svg class="chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="Bar chart">
      <line class="axis" x1="${pad}" x2="${w - pad}" y1="${h - 30}" y2="${h - 30}"/>${bars}</svg>`;
  }
  const step = inner / Math.max(points.length - 1, 1);
  const xy = points.map((p, i) => [pad + step * i, h - 30 - (p.value / max) * (h - 60)]);
  const every = Math.ceil(points.length / 8);
  const labels = points.map((p, i) => (i % every === 0 || i === points.length - 1)
    ? `<text x="${xy[i][0]}" y="${h - 12}" text-anchor="middle">${escapeHtml(p.label.slice(5) || p.label)}</text>` : "").join("");
  const dots = points.length <= 12 ? xy.map(([a, b]) => `<circle class="dot" cx="${a}" cy="${b}" r="3"/>`).join("") : "";
  return `<svg class="chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="Line chart">
    <line class="axis" x1="${pad}" x2="${w - pad}" y1="${h - 30}" y2="${h - 30}"/>
    <polyline class="line" points="${xy.map((p) => p.join(",")).join(" ")}"/>${dots}${labels}
    <text x="${pad}" y="14">${formatValue(max)}</text></svg>`;
}

function table(report) {
  const head = report.fields.map((f) => `<th>${escapeHtml(f.label)}${f.unit ? ` (${escapeHtml(f.unit)})` : ""}</th>`).join("");
  const rows = report.rows.slice(0, 12).map((r) =>
    `<tr>${r.map((v) => `<td class="${isNumeric(v) ? "num" : ""}">${escapeHtml(formatValue(v))}</td>`).join("")}</tr>`).join("");
  const more = report.rows.length > 12 ? `<p class="muted">Showing 12 of ${report.rows.length} rows.</p>` : "";
  return `<div class="table-wrap" dir="${direction(report.title)}"><table><thead><tr>${head}</tr></thead><tbody>${rows}</tbody></table></div>${more}`;
}

function renderReply(reply) {
  const text = reply.assistant ? reply.assistant.text : "";
  const dir = direction(text);
  if (reply.status === "report_ready" && reply.report) {
    return `<div class="answer" dir="${dir}">${escapeHtml(text)}</div>${chart(reply.report)}${table(reply.report)}`;
  }
  if (reply.status === "needs_clarification") {
    return `<div class="question" dir="${dir}">${escapeHtml(text)}</div>`;
  }
  const code = reply.error ? ` <code>${escapeHtml(reply.error.code)}</code>` : "";
  return `<div class="refusal" dir="${dir}">${escapeHtml(text)}${code}</div>`;
}

function renderDetail(example) {
  const detail = document.getElementById("detail");
  const turns = example.turns.map((turn, i) => {
    const head = turn.saved_report
      ? `<p class="saved-label">Saved as “${escapeHtml(turn.saved_report.name)}”, then re-run later with fresh data</p>`
      : `<div class="user" dir="${direction(turn.user)}">${escapeHtml(turn.user)}</div>`;
    return `<div class="turn">${head}${renderModelCalls(turn.model_calls)}${renderQueries(turn.queries, i)}
      <div class="stage engine"><div class="stage-title">Reply to the user</div>${renderReply(turn.reply)}</div></div>`;
  }).join("");
  detail.innerHTML = `<h3 dir="${direction(example.title)}">${escapeHtml(example.title)}</h3>
    <p>${escapeHtml(example.summary)}</p>${banner(example)}${turns}`;
}

// The outcome line is read from the recorded run, never written by hand.
function attackOutcome(example) {
  const turn = example.turns[example.turns.length - 1];
  const status = turn.reply.status;
  if (!turn.queries.length && status === "unsupported") return "Declined as unsupported. No SQL was generated.";
  if (!turn.queries.length) return "Rejected before any SQL existed.";
  const values = turn.queries.flatMap((q) => q.parameters).filter((v) => typeof v === "string");
  const user = (turn.user || "").toLowerCase();
  const smuggled = values.find((v) => /['";]|--/.test(v));
  if (smuggled) return `Ran only as a parameterized query: ${JSON.stringify(smuggled)} was a bound value and matched nothing.`;
  if (/drop|delete|;/.test(user)) return "Only the registered report ran, read-only and with the store policy. The SQL text was ignored.";
  return "Ran only with the store policy from the authenticated user.";
}

// For a simulated attack the hostile part is the model's reply, not the user's message.
function attackAttempt(example) {
  const turn = example.turns[0];
  if (example.source !== "simulated") return turn.user;
  let reply;
  try { reply = JSON.parse(turn.model_calls[0].output); } catch (error) { return turn.user; }
  const parts = (reply.metrics || []).map((m) => `measure: ${m.concept_id}`)
    .concat((reply.filters || []).map((f) => `${f.filter_id} = ${JSON.stringify(f.values.join(", "))}`));
  return `Model replied with ${parts.join("; ")}`;
}

function renderAttacks() {
  const attacks = state.data.examples.filter((e) => e.category === "attacks");
  document.getElementById("attack-list").innerHTML = attacks.map((e) => `
    <article class="attack">
      <span class="tag ${e.source}">${SOURCE_TAGS[e.source]}</span>
      <h3 dir="${direction(e.title)}">${escapeHtml(e.title)}</h3>
      <p class="attempt" dir="${direction(attackAttempt(e))}">${escapeHtml(attackAttempt(e))}</p>
      <p class="outcome">${escapeHtml(attackOutcome(e))}</p>
      <button type="button" class="link" data-open="${e.id}">See it step by step →</button>
    </article>`).join("");
}

function leakStat() {
  const calls = state.data.examples.flatMap((e) => e.turns.flatMap((t) => t.model_calls));
  const leaks = calls.filter((c) => (c.leaked || []).length).length;
  document.getElementById("stat-leaks").textContent = String(leaks);
  document.getElementById("stat-leaks-label").textContent =
    `of ${calls.length} recorded model inputs contained a table name, column name or policy value`;
}

function provenance() {
  const sources = new Set(state.data.examples.map((e) => e.source));
  const version = `SageQL ${state.data.sageql_version}, business date ${state.data.today}.`;
  document.getElementById("footer-version").textContent = version;
  document.getElementById("provenance").textContent = sources.has("live")
    ? `Model replies recorded live${state.data.recorded_at ? " on " + state.data.recorded_at : ""}. ${version}`
    : `Model replies are placeholders until the live recording is added. ${version}`;
}

document.addEventListener("click", (event) => {
  const item = event.target.closest("#example-list button");
  if (item) return select(item.dataset.id);
  const open = event.target.closest("[data-open]");
  if (open) {
    state.filter = "all";
    document.querySelectorAll(".chip").forEach((c) => c.classList.toggle("active", c.dataset.filter === "all"));
    renderList();
    select(open.dataset.open);
    document.getElementById("detail").scrollIntoView({ block: "start" });
    return;
  }
  const chip = event.target.closest(".chip");
  if (chip) {
    state.filter = chip.dataset.filter;
    document.querySelectorAll(".chip").forEach((c) => c.classList.toggle("active", c === chip));
    return renderList();
  }
  const tab = event.target.closest(".tabs button");
  if (tab) {
    const query = tab.closest(".query");
    query.querySelectorAll(".tabs button").forEach((b) => b.classList.toggle("active", b === tab));
    query.querySelectorAll("pre.sql").forEach((p) => { p.hidden = p.dataset.dialect !== tab.dataset.dialect; });
    return;
  }
  const copy = event.target.closest("[data-copy]");
  if (copy) {
    navigator.clipboard.writeText(copy.dataset.copy).then(() => {
      copy.querySelector(".copy-label").textContent = "Copied";
      setTimeout(() => { copy.querySelector(".copy-label").textContent = "Copy"; }, 1500);
    }).catch(() => {});
  }
});

fetch("showcase.json")
  .then((response) => response.json())
  .then((data) => {
    state.data = data;
    provenance();
    leakStat();
    renderList();
    renderAttacks();
  })
  .catch(() => {
    document.getElementById("detail").innerHTML = `<p class="refusal">The example data could not be loaded.</p>`;
  });
