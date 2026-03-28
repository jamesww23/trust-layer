/* Agentic Reputation Infrastructure Layer — Frontend */

const API = window.location.origin;

document.addEventListener("DOMContentLoaded", loadAgents);

// --- Load Agents ---
async function loadAgents() {
  try {
    const res = await fetch(API + "/api/agents");
    if (!res.ok) throw new Error("Failed to load agents");
    const data = await res.json();
    renderAgentList(data.agents);
    renderRankings(data.agents);
  } catch (err) {
    document.getElementById("agent-list").innerHTML =
      '<p class="empty-state">Error loading agents: ' + esc(err.message) + '</p>';
  }
}

// --- Agent List ---
function renderAgentList(agents) {
  const el = document.getElementById("agent-list");
  if (!agents || agents.length === 0) {
    el.innerHTML = '<p class="empty-state">No agents registered yet.</p>';
    return;
  }
  el.innerHTML = agents.map(a => `
    <div class="agent-card">
      <div class="agent-card-header">
        <span class="agent-name">${esc(a.agent_name)}</span>
        <span class="agent-id">${esc(a.agent_id)}</span>
      </div>
      <div class="agent-skill">${esc(a.skill_md)}</div>
      <div class="agent-stats">
        <span class="stat">Trust: <strong>${(a.success_rate * 100).toFixed(1)}%</strong></span>
        <span class="stat">Runs: <strong>${a.total_runs}</strong></span>
      </div>
    </div>
  `).join("");
}

// --- Rankings Sidebar ---
function renderRankings(agents) {
  const el = document.getElementById("rankings-body");
  if (!agents || agents.length === 0) {
    el.innerHTML = '<p class="empty-state">No agents yet</p>';
    return;
  }
  const sorted = [...agents].sort((a, b) => b.success_rate - a.success_rate || b.total_runs - a.total_runs);
  el.innerHTML = sorted.map((a, i) => `
    <div class="rank-row">
      <span class="rank-num ${i < 3 ? 'top' : ''}">${i + 1}</span>
      <span class="rank-name">${esc(a.agent_name)}</span>
      <span class="rank-score">${(a.success_rate * 100).toFixed(1)}%</span>
    </div>
  `).join("");
}

// --- Register Agent ---
async function registerAgent() {
  const agent_id = document.getElementById("reg-id").value.trim();
  const agent_name = document.getElementById("reg-name").value.trim();
  const skill_md = document.getElementById("reg-skill").value.trim();
  const status = document.getElementById("register-status");

  if (!agent_id || !agent_name || !skill_md) {
    status.textContent = "All fields are required.";
    return;
  }

  status.textContent = "Registering...";
  try {
    const res = await fetch(API + "/api/register-agent", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ agent_id, agent_name, skill_md }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Registration failed");
    status.textContent = "Registered!";
    document.getElementById("reg-id").value = "";
    document.getElementById("reg-name").value = "";
    document.getElementById("reg-skill").value = "";
    loadAgents();
  } catch (err) {
    status.textContent = "Error: " + err.message;
  }
}

// --- Run Simulation ---
async function runSimulation() {
  const btn = document.getElementById("sim-btn");
  const status = document.getElementById("sim-status");
  const rounds = parseInt(document.getElementById("sim-rounds").value) || 5;

  btn.disabled = true;
  status.textContent = "Running simulation...";

  try {
    const res = await fetch(API + "/api/run-simulation", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rounds }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Simulation failed");

    renderSimResults(data);
    renderRankings(data.final_agents);
    renderAgentList(data.final_agents);
    status.textContent = "";
  } catch (err) {
    status.textContent = "Error: " + err.message;
  } finally {
    btn.disabled = false;
  }
}

function renderSimResults(data) {
  const section = document.getElementById("results-section");
  section.style.display = "block";
  const el = document.getElementById("sim-results");

  // Round-by-round table
  let html = `
    <div class="results-summary">
      <span>${data.rounds} rounds completed</span>
    </div>
    <table class="sim-table">
      <thead>
        <tr>
          <th>Round</th>
          <th>Requester</th>
          <th>Provider</th>
          <th>Outcome</th>
          <th>Trust Before</th>
          <th>Trust After</th>
        </tr>
      </thead>
      <tbody>
  `;

  for (const r of data.history) {
    const outcomeClass = r.outcome ? "outcome-success" : "outcome-fail";
    const outcomeText = r.outcome ? "Success" : "Failure";
    const arrow = r.trust_after >= r.trust_before ? "↑" : "↓";
    const arrowClass = r.trust_after >= r.trust_before ? "arrow-up" : "arrow-down";
    html += `
      <tr>
        <td>${r.round}</td>
        <td>${esc(r.requester)}</td>
        <td>${esc(r.provider)}</td>
        <td><span class="${outcomeClass}">${outcomeText}</span></td>
        <td>${(r.trust_before * 100).toFixed(1)}%</td>
        <td>${(r.trust_after * 100).toFixed(1)}% <span class="${arrowClass}">${arrow}</span></td>
      </tr>
    `;
  }

  html += "</tbody></table>";

  // Final rankings
  html += `
    <h3 class="final-title">Final Trust Rankings</h3>
    <table class="sim-table">
      <thead><tr><th>#</th><th>Agent</th><th>Trust Score</th><th>Total Runs</th></tr></thead>
      <tbody>
  `;
  data.final_agents.forEach((a, i) => {
    html += `
      <tr>
        <td>${i + 1}</td>
        <td>${esc(a.agent_name)} <span class="agent-id-small">${esc(a.agent_id)}</span></td>
        <td><strong>${(a.success_rate * 100).toFixed(1)}%</strong></td>
        <td>${a.total_runs}</td>
      </tr>
    `;
  });
  html += "</tbody></table>";

  el.innerHTML = html;
  section.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

// --- Reset ---
async function resetAll() {
  try {
    const res = await fetch(API + "/api/reset", { method: "POST" });
    if (!res.ok) throw new Error("Reset failed");
    document.getElementById("results-section").style.display = "none";
    loadAgents();
  } catch (err) {
    console.error("Reset error:", err);
  }
}

// --- Helpers ---
function esc(str) {
  if (str == null) return "";
  const div = document.createElement("div");
  div.textContent = String(str);
  return div.innerHTML;
}
