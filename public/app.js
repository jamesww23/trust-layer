/* Trust Layer MVP — Frontend Logic */

const API_BASE = window.location.origin;

// --- Page Load ---
document.addEventListener("DOMContentLoaded", loadState);

async function loadState() {
  try {
    const res = await fetch(API_BASE + "/api/state");
    if (!res.ok) throw new Error("Failed to load state");
    const data = await res.json();
    renderProfiles(data.profiles);
    renderTask(data.task);
    renderCandidates(data.candidates);
    renderConfig(data.config);
  } catch (err) {
    setStatus("Error loading state: " + err.message);
  }
}

// --- Run Demo ---
async function runDemo() {
  const btn = document.getElementById("run-btn");
  btn.disabled = true;
  setStatus("Running evaluation...");

  try {
    const res = await fetch(API_BASE + "/api/run-demo", { method: "POST" });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.error || "Run failed");
    }
    const data = await res.json();
    renderResults(data);
    renderProfilesFromList(data.profiles_after);
    setStatus("Evaluation complete.");
  } catch (err) {
    setStatus("Error: " + err.message);
  } finally {
    btn.disabled = false;
  }
}

// --- Reset ---
async function resetState() {
  setStatus("Resetting reputation...");

  try {
    const res = await fetch(API_BASE + "/api/reset", { method: "POST" });
    if (!res.ok) throw new Error("Reset failed");
    const data = await res.json();
    renderProfiles(data.profiles);
    document.getElementById("results-section").style.display = "none";
    setStatus("Reputation reset to seed values.");
  } catch (err) {
    setStatus("Error: " + err.message);
  }
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

function renderProfilesFromList(profiles) {
  renderProfiles(profiles);
}

function renderTask(task) {
  const el = document.getElementById("task-info");
  el.textContent =
    `ID: ${task.task_id}\n` +
    `Prompt: ${task.prompt}\n` +
    `Keywords: ${task.expected_keywords.join(", ")}`;
}

function renderCandidates(candidates) {
  const el = document.getElementById("candidates-info");
  el.textContent = candidates.map(c =>
    `[${c.agent_id}] ${c.output_text.substring(0, 120)}${c.output_text.length > 120 ? "..." : ""}`
  ).join("\n\n");
}

function renderConfig(config) {
  const el = document.getElementById("config-info");
  el.textContent =
    `w_reputation: ${config.w_reputation}\n` +
    `w_relevancy: ${config.w_relevancy}`;
}

function renderResults(data) {
  const section = document.getElementById("results-section");
  section.style.display = "block";

  const result = data.result;

  // Winner box
  const winnerBox = document.getElementById("winner-box");
  const outcomeClass = result.outcome ? "outcome-accepted" : "outcome-rejected";
  const outcomeText = result.outcome ? "ACCEPTED" : "REJECTED";
  winnerBox.innerHTML =
    `<div class="winner-label">Winner: ${esc(result.winner_agent_id)}</div>` +
    `<div>Trust Score: ${result.winner_score}</div>` +
    `<div>Outcome: <span class="${outcomeClass}">${outcomeText}</span></div>` +
    `<div style="margin-top:8px;color:#8b949e;font-size:13px">${esc(result.explanation)}</div>`;

  // Ranking table
  const tbody = document.getElementById("ranking-body");
  tbody.innerHTML = result.ranking.map((r, i) => {
    const isWinner = r.agent_id === result.winner_agent_id;
    return `
      <tr class="${isWinner ? "winner-row" : ""}">
        <td>#${i + 1}</td>
        <td>${esc(r.agent_id)}</td>
        <td>${r.relevancy.toFixed(4)}</td>
        <td>${r.trust_score.toFixed(4)}</td>
        <td>${r.success_rate.toFixed(4)}</td>
      </tr>
    `;
  }).join("");

  // Reputation diff
  const diffEl = document.getElementById("reputation-diff");
  const winnerId = result.winner_agent_id;
  const before = data.profiles_before.find(p => p.agent_id === winnerId);
  const after = data.profiles_after.find(p => p.agent_id === winnerId);
  if (before && after) {
    diffEl.textContent =
      `Agent: ${winnerId}\n` +
      `success_rate: ${before.success_rate.toFixed(4)} → ${after.success_rate.toFixed(4)}\n` +
      `total_runs:   ${before.total_runs} → ${after.total_runs}`;
  }

  // Logs
  const logsEl = document.getElementById("logs-output");
  logsEl.textContent = data.logs.join("\n");
}

function setStatus(msg) {
  document.getElementById("status-msg").textContent = msg;
}

function esc(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}
