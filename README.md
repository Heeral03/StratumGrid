# StratumGrid

StratumGrid is a high-performance backend resource arbiter that implements a Tree of Space hierarchical locking model for automated warehouse management systems.

## Problem Statement

In automated fulfillment centers, Autonomous Mobile Robots (AMRs), pickers, and safety supervisors continuously request exclusive spatial access over warehouse regions (Facility -> Zone -> Aisle -> Rack -> Bin). Concurrent requests without proper coordination cause spatial collisions, race conditions, or expensive linear traversal bottlenecks. If a robot crashes or suffers network failure while holding a lock, spatial resources remain permanently blocked.

## Solution and Algorithmic Design

StratumGrid structures the warehouse as an M-ary dynamic tree node graph. Lock acquisition validates that no ancestor node is locked and no descendant node is occupied.

- Complexity Optimization: Each node maintains parent pointers and an atomic `locked_descendant_count` counter. Lock validation scales with tree height O(h) instead of total node count O(N).
- TTL Lease & Heartbeat Renewal: Locks are acquired with a temporary 30-second Time-To-Live (TTL) lease. Active bots issue periodic heartbeats to renew their lease. If a bot crashes, its lock automatically expires after 30 seconds.
- Real-Time WebSocket Streaming: State changes, heartbeat renewals, and lease expirations are broadcast instantly to connected clients via WebSockets (`/ws/events`).
- Concurrency Guarantee: All state mutations are protected by a threading mutex lock to prevent race conditions during multi-agent requests.
- Lock Upgrade: Consolidates child node locks into a single parent zone lock when owned by the same agent.

## Architecture

The system follows a decoupled client-server model:

```text
+-------------------------------------------------------------+
|                     Frontend Dashboard                      |
|      (HTML5, CSS3, Vanilla JS UI with WebSockets Stream)    |
+------------------------------+------------------------------+
                               | REST API & WebSockets (/ws/events)
                               v
+-------------------------------------------------------------+
|                      FastAPI Backend                        |
|   - Pydantic DTOs & Strict Request Controllers              |
|   - WebSocket Event Stream Broadcast Manager                |
|   - Async Background Expired Lease Cleanup Worker           |
+------------------------------+------------------------------+
                               |
                               v
+-------------------------------------------------------------+
|                     Core Engine Layer                       |
|         - M-Ary Tree Graph & Ancestor Pointers              |
|         - Atomic Descendant Counter Tracking                |
|         - TTL Lease Expiration & Heartbeat Renewal          |
|         - Mutex Synchronization (threading.Lock)            |
+------------------------------+------------------------------+
                               |
                               v
+-------------------------------------------------------------+
|                     Audit Ledger Layer                      |
|         - Append-Only JSON Transaction Log                 |
+-------------------------------------------------------------+
```

## Tech Stack

- Core Engine: Python 3.12, Threading, Mutex Synchronization
- Backend API: FastAPI, Pydantic, Uvicorn, WebSockets
- Testing Framework: Pytest, Concurrent ThreadPoolExecutor, Sync Barriers
- Frontend UI: HTML5, CSS3 (Light Theme Design System), Vanilla JavaScript, WebSockets
- Audit Persistence: JSON File Ledger

## API Endpoints

- POST `/api/v1/resource/lock` - Acquires exclusive spatial lock on a target node (default: 30s TTL)
- POST `/api/v1/resource/heartbeat` - Renews active lease timestamp by 30s
- POST `/api/v1/resource/unlock` - Releases lock and decrements descendant counters upward
- POST `/api/v1/resource/upgrade` - Consolidates child locks into parent node lock
- GET `/api/v1/resource/status` - Returns complete tree hierarchy snapshot
- GET `/api/v1/audit` - Returns append-only transaction ledger
- WS `/ws/events` - Real-time WebSocket event stream for instant UI synchronization

## Concurrency & Unit Tests

The test suite in `tests/` uses `pytest` and multi-threaded execution barriers (`threading.Barrier`, `ThreadPoolExecutor`) to prove thread safety and lease behavior under contention:

1. Simultaneous Same-Node Contention: 20 parallel threads attempt to lock the exact same node at the exact same instant. Verifies exactly 1 thread succeeds and 19 fail.
2. Overlapping Ancestor/Descendant Contention: 24 concurrent threads request parent zones and child bins simultaneously. Verifies parent and child nodes are never concurrently locked.
3. High-Concurrency Stress Test: 50 concurrent threads execute continuous lock/unlock cycles across random spatial nodes. Verifies zero deadlocks and 100% counter recovery.
4. Heartbeat Renewal Test: Validates lease timestamp extension upon receiving valid heartbeat requests.
5. Automatic Lease Expiration Test: Proves stale locks automatically expire and clear parent counters when heartbeat pulses stop.

Run the test suite:
```bash
pytest -v
```

## Getting Started

Install dependencies:
```bash
pip install -r requirements.txt
```

Start the application:
```bash
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Access the dashboard in your browser:
```text
http://localhost:8000
```
