/* Trust Layer MVP — Redesigned Frontend */

const API_BASE = window.location.origin;
let currentRunId = null;
let currentTab = "demo";

// --- Init ---
document.addEventListener("DOMContentLoaded", () => {
  loadState();
  loadHistory();
});

// --- Tabs ---
function switchTab(tab) {
  document.querySelectorAll(".tab").forEach(t => t.classList.toggle("active", t.dataset.tab === tab));
  document.querySelectorAll(".tab-content").forEach(s => s.classList.toggle("active", s.id === "tab-" + tab));
  currentTab = tab;
  if (tab === "history") loadHistory();
}

// --- Load State ---
async function loadState() {
  try {
    const res = await fetch(API_BASE + "/api/state");
    if (!res.ok) throw new Error("Failed to load state");
    const data = await res.json();
    renderLeaderboard(data.profiles, data.config);
    renderDemoTask(data.task);
    renderDemoCandidates(data.candidates);
    if (data.scenarios) renderScenarios(data.scenarios);
    if (data.available_providers) renderProviders(data.available_providers);
  } catch (err) {
    setStatus("demo", "Error loading: " + err.message);
  }
}

// --- Leaderboard ---
function renderLeaderboard(profiles, config) {
  const el = document.getElementById("leaderboard-body");
  if (!profiles || profiles.length === 0) {
    el.innerHTML = '<p class="empty-state">No agents yet</p>';
    return;
  }
  // Sort by success_rate DESC, then total_runs DESC
  const sorted = [...profiles].sort((a, b) => b.success_rate - a.success_rate || b.total_runs - a.total_runs);
  el.innerHTML = sorted.map((p, i) => `
    <div class="leaderboard-agent">
      <div class="leaderboard-rank ${i < 3 ? 'top' : ''}">${i + 1}</div>
      <div class="leaderboard-info">
        <div class="leaderboard-name">${esc(p.agent_name)}</div>
        <div class="leaderboard-id">${esc(p.agent_id)}</div>
      </div>
      <div class="leaderboard-score">
        <div class="leaderboard-sr">${(p.success_rate * 100).toFixed(1)}%</div>
        <div class="leaderboard-runs">${p.total_runs} run${p.total_runs !== 1 ? 's' : ''}</div>
      </div>
    </div>
  `).join("");

  // Scoring note
  if (config) {
    document.getElementById("scoring-note").textContent =
      `Score = ${(config.w_reputation * 100).toFixed(0)}% reputation + ${(config.w_relevancy * 100).toFixed(0)}% relevancy`;
  }
}

// --- Scenarios ---
function renderScenarios(scenarios) {
  const select = document.getElementById("scenario-select");
  select.innerHTML = scenarios.map(s =>
    `<option value="${esc(s.task_id)}">${esc(s.title)} — ${esc(s.domain)}</option>`
  ).join("");
}

async function onScenarioChange() {
  const taskId = document.getElementById("scenario-select").value;
  if (!taskId) return;
  try {
    const res = await fetch(API_BASE + "/api/state?task_id=" + encodeURIComponent(taskId));
    if (!res.ok) throw new Error("Failed to load scenario");
    const data = await res.json();
    renderDemoTask(data.task);
    renderDemoCandidates(data.candidates);
  } catch (err) {
    setStatus("demo", "Error: " + err.message);
  }
}

// --- Demo Task/Candidates Preview ---
function renderDemoTask(task) {
  document.getElementById("demo-task-prompt").textContent = task.prompt;
  const kwEl = document.getElementById("demo-task-keywords");
  kwEl.innerHTML = task.expected_keywords.map(k =>
    `<span class="keyword-tag">${esc(k)}</span>`
  ).join("");
}

function renderDemoCandidates(candidates) {
  const el = document.getElementById("demo-candidates-list");
  el.innerHTML = candidates.map(c => `
    <div class="candidate-preview-item">
      <div class="agent-label">${esc(c.agent_id)}</div>
      <div class="agent-output">${esc(truncate(c.output_text, 180))}</div>
    </div>
  `).join("");
}

// --- Run Demo ---
async function runDemo() {
  const btn = document.getElementById("run-demo-btn");
  btn.disabled = true;
  setStatus("demo", "Running evaluation...");
  try {
    const taskId = document.getElementById("scenario-select").value;
    const body = taskId ? { task_id: taskId } : {};
    const res = await fetch(API_BASE + "/api/run-demo", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) { const err = await res.json(); throw new Error(err.error || "Run failed"); }
    const data = await res.json();
    renderResultsInto("demo-results", data);
    renderLeaderboard(data.profiles_after, null);
    loadHistory();
    setStatus("demo", "");
  } catch (err) {
    setStatus("demo", "Error: " + err.message);
  } finally {
    btn.disabled = false;
  }
}

// --- LLM ---
function renderProviders(providers) {
  const el = document.getElementById("providers-status");
  if (!providers || providers.length === 0) {
    el.innerHTML = '<span class="provider-tag">No providers configured</span>';
    return;
  }
  el.innerHTML = providers.map(p =>
    `<span class="provider-tag available">${esc(p.agent_name)}</span>`
  ).join("");
}

async function runLLM() {
  setStatus("llm", "Calling AI agents...");
  try {
    const prompt = document.getElementById("llm-prompt").value.trim();
    if (!prompt) { setStatus("llm", "Enter a task prompt."); return; }
    const keywordsRaw = document.getElementById("llm-keywords").value.trim();
    const keywords = keywordsRaw ? keywordsRaw.split(",").map(k => k.trim()).filter(Boolean) : [];

    const res = await fetch(API_BASE + "/api/run-llm", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt, expected_keywords: keywords }),
    });
    if (!res.ok) { const err = await res.json(); throw new Error(err.error || "LLM run failed"); }
    const data = await res.json();
    renderResultsInto("llm-results", data, true);
    renderLeaderboard(data.profiles_after, null);
    loadHistory();
    setStatus("llm", "");
  } catch (err) {
    setStatus("llm", "Error: " + err.message);
  }
}

// --- Custom ---
function addCandidate() {
  const list = document.getElementById("candidates-list");
  const block = document.createElement("div");
  block.className = "candidate-input";
  block.innerHTML =
    '<input type="text" placeholder="Agent name" class="cand-agent-id">' +
    '<textarea rows="2" placeholder="Paste the agent\'s response here..." class="cand-output"></textarea>' +
    '<button class="remove-cand-btn" onclick="removeCandidate(this)">&times;</button>';
  list.appendChild(block);
}

function removeCandidate(btn) {
  const list = document.getElementById("candidates-list");
  if (list.children.length <= 2) { setStatus("custom", "At least 2 agents required."); return; }
  btn.parentElement.remove();
}

async function runCustom() {
  setStatus("custom", "Running evaluation...");
  try {
    const prompt = document.getElementById("custom-prompt").value.trim();
    if (!prompt) { setStatus("custom", "Enter a task description."); return; }
    const keywordsRaw = document.getElementById("custom-keywords").value.trim();
    const keywords = keywordsRaw ? keywordsRaw.split(",").map(k => k.trim()).filter(Boolean) : [];

    const blocks = document.querySelectorAll(".candidate-input");
    const candidates = [];
    for (const block of blocks) {
      const agentId = block.querySelector(".cand-agent-id").value.trim();
      const outputText = block.querySelector(".cand-output").value.trim();
      if (!agentId || !outputText) { setStatus("custom", "Fill in all agent names and outputs."); return; }
      candidates.push({ agent_id: agentId, output_text: outputText });
    }
    if (candidates.length < 2) { setStatus("custom", "At least 2 agents required."); return; }
    const ids = candidates.map(c => c.agent_id);
    if (new Set(ids).size !== ids.length) { setStatus("custom", "Agent names must be unique."); return; }

    const res = await fetch(API_BASE + "/api/run-custom", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ task: { prompt, expected_keywords: keywords }, candidates }),
    });
    if (!res.ok) { const err = await res.json(); throw new Error(err.error || "Custom run failed"); }
    const data = await res.json();
    renderResultsInto("custom-results", data);
    renderLeaderboard(data.profiles_after, null);
    loadHistory();
    setStatus("custom", "");
  } catch (err) {
    setStatus("custom", "Error: " + err.message);
  }
}

// --- Results Renderer ---
function renderResultsInto(containerId, data, showCandidates = false) {
  const container = document.getElementById(containerId);
  container.style.display = "block";
  const result = data.result;
  const runId = data.run_id || null;
  currentRunId = runId;

  const winnerId = result.winner_agent_id;
  const outcomeClass = result.outcome ? "outcome-accepted" : "outcome-rejected";
  const outcomeText = result.outcome ? "Accepted" : "Rejected";

  // Build reputation diff
  const before = data.profiles_before ? data.profiles_before.find(p => p.agent_id === winnerId) : null;
  const after = data.profiles_after ? data.profiles_after.find(p => p.agent_id === winnerId) : null;
  let repDiffHtml = "";
  if (before && after) {
    const dir = after.success_rate >= before.success_rate ? "up" : "down";
    repDiffHtml = `
      <div class="rep-diff">
        <span>${(before.success_rate * 100).toFixed(1)}%</span>
        <span class="rep-arrow">&rarr;</span>
        <span class="rep-change-${dir}">${(after.success_rate * 100).toFixed(1)}%</span>
        <span style="color:#484f58;font-size:12px">(${before.total_runs} &rarr; ${after.total_runs} runs)</span>
      </div>`;
  }

  // Build candidate outputs section
  let candidatesHtml = "";
  if (showCandidates && data.candidates) {
    candidatesHtml = `
      <div class="result-section">
        <div class="result-section-title">Agent Responses</div>
        ${data.candidates.map(c => `
          <div class="result-candidate">
            <span class="agent-label">${esc(c.agent_id)}</span>
            <span class="latency">${c.latency_ms}ms</span>
            <div class="output-text">${esc(c.output_text)}</div>
          </div>
        `).join("")}
      </div>`;
  }

  container.innerHTML = `
    <div class="result-winner">
      <div class="result-winner-label">${outcomeText} Winner</div>
      <div class="result-winner-name">${esc(winnerId)}</div>
      <div class="result-winner-score">Trust Score: ${result.winner_score} &nbsp; | &nbsp; Outcome: <span class="${outcomeClass}">${outcomeText}</span></div>
      ${result.explanation ? `<div class="result-winner-explanation">${esc(result.explanation)}</div>` : ""}
    </div>

    ${runId ? `
    <div class="result-feedback" id="feedback-${containerId}">
      <span>Was this the right choice?</span>
      <button class="feedback-btn feedback-accept" onclick="submitFeedback(true, '${containerId}')">Yes</button>
      <button class="feedback-btn feedback-reject" onclick="submitFeedback(false, '${containerId}')">No</button>
      <span class="feedback-status" id="feedback-status-${containerId}"></span>
    </div>` : ""}

    ${candidatesHtml}

    <div class="result-section">
      <div class="result-section-title">Ranking</div>
      <table class="ranking-table">
        <thead><tr><th>#</th><th>Agent</th><th>Relevancy</th><th>Trust Score</th><th>Success Rate</th></tr></thead>
        <tbody>
          ${result.ranking.map((r, i) => `
            <tr class="${r.agent_id === winnerId ? 'winner-row' : ''}">
              <td>${i + 1}</td>
              <td>${esc(r.agent_id)}</td>
              <td>${(r.relevancy * 100).toFixed(1)}%</td>
              <td>${r.trust_score.toFixed(4)}</td>
              <td>${(r.success_rate * 100).toFixed(1)}%</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>

    <div class="result-section">
      <div class="result-section-title">Reputation Update — ${esc(winnerId)}</div>
      ${repDiffHtml}
    </div>

    <div class="result-section">
      <button class="logs-toggle" onclick="toggleLogs('${containerId}')">Show evaluation logs</button>
      <div class="logs-content" id="logs-${containerId}" style="display:none;">${esc(data.logs.join("\n"))}</div>
    </div>
  `;

  container.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function toggleLogs(containerId) {
  const el = document.getElementById("logs-" + containerId);
  const btn = el.previousElementSibling;
  if (el.style.display === "none") {
    el.style.display = "block";
    btn.textContent = "Hide evaluation logs";
  } else {
    el.style.display = "none";
    btn.textContent = "Show evaluation logs";
  }
}

// --- Feedback ---
async function submitFeedback(outcome, containerId) {
  if (!currentRunId) return;
  const statusEl = document.getElementById("feedback-status-" + containerId);
  statusEl.textContent = "Submitting...";

  try {
    const res = await fetch(API_BASE + "/api/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ run_id: currentRunId, outcome }),
    });
    if (!res.ok) { const err = await res.json(); throw new Error(err.error || "Feedback failed"); }
    const data = await res.json();
    renderLeaderboard(data.profiles, null);

    const outcomeText = outcome ? "Accepted" : "Rejected";
    const outcomeClass = outcome ? "outcome-accepted" : "outcome-rejected";
    statusEl.innerHTML = `Overridden: <span class="${outcomeClass}">${outcomeText}</span>`;

    const feedbackEl = document.getElementById("feedback-" + containerId);
    feedbackEl.querySelectorAll(".feedback-btn").forEach(b => b.disabled = true);
    loadHistory();
  } catch (err) {
    statusEl.textContent = "Error: " + err.message;
  }
}

// --- Reset ---
async function resetState() {
  try {
    const res = await fetch(API_BASE + "/api/reset", { method: "POST" });
    if (!res.ok) throw new Error("Reset failed");
    const data = await res.json();
    renderLeaderboard(data.profiles, null);
    // Hide all result containers
    document.querySelectorAll(".results-container").forEach(el => el.style.display = "none");
    loadHistory();
  } catch (err) {
    console.error("Reset error:", err);
  }
}

// --- History ---
async function loadHistory() {
  try {
    const res = await fetch(API_BASE + "/api/runs?limit=20");
    if (!res.ok) return;
    const data = await res.json();
    renderHistory(data.runs);
  } catch (err) {
    // Silently fail
  }
}

function renderHistory(runs) {
  const el = document.getElementById("history-list");
  if (!runs || runs.length === 0) {
    el.innerHTML = '<p class="empty-state">No evaluations yet. Run a demo to get started.</p>';
    return;
  }
  let html = '<table class="history-table"><thead><tr>' +
    '<th>Time</th><th>Source</th><th>Task</th><th>Winner</th><th>Score</th><th>Outcome</th>' +
    '</tr></thead><tbody>';
  for (const run of runs) {
    const time = new Date(run.created_at).toLocaleString(undefined, {
      month: "short", day: "numeric", hour: "2-digit", minute: "2-digit"
    });
    const r = run.result;
    const outcomeClass = r.outcome ? "outcome-accepted" : "outcome-rejected";
    const outcomeText = r.outcome ? "Accepted" : "Rejected";
    const overridden = run.feedback_override ? ' *' : '';
    html += `<tr>
      <td>${esc(time)}</td>
      <td><span class="source-badge">${esc(run.source)}</span></td>
      <td>${esc(truncate(r.task_id, 30))}</td>
      <td>${esc(r.winner_agent_id)}</td>
      <td>${r.winner_score}</td>
      <td><span class="${outcomeClass}">${outcomeText}${overridden}</span></td>
    </tr>`;
  }
  html += '</tbody></table>';
  el.innerHTML = html;
}

// --- Helpers ---
function setStatus(tab, msg) {
  const el = document.getElementById(tab + "-status");
  if (el) el.textContent = msg;
}

function esc(str) {
  if (str == null) return "";
  const div = document.createElement("div");
  div.textContent = String(str);
  return div.innerHTML;
}

function truncate(str, len) {
  if (!str) return "";
  return str.length > len ? str.substring(0, len) + "..." : str;
}
