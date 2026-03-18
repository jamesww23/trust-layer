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
    if (data.scenarios) {
      renderScenarios(data.scenarios);
    }
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

// --- Custom Input ---
function toggleCustom() {
  const form = document.getElementById("custom-form");
  const btn = document.getElementById("custom-toggle");
  if (form.style.display === "none") {
    form.style.display = "block";
    btn.textContent = "− Custom Input";
  } else {
    form.style.display = "none";
    btn.textContent = "+ Custom Input";
  }
}

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
  if (list.children.length <= 2) {
    setStatus("At least 2 candidates required.");
    return;
  }
  btn.parentElement.remove();
}

async function runCustom() {
  const btn = document.getElementById("run-custom-btn");
  btn.disabled = true;
  setStatus("Running custom evaluation...");

  try {
    const prompt = document.getElementById("custom-prompt").value.trim();
    if (!prompt) {
      setStatus("Task prompt is required.");
      btn.disabled = false;
      return;
    }

    const keywordsRaw = document.getElementById("custom-keywords").value.trim();
    const keywords = keywordsRaw
      ? keywordsRaw.split(",").map(k => k.trim()).filter(k => k)
      : [];

    const blocks = document.querySelectorAll(".candidate-input");
    const candidates = [];
    for (const block of blocks) {
      const agentId = block.querySelector(".cand-agent-id").value.trim();
      const outputText = block.querySelector(".cand-output").value.trim();
      if (!agentId || !outputText) {
        setStatus("All candidates need an Agent ID and output text.");
        btn.disabled = false;
        return;
      }
      candidates.push({ agent_id: agentId, output_text: outputText });
    }

    if (candidates.length < 2) {
      setStatus("At least 2 candidates required.");
      btn.disabled = false;
      return;
    }

    // Check for duplicate agent IDs
    const ids = candidates.map(c => c.agent_id);
    if (new Set(ids).size !== ids.length) {
      setStatus("Candidate agent IDs must be unique.");
      btn.disabled = false;
      return;
    }

    const payload = {
      task: { prompt: prompt, expected_keywords: keywords },
      candidates: candidates,
    };

    const res = await fetch(API_BASE + "/api/run-custom", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.error || "Custom run failed");
    }

    const data = await res.json();
    renderResults(data);
    renderProfilesFromList(data.profiles_after);
    setStatus("Custom evaluation complete.");
  } catch (err) {
    setStatus("Error: " + err.message);
  } finally {
    btn.disabled = false;
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
  } else if (after) {
    diffEl.textContent =
      `Agent: ${winnerId} (new)\n` +
      `success_rate: 0.5000 → ${after.success_rate.toFixed(4)}\n` +
      `total_runs:   0 → ${after.total_runs}`;
  }

  // Logs
  const logsEl = document.getElementById("logs-output");
  logsEl.textContent = data.logs.join("\n");

  // Scroll to results
  section.scrollIntoView({ behavior: "smooth" });
}

function setStatus(msg) {
  document.getElementById("status-msg").textContent = msg;
}

function esc(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}
