/**
 * FleetScale — Dashboard Controller, WebSockets & Heartbeat Simulator
 */

const API = "";

// ── DOM References ────────────────────────────────────────────
const navLanding       = document.getElementById("nav-landing");
const navDashboard     = document.getElementById("nav-dashboard");
const landingView      = document.getElementById("landing-view");
const dashboardView    = document.getElementById("dashboard-view");
const btnLaunchDash    = document.getElementById("btn-launch-dashboard");

const treeContainer    = document.getElementById("tree-container");
const nodeSelect       = document.getElementById("select-node");
const agentSelect      = document.getElementById("select-agent");
const btnLock          = document.getElementById("btn-lock");
const btnUnlock        = document.getElementById("btn-unlock");
const btnUpgrade       = document.getElementById("btn-upgrade");
const btnRefresh       = document.getElementById("btn-refresh");

const btnSendHb        = document.getElementById("btn-send-hb");
const btnSimCrash      = document.getElementById("btn-sim-crash");
const chkAutoHb        = document.getElementById("chk-auto-hb");
const wsStatusText     = document.getElementById("ws-status-text");

const toast            = document.getElementById("response-toast");
const toastIcon        = document.getElementById("toast-icon");
const toastMsg         = document.getElementById("toast-msg");
const auditList        = document.getElementById("audit-list");
const auditCount       = document.getElementById("audit-count");

// ── State ─────────────────────────────────────────────────────
let currentTree  = null;
let selectedNode = null;
let ws           = null;
let heartbeatInterval = null;

// ── Initialization ────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
    setupTabNavigation();
    setupWebSocket();
    loadAll();

    btnLock.addEventListener("click", () => doAction("lock"));
    btnUnlock.addEventListener("click", () => doAction("unlock"));
    btnUpgrade.addEventListener("click", () => doAction("upgrade"));
    btnRefresh.addEventListener("click", loadAll);

    if (btnSendHb) btnSendHb.addEventListener("click", sendManualHeartbeat);
    if (btnSimCrash) btnSimCrash.addEventListener("click", simulateBotCrash);

    // Start Auto-Heartbeat pulse loop (every 10s)
    startAutoHeartbeatLoop();
});

// ── Navigation Handler ────────────────────────────────────────
function setupTabNavigation() {
    navLanding.addEventListener("click", () => switchView("landing"));
    navDashboard.addEventListener("click", () => switchView("dashboard"));
    if (btnLaunchDash) {
        btnLaunchDash.addEventListener("click", () => switchView("dashboard"));
    }
}

function switchView(viewName) {
    if (viewName === "landing") {
        navLanding.classList.add("active");
        navDashboard.classList.remove("active");
        landingView.classList.add("active");
        dashboardView.classList.remove("active");
    } else {
        navDashboard.classList.add("active");
        navLanding.classList.remove("active");
        dashboardView.classList.add("active");
        landingView.classList.remove("active");
        if (currentTree) {
            renderTree(currentTree);
        }
    }
}

// ── WebSockets Stream ─────────────────────────────────────────
function setupWebSocket() {
    const protocol = location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl    = `${protocol}//${location.host}/ws/events`;

    try {
        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
            if (wsStatusText) wsStatusText.textContent = "WebSocket Active";
        };

        ws.onmessage = (event) => {
            const msg = JSON.parse(event.data);

            if (msg.tree) {
                currentTree = msg.tree;
                renderTree(currentTree);
            }
            if (msg.audit) {
                renderAudit(msg.audit);
            }

            if (msg.type === "LEASE_EXPIRED") {
                showToast(false, `⚠ Lease Expired: ${msg.detail.message}`);
            }
        };

        ws.onclose = () => {
            if (wsStatusText) wsStatusText.textContent = "WS Reconnecting...";
            setTimeout(setupWebSocket, 3000);
        };

        ws.onerror = () => {
            if (wsStatusText) wsStatusText.textContent = "WS Offline";
        };
    } catch (e) {
        if (wsStatusText) wsStatusText.textContent = "WS Unsupported";
    }
}

// ── Data Fetching ─────────────────────────────────────────────
async function loadAll() {
    await Promise.all([loadTree(), loadAudit()]);
}

async function loadTree() {
    try {
        const res  = await fetch(`${API}/api/v1/resource/status`);
        const data = await res.json();
        if (data.success) {
            currentTree = data.data.tree;
            renderTree(currentTree);
            populateNodeSelect(data.data.nodes);
        }
    } catch (err) {
        treeContainer.innerHTML = `<div class="tree-loading">⚠ Unable to connect to arbiter engine</div>`;
    }
}

// ── Tree Rendering ────────────────────────────────────────────
function renderTree(node) {
    treeContainer.innerHTML = "";
    const ul = buildTreeDOM(node);
    treeContainer.appendChild(ul);
}

function buildTreeDOM(node) {
    const ul = document.createElement("ul");
    ul.className = "tree-level";

    const li = document.createElement("li");
    li.className = "tree-node";

    const card = document.createElement("div");
    card.className = "node-card";
    card.dataset.nodeId = node.id;

    if (node.is_locked) {
        card.classList.add("state-locked");
    } else if (node.locked_descendant_count > 0) {
        card.classList.add("state-partial");
    } else {
        card.classList.add("state-free");
    }

    if (selectedNode === node.id) {
        card.classList.add("selected");
    }

    const dot = document.createElement("span");
    dot.className = "node-status-dot";
    card.appendChild(dot);

    const info = document.createElement("div");
    info.className = "node-info";

    const name = document.createElement("span");
    name.className = "node-name";
    name.textContent = node.name;

    const type = document.createElement("span");
    type.className = "node-type";
    type.textContent = node.type;

    info.appendChild(name);
    info.appendChild(type);
    card.appendChild(info);

    // Agent Ownership Badge & TTL Countdown Badge
    if (node.is_locked && node.locked_by) {
        const badge = document.createElement("span");
        badge.className = "node-agent-badge";
        badge.textContent = node.locked_by;
        card.appendChild(badge);

        if (node.ttl_remaining > 0) {
            const ttlBadge = document.createElement("span");
            ttlBadge.className = "node-ttl-badge";
            ttlBadge.textContent = `${node.ttl_remaining}s`;
            card.appendChild(ttlBadge);
        }
    }

    card.addEventListener("click", (e) => {
        e.stopPropagation();
        selectedNode = node.id;
        nodeSelect.value = node.id;
        renderTree(currentTree);
    });

    li.appendChild(card);

    if (node.children && node.children.length > 0) {
        const childUl = document.createElement("ul");
        childUl.className = "tree-level";
        for (const child of node.children) {
            const childLi = buildTreeDOM(child);
            childUl.appendChild(childLi.firstChild);
        }
        li.appendChild(childUl);
    }

    ul.appendChild(li);
    return ul;
}

function populateNodeSelect(nodes) {
    const currentVal = nodeSelect.value;
    nodeSelect.innerHTML = "";
    for (const n of nodes) {
        const opt = document.createElement("option");
        opt.value = n.id;
        opt.textContent = `${n.name} (${n.type})`;
        nodeSelect.appendChild(opt);
    }
    if (currentVal && nodes.some(n => n.id === currentVal)) {
        nodeSelect.value = currentVal;
    }
}

// ── Action Handlers ───────────────────────────────────────────
async function doAction(action) {
    const agentId = agentSelect.value;
    const nodeId  = nodeSelect.value;

    if (!nodeId) {
        showToast(false, "Please select a target spatial node.");
        return;
    }

    let url, body;
    if (action === "lock") {
        url  = `${API}/api/v1/resource/lock`;
        body = { node_id: nodeId, agent_id: agentId, ttl_seconds: 30 };
    } else if (action === "unlock") {
        url  = `${API}/api/v1/resource/unlock`;
        body = { node_id: nodeId, agent_id: agentId };
    } else if (action === "upgrade") {
        url  = `${API}/api/v1/resource/upgrade`;
        body = { parent_id: nodeId, agent_id: agentId };
    }

    try {
        const res  = await fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        });
        const data = await res.json();
        showToast(data.success, data.message || data.detail);
        await loadAll();
    } catch (err) {
        showToast(false, "Network error: unable to contact backend API.");
    }
}

// ── Heartbeat & Crash Simulator Handlers ──────────────────────
async function sendManualHeartbeat() {
    const agentId = agentSelect.value;
    const nodeId  = nodeSelect.value;

    if (!nodeId) {
        showToast(false, "Select a target node to send heartbeat.");
        return;
    }

    try {
        const res = await fetch(`${API}/api/v1/resource/heartbeat`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ node_id: nodeId, agent_id: agentId, ttl_seconds: 30 }),
        });
        const data = await res.json();
        showToast(data.success, data.message || data.detail);
        await loadAll();
    } catch (err) {
        showToast(false, "Heartbeat failed.");
    }
}

function simulateBotCrash() {
    chkAutoHb.checked = false;
    showToast(false, "🚨 Bot Crash Simulated! Auto-heartbeat stopped. Watch lock expire in 30 seconds!");
}

function startAutoHeartbeatLoop() {
    if (heartbeatInterval) clearInterval(heartbeatInterval);

    heartbeatInterval = setInterval(async () => {
        if (!chkAutoHb || !chkAutoHb.checked || !currentTree) return;

        // Collect all locked nodes owned by agents and send heartbeats
        const lockedNodes = getLockedNodes(currentTree);
        for (const n of lockedNodes) {
            try {
                await fetch(`${API}/api/v1/resource/heartbeat`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ node_id: n.id, agent_id: n.locked_by, ttl_seconds: 30 }),
                });
            } catch (e) {
                // Ignore
            }
        }
    }, 10000); // 10s heartbeat pulse
}

function getLockedNodes(node) {
    let result = [];
    if (node.is_locked && node.locked_by) {
        result.push(node);
    }
    if (node.children) {
        for (const child of node.children) {
            result = result.concat(getLockedNodes(child));
        }
    }
    return result;
}

// ── Feedback Toast ────────────────────────────────────────────
function showToast(success, message) {
    toast.classList.remove("hidden", "success", "error");
    toast.classList.add(success ? "success" : "error");
    toastIcon.textContent = success ? "✓" : "✕";
    toastMsg.textContent  = message;

    clearTimeout(toast._timer);
    toast._timer = setTimeout(() => toast.classList.add("hidden"), 5000);
}

// ── Audit Trail Ledger ────────────────────────────────────────
async function loadAudit() {
    try {
        const res  = await fetch(`${API}/api/v1/audit`);
        const data = await res.json();
        if (data.success) {
            renderAudit(data.data.log);
        }
    } catch (err) {
        // Silently handle
    }
}

function renderAudit(log) {
    auditCount.textContent = log.length;
    if (log.length === 0) {
        auditList.innerHTML = `<div class="audit-empty">No transactions recorded yet.</div>`;
        return;
    }

    auditList.innerHTML = "";
    const reversed = [...log].reverse();

    for (const entry of reversed) {
        const el = document.createElement("div");
        el.className = `audit-item ${entry.success ? "success" : "fail"}`;

        const headerLine = document.createElement("div");
        headerLine.className = "audit-header-line";

        const badge = document.createElement("span");
        badge.className = `audit-badge ${entry.action}`;
        badge.textContent = entry.action;

        const time = document.createElement("span");
        time.className = "audit-timestamp";
        time.textContent = formatTime(entry.timestamp);

        headerLine.appendChild(badge);
        headerLine.appendChild(time);

        const text = document.createElement("div");
        text.className = "audit-text";
        text.innerHTML = `<span class="audit-agent">${entry.agent_id}</span> &rarr; ${entry.node_id}<br><span style="color:var(--text-muted); font-size:0.74rem;">${entry.detail}</span>`;

        el.appendChild(headerLine);
        el.appendChild(text);

        auditList.appendChild(el);
    }
}

function formatTime(isoStr) {
    try {
        const d = new Date(isoStr);
        return d.toLocaleTimeString("en-US", { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" });
    } catch {
        return isoStr;
    }
}
