import time
from typing import Optional, List, Dict, Any

class TreeNode:
    """
    Represents a spatial node in the M-ary physical warehouse hierarchy.
    """

    def __init__(self, node_id: str, name: str, node_type: str, parent: Optional['TreeNode'] = None):
        self.id: str = node_id
        self.name: str = name
        self.type: str = node_type  # FACILITY, ZONE, AISLE, RACK, BIN
        self.parent: Optional['TreeNode'] = parent
        self.children: List['TreeNode'] = []
        
        self.is_locked: bool = False
        self.locked_by: Optional[str] = None
        self.locked_descendant_count: int = 0
        self.expires_at: Optional[float] = None  # Unix timestamp when TTL lease expires

    def add_child(self, child_node: 'TreeNode') -> None:
        child_node.parent = self
        self.children.append(child_node)

    @property
    def ttl_remaining(self) -> float:
        """Returns remaining seconds on active lease, or 0 if expired/unlocked."""
        if not self.is_locked or not self.expires_at:
            return 0.0
        return max(0.0, round(self.expires_at - time.time(), 1))

    def to_dict(self) -> Dict[str, Any]:
        """Serializes node and descendants for API responses."""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "is_locked": self.is_locked,
            "locked_by": self.locked_by,
            "locked_descendant_count": self.locked_descendant_count,
            "expires_at": self.expires_at,
            "ttl_remaining": self.ttl_remaining,
            "children": [child.to_dict() for child in self.children]
        }
