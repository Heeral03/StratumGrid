"""
AuditLogger — Append-only transaction ledger for all spatial lock operations.
"""

import json
import os
from datetime import datetime, timezone


class AuditLogger:
    def __init__(self, log_path: str = "audit_log.json"):
        self.log_path = log_path
        self._log: list[dict] = []
        # Load existing log if present
        if os.path.exists(log_path):
            try:
                with open(log_path, "r") as f:
                    self._log = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._log = []

    def record(self, action: str, node_id: str, agent_id: str, success: bool, detail: str = ""):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "node_id": node_id,
            "agent_id": agent_id,
            "success": success,
            "detail": detail,
        }
        self._log.append(entry)
        self._persist()

    def get_log(self) -> list[dict]:
        return list(self._log)

    def _persist(self):
        with open(self.log_path, "w") as f:
            json.dump(self._log, f, indent=2)
