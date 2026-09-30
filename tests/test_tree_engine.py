"""
Unit tests for basic tree engine lock, unlock, and upgrade logic.
"""

import pytest
from engine.tree_manager import TreeManager


@pytest.fixture
def tm():
    """Provides a fresh TreeManager instance for each test."""
    return TreeManager()


def test_initial_tree_structure(tm):
    tree = tm.get_tree_state()
    assert tree["id"] == "facility"
    assert tree["is_locked"] is False
    assert tree["locked_descendant_count"] == 0
    assert len(tree["children"]) == 2  # Zone-A, Zone-B


def test_lock_node_success(tm):
    res = tm.lock("aisle-A1", "bot-alpha")
    assert res["success"] is True
    assert "locked by agent 'bot-alpha'" in res["message"]

    aisle = tm.node_lookup["aisle-A1"]
    assert aisle.is_locked is True
    assert aisle.locked_by == "bot-alpha"

    # Verify ancestor locked_descendant_count tracking
    zone = tm.node_lookup["zone-A"]
    facility = tm.node_lookup["facility"]
    assert zone.locked_descendant_count == 1
    assert facility.locked_descendant_count == 1


def test_lock_duplicate_failure(tm):
    tm.lock("aisle-A1", "bot-alpha")
    res = tm.lock("aisle-A1", "bot-beta")
    assert res["success"] is False
    assert "already locked" in res["message"]


def test_lock_child_when_ancestor_locked(tm):
    tm.lock("zone-A", "bot-alpha")
    res = tm.lock("rack-A1R1", "bot-beta")
    assert res["success"] is False
    assert "ancestor node is currently locked" in res["message"]


def test_lock_ancestor_when_child_locked(tm):
    tm.lock("bin-A1R1B1", "bot-alpha")
    res = tm.lock("zone-A", "bot-beta")
    assert res["success"] is False
    assert "descendant node(s) currently locked" in res["message"]


def test_unlock_success(tm):
    tm.lock("aisle-A1", "bot-alpha")
    res = tm.unlock("aisle-A1", "bot-alpha")
    assert res["success"] is True

    aisle = tm.node_lookup["aisle-A1"]
    assert aisle.is_locked is False
    assert aisle.locked_by is None

    zone = tm.node_lookup["zone-A"]
    facility = tm.node_lookup["facility"]
    assert zone.locked_descendant_count == 0
    assert facility.locked_descendant_count == 0


def test_unlock_wrong_agent_failure(tm):
    tm.lock("aisle-A1", "bot-alpha")
    res = tm.unlock("aisle-A1", "bot-beta")
    assert res["success"] is False
    assert "locked by agent 'bot-alpha', not 'bot-beta'" in res["message"]


def test_upgrade_lock_success(tm):
    tm.lock("aisle-A1", "bot-alpha")
    tm.lock("aisle-A2", "bot-alpha")

    res = tm.upgrade("zone-A", "bot-alpha")
    assert res["success"] is True

    zone = tm.node_lookup["zone-A"]
    aisle1 = tm.node_lookup["aisle-A1"]
    aisle2 = tm.node_lookup["aisle-A2"]

    assert zone.is_locked is True
    assert zone.locked_by == "bot-alpha"
    assert aisle1.is_locked is False
    assert aisle2.is_locked is False
