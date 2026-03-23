/* Trust Layer MVP — Frontend Logic */

const API_BASE = window.location.origin;
let currentRunId = null;

// --- Page Load ---
document.addEventListener("DOMContentLoaded", () => {
  loadState();
  loadHistory();
});

async function loadState() {
  try {
    const res = await fetch(API_BASE + "/api/state");
    if (!res.ok) throw new Error("Failed to load state");
    const data = await res.json();
    renderProfiles(data.profiles);
    renderTask(data.task);
    renderCandidates(data.candidates);
    renderConfig(data.config);
    if (data.scenarios) renderScenarios(data.scenarios);
  } catch (err) {
    setStatus("Error loading state: " + err.message);
  }
}

// --- Scenario Selection ---
function renderScenarios(scenarios) {
  const select = document.getElementById("scenario-select");
  select.innerHTML = scenarios.map(s =>
    `<option value="${esc(s.task_id)}">${esc(s.title)} (${esc(s.domain)})</option>`
  ).join("");
}

async function onScenarioChange() {
  const select = document.getElementById("scenario-select");
  const taskId = select.value;
  if (!taskId) return;
  try {
    const res = await fetch(API_BASE + "/api/state?task_id=" + encodeURIComponent(taskId));
    if (!res.ok) throw new Error("Failed to load scenario");
    const data = await res.json();
    renderTask(data.task);
    renderCandidates(data.candidates);
    setStatus("");
  } catch (err) {
    setStatus("Error loading scenario: " + err.message);
  }
}

// --- Run Demo ---
async function runDemo() {
  const btn = document.getElementById("run-btn");
  btn.disabled = true;
  setStatus("Running evaluation...");
  try {
    const select = document.getElementById("scenario-select");
    const taskId = select.value;
    const body = taskId ? { task_id: taskId } : {};
    const res = await fetch(API_BASE + "/api/run-demo", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.error || "Run failed");
    }
    const data = await res.json();
    renderResults(data);
    renderProfiles(data.profiles_after);
    loadHistory();
    setStatus("Evaluation complete.");
  } catch (err) {
    setStatus("Error: " + err.message);
  } finally {
    btn.disabled = false;
  }
}

// --- Reset ---
async function resetState() {
  setStatus("Resetting...");
  try {
    const res = await fetch(API_BASE + "/api/reset", { method: "POST" });
    if (!res.ok) throw new Error("Reset failed");
    const data = await res.json();
    renderProfiles(data.profiles);
    document.getElementById("results-section").style.display = "none";
    document.getElementById("batch-results-section").style.display = "none";
    loadHistory();
    setStatus("Reset to seed values. History cleared.");
  } catch (err) {
    setStatus("Error: " + err.message);
  }
}

// --- LLM Evaluation ---
async function runLLM() {
  setStatus("Calling OpenAI API (3 personas)...");
  try {
    const prompt = document.getElementById("llm-prompt").value.trim();
    if (!prompt) { setStatus("Task prompt is required."); return; }

    const keywordsRaw = document.getElementById("llm-keywords").value.trim();
    const keywords = keywordsRaw ? keywordsRaw.split(",").map(k => k.trim()).filter(k => k) : [];
    const model = document.getElementById("llm-model").value;

    const res = await fetch(API_BASE + "/api/run-llm", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt, expected_keywords: keywords, model }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.error || "LLM run failed");
    }
    const data = await res.json();
    renderResults(data, true);
    renderProfiles(data.profiles_after);
    loadHistory();
    setStatus("LLM evaluation complete.");
  } catch (err) {
    setStatus("Error: " + err.message);
  }
}

// --- Batch Evaluation ---
function onBatchModeChange() {
  const mode = document.getElementById("batch-mode").value;
  const opts = document.getElementById("batch-options");
  if (mode === "repeat") {
    const select = document.getElementById("scenario-select");
    opts.innerHTML =
      '<label>Scenario</label>' +
      '<select id="batch-task-id">' + select.innerHTML + '</select>' +
      '<label>Repeat Count</label>' +
      '<input type="number" id="batch-count" value="3" min="1" max="10">';
  } else {
    opts.innerHTML = '';
  }
}

async function runBatch() {
  setStatus("Running batch evaluation...");
  try {
    const mode = document.getElementById("batch-mode").value;
    const payload = { mode };

    if (mode === "repeat") {
      payload.task_id = document.getElementById("batch-task-id").value;
      payload.count = parseInt(document.getElementById("batch-count").value) || 3;
    }

    const res = await fetch(API_BASE + "/api/run-batch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.error || "Batch failed");
    }
    const data = await res.json();
    renderBatchResults(data);
    renderProfiles(data.profiles_after);
    loadHistory();
    setStatus(`Batch complete: ${data.total_runs} evaluations.`);
  } catch (err) {
    setStatus("Error: " + err.message);
  }
}

// --- Custom Input ---
function addCandidate() {
  const list = document.getElementById("candidates-list");
  const block = document.createElement("div");
  block.className = "candidate-input";
  block.innerHTML =
    '<input type="text" placeholder="Agent ID (e.g. agent_gamma)" class="cand-agent-id">' +
    '<textarea rows="2" placeholder="Agent output text..." class="cand-output"></textarea>' +
    '<button class="remove-cand-btn" onclick="removeCandidate(this)">Remove</button>';
  list.appendChild(block);
}

function removeCandidate(btn) {
  const list = document.getElementById("candidates-list");
  if (list.children.length <= 2) { setStatus("At least 2 candidates required."); return; }
  btn.parentElement.remove();
}

async function runCustom() {
  setStatus("Running custom evaluation...");
  try {
    const prompt = document.getElementById("custom-prompt").value.trim();
    if (!prompt) { setStatus("Task prompt is required."); return; }

    const keywordsRaw = document.getElementById("custom-keywords").value.trim();
    const keywords = keywordsRaw ? keywordsRaw.split(",").map(k => k.trim()).filter(k => k) : [];

    const blocks = document.querySelectorAll(".candidate-input");
    const candidates = [];
    for (const block of blocks) {
      const agentId = block.querySelector(".cand-agent-id").value.trim();
      const outputText = block.querySelector(".cand-output").value.trim();
      if (!agentId || !outputText) { setStatus("All candidates need Agent ID and output text."); return; }
      candidates.push({ agent_id: agentId, output_text: outputText });
    }
    if (candidates.length < 2) { setStatus("At least 2 candidates required."); return; }
    const ids = candidates.map(c => c.agent_id);
    if (new Set(ids).size !== ids.length) { setStatus("Candidate agent IDs must be unique."); return; }

    const res = await fetch(API_BASE + "/api/run-custom", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ task: { prompt, expected_keywords: keywords }, candidates }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.error || "Custom run failed");
    }
    const data = await res.json();
    renderResults(data);
    renderProfiles(data.profiles_after);
    loadHistory();
    setStatus("Custom evaluation complete.");
  } catch (err) {
    setStatus("Error: " + err.message);
  }
}

// --- Human Feedback ---
async function submitFeedback(outcome) {
  if (!currentRunId) return;
  const statusEl = document.getElementById("feedback-status");
  statusEl.textContent = "Submitting...";

  try {
    const res = await fetch(API_BASE + "/api/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ run_id: currentRunId, outcome }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.error || "Feedback failed");
    }
    const data = await res.json();
    renderProfiles(data.profiles);

    // Update winner box outcome display
    const outcomeText = outcome ? "ACCEPTED" : "REJECTED";
    const outcomeClass = outcome ? "outcome-accepted" : "outcome-rejected";
    statusEl.innerHTML = `Overridden to <span class="${outcomeClass}">${outcomeText}</span>`;

    // Disable buttons
    document.querySelectorAll(".feedback-accept, .feedback-reject").forEach(b => b.disabled = true);
    loadHistory();
  } catch (err) {
    statusEl.textContent = "Error: " + err.message;
  }
}

// --- Run History ---
async function loadHistory() {
  try {
    const res = await fetch(API_BASE + "/api/runs?limit=20");
    if (!res.ok) return;
    const data = await res.json();
    renderHistory(data.runs);
  } catch (err) {
    // Silently fail — history is supplementary
  }
}

function renderHistory(runs) {
  const el = document.getElementById("history-list");
  if (!runs || runs.length === 0) {
    el.innerHTML = '<p class="loading">No runs yet. Run an evaluation to see history.</p>';
    return;
  }
  let html = '<table class="history-table"><thead><tr>' +
    '<th>Time</th><th>Source</th><th>Task</th><th>Winner</th><th>Score</th><th>Outcome</th>' +
    '</tr></thead><tbody>';
  for (const run of runs) {
    const time = new Date(run.created_at).toLocaleString();
    const r = run.result;
    const outcomeClass = r.outcome ? "outcome-accepted" : "outcome-rejected";
    const outcomeText = r.outcome ? "Accepted" : "Rejected";
    const overridden = run.feedback_override ? ' (overridden)' : '';
    html += `<tr>
      <td>${esc(time)}</td>
      <td>${esc(run.source)}</td>
      <td>${esc(r.task_id)}</td>
      <td>${esc(r.winner_agent_id)}</td>
      <td>${r.winner_score}</td>
      <td><span class="${outcomeClass}">${outcomeText}${overridden}</span></td>
    </tr>`;
  }
  html += '</tbody></table>';
  el.innerHTML = html;
}

// --- Renderers ---
function renderProfiles(profiles) {
  const tbody = document.getElementById("profiles-body");
  if (!profiles || profiles.length === 0) {
    tbody.innerHTML = '<tr><td colspan="5" class="loading">No profiles found</td></tr>';
    return;
  }
  profiles.sort((a, b) => a.agent_id.localeCompare(b.agent_id));
  tbody.innerHTML = profiles.map(p => `
    <tr>
      <td>${esc(p.agent_id)}</td>
      <td>${esc(p.agent_name)}</td>
      <td>${p.success_rate.toFixed(4)}</td>
      <td>${p.total_runs}</td>
      <td>${esc(p.version)}</td>
    </tr>
  `).join("");
}

function renderTask(task) {
  document.getElementById("task-info").textContent =
    `ID: ${task.task_id}\nPrompt: ${task.prompt}\nKeywords: ${task.expected_keywords.join(", ")}`;
}

function renderCandidates(candidates) {
  document.getElementById("candidates-info").textContent = candidates.map(c =>
    `[${c.agent_id}] ${c.output_text.substring(0, 120)}${c.output_text.length > 120 ? "..." : ""}`
  ).join("\n\n");
}

function renderConfig(config) {
  document.getElementById("config-info").textContent =
    `w_reputation: ${config.w_reputation}\nw_relevancy: ${config.w_relevancy}`;
}

function renderResults(data, showCandidates = false) {
  const section = document.getElementById("results-section");
  section.style.display = "block";
  document.getElementById("batch-results-section").style.display = "none";

  const result = data.result;
  currentRunId = data.run_id || null;

  // Winner box
  const winnerBox = document.getElementById("winner-box");
  const outcomeClass = result.outcome ? "outcome-accepted" : "outcome-rejected";
  const outcomeText = result.outcome ? "ACCEPTED" : "REJECTED";
  winnerBox.innerHTML =
    `<div class="winner-label">Winner: ${esc(result.winner_agent_id)}</div>` +
    `<div>Trust Score: ${result.winner_score}</div>` +
    `<div>Outcome: <span class="${outcomeClass}">${outcomeText}</span></div>` +
    `<div style="margin-top:8px;color:#8b949e;font-size:13px">${esc(result.explanation)}</div>`;

  // Feedback buttons
  const feedbackSection = document.getElementById("feedback-section");
  if (currentRunId) {
    feedbackSection.style.display = "block";
    document.querySelectorAll(".feedback-accept, .feedback-reject").forEach(b => b.disabled = false);
    document.getElementById("feedback-status").textContent = "";
  } else {
    feedbackSection.style.display = "none";
  }

  // Candidate outputs (for LLM runs)
  const candOutSection = document.getElementById("candidates-output-section");
  if (showCandidates && data.candidates) {
    candOutSection.style.display = "block";
    document.getElementById("candidates-output").textContent = data.candidates.map(c =>
      `[${c.agent_id}] (${c.latency_ms}ms)\n${c.output_text}`
    ).join("\n\n---\n\n");
  } else {
    candOutSection.style.display = "none";
  }

  // Ranking table
  const tbody = document.getElementById("ranking-body");
  tbody.innerHTML = result.ranking.map((r, i) => {
    const isWinner = r.agent_id === result.winner_agent_id;
    return `<tr class="${isWinner ? "winner-row" : ""}">
      <td>#${i + 1}</td><td>${esc(r.agent_id)}</td>
      <td>${r.relevancy.toFixed(4)}</td><td>${r.trust_score.toFixed(4)}</td>
      <td>${r.success_rate.toFixed(4)}</td>
    </tr>`;
  }).join("");

  // Reputation diff
  const diffEl = document.getElementById("reputation-diff");
  const winnerId = result.winner_agent_id;
  const before = data.profiles_before.find(p => p.agent_id === winnerId);
  const after = data.profiles_after.find(p => p.agent_id === winnerId);
  if (before && after) {
    diffEl.textContent =
      `Agent: ${winnerId}\nsuccess_rate: ${before.success_rate.toFixed(4)} -> ${after.success_rate.toFixed(4)}\ntotal_runs:   ${before.total_runs} -> ${after.total_runs}`;
  } else if (after) {
    diffEl.textContent =
      `Agent: ${winnerId} (new)\nsuccess_rate: 0.5000 -> ${after.success_rate.toFixed(4)}\ntotal_runs:   0 -> ${after.total_runs}`;
  }

  // Logs
  document.getElementById("logs-output").textContent = data.logs.join("\n");
  section.scrollIntoView({ behavior: "smooth" });
}

function renderBatchResults(data) {
  document.getElementById("results-section").style.display = "none";
  const section = document.getElementById("batch-results-section");
  section.style.display = "block";

  // Summary
  document.getElementById("batch-summary").textContent =
    `Total runs: ${data.total_runs}\nRun IDs: ${data.run_ids.join(", ")}`;

  // Aggregate stats table
  const tbody = document.getElementById("batch-stats-body");
  const stats = data.aggregate_stats;
  tbody.innerHTML = Object.keys(stats).sort((a, b) => stats[b].wins - stats[a].wins).map(aid =>
    `<tr><td>${esc(aid)}</td><td>${stats[aid].wins}</td><td>${stats[aid].avg_score}</td></tr>`
  ).join("");

  // Per-run results
  const runsList = document.getElementById("batch-runs-list");
  runsList.innerHTML = data.results.map((r, i) => {
    const outcomeClass = r.outcome ? "outcome-accepted" : "outcome-rejected";
    const outcomeText = r.outcome ? "Accepted" : "Rejected";
    return `<div class="batch-run-item">
      <strong>Run ${i + 1}:</strong> ${esc(r.task_id)} | Winner: ${esc(r.winner_agent_id)} (${r.winner_score}) | <span class="${outcomeClass}">${outcomeText}</span>
    </div>`;
  }).join("");

  // Reputation timeline
  const timeline = data.reputation_timeline;
  if (timeline && timeline.length > 0) {
    const agents = {};
    timeline.forEach((snapshot, i) => {
      snapshot.forEach(p => {
        if (!agents[p.agent_id]) agents[p.agent_id] = [];
        agents[p.agent_id].push({ run: i + 1, sr: p.success_rate, runs: p.total_runs });
      });
    });
    let text = "";
    for (const [aid, entries] of Object.entries(agents).sort()) {
      text += `${aid}: ` + entries.map(e => `${e.sr.toFixed(4)} (${e.runs})`).join(" -> ") + "\n";
    }
    document.getElementById("reputation-timeline").textContent = text;
  }

  section.scrollIntoView({ behavior: "smooth" });
}

// --- UI Helpers ---
function toggleSection(name) {
  const form = document.getElementById(name + "-form");
  const btn = form.previousElementSibling;
  if (form.style.display === "none") {
    form.style.display = "block";
    btn.textContent = btn.textContent.replace("+", "\u2212");
  } else {
    form.style.display = "none";
    btn.textContent = btn.textContent.replace("\u2212", "+");
  }
}

function setStatus(msg) {
  document.getElementById("status-msg").textContent = msg;
}

function esc(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}
