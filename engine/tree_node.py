"""
TreeNode — Represents a single node in the warehouse spatial hierarchy.

Each node tracks:
  - Parent pointer for O(h) ancestor traversal
  - locked_descendant_count for O(1) descendant conflict detection
  - Lock state (is_locked, locked_by agent)
"""


class TreeNode:
    __slots__ = (
        "id", "name", "node_type", "parent", "children",
        "is_locked", "locked_by", "locked_descendant_count",
    )

    def __init__(self, node_id: str, name: str, node_type: str, parent: "TreeNode | None" = None):
        self.id = node_id
        self.name = name
        self.node_type = node_type          # facility | zone | aisle | rack | bin
        self.parent: TreeNode | None = parent
        self.children: list[TreeNode] = []
        self.is_locked: bool = False
        self.locked_by: str | None = None
        self.locked_descendant_count: int = 0

    # ── O(h) ancestor walk ──────────────────────────────────────────
    def is_ancestor_locked(self) -> bool:
        """Walk up the parent chain. Return True if any ancestor is locked."""
        current = self.parent
        while current is not None:
            if current.is_locked:
                return True
            current = current.parent
        return False

    # ── O(1) descendant check ───────────────────────────────────────
    def has_locked_descendant(self) -> bool:
        return self.locked_descendant_count > 0

    # ── Serialization ───────────────────────────────────────────────
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.node_type,
            "is_locked": self.is_locked,
            "locked_by": self.locked_by,
            "locked_descendant_count": self.locked_descendant_count,
            "children": [child.to_dict() for child in self.children],
        }
