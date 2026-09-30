"""
Unit tests for TTL lease heartbeats and automatic lease expiration.
"""

import time
import pytest
from engine.tree_manager import TreeManager


@pytest.fixture
def tm():
    return TreeManager()


def test_lock_sets_ttl_expires_at(tm):
    res = tm.lock("aisle-A1", "bot-alpha", ttl_seconds=10)
    assert res["success"] is True
    assert "expires_at" in res
    assert res["expires_at"] > time.time()

    aisle = tm.node_lookup["aisle-A1"]
    assert aisle.is_locked is True
    assert aisle.ttl_remaining > 0


def test_heartbeat_renewal_extends_lease(tm):
    # Acquire 5-second lease
    tm.lock("aisle-A1", "bot-alpha", ttl_seconds=5)
    initial_exp = tm.node_lookup["aisle-A1"].expires_at

    time.sleep(0.1)

    # Fire heartbeat to extend lease by 30 seconds
    hb_res = tm.heartbeat("aisle-A1", "bot-alpha", ttl_seconds=30)
    assert hb_res["success"] is True
    assert "Lease for 'aisle-A1' renewed" in hb_res["message"]

    new_exp = tm.node_lookup["aisle-A1"].expires_at
    assert new_exp > initial_exp


def test_heartbeat_unauthorized_agent_rejected(tm):
    tm.lock("aisle-A1", "bot-alpha", ttl_seconds=10)
    hb_res = tm.heartbeat("aisle-A1", "bot-beta", ttl_seconds=10)
    assert hb_res["success"] is False
    assert "locked by 'bot-alpha', not 'bot-beta'" in hb_res["message"]


def test_heartbeat_unlocked_node_rejected(tm):
    hb_res = tm.heartbeat("aisle-A1", "bot-alpha", ttl_seconds=10)
    assert hb_res["success"] is False
    assert "not currently locked" in hb_res["message"]


def test_automatic_lease_expiration(tm):
    # Lock with very short 0.2 second TTL lease
    tm.lock("aisle-A1", "bot-alpha", ttl_seconds=0.2)

    aisle = tm.node_lookup["aisle-A1"]
    zone_a = tm.node_lookup["zone-A"]
    assert aisle.is_locked is True
    assert zone_a.locked_descendant_count == 1

    # Wait 0.3 seconds for lease to expire
    time.sleep(0.3)

    # Run check_and_expire_locks
    expired = tm.check_and_expire_locks()
    assert len(expired) == 1
    assert expired[0]["node_id"] == "aisle-A1"
    assert expired[0]["agent_id"] == "bot-alpha"

    # Verify node is automatically released and parent counter decremented
    assert aisle.is_locked is False
    assert aisle.locked_by is None
    assert zone_a.locked_descendant_count == 0
