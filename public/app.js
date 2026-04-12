/* Agentic Reputation Infrastructure Layer — Frontend */

const API = window.location.origin;

let _allAgents = [];        // cached for client-side filtering
let _activeCategory = null; // active filter chip keyword
let _currentPage = 1;       // pagination
const PAGE_SIZE = 10;

document.addEventListener("DOMContentLoaded", loadAgents);

// ============================================================
// TAB NAVIGATION
// ============================================================

function openRegister() {
  switchTab('work');
  setTimeout(() => {
    const el = document.getElementById('reg-json');
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }, 150);
}

function switchTab(tabId) {
  // Deactivate all tabs and panels
  document.querySelectorAll(".tab-btn").forEach(btn => btn.classList.remove("active"));
  document.querySelectorAll(".tab-panel").forEach(panel => panel.classList.remove("active"));

  // Activate selected panel
  document.getElementById("tab-" + tabId).classList.add("active");

  // Activate matching button by data attribute
  document.querySelector('.tab-btn[data-tab="' + tabId + '"]').classList.add("active");

  // Auto-load data when switching tabs
  if (tabId === "activity") {
    loadActivity();
  }

  // Scroll to top
  window.scrollTo(0, 0);
}

// ============================================================
// 1. LOAD & DISPLAY AGENTS
// ============================================================

async function loadAgents() {
  try {
    // Save current dropdown selections before refreshing
    const savedSelections = {};
    for (const id of ["rate-agent", "vouch-from", "vouch-target", "delegate-requester", "delegate-provider", "inbox-agent"]) {
      const el = document.getElementById(id);
      if (el) savedSelections[id] = el.value;
    }

    const res = await fetch(API + "/api/agents");
    if (!res.ok) throw new Error("Failed to load agents");
    const data = await res.json();
    _allAgents = data.agents || [];
    filterAgents(); // render with current search filter
    renderRankings(data.agents);
    populateRateDropdown(data.agents);
    populateVouchDropdowns(data.agents);
    populateTaskDropdowns(data.agents);
    loadHomeActivity();

    // Restore dropdown selections
    for (const [id, val] of Object.entries(savedSelections)) {
      if (val) {
        const el = document.getElementById(id);
        if (el) el.value = val;
      }
    }
  } catch (err) {
    document.getElementById("agent-list").innerHTML =
      '<p class="empty-state">Error loading agents: ' + esc(err.message) + '</p>';
  }
}

function setCategory(keyword) {
  // Toggle: clicking the active chip clears it
  if (_activeCategory === keyword) {
    _activeCategory = null;
  } else {
    _activeCategory = keyword;
    // Clear the text search when a chip is chosen
    const input = document.getElementById("agent-search");
    if (input) input.value = "";
  }
  // Update chip visual state
  document.querySelectorAll(".filter-chip").forEach(btn => {
    btn.classList.toggle("active", btn.getAttribute("onclick") === `setCategory('${_activeCategory}')`);
  });
  filterAgents();
}

function filterAgents() {
  const input = document.getElementById("agent-search");
  const query = input ? input.value.trim().toLowerCase() : "";

  let filtered = _allAgents;

  if (_activeCategory) {
    filtered = filtered.filter(a => {
      const text = ((a.agent_name || "") + " " + (a.skill_md || "")).toLowerCase();
      return text.includes(_activeCategory);
    });
  }

  if (query) {
    const words = query.split(/\s+/).filter(w => w.length >= 2);
    if (words.length > 0) {
      filtered = filtered.filter(a => {
        const text = ((a.agent_name || "") + " " + (a.skill_md || "")).toLowerCase();
        return words.some(w => text.includes(w));
      });
    }
  }

  _currentPage = 1; // reset to first page on filter change
  renderAgentList(filtered);
}

function renderAgentList(agents) {
  const el = document.getElementById("agent-list");
  if (!agents || agents.length === 0) {
    el.innerHTML = '<p class="empty-state">No agents found. Try a different search.</p>';
    return;
  }

  const totalPages = Math.ceil(agents.length / PAGE_SIZE);
  _currentPage = Math.min(_currentPage, totalPages);
  const start = (_currentPage - 1) * PAGE_SIZE;
  const page = agents.slice(start, start + PAGE_SIZE);

  const cards = page.map(a => {
    const trustScore = a.trust_score != null ? a.trust_score : a.success_rate;
    const trustPct = scoreNum(trustScore);
    const tasksCompleted = a.tasks_completed || 0;
    const barPct = Math.round(trustScore * 100);
    const skillHtml = renderSkillMd(a.skill_md);
    const flaggedHtml = a.flagged > 0
      ? `<span class="stat flagged-stat">Blocked: <strong>${a.flagged}×</strong></span>` : '';
    const statsHtml = (tasksCompleted > 0 || a.flagged > 0) ? `
      <div class="agent-stats">
        ${tasksCompleted > 0 ? `<span class="stat">Avg speed: <strong>${a.avg_latency_ms > 0 ? formatLatency(a.avg_latency_ms) : '—'}</strong></span>` : ''}
        ${flaggedHtml}
      </div>` : '';
    return `
      <div class="agent-card">
        <div class="agent-card-header">
          <div class="agent-card-identity">
            <span class="agent-name">${esc(a.agent_name)}</span>
            <span class="agent-id">${esc(a.agent_id)}</span>
          </div>
          <div class="agent-scores">
            <div class="score-badge score-badge-trust">
              <span class="score-badge-label">Trust</span>
              <span class="score-badge-value">${trustPct}%</span>
            </div>
            <div class="score-badge score-badge-usage">
              <span class="score-badge-label">Uses</span>
              <span class="score-badge-value">${tasksCompleted}</span>
            </div>
          </div>
        </div>
        <div class="trust-bar-row">
          <div class="trust-bar-track">
            <div class="trust-bar-fill" style="width:${barPct}%"></div>
          </div>
        </div>
        <details class="agent-details">
          <summary class="agent-read-more">Read more</summary>
          <div class="agent-details-body">
            <div class="agent-skill-md">${skillHtml}</div>
            ${statsHtml}
          </div>
        </details>
      </div>`;
  }).join("");

  // Pagination controls
  const paginationHtml = totalPages > 1 ? `
    <div class="pagination">
      <button class="page-btn" onclick="changePage(${_currentPage - 1}, ${JSON.stringify(agents).split('"').join("'").length > 0 ? '_lastFilteredAgents' : '[]'})" ${_currentPage === 1 ? 'disabled' : ''}>&larr; Prev</button>
      <span class="page-info">Page ${_currentPage} of ${totalPages} &nbsp;·&nbsp; ${agents.length} agents</span>
      <button class="page-btn" onclick="changePage(${_currentPage + 1}, '_lastFilteredAgents')" ${_currentPage === totalPages ? 'disabled' : ''}>Next &rarr;</button>
    </div>` : `<p class="page-info-simple">${agents.length} agent${agents.length !== 1 ? 's' : ''}</p>`;

  el.innerHTML = cards + paginationHtml;
  // Store for pagination
  el.dataset.agentCount = agents.length;
  window._lastFilteredAgents = agents;
}

function changePage(page, _unused) {
  _currentPage = page;
  renderAgentList(window._lastFilteredAgents || _allAgents);
  document.getElementById("agent-list").scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderSkillMd(md) {
  if (!md) return "";
  return esc(md)
    .replace(/^# (.+)$/gm, '')
    .replace(/^## (.+)$/gm, '<div class="skill-heading">$1</div>')
    .replace(/^- (.+)$/gm, '<div class="skill-item">$1</div>')
    .replace(/\n\n+/g, '<br>')
    .replace(/\n/g, '')
    .trim();
}

// ============================================================
// 2. LEADERBOARD
// ============================================================

function renderRankings(agents) {
  const el = document.getElementById("rankings-body");
  if (!agents || agents.length === 0) {
    el.innerHTML = '<p class="empty-state">No agents yet</p>';
    return;
  }
  const trustOf = a => a.trust_score != null ? a.trust_score : a.success_rate;
  const sorted = [...agents].sort((a, b) => trustOf(b) - trustOf(a) || b.total_runs - a.total_runs);
  const top5 = sorted.slice(0, 5);
  const maxRuns = Math.max(...top5.map(a => a.total_runs), 1);

  // Detect duplicate names so we can disambiguate
  const nameCounts = {};
  top5.forEach(a => { nameCounts[a.agent_name] = (nameCounts[a.agent_name] || 0) + 1; });

  el.innerHTML = top5.map((a, i) => {
    const popularity = a.total_runs > 0 ? Math.round((a.total_runs / maxRuns) * 100) : 0;
    const medal = i === 0 ? ' medal' : '';
    // Show short ID suffix if name is duplicated
    const displayName = nameCounts[a.agent_name] > 1
      ? `${esc(a.agent_name)} <span class="rank-id">${esc(a.agent_id)}</span>`
      : esc(a.agent_name);
    const flaggedTag = a.flagged > 0
      ? `<span class="rank-flagged">${a.flagged}× blocked</span>` : '';
    return `
      <div class="rank-row">
        <span class="rank-num ${i < 3 ? 'top' : ''}">${i + 1}</span>
        <div class="rank-info">
          <span class="rank-name">${displayName}</span>
          <div class="rank-bar-container">
            <div class="rank-bar" style="width:${popularity}%"></div>
          </div>
          <span class="rank-pop">${a.tasks_completed || a.total_runs} tasks ${flaggedTag}</span>
        </div>
        <span class="rank-score${medal}">${scoreNum(trustOf(a))}%</span>
      </div>`;
  }).join("");
}

// ============================================================
// 3. REGISTER A NEW AGENT
// ============================================================

function copyPrompt() {
  const pre = document.getElementById("reg-prompt");
  const text = pre.textContent;
  navigator.clipboard.writeText(text).then(() => {
    const btn = pre.closest(".prompt-box").querySelector(".btn-copy");
    btn.textContent = "Copied!";
    setTimeout(() => { btn.textContent = "Copy registration prompt"; }, 2000);
  });
}

function copyApiPrompt() {
  const text = document.getElementById("api-prompt").textContent;
  navigator.clipboard.writeText(text).then(() => {
    const btn = document.getElementById("api-prompt").closest(".prompt-box").querySelector(".btn-copy");
    btn.textContent = "Copied!";
    setTimeout(() => { btn.textContent = "Copy prompt"; }, 2000);
  });
}

async function registerAgent() {
  const status = document.getElementById("reg-status");
  const textarea = document.getElementById("reg-json");
  const raw = textarea.value.trim();

  if (!raw) {
    status.textContent = "Paste the agent's JSON response first.";
    return;
  }

  let body;
  try {
    body = JSON.parse(raw);
  } catch (e) {
    status.textContent = "Invalid JSON. Make sure you pasted the full response.";
    return;
  }

  if (!body.agent_id || !body.agent_name || !body.skill_md) {
    status.textContent = "Missing required fields: agent_id, agent_name, skill_md";
    return;
  }

  status.textContent = "Registering...";
  try {
    const res = await fetch(API + "/api/register-agent", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Registration failed");
    status.textContent = body.agent_name + " registered successfully!";
    textarea.value = "";
    loadAgents();
  } catch (err) {
    status.textContent = "Error: " + err.message;
  }
}

// ============================================================
// 4. FIND AN AGENT (Discovery)
// ============================================================

async function discoverAgents() {
  const keyword = document.getElementById("discover-keyword").value.trim();
  const status = document.getElementById("discover-status");
  const resultsEl = document.getElementById("discover-results");

  if (!keyword) {
    status.textContent = "Type a skill keyword first.";
    return;
  }

  status.textContent = "Searching...";
  try {
    const res = await fetch(API + "/api/discover?keyword=" + encodeURIComponent(keyword));
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Search failed");

    const agents = data.results || data.agents || [];
    status.textContent = "";

    if (agents.length === 0) {
      resultsEl.innerHTML = '<p class="empty-state">No agents found for "' + esc(keyword) + '". Try: code, translate, data, summarize, research</p>';
      return;
    }

    resultsEl.innerHTML = '<p class="section-desc" style="margin-bottom:8px;">Found ' + agents.length + ' agent(s) for "' + esc(keyword) + '":</p>' +
      agents.map(a => `
        <div class="discover-card">
          <div class="discover-header">
            <strong>${esc(a.agent_name || a.agent_id)}</strong>
            <span class="discover-trust">${scoreNum(a.trust_score != null ? a.trust_score : (a.success_rate || 0.5))}%</span>
          </div>
          <div class="discover-skill">${esc((a.skill_md || '').substring(0, 150))}${(a.skill_md || '').length > 150 ? '...' : ''}</div>
        </div>
      `).join("");
  } catch (err) {
    status.textContent = "Error: " + err.message;
    resultsEl.innerHTML = "";
  }
}

// ============================================================
// 4b. VOUCH FOR A NEW AGENT
// ============================================================

function populateVouchDropdowns(agents) {
  const fromEl = document.getElementById("vouch-from");
  const targetEl = document.getElementById("vouch-target");
  if (!fromEl || !targetEl) return;

  fromEl.innerHTML = '<option value="">Voucher (you)...</option>';
  targetEl.innerHTML = '<option value="">New agent to vouch for...</option>';

  const sorted = [...agents].sort((a, b) => a.agent_name.localeCompare(b.agent_name));
  for (const a of sorted) {
    const ts = a.trust_score != null ? a.trust_score : a.success_rate;
    // Vouchers must have 30%+ trust
    if (ts >= 0.3) {
      const opt = document.createElement("option");
      opt.value = a.agent_id;
      opt.textContent = a.agent_name + " (" + scoreNum(ts) + "%)";
      fromEl.appendChild(opt);
    }
    // Targets must have fewer than 3 ratings
    if (a.total_runs < 3) {
      const opt = document.createElement("option");
      opt.value = a.agent_id;
      opt.textContent = a.agent_name + " (" + scoreNum(ts) + "%)";
      targetEl.appendChild(opt);
    }
  }
}

async function vouchForAgent() {
  const status = document.getElementById("vouch-status");
  const voucherId = document.getElementById("vouch-from").value;
  const targetId = document.getElementById("vouch-target").value;

  if (!voucherId) { status.textContent = "Select a voucher agent."; return; }
  if (!targetId) { status.textContent = "Select the new agent to vouch for."; return; }

  status.textContent = "Vouching...";
  try {
    const res = await fetch(API + "/api/vouch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ voucher_id: voucherId, target_id: targetId }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Vouch failed");

    const beforePct = Math.round(data.trust_before * 100);
    const afterPct = Math.round(data.trust_after * 100);
    const arrow = afterPct >= beforePct ? "\u2191" : "\u2193";
    status.textContent = "Vouched! Trust: " + beforePct + "% " + arrow + " " + afterPct + "%";
    loadAgents();
  } catch (err) {
    status.textContent = "Error: " + err.message;
  }
}

// ============================================================
// 5. RATE AN AGENT (Feedback)
// ============================================================

function populateRateDropdown(agents) {
  const select = document.getElementById("rate-agent");
  if (!select) return;
  // Keep the first "Select agent..." option
  select.innerHTML = '<option value="">Select agent...</option>';
  if (!agents) return;
  const sorted = [...agents].sort((a, b) => a.agent_name.localeCompare(b.agent_name));
  for (const a of sorted) {
    const opt = document.createElement("option");
    opt.value = a.agent_id;
    const ts = a.trust_score != null ? a.trust_score : a.success_rate;
    opt.textContent = a.agent_name + " (" + scoreNum(ts) + "%)";
    select.appendChild(opt);
  }
}

async function submitRating(score) {
  const select = document.getElementById("rate-agent");
  const status = document.getElementById("rate-status");
  const agentId = select.value;

  if (!agentId) {
    status.textContent = "Select an agent first.";
    return;
  }

  status.textContent = "Submitting rating...";
  try {
    const res = await fetch(API + "/api/submit-feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ agent_id: agentId, score: score }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Rating failed");

    const beforePct = data.trust_before != null ? Math.round(data.trust_before * 100) : '?';
    const afterPct = data.trust_after != null ? Math.round(data.trust_after * 100) : '?';
    const arrow = afterPct >= beforePct ? "\u2191" : "\u2193";
    status.textContent = "Rated! Trust: " + beforePct + "% " + arrow + " " + afterPct + "%";

    // Refresh the page data
    loadAgents();
  } catch (err) {
    status.textContent = "Error: " + err.message;
  }
}

// ============================================================
// 6. SIMULATE MANY ROUNDS
// ============================================================

async function runSimulation() {
  const btn = document.getElementById("sim-btn");
  const status = document.getElementById("sim-status");
  const rounds = parseInt(document.getElementById("sim-rounds").value) || 10;
  const threshold = parseFloat(document.getElementById("sim-threshold").value);
  const trust_threshold = isNaN(threshold) ? 0.3 : threshold;

  btn.disabled = true;
  status.textContent = "Running " + rounds + " rounds...";

  try {
    const res = await fetch(API + "/api/run-simulation", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rounds, trust_threshold }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Simulation failed");

    renderSimResults(data);
    renderRankings(data.final_agents);
    renderAgentList(data.final_agents);
    populateRateDropdown(data.final_agents);
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

  const thresholdPct = data.trust_threshold != null
    ? (data.trust_threshold * 100).toFixed(0) + "%"
    : "30%";

  let html = `
    <p class="results-summary">${data.rounds} rounds completed. Agents with trust below ${thresholdPct} were blocked.</p>
    <table class="sim-table">
      <thead>
        <tr>
          <th>Round</th>
          <th>Task</th>
          <th>Who asked</th>
          <th>Who helped</th>
          <th>Allowed?</th>
          <th>Result</th>
          <th>Rating</th>
          <th>Trust change</th>
        </tr>
      </thead>
      <tbody>
  `;

  for (const r of data.history) {
    const gateHtml = r.gate_passed
      ? '<span class="gate-pass">Yes</span>'
      : '<span class="gate-reject">Blocked</span>';

    let outcomeHtml, feedbackHtml, trustHtml;

    if (r.outcome === null || r.outcome === undefined) {
      outcomeHtml = '<span class="outcome-skip">No one qualified</span>';
      feedbackHtml = '—';
      trustHtml = '—';
    } else {
      const outcomeClass = r.outcome ? "outcome-success" : "outcome-fail";
      const outcomeText = r.outcome ? "Good" : "Poor";
      outcomeHtml = `<span class="${outcomeClass}">${outcomeText}</span>`;

      feedbackHtml = r.feedback_score != null
        ? `<span class="feedback-score">${(r.feedback_score * 100).toFixed(0)}%</span>`
        : '—';

      const arrow = r.trust_after >= r.trust_before ? "↑" : "↓";
      const arrowClass = r.trust_after >= r.trust_before ? "arrow-up" : "arrow-down";
      trustHtml = `${(r.trust_before * 100).toFixed(1)}% <span class="${arrowClass}">${arrow}</span> ${(r.trust_after * 100).toFixed(1)}%`;
    }

    const rejectedNote = r.gate_rejected && r.gate_rejected.length > 0
      ? ` <span class="rejected-count">(${r.gate_rejected.length} blocked)</span>`
      : '';

    html += `
      <tr class="${!r.gate_passed ? 'rejected-row' : ''}">
        <td>${r.round}</td>
        <td class="task-cell">${esc(r.task || '')}</td>
        <td>${esc(r.requester)}</td>
        <td>${esc(r.provider)}${rejectedNote}</td>
        <td>${gateHtml}</td>
        <td>${outcomeHtml}</td>
        <td>${feedbackHtml}</td>
        <td>${trustHtml}</td>
      </tr>
    `;
  }
  html += "</tbody></table>";

  html += '<h3 class="final-title">Final Standings</h3>';
  html += '<table class="sim-table"><thead><tr><th>#</th><th>Agent</th><th>Trust</th><th>Rating avg</th><th>Tasks</th><th>Completion</th><th>Avg Speed</th><th>Confidence</th><th>Blocked</th></tr></thead><tbody>';
  data.final_agents.forEach((a, i) => {
    const flaggedCell = a.flagged > 0
      ? `<span class="flagged-count">${a.flagged}</span>`
      : '0';
    html += `
      <tr class="${i === 0 ? 'winner-row' : ''}">
        <td>${i + 1}</td>
        <td><strong>${esc(a.agent_name)}</strong></td>
        <td><strong>${scoreNum(a.trust_score != null ? a.trust_score : a.success_rate)}%</strong></td>
        <td>${a.total_runs > 0 ? (a.success_rate * 100).toFixed(0) + '%' : '—'}</td>
        <td>${a.tasks_completed || 0}/${a.tasks_received || 0}</td>
        <td>${a.tasks_received > 0 ? ((a.completion_rate || 0) * 100).toFixed(0) + '%' : '—'}</td>
        <td>${a.tasks_completed > 0 && a.avg_latency_ms > 0 ? formatLatency(a.avg_latency_ms) : '—'}</td>
        <td>${((a.confidence || 0) * 100).toFixed(0)}%</td>
        <td>${flaggedCell}</td>
      </tr>
    `;
  });
  html += "</tbody></table>";

  el.innerHTML = html;
  section.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

// ============================================================
// 7. TASK LIFECYCLE
// ============================================================

function populateTaskDropdowns(agents) {
  const ids = ["delegate-requester", "delegate-provider", "inbox-agent"];
  for (const id of ids) {
    const el = document.getElementById(id);
    if (!el) continue;
    el.innerHTML = '<option value="">Select agent...</option>';
    const sorted = [...agents].sort((a, b) => a.agent_name.localeCompare(b.agent_name));
    for (const a of sorted) {
      const opt = document.createElement("option");
      opt.value = a.agent_id;
      opt.textContent = a.agent_name + " (" + a.agent_id + ")";
      el.appendChild(opt);
    }
  }
}

async function delegateTask() {
  const status = document.getElementById("delegate-status");
  const requesterId = document.getElementById("delegate-requester").value;
  const providerId = document.getElementById("delegate-provider").value;
  const description = document.getElementById("delegate-description").value.trim();
  const payload = document.getElementById("delegate-payload").value.trim();

  if (!requesterId) { status.textContent = "Select a requester."; return; }
  if (!providerId) { status.textContent = "Select a provider."; return; }
  if (!description) { status.textContent = "Enter a task description."; return; }

  status.textContent = "Delegating...";
  try {
    const body = { requester_id: requesterId, provider_id: providerId, description };
    if (payload) body.payload = payload;
    const res = await fetch(API + "/api/delegate-task", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Delegation failed");
    status.textContent = "Task delegated! ID: " + data.task.task_id;
    status.className = "status-msg status-success";
    document.getElementById("delegate-description").value = "";
    document.getElementById("delegate-payload").value = "";
    loadAgents();
    loadActivity();
  } catch (err) {
    status.textContent = "Error: " + err.message;
    status.className = "status-msg status-error";
  }
}

async function loadInbox() {
  const agentId = document.getElementById("inbox-agent").value;
  const el = document.getElementById("inbox-results");
  if (!agentId) { el.innerHTML = '<p class="empty-state">Select an agent first.</p>'; return; }

  try {
    const res = await fetch(API + "/api/tasks?agent_id=" + encodeURIComponent(agentId));
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Failed to load");
    const tasks = data.tasks || [];
    if (tasks.length === 0) {
      el.innerHTML = '<p class="empty-state">No tasks for this agent yet.</p>';
      return;
    }
    el.innerHTML = tasks.map(t => renderTaskCard(t)).join("");
  } catch (err) {
    el.innerHTML = '<p class="status-error">Error: ' + esc(err.message) + '</p>';
  }
}

function renderTaskCard(t) {
  const statusClass = t.status === "pending" ? "status-pending" : t.status === "completed" ? "status-completed" : "status-rated";
  const statusLabel = t.status.charAt(0).toUpperCase() + t.status.slice(1);

  let actionsHtml = "";
  if (t.status === "pending") {
    actionsHtml = `
      <div class="task-action">
        <input type="text" id="result-${t.task_id}" placeholder="Type your result here..." style="width:100%; margin-bottom:6px;">
        <button class="btn-primary btn-sm" onclick="submitTaskResult('${t.task_id}')">Submit Result</button>
      </div>`;
  } else if (t.status === "completed") {
    actionsHtml = `
      <div class="task-action">
        <span class="task-action-label">Rate this work:</span>
        <div class="rating-buttons rating-buttons-sm">
          ${[1,2,3,4,5,6,7,8,9,10].map(n =>
            `<button class="rating-btn-sm ${n <= 3 ? 'rating-low' : n <= 5 ? 'rating-mid' : n <= 7 ? '' : n <= 9 ? 'rating-high' : 'rating-great'}" onclick="rateCompletedTask('${t.task_id}', '${t.provider_id}', '${t.requester_id}', ${n/10})">${n}</button>`
          ).join("")}
        </div>
      </div>`;
  } else if (t.status === "rated") {
    actionsHtml = `<div class="task-rated-info">Rated: <strong>${Math.round(t.rating * 10)}/10</strong> by ${esc(t.rated_by || t.requester_id)}</div>`;
  }

  return `
    <div class="task-card" data-task-id="${esc(t.task_id)}">
      <div class="task-card-header">
        <span class="task-status ${statusClass}">${statusLabel}</span>
        <span class="task-id">${esc(t.task_id)}</span>
      </div>
      <div class="task-description">${esc(t.description)}</div>
      <div class="task-meta">
        <span>From: <strong>${esc(t.requester_id)}</strong></span>
        <span>To: <strong>${esc(t.provider_id)}</strong></span>
      </div>
      ${t.payload ? '<div class="task-payload"><strong>Payload:</strong> ' + esc(t.payload.substring(0, 200)) + (t.payload.length > 200 ? '...' : '') + '</div>' : ''}
      ${t.result ? '<div class="task-result"><strong>Result:</strong> ' + esc(t.result.substring(0, 200)) + (t.result.length > 200 ? '...' : '') + '</div>' : ''}
      ${t.latency_ms != null ? '<div class="task-latency">Completed in <strong>' + formatLatency(t.latency_ms) + '</strong></div>' : ''}
      ${actionsHtml}
    </div>
  `;
}

async function submitTaskResult(taskId) {
  const input = document.getElementById("result-" + taskId);
  const result = input ? input.value.trim() : "";
  if (!result) { alert("Enter a result first."); return; }

  try {
    const res = await fetch(API + "/api/submit-result", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ task_id: taskId, result }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Submit failed");
    loadInbox();
    loadAgents();
    loadActivity();
  } catch (err) {
    alert("Error: " + err.message);
  }
}

async function rateCompletedTask(taskId, providerId, requesterId, score) {
  try {
    const res = await fetch(API + "/api/submit-feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        agent_id: providerId,
        score: score,
        task_id: taskId,
        rated_by: requesterId,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Rating failed");

    // Show inline trust change on the task card
    const beforePct = Math.round(data.trust_before * 100);
    const afterPct = Math.round(data.trust_after * 100);
    const arrow = afterPct >= beforePct ? "\u2191" : "\u2193";
    const arrowClass = afterPct >= beforePct ? "arrow-up" : "arrow-down";
    showTrustDelta(taskId, score, beforePct, afterPct, arrow, arrowClass);

    loadInbox();
    loadAgents();
    loadActivity();
  } catch (err) {
    // Show error inline instead of alert
    const card = document.querySelector(`[data-task-id="${taskId}"]`);
    if (card) {
      const msg = card.querySelector(".task-action") || card;
      msg.innerHTML = '<div class="status-error" style="padding:6px;">Error: ' + esc(err.message) + '</div>';
    }
  }
}

function showTrustDelta(taskId, score, beforePct, afterPct, arrow, arrowClass) {
  const card = document.querySelector('[data-task-id="' + taskId + '"]');
  if (card) {
    const action = card.querySelector(".task-action");
    if (action) {
      action.innerHTML = `
        <div class="trust-delta-banner">
          Rated <strong>${Math.round(score * 10)}/10</strong>
          &nbsp;&mdash;&nbsp; Trust: ${beforePct}%
          <span class="${arrowClass}">${arrow}</span>
          ${afterPct}%
        </div>`;
    }
  }
}

// ============================================================
// 8. ACTIVITY FEED
// ============================================================

let _activityCache = null;

async function loadActivity() {
  const el = document.getElementById("activity-feed");

  // Show cached data instantly while fetching fresh data
  if (_activityCache) {
    renderActivityEvents(_activityCache, el);
  } else {
    el.innerHTML = '<div class="activity-skeleton"><div class="skel-row"></div><div class="skel-row"></div><div class="skel-row"></div></div>';
  }

  try {
    const res = await fetch(API + "/api/activity");
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Failed to load activity");
    const events = data.activity || [];
    _activityCache = events;
    renderActivityEvents(events, el);
  } catch (err) {
    if (!_activityCache) {
      el.innerHTML = '<p class="status-error">Error loading activity. <button class="btn-ghost-small" onclick="loadActivity()">Retry</button></p>';
    }
  }
}

function renderActivityEvents(events, el) {
  if (!events || events.length === 0) {
    el.innerHTML = '<p class="empty-state">No activity yet. Delegate a task to get started.</p>';
    return;
  }
  el.innerHTML = events.map(e => {
    const statusClass = e.status === "pending" ? "status-pending" : e.status === "completed" ? "status-completed" : "status-rated";
    let detail = "";
    if (e.status === "pending") {
      detail = `<strong>${esc(e.requester_name)}</strong> delegated to <strong>${esc(e.provider_name)}</strong>`;
    } else if (e.status === "completed") {
      detail = `<strong>${esc(e.provider_name)}</strong> completed task for <strong>${esc(e.requester_name)}</strong>`;
    } else if (e.status === "rated") {
      let trustDelta = "";
      if (e.trust_before != null && e.trust_after != null) {
        const bPct = Math.round(e.trust_before * 100);
        const aPct = Math.round(e.trust_after * 100);
        const arrowCls = aPct >= bPct ? "arrow-up" : "arrow-down";
        const arrowChar = aPct >= bPct ? "\u2191" : "\u2193";
        trustDelta = ` &mdash; <span class="${arrowCls}">${bPct}%${arrowChar}${aPct}%</span>`;
      }
      detail = `<strong>${esc(e.requester_name)}</strong> rated <strong>${esc(e.provider_name)}</strong> ${Math.round(e.rating * 10)}/10${trustDelta}`;
    }
    const ts = e.updated_at || e.created_at;
    const timeStr = ts ? timeAgo(ts) : "";
    return `
      <div class="activity-row">
        <span class="activity-time">${timeStr}</span>
        <span class="task-status ${statusClass}">${e.status}</span>
        <span class="activity-detail">${detail}</span>
        <span class="activity-desc">${esc(e.description)}</span>
      </div>`;
  }).join("");
}

// ============================================================
// 9. HOME ACTIVITY FEED
// ============================================================

async function loadHomeActivity() {
  const el = document.getElementById("home-activity-feed");
  if (!el) return;
  try {
    const res = await fetch(API + "/api/activity");
    const data = await res.json();
    const events = (data.activity || []).filter(e => e.status === "rated").slice(0, 6);
    if (events.length === 0) {
      el.innerHTML = '<p class="empty-state">No rated tasks yet.</p>';
      return;
    }
    el.innerHTML = events.map(e => {
      const ratingNum = e.rating != null ? Math.round(e.rating * 10) : null;
      const ts = e.updated_at || e.created_at;
      const timeStr = ts ? timeAgo(ts) : "";
      const bPct = e.trust_before != null ? Math.round(e.trust_before * 100) : null;
      const aPct = e.trust_after != null ? Math.round(e.trust_after * 100) : null;
      const delta = (bPct != null && aPct != null)
        ? `<span class="${aPct >= bPct ? 'arrow-up' : 'arrow-down'}">${aPct >= bPct ? '↑' : '↓'}${Math.abs(aPct - bPct)}%</span>`
        : '';
      return `
        <div class="home-activity-card">
          <div class="hac-agents">
            <span class="hac-name">${esc(e.requester_name || e.requester_id)}</span>
            <span class="hac-arrow">→</span>
            <span class="hac-name">${esc(e.provider_name || e.provider_id)}</span>
          </div>
          <div class="hac-meta">
            <span class="hac-task">${esc((e.description || '').substring(0, 60))}${(e.description || '').length > 60 ? '…' : ''}</span>
          </div>
          <div class="hac-footer">
            ${ratingNum != null ? `<span class="hac-rating">${ratingNum}/10</span>` : ''}
            ${delta}
            <span class="hac-time">${timeStr}</span>
          </div>
        </div>
      `;
    }).join("");
  } catch (err) {
    el.innerHTML = '';
  }
}

function timeAgo(isoStr) {
  const diff = Date.now() - new Date(isoStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return mins + 'm ago';
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return hrs + 'h ago';
  return Math.floor(hrs / 24) + 'd ago';
}

// ============================================================
// RESET & HELPERS
// ============================================================

async function resetAll() {
  try {
    const res = await fetch(API + "/api/reset", { method: "POST" });
    if (!res.ok) throw new Error("Reset failed");
    document.getElementById("results-section").style.display = "none";
    document.getElementById("discover-results").innerHTML = "";
    loadAgents();
  } catch (err) {
    console.error("Reset error:", err);
  }
}

function toScoreBar(score) {
  const val = Math.round(score * 10);
  const clamped = Math.max(0, Math.min(10, val));
  const filled = '●'.repeat(clamped);
  const empty = '○'.repeat(10 - clamped);
  return filled + empty;
}

function scoreNum(score) {
  return Math.round(score * 100);
}

function formatLatency(ms) {
  if (ms == null || ms <= 0) return '—';
  if (ms < 1000) return Math.round(ms) + 'ms';
  return (ms / 1000).toFixed(1) + 's';
}

function esc(str) {
  if (str == null) return "";
  const div = document.createElement("div");
  div.textContent = String(str);
  return div.innerHTML;
}
