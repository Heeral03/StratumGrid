/**
 * StratumGrid — Dashboard Controller, WebSockets, Heartbeat Simulator & 2D Warehouse Floor Canvas
 */

const API = "";

// ── DOM References ────────────────────────────────────────────
const navLanding       = document.getElementById("nav-landing");
const navDashboard     = document.getElementById("nav-dashboard");
const landingView      = document.getElementById("landing-view");
const dashboardView    = document.getElementById("dashboard-view");
const btnLaunchDash    = document.getElementById("btn-launch-dashboard");

const treeContainer    = document.getElementById("tree-container");
const canvasContainer  = document.getElementById("canvas-container");
const spatialViewport  = document.getElementById("spatial-viewport");
const canvas           = document.getElementById("warehouse-canvas");
const canvasTooltip    = document.getElementById("canvas-tooltip");
const ttTitle          = document.getElementById("tt-title");
const ttBody           = document.getElementById("tt-body");

const btnModeTree      = document.getElementById("btn-mode-tree");
const btnModeCanvas    = document.getElementById("btn-mode-canvas");
const btnModeSplit     = document.getElementById("btn-mode-split");

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
let currentTree       = null;
let selectedNode      = null;
let ws                = null;
let heartbeatInterval = null;
let canvasRenderer    = null;

// ── Initialization ────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
    setupTabNavigation();
    setupViewModeSwitcher();
    setupWebSocket();
    loadAll();

    // Initialize 2D Canvas Engine
    if (canvas) {
        canvasRenderer = new WarehouseCanvasRenderer(canvas);
        canvasRenderer.start();
    }

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
            if (canvasRenderer) canvasRenderer.updateTreeState(currentTree);
        }
    }
}

// ── View Mode Switcher (Tree | 2D Floor | Split) ──────────────
function setupViewModeSwitcher() {
    if (!btnModeTree || !btnModeCanvas || !btnModeSplit) return;

    btnModeTree.addEventListener("click", () => setViewMode("tree"));
    btnModeCanvas.addEventListener("click", () => setViewMode("canvas"));
    btnModeSplit.addEventListener("click", () => setViewMode("split"));
}

function setViewMode(mode) {
    btnModeTree.classList.remove("active");
    btnModeCanvas.classList.remove("active");
    btnModeSplit.classList.remove("active");

    treeContainer.classList.remove("active");
    canvasContainer.classList.remove("active");
    spatialViewport.classList.remove("split-mode");

    if (mode === "tree") {
        btnModeTree.classList.add("active");
        treeContainer.classList.add("active");
    } else if (mode === "canvas") {
        btnModeCanvas.classList.add("active");
        canvasContainer.classList.add("active");
    } else if (mode === "split") {
        btnModeSplit.classList.add("active");
        spatialViewport.classList.add("split-mode");
        treeContainer.classList.add("active");
        canvasContainer.classList.add("active");
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
                if (canvasRenderer) canvasRenderer.updateTreeState(currentTree);
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
            if (canvasRenderer) canvasRenderer.updateTreeState(currentTree);
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
        if (canvasRenderer) canvasRenderer.selectNode(node.id);
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

// ==============================================================================
// ── 2D WAREHOUSE FLOOR CANVAS RENDERER CLASS ──────────────────────────────────
// ==============================================================================

class WarehouseCanvasRenderer {
    constructor(canvasElement) {
        this.canvas  = canvasElement;
        this.ctx     = canvasElement.getContext("2d");
        this.treeMap = new Map();
        this.selectedId = null;
        this.hoveredId  = null;
        this.animFrame  = null;

        // Physical Spatial Node Coordinate Map (scaled to 840x540 canvas)
        this.regions = [
            // Facility Root Boundary
            { id: "warehouse-1", name: "Warehouse Facility 1", type: "FACILITY", x: 20, y: 20, w: 800, h: 500 },

            // Zone A (Left Hall)
            { id: "zone-A", name: "Zone A (Storage Hall A)", type: "ZONE", x: 45, y: 60, w: 360, h: 380 },
            // Zone B (Right Hall)
            { id: "zone-B", name: "Zone B (Storage Hall B)", type: "ZONE", x: 435, y: 60, w: 360, h: 380 },

            // Aisles inside Zone A
            { id: "aisle-A1", name: "Aisle A1", type: "AISLE", x: 65, y: 100, w: 320, h: 140 },
            { id: "aisle-A2", name: "Aisle A2", type: "AISLE", x: 65, y: 270, w: 320, h: 140 },

            // Aisles inside Zone B
            { id: "aisle-B1", name: "Aisle B1", type: "AISLE", x: 455, y: 100, w: 320, h: 140 },
            { id: "aisle-B2", name: "Aisle B2", type: "AISLE", x: 455, y: 270, w: 320, h: 140 },

            // Racks inside Aisle A1
            { id: "rack-A1R1", name: "Rack A1-R1", type: "RACK", x: 80, y: 140, w: 135, h: 80 },
            { id: "rack-A1R2", name: "Rack A1-R2", type: "RACK", x: 235, y: 140, w: 135, h: 80 },

            // Racks inside Aisle A2
            { id: "rack-A2R1", name: "Rack A2-R1", type: "RACK", x: 80, y: 310, w: 290, h: 80 },

            // Racks inside Zone B Aisles
            { id: "rack-B1R1", name: "Rack B1-R1", type: "RACK", x: 470, y: 140, w: 290, h: 80 },
            { id: "rack-B2R1", name: "Rack B2-R1", type: "RACK", x: 470, y: 310, w: 290, h: 80 },

            // Bins inside Rack A1R1
            { id: "bin-A1R1B1", name: "Bin A1-R1-B1", type: "BIN", x: 90, y: 170, w: 55, h: 40 },
            { id: "bin-A1R1B2", name: "Bin A1-R1-B2", type: "BIN", x: 152, y: 170, w: 55, h: 40 },

            // Bins inside Rack A1R2
            { id: "bin-A1R2B1", name: "Bin A1-R2-B1", type: "BIN", x: 245, y: 170, w: 55, h: 40 },
            { id: "bin-A1R2B2", name: "Bin A1-R2-B2", type: "BIN", x: 307, y: 170, w: 55, h: 40 },

            // Bins inside Rack A2R1
            { id: "bin-A2R1B1", name: "Bin A2-R1-B1", type: "BIN", x: 90, y: 340, w: 120, h: 40 },

            // Bins inside Rack B1R1 & B2R1
            { id: "bin-B1R1B1", name: "Bin B1-R1-B1", type: "BIN", x: 480, y: 170, w: 120, h: 40 },
            { id: "bin-B2R1B1", name: "Bin B2-R1-B1", type: "BIN", x: 480, y: 340, w: 120, h: 40 },

            // Charging Docks at Bottom Floor Corridor
            { id: "dock-1", name: "AMR Dock 1", type: "DOCK", x: 100, y: 460, w: 70, h: 45 },
            { id: "dock-2", name: "AMR Dock 2", type: "DOCK", x: 375, y: 460, w: 70, h: 45 },
            { id: "dock-3", name: "AMR Dock 3", type: "DOCK", x: 650, y: 460, w: 70, h: 45 },
        ];

        // Animated AMR Bot Fleet State
        this.bots = {
            "bot-alpha": { id: "bot-alpha", label: "Alpha", x: 135, y: 482, targetX: 135, targetY: 482, color: "#38bdf8", isLocked: false },
            "bot-beta":  { id: "bot-beta",  label: "Beta",  x: 410, y: 482, targetX: 410, targetY: 482, color: "#a855f7", isLocked: false },
            "bot-gamma": { id: "bot-gamma", label: "Gamma", x: 685, y: 482, targetX: 685, targetY: 482, color: "#ec4899", isLocked: false },
        };

        this.pulseTime = 0;
        this.setupEvents();
    }

    start() {
        const renderLoop = () => {
            this.pulseTime += 0.05;
            this.updateBotTargets();
            this.draw();
            this.animFrame = requestAnimationFrame(renderLoop);
        };
        renderLoop();
    }

    updateTreeState(rootNode) {
        this.treeMap.clear();
        this.flattenTree(rootNode);
    }

    flattenTree(node) {
        if (!node) return;
        this.treeMap.set(node.id, node);
        if (node.children) {
            for (const child of node.children) {
                this.flattenTree(child);
            }
        }
    }

    selectNode(nodeId) {
        this.selectedId = nodeId;
    }

    updateBotTargets() {
        // Reset bot active targets to default charging docks
        this.bots["bot-alpha"].targetX = 135;
        this.bots["bot-alpha"].targetY = 482;
        this.bots["bot-alpha"].isLocked = false;

        this.bots["bot-beta"].targetX = 410;
        this.bots["bot-beta"].targetY = 482;
        this.bots["bot-beta"].isLocked = false;

        this.bots["bot-gamma"].targetX = 685;
        this.bots["bot-gamma"].targetY = 482;
        this.bots["bot-gamma"].isLocked = false;

        // Check if any bot currently holds a lock
        for (const [nodeId, nodeData] of this.treeMap.entries()) {
            if (nodeData.is_locked && nodeData.locked_by && this.bots[nodeData.locked_by]) {
                const reg = this.regions.find(r => r.id === nodeId);
                if (reg) {
                    const bot = this.bots[nodeData.locked_by];
                    bot.targetX = reg.x + reg.w / 2;
                    bot.targetY = reg.y + reg.h / 2;
                    bot.isLocked = true;
                }
            }
        }

        // Smooth position interpolation (lerp)
        for (const bKey in this.bots) {
            const bot = this.bots[bKey];
            bot.x += (bot.targetX - bot.x) * 0.08;
            bot.y += (bot.targetY - bot.y) * 0.08;
        }
    }

    draw() {
        const ctx = this.ctx;
        const w = this.canvas.width;
        const h = this.canvas.height;

        // Clear Background Grid
        ctx.fillStyle = "#0f172a";
        ctx.fillRect(0, 0, w, h);

        this.drawFloorGridPattern(ctx, w, h);

        // Render spatial regions hierarchy (Facilities, Zones, Aisles, Racks, Bins, Docks)
        for (const reg of this.regions) {
            const nodeData = this.treeMap.get(reg.id);
            const isHovered  = this.hoveredId === reg.id;
            const isSelected = this.selectedId === reg.id;

            this.drawSpatialRegion(ctx, reg, nodeData, isHovered, isSelected);
        }

        // Draw AMR Bot Fleet Icons
        for (const bKey in this.bots) {
            this.drawAMRBot(ctx, this.bots[bKey]);
        }
    }

    drawFloorGridPattern(ctx, w, h) {
        ctx.strokeStyle = "rgba(51, 65, 85, 0.3)";
        ctx.lineWidth = 1;

        const gridSize = 30;
        ctx.beginPath();
        for (let x = 0; x < w; x += gridSize) {
            ctx.moveTo(x, 0);
            ctx.lineTo(x, h);
        }
        for (let y = 0; y < h; y += gridSize) {
            ctx.moveTo(0, y);
            ctx.lineTo(w, y);
        }
        ctx.stroke();
    }

    drawSpatialRegion(ctx, reg, nodeData, isHovered, isSelected) {
        const isLocked = nodeData ? nodeData.is_locked : false;
        const isDescLocked = nodeData ? nodeData.locked_descendant_count > 0 : false;

        ctx.save();

        // Color Fill Logic based on lock state
        if (isLocked) {
            // Glowing Red Lock Fill
            const pulseGlow = Math.sin(this.pulseTime * 4) * 0.1 + 0.25;
            ctx.fillStyle = `rgba(239, 68, 68, ${pulseGlow})`;
            ctx.strokeStyle = "#ef4444";
            ctx.lineWidth = 2.5;
        } else if (isDescLocked) {
            // Amber Descendant Lock Fill
            ctx.fillStyle = "rgba(245, 158, 11, 0.15)";
            ctx.strokeStyle = "#f59e0b";
            ctx.lineWidth = 1.8;
            ctx.setLineDash([4, 4]);
        } else if (reg.type === "DOCK") {
            ctx.fillStyle = "rgba(56, 189, 248, 0.1)";
            ctx.strokeStyle = "#0284c7";
            ctx.lineWidth = 1;
        } else {
            // Free Node
            ctx.fillStyle = "rgba(30, 41, 59, 0.6)";
            ctx.strokeStyle = "rgba(71, 85, 105, 0.5)";
            ctx.lineWidth = 1;
        }

        if (isSelected) {
            ctx.strokeStyle = "#38bdf8";
            ctx.lineWidth = 3;
        }

        if (isHovered) {
            ctx.shadowColor = "#38bdf8";
            ctx.shadowBlur = 12;
        }

        // Draw Rectangle Region
        ctx.beginPath();
        ctx.roundRect(reg.x, reg.y, reg.w, reg.h, 6);
        ctx.fill();
        ctx.stroke();
        ctx.setLineDash([]);

        // Region Labels
        if (reg.type === "FACILITY" || reg.type === "ZONE" || reg.type === "AISLE" || reg.type === "RACK" || reg.type === "DOCK") {
            ctx.fillStyle = isLocked ? "#fca5a5" : (isDescLocked ? "#fde68a" : "#94a3b8");
            ctx.font = reg.type === "FACILITY" ? "bold 11px sans-serif" : (reg.type === "ZONE" ? "bold 12px sans-serif" : "bold 10px sans-serif");

            const labelY = reg.y + (reg.type === "FACILITY" ? 14 : (reg.type === "ZONE" ? 18 : 16));
            ctx.fillText(reg.name, reg.x + 8, labelY);
        }

        // Lock Ownership Badge & TTL Countdown Overlay
        if (isLocked && nodeData && nodeData.locked_by) {
            ctx.fillStyle = "#ef4444";
            ctx.beginPath();
            ctx.roundRect(reg.x + reg.w - 110, reg.y + 4, 104, 20, 4);
            ctx.fill();

            ctx.fillStyle = "#ffffff";
            ctx.font = "bold 9px monospace";
            const ttlText = nodeData.ttl_remaining > 0 ? `${nodeData.ttl_remaining}s` : "LOCK";
            ctx.fillText(`🔒 ${nodeData.locked_by} (${ttlText})`, reg.x + reg.w - 106, reg.y + 17);
        }

        ctx.restore();
    }

    drawAMRBot(ctx, bot) {
        ctx.save();

        // Bot Chassis Circle
        ctx.fillStyle = bot.color;
        ctx.shadowColor = bot.color;
        ctx.shadowBlur = bot.isLocked ? 16 : 8;

        ctx.beginPath();
        ctx.arc(bot.x, bot.y, 11, 0, Math.PI * 2);
        ctx.fill();

        // Inner Core Light
        ctx.fillStyle = bot.isLocked ? "#ef4444" : "#ffffff";
        ctx.beginPath();
        ctx.arc(bot.x, bot.y, 4, 0, Math.PI * 2);
        ctx.fill();

        // Floating Bot Label Tag
        ctx.fillStyle = "rgba(15, 23, 42, 0.85)";
        ctx.beginPath();
        ctx.roundRect(bot.x - 22, bot.y - 25, 44, 14, 3);
        ctx.fill();

        ctx.fillStyle = bot.color;
        ctx.font = "bold 8px sans-serif";
        ctx.textAlign = "center";
        ctx.fillText(bot.label, bot.x, bot.y - 15);

        ctx.restore();
    }

    setupEvents() {
        this.canvas.addEventListener("mousemove", (e) => {
            const rect = this.canvas.getBoundingClientRect();
            const scaleX = this.canvas.width / rect.width;
            const scaleY = this.canvas.height / rect.height;

            const mouseX = (e.clientX - rect.left) * scaleX;
            const mouseY = (e.clientY - rect.top) * scaleY;

            // Hit test smallest region under cursor (Bins -> Racks -> Aisles -> Zones -> Facility)
            let found = null;
            const typePriority = { "BIN": 5, "RACK": 4, "AISLE": 3, "ZONE": 2, "DOCK": 2, "FACILITY": 1 };

            for (const reg of this.regions) {
                if (mouseX >= reg.x && mouseX <= reg.x + reg.w && mouseY >= reg.y && mouseY <= reg.y + reg.h) {
                    if (!found || typePriority[reg.type] > typePriority[found.type]) {
                        found = reg;
                    }
                }
            }

            if (found) {
                this.hoveredId = found.id;
                this.showTooltip(e, found);
            } else {
                this.hoveredId = null;
                canvasTooltip.classList.add("hidden");
            }
        });

        this.canvas.addEventListener("mouseleave", () => {
            this.hoveredId = null;
            canvasTooltip.classList.add("hidden");
        });

        this.canvas.addEventListener("click", (e) => {
            if (this.hoveredId) {
                selectedNode = this.hoveredId;
                nodeSelect.value = this.hoveredId;
                renderTree(currentTree);
                this.selectedId = this.hoveredId;
            }
        });
    }

    showTooltip(e, reg) {
        const containerRect = canvasContainer.getBoundingClientRect();
        const mouseX = e.clientX - containerRect.left;
        const mouseY = e.clientY - containerRect.top;

        const nodeData = this.treeMap.get(reg.id);
        const statusText = nodeData ? (nodeData.is_locked ? `Locked by ${nodeData.locked_by} (${nodeData.ttl_remaining}s)` : (nodeData.locked_descendant_count > 0 ? `Descendants locked (${nodeData.locked_descendant_count})` : "Free")) : "Free";

        ttTitle.textContent = reg.name;
        ttBody.textContent  = `Type: ${reg.type} | Status: ${statusText}`;

        canvasTooltip.style.left = `${mouseX + 12}px`;
        canvasTooltip.style.top  = `${mouseY + 12}px`;
        canvasTooltip.classList.remove("hidden");
    }
}
