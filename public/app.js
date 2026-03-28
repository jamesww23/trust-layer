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

// --- Agent List (self-presenting with skill.md) ---
function renderAgentList(agents) {
  const el = document.getElementById("agent-list");
  if (!agents || agents.length === 0) {
    el.innerHTML = '<p class="empty-state">No agents registered.</p>';
    return;
  }
  el.innerHTML = agents.map(a => {
    const skillHtml = renderSkillMd(a.skill_md);
    return `
      <div class="agent-card">
        <div class="agent-card-header">
          <div>
            <span class="agent-name">${esc(a.agent_name)}</span>
            <span class="agent-id">${esc(a.agent_id)}</span>
          </div>
          <div class="agent-trust-badge">
            <span class="trust-value">${(a.success_rate * 100).toFixed(1)}%</span>
            <span class="trust-label">trust</span>
          </div>
        </div>
        <div class="agent-skill-md">${skillHtml}</div>
        <div class="agent-stats">
          <span class="stat">Interactions: <strong>${a.total_runs}</strong></span>
        </div>
      </div>
    `;
  }).join("");
}

// --- Simple markdown-to-HTML for skill_md ---
function renderSkillMd(md) {
  if (!md) return "";
  return esc(md)
    .replace(/^# (.+)$/gm, '')  // skip h1 (already shown as agent name)
    .replace(/^## (.+)$/gm, '<div class="skill-heading">$1</div>')
    .replace(/^- (.+)$/gm, '<div class="skill-item">$1</div>')
    .replace(/\n\n+/g, '<br>')
    .replace(/\n/g, '')
    .trim();
}

// --- Rankings Sidebar (trust + popularity) ---
function renderRankings(agents) {
  const el = document.getElementById("rankings-body");
  if (!agents || agents.length === 0) {
    el.innerHTML = '<p class="empty-state">No agents yet</p>';
    return;
  }
  const sorted = [...agents].sort((a, b) => b.success_rate - a.success_rate || b.total_runs - a.total_runs);
  const maxRuns = Math.max(...sorted.map(a => a.total_runs), 1);

  el.innerHTML = sorted.map((a, i) => {
    const popularity = a.total_runs > 0 ? Math.round((a.total_runs / maxRuns) * 100) : 0;
    const medal = i === 0 ? ' medal' : '';
    return `
      <div class="rank-row">
        <span class="rank-num ${i < 3 ? 'top' : ''}">${i + 1}</span>
        <div class="rank-info">
          <span class="rank-name">${esc(a.agent_name)}</span>
          <div class="rank-bar-container">
            <div class="rank-bar" style="width:${popularity}%"></div>
          </div>
          <span class="rank-pop">${a.total_runs} interactions</span>
        </div>
        <span class="rank-score${medal}">${(a.success_rate * 100).toFixed(1)}%</span>
      </div>
    `;
  }).join("");
}

// --- Run Simulation ---
async function runSimulation() {
  const btn = document.getElementById("sim-btn");
  const status = document.getElementById("sim-status");
  const rounds = parseInt(document.getElementById("sim-rounds").value) || 10;

  btn.disabled = true;
  status.textContent = "Simulating " + rounds + " rounds...";

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

  let html = `
    <div class="results-summary">${data.rounds} rounds completed</div>
    <table class="sim-table">
      <thead>
        <tr>
          <th>#</th>
          <th>Task</th>
          <th>Requester</th>
          <th>Provider</th>
          <th>Outcome</th>
          <th>Trust Change</th>
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
        <td class="task-cell">${esc(r.task || '')}</td>
        <td>${esc(r.requester)}</td>
        <td>${esc(r.provider)}</td>
        <td><span class="${outcomeClass}">${outcomeText}</span></td>
        <td>${(r.trust_before * 100).toFixed(1)}% <span class="${arrowClass}">${arrow}</span> ${(r.trust_after * 100).toFixed(1)}%</td>
      </tr>
    `;
  }
  html += "</tbody></table>";

  // Final rankings
  html += '<h3 class="final-title">Final Trust Rankings</h3>';
  html += '<table class="sim-table"><thead><tr><th>#</th><th>Agent</th><th>Trust Score</th><th>Interactions</th></tr></thead><tbody>';
  data.final_agents.forEach((a, i) => {
    html += `
      <tr class="${i === 0 ? 'winner-row' : ''}">
        <td>${i + 1}</td>
        <td><strong>${esc(a.agent_name)}</strong> <span class="agent-id-small">${esc(a.agent_id)}</span></td>
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
