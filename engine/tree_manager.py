"""
TreeManager — Core engine for hierarchical spatial locking.

Manages an M-ary tree representing the warehouse topology.
All state mutations (lock / unlock / upgrade) are protected by
a single threading.Lock to guarantee atomicity and prevent race conditions.

Complexity: O(h) per operation where h = tree height.
"""

import threading
from .tree_node import TreeNode
from .audit import AuditLogger


class TreeManager:
    def __init__(self):
        self._lock = threading.Lock()
        self.root: TreeNode | None = None
        self.node_lookup: dict[str, TreeNode] = {}
        self.audit = AuditLogger()
        self._build_default_tree()

    # ── Tree Construction ───────────────────────────────────────────
    def _add_node(self, node_id: str, name: str, node_type: str, parent: TreeNode | None = None) -> TreeNode:
        node = TreeNode(node_id, name, node_type, parent)
        if parent is not None:
            parent.children.append(node)
        self.node_lookup[node_id] = node
        return node

    def _build_default_tree(self):
        """
        Default warehouse topology:
          Facility
          ├── Zone-A
          │   ├── Aisle-A1
          │   │   ├── Rack-A1R1
          │   │   │   ├── Bin-A1R1B1
          │   │   │   └── Bin-A1R1B2
          │   │   └── Rack-A1R2
          │   │       ├── Bin-A1R2B1
          │   │       └── Bin-A1R2B2
          │   └── Aisle-A2
          │       ├── Rack-A2R1
          │       │   ├── Bin-A2R1B1
          │       │   └── Bin-A2R1B2
          │       └── Rack-A2R2
          │           ├── Bin-A2R2B1
          │           └── Bin-A2R2B2
          └── Zone-B
              ├── Aisle-B1
              │   ├── Rack-B1R1
              │   │   ├── Bin-B1R1B1
              │   │   └── Bin-B1R1B2
              │   └── Rack-B1R2
              │       ├── Bin-B1R2B1
              │       └── Bin-B1R2B2
              └── Aisle-B2
                  ├── Rack-B2R1
                  │   ├── Bin-B2R1B1
                  │   └── Bin-B2R1B2
                  └── Rack-B2R2
                      ├── Bin-B2R2B1
                      └── Bin-B2R2B2
        """
        facility = self._add_node("facility", "Warehouse-1", "facility")
        self.root = facility

        for zone_label in ("A", "B"):
            zone = self._add_node(f"zone-{zone_label}", f"Zone-{zone_label}", "zone", facility)
            for aisle_idx in ("1", "2"):
                aisle_id = f"{zone_label}{aisle_idx}"
                aisle = self._add_node(f"aisle-{aisle_id}", f"Aisle-{aisle_id}", "aisle", zone)
                for rack_idx in ("1", "2"):
                    rack_id = f"{aisle_id}R{rack_idx}"
                    rack = self._add_node(f"rack-{rack_id}", f"Rack-{rack_id}", "rack", aisle)
                    for bin_idx in ("1", "2"):
                        bin_id = f"{rack_id}B{bin_idx}"
                        self._add_node(f"bin-{bin_id}", f"Bin-{bin_id}", "bin", rack)

    # ── Counter Propagation ─────────────────────────────────────────
    @staticmethod
    def _increment_ancestors(node: TreeNode):
        current = node.parent
        while current is not None:
            current.locked_descendant_count += 1
            current = current.parent

    @staticmethod
    def _decrement_ancestors(node: TreeNode):
        current = node.parent
        while current is not None:
            current.locked_descendant_count -= 1
            current = current.parent

    # ── Lock ────────────────────────────────────────────────────────
    def lock(self, node_id: str, agent_id: str) -> dict:
        with self._lock:
            node = self.node_lookup.get(node_id)
            if node is None:
                self.audit.record("LOCK", node_id, agent_id, False, "Node not found")
                return {"success": False, "message": f"Node '{node_id}' not found."}

            if node.is_locked:
                self.audit.record("LOCK", node_id, agent_id, False, f"Already locked by {node.locked_by}")
                return {"success": False, "message": f"Node '{node_id}' is already locked by agent '{node.locked_by}'."}

            if node.is_ancestor_locked():
                self.audit.record("LOCK", node_id, agent_id, False, "Ancestor is locked")
                return {"success": False, "message": f"Cannot lock '{node_id}': an ancestor node is currently locked."}

            if node.has_locked_descendant():
                self.audit.record("LOCK", node_id, agent_id, False, f"{node.locked_descendant_count} descendant(s) locked")
                return {
                    "success": False,
                    "message": f"Cannot lock '{node_id}': {node.locked_descendant_count} descendant node(s) currently locked.",
                }

            # All clear — lock the node
            node.is_locked = True
            node.locked_by = agent_id
            self._increment_ancestors(node)
            self.audit.record("LOCK", node_id, agent_id, True, "Locked successfully")
            return {"success": True, "message": f"Node '{node_id}' locked by agent '{agent_id}'."}

    # ── Unlock ──────────────────────────────────────────────────────
    def unlock(self, node_id: str, agent_id: str) -> dict:
        with self._lock:
            node = self.node_lookup.get(node_id)
            if node is None:
                self.audit.record("UNLOCK", node_id, agent_id, False, "Node not found")
                return {"success": False, "message": f"Node '{node_id}' not found."}

            if not node.is_locked:
                self.audit.record("UNLOCK", node_id, agent_id, False, "Node not locked")
                return {"success": False, "message": f"Node '{node_id}' is not locked."}

            if node.locked_by != agent_id:
                self.audit.record("UNLOCK", node_id, agent_id, False, f"Owned by {node.locked_by}")
                return {"success": False, "message": f"Node '{node_id}' is locked by agent '{node.locked_by}', not '{agent_id}'."}

            node.is_locked = False
            node.locked_by = None
            self._decrement_ancestors(node)
            self.audit.record("UNLOCK", node_id, agent_id, True, "Unlocked successfully")
            return {"success": True, "message": f"Node '{node_id}' unlocked by agent '{agent_id}'."}

    # ── Upgrade (consolidate child locks → parent lock) ─────────────
    def upgrade(self, parent_id: str, agent_id: str) -> dict:
        with self._lock:
            parent = self.node_lookup.get(parent_id)
            if parent is None:
                self.audit.record("UPGRADE", parent_id, agent_id, False, "Node not found")
                return {"success": False, "message": f"Node '{parent_id}' not found."}

            if parent.is_locked:
                self.audit.record("UPGRADE", parent_id, agent_id, False, "Parent already locked")
                return {"success": False, "message": f"Node '{parent_id}' is already locked."}

            if not parent.children:
                self.audit.record("UPGRADE", parent_id, agent_id, False, "No children to upgrade")
                return {"success": False, "message": f"Node '{parent_id}' has no children to consolidate."}

            if parent.is_ancestor_locked():
                self.audit.record("UPGRADE", parent_id, agent_id, False, "Ancestor locked")
                return {"success": False, "message": f"Cannot upgrade '{parent_id}': an ancestor is locked."}

            # Check every child is locked by the same agent
            for child in parent.children:
                if not child.is_locked or child.locked_by != agent_id:
                    self.audit.record("UPGRADE", parent_id, agent_id, False,
                                      f"Child '{child.id}' not locked by {agent_id}")
                    return {
                        "success": False,
                        "message": f"Cannot upgrade: child '{child.id}' is not locked by agent '{agent_id}'.",
                    }

            # Unlock all children, then lock parent
            for child in parent.children:
                child.is_locked = False
                child.locked_by = None
                self._decrement_ancestors(child)

            parent.is_locked = True
            parent.locked_by = agent_id
            self._increment_ancestors(parent)

            self.audit.record("UPGRADE", parent_id, agent_id, True,
                              f"Consolidated {len(parent.children)} child locks")
            return {
                "success": True,
                "message": f"Upgraded: {len(parent.children)} child locks consolidated into '{parent_id}'.",
            }

    # ── State Snapshot ──────────────────────────────────────────────
    def get_tree_state(self) -> dict:
        if self.root is None:
            return {}
        return self.root.to_dict()

    def get_all_node_ids(self) -> list[dict]:
        return [{"id": n.id, "name": n.name, "type": n.node_type} for n in self.node_lookup.values()]
