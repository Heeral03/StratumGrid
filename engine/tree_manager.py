import time
import threading
from typing import Dict, Any, List, Optional
from engine.tree_node import TreeNode
from engine.audit import AuditLogger


class TreeManager:
    """
    Thread-safe manager for the dynamic warehouse M-ary spatial tree topology.
    Enforces $O(h)$ ancestor checks, descendant counters, pessimistic locking,
    TTL lease heartbeats, and automatic background lease expirations.
    """

    def __init__(self, audit_logger: Optional[AuditLogger] = None):
        self.lock_mutex = threading.Lock()
        self.audit_logger = audit_logger or AuditLogger()
        self.node_lookup: Dict[str, TreeNode] = {}
        self.root = self._build_default_warehouse_topology()

    def _build_default_warehouse_topology(self) -> TreeNode:
        """
        Builds default warehouse layout:
        Facility-1 -> Zone-A, Zone-B
          Zone-A -> Aisle-A1, Aisle-A2
            Aisle-A1 -> Rack-A1R1, Rack-A1R2
              Rack-A1R1 -> Bin-A1R1B1, Bin-A1R1B2
              Rack-A1R2 -> Bin-A1R2B1, Bin-A1R2B2
            Aisle-A2 -> Rack-A2R1
              Rack-A2R1 -> Bin-A2R1B1
          Zone-B -> Aisle-B1, Aisle-B2
            Aisle-B1 -> Rack-B1R1
              Rack-B1R1 -> Bin-B1R1B1
            Aisle-B2 -> Rack-B2R2
              Rack-B2R2 -> Bin-B2R2B1
        """
        facility = TreeNode("facility", "Warehouse-1", "FACILITY")
        self.node_lookup["facility"] = facility

        zones = [("zone-A", "Zone-A"), ("zone-B", "Zone-B")]
        for z_id, z_name in zones:
            z_node = TreeNode(z_id, z_name, "ZONE", parent=facility)
            facility.add_child(z_node)
            self.node_lookup[z_id] = z_node

        aisles = [
            ("aisle-A1", "Aisle-A1", "zone-A"),
            ("aisle-A2", "Aisle-A2", "zone-A"),
            ("aisle-B1", "Aisle-B1", "zone-B"),
            ("aisle-B2", "Aisle-B2", "zone-B"),
        ]
        for a_id, a_name, parent_id in aisles:
            p_node = self.node_lookup[parent_id]
            a_node = TreeNode(a_id, a_name, "AISLE", parent=p_node)
            p_node.add_child(a_node)
            self.node_lookup[a_id] = a_node

        racks = [
            ("rack-A1R1", "Rack-A1R1", "aisle-A1"),
            ("rack-A1R2", "Rack-A1R2", "aisle-A1"),
            ("rack-A2R1", "Rack-A2R1", "aisle-A2"),
            ("rack-B1R1", "Rack-B1R1", "aisle-B1"),
            ("rack-B2R2", "Rack-B2R2", "aisle-B2"),
        ]
        for r_id, r_name, parent_id in racks:
            p_node = self.node_lookup[parent_id]
            r_node = TreeNode(r_id, r_name, "RACK", parent=p_node)
            p_node.add_child(r_node)
            self.node_lookup[r_id] = r_node

        bins = [
            ("bin-A1R1B1", "Bin-A1R1B1", "rack-A1R1"),
            ("bin-A1R1B2", "Bin-A1R1B2", "rack-A1R1"),
            ("bin-A1R2B1", "Bin-A1R2B1", "rack-A1R2"),
            ("bin-A1R2B2", "Bin-A1R2B2", "rack-A1R2"),
            ("bin-A2R1B1", "Bin-A2R1B1", "rack-A2R1"),
            ("bin-B1R1B1", "Bin-B1R1B1", "rack-B1R1"),
            ("bin-B2R2B1", "Bin-B2R2B1", "rack-B2R2"),
        ]
        for b_id, b_name, parent_id in bins:
            p_node = self.node_lookup[parent_id]
            b_node = TreeNode(b_id, b_name, "BIN", parent=p_node)
            p_node.add_child(b_node)
            self.node_lookup[b_id] = b_node

        return facility

    def _has_locked_ancestor(self, node: TreeNode) -> bool:
        curr = node.parent
        while curr:
            if curr.is_locked:
                return True
            curr = curr.parent
        return False

    def _update_ancestor_descendant_counts(self, node: TreeNode, delta: int) -> None:
        curr = node.parent
        while curr:
            curr.locked_descendant_count += delta
            curr = curr.parent

    def lock(self, node_id: str, agent_id: str, ttl_seconds: int = 30) -> Dict[str, Any]:
        """
        Attempts to acquire an exclusive lock on node_id with a TTL lease.
        """
        with self.lock_mutex:
            if node_id not in self.node_lookup:
                msg = f"Node '{node_id}' does not exist in spatial topology."
                self.audit_logger.log("LOCK", agent_id, node_id, False, msg)
                return {"success": False, "message": msg}

            node = self.node_lookup[node_id]

            if node.is_locked:
                msg = f"Node '{node_id}' is already locked by agent '{node.locked_by}'."
                self.audit_logger.log("LOCK", agent_id, node_id, False, msg)
                return {"success": False, "message": msg}

            if self._has_locked_ancestor(node):
                msg = f"Cannot lock '{node_id}': an ancestor node is currently locked."
                self.audit_logger.log("LOCK", agent_id, node_id, False, msg)
                return {"success": False, "message": msg}

            if node.locked_descendant_count > 0:
                msg = f"Cannot lock '{node_id}': {node.locked_descendant_count} descendant node(s) currently locked."
                self.audit_logger.log("LOCK", agent_id, node_id, False, msg)
                return {"success": False, "message": msg}

            # State mutation
            node.is_locked = True
            node.locked_by = agent_id
            node.expires_at = time.time() + ttl_seconds
            self._update_ancestor_descendant_counts(node, delta=1)

            msg = f"Node '{node_id}' locked by agent '{agent_id}' (TTL: {ttl_seconds}s)."
            self.audit_logger.log("LOCK", agent_id, node_id, True, msg)
            return {"success": True, "message": msg, "expires_at": node.expires_at, "ttl_seconds": ttl_seconds}

    def unlock(self, node_id: str, agent_id: str) -> Dict[str, Any]:
        """
        Releases exclusive lock on node_id if owned by agent_id.
        """
        with self.lock_mutex:
            return self._unlock_internal(node_id, agent_id, reason="UNLOCK")

    def _unlock_internal(self, node_id: str, agent_id: str, reason: str = "UNLOCK") -> Dict[str, Any]:
        """Internal helper for unlock (mutex must be held by caller)."""
        if node_id not in self.node_lookup:
            msg = f"Node '{node_id}' does not exist."
            self.audit_logger.log(reason, agent_id, node_id, False, msg)
            return {"success": False, "message": msg}

        node = self.node_lookup[node_id]

        if not node.is_locked:
            msg = f"Node '{node_id}' is not currently locked."
            self.audit_logger.log(reason, agent_id, node_id, False, msg)
            return {"success": False, "message": msg}

        if node.locked_by != agent_id and reason == "UNLOCK":
            msg = f"Node '{node_id}' is locked by agent '{node.locked_by}', not '{agent_id}'."
            self.audit_logger.log(reason, agent_id, node_id, False, msg)
            return {"success": False, "message": msg}

        # State mutation
        node.is_locked = False
        node.locked_by = None
        node.expires_at = None
        self._update_ancestor_descendant_counts(node, delta=-1)

        msg = f"Node '{node_id}' unlocked successfully ({reason})."
        self.audit_logger.log(reason, agent_id, node_id, True, msg)
        return {"success": True, "message": msg}

    def heartbeat(self, node_id: str, agent_id: str, ttl_seconds: int = 30) -> Dict[str, Any]:
        """
        Renews an active TTL lease for a locked node.
        Fails if node is not locked or owned by a different agent.
        """
        with self.lock_mutex:
            if node_id not in self.node_lookup:
                msg = f"Node '{node_id}' does not exist."
                self.audit_logger.log("HEARTBEAT", agent_id, node_id, False, msg)
                return {"success": False, "message": msg}

            node = self.node_lookup[node_id]

            if not node.is_locked:
                msg = f"Heartbeat rejected: Node '{node_id}' is not currently locked."
                self.audit_logger.log("HEARTBEAT", agent_id, node_id, False, msg)
                return {"success": False, "message": msg}

            if node.locked_by != agent_id:
                msg = f"Heartbeat rejected: Node '{node_id}' is locked by '{node.locked_by}', not '{agent_id}'."
                self.audit_logger.log("HEARTBEAT", agent_id, node_id, False, msg)
                return {"success": False, "message": msg}

            # Renew lease
            node.expires_at = time.time() + ttl_seconds
            msg = f"Heartbeat accepted: Lease for '{node_id}' renewed (+{ttl_seconds}s)."
            self.audit_logger.log("HEARTBEAT", agent_id, node_id, True, msg)
            return {
                "success": True,
                "message": msg,
                "expires_at": node.expires_at,
                "ttl_remaining": node.ttl_remaining
            }

    def check_and_expire_locks(self) -> List[Dict[str, Any]]:
        """
        Scans all locked nodes and automatically expires any whose expires_at <= current time.
        Returns list of expired events.
        """
        expired_events = []
        now = time.time()
        with self.lock_mutex:
            for node_id, node in self.node_lookup.items():
                if node.is_locked and node.expires_at and node.expires_at <= now:
                    agent_id = node.locked_by or "unknown"
                    # Release expired lock
                    node.is_locked = False
                    node.locked_by = None
                    node.expires_at = None
                    self._update_ancestor_descendant_counts(node, delta=-1)

                    msg = f"Lease expired for node '{node_id}' (bot '{agent_id}' heartbeat timeout)."
                    self.audit_logger.log("EXPIRE", agent_id, node_id, True, msg)
                    expired_events.append({
                        "node_id": node_id,
                        "agent_id": agent_id,
                        "message": msg
                    })

        return expired_events

    def upgrade(self, parent_id: str, agent_id: str) -> Dict[str, Any]:
        """
        Consolidates child locks owned by agent_id into a parent node lock.
        """
        with self.lock_mutex:
            if parent_id not in self.node_lookup:
                msg = f"Parent node '{parent_id}' does not exist."
                self.audit_logger.log("UPGRADE", agent_id, parent_id, False, msg)
                return {"success": False, "message": msg}

            parent = self.node_lookup[parent_id]

            if parent.is_locked:
                msg = f"Parent node '{parent_id}' is already locked."
                self.audit_logger.log("UPGRADE", agent_id, parent_id, False, msg)
                return {"success": False, "message": msg}

            if self._has_locked_ancestor(parent):
                msg = f"Cannot upgrade '{parent_id}': ancestor node is locked."
                self.audit_logger.log("UPGRADE", agent_id, parent_id, False, msg)
                return {"success": False, "message": msg}

            def get_descendants(node: TreeNode) -> List[TreeNode]:
                result = []
                for child in node.children:
                    result.append(child)
                    result.extend(get_descendants(child))
                return result

            descendants = get_descendants(parent)
            locked_descendants = [d for d in descendants if d.is_locked]

            if not locked_descendants:
                msg = f"Cannot upgrade '{parent_id}': no locked child nodes found under parent."
                self.audit_logger.log("UPGRADE", agent_id, parent_id, False, msg)
                return {"success": False, "message": msg}

            foreign_locks = [d for d in locked_descendants if d.locked_by != agent_id]
            if foreign_locks:
                msg = f"Cannot upgrade '{parent_id}': some child nodes are locked by other agents."
                self.audit_logger.log("UPGRADE", agent_id, parent_id, False, msg)
                return {"success": False, "message": msg}

            for d in locked_descendants:
                d.is_locked = False
                d.locked_by = None
                d.expires_at = None
                self._update_ancestor_descendant_counts(d, delta=-1)

            parent.is_locked = True
            parent.locked_by = agent_id
            parent.expires_at = time.time() + 30
            self._update_ancestor_descendant_counts(parent, delta=1)

            msg = f"Successfully upgraded {len(locked_descendants)} child lock(s) into parent '{parent_id}' lock for agent '{agent_id}'."
            self.audit_logger.log("UPGRADE", agent_id, parent_id, True, msg)
            return {"success": True, "message": msg}

    def get_tree_state(self) -> Dict[str, Any]:
        """Returns full topology state dictionary."""
        with self.lock_mutex:
            return self.root.to_dict()

    def get_all_nodes_flat(self) -> List[Dict[str, Any]]:
        """Returns flat list of nodes for selectors."""
        with self.lock_mutex:
            return [
                {"id": n.id, "name": n.name, "type": n.type, "is_locked": n.is_locked, "locked_by": n.locked_by, "ttl_remaining": n.ttl_remaining}
                for n in self.node_lookup.values()
            ]
