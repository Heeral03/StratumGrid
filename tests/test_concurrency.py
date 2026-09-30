"""
Concurrency and Thread Safety Tests for FleetScale TreeManager.

Uses threading Barrier and ThreadPoolExecutor to simulate simultaneous,
overlapping lock acquisition, unlock, and upgrade attempts across multiple threads.
"""

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import pytest
from engine.tree_manager import TreeManager


@pytest.fixture
def tm():
    return TreeManager()


def test_simultaneous_same_node_lock_contention(tm):
    """
    20 parallel threads attempt to lock the exact same node ('aisle-A1')
    simultaneously using a sync barrier.

    Verification:
    - Exactly ONE thread acquires the lock.
    - 19 threads receive conflict rejection.
    - The node remains locked by the single winning agent.
    - Parent descendant counter equals exactly 1 (no corrupted increment loops).
    """
    num_threads = 20
    target_node = "aisle-A1"
    barrier = threading.Barrier(num_threads)
    results = []

    def worker(agent_idx):
        agent_id = f"bot-{agent_idx}"
        # Synchronize all threads to fire at the exact same instant
        barrier.wait()
        res = tm.lock(target_node, agent_id)
        return agent_id, res

    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(worker, i) for i in range(num_threads)]
        for f in as_completed(futures):
            results.append(f.result())

    successes = [r for r in results if r[1]["success"] is True]
    failures = [r for r in results if r[1]["success"] is False]

    assert len(successes) == 1, f"Expected 1 winner, got {len(successes)}"
    assert len(failures) == num_threads - 1

    winning_agent = successes[0][0]
    aisle = tm.node_lookup[target_node]
    assert aisle.is_locked is True
    assert aisle.locked_by == winning_agent

    zone_a = tm.node_lookup["zone-A"]
    facility = tm.node_lookup["facility"]

    # Verify atomic counter mathematical integrity under race conditions
    assert zone_a.locked_descendant_count == 1
    assert facility.locked_descendant_count == 1


def test_simultaneous_overlapping_parent_child_contention(tm):
    """
    Simultaneously attempt to lock a parent ('zone-A') and its children ('aisle-A1', 'rack-A1R1', 'bin-A1R1B1')
    across 24 concurrent threads.

    Verification:
    - No invalid state where both an ancestor and a descendant are simultaneously locked.
    - Counter invariants hold perfectly.
    """
    num_threads = 24
    barrier = threading.Barrier(num_threads)
    results = []

    nodes_to_target = ["zone-A", "aisle-A1", "rack-A1R1", "bin-A1R1B1"]

    def worker(idx):
        target = nodes_to_target[idx % len(nodes_to_target)]
        agent_id = f"bot-{idx}"
        barrier.wait()
        res = tm.lock(target, agent_id)
        return target, agent_id, res

    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(worker, i) for i in range(num_threads)]
        for f in as_completed(futures):
            results.append(f.result())

    zone_a = tm.node_lookup["zone-A"]
    aisle_a1 = tm.node_lookup["aisle-A1"]
    rack_a1r1 = tm.node_lookup["rack-A1R1"]
    bin_a1r1b1 = tm.node_lookup["bin-A1R1B1"]

    # Invariant: If parent zone-A is locked, none of its descendants can be locked.
    if zone_a.is_locked:
        assert aisle_a1.is_locked is False
        assert rack_a1r1.is_locked is False
        assert bin_a1r1b1.is_locked is False

    # Invariant: If any child/descendant is locked, parent zone-A cannot be locked.
    descendant_locked = any([aisle_a1.is_locked, rack_a1r1.is_locked, bin_a1r1b1.is_locked])
    if descendant_locked:
        assert zone_a.is_locked is False

    # Calculate actual locked descendants manually and compare with tracked counter
    def count_locked_descendants(node):
        count = 0
        for child in node.children:
            if child.is_locked:
                count += 1
            count += count_locked_descendants(child)
        return count

    actual_locked_descendants = count_locked_descendants(zone_a)
    assert zone_a.locked_descendant_count == actual_locked_descendants


def test_high_concurrency_lock_unlock_stress(tm):
    """
    Stress test with 50 threads continuously locking and unlocking random nodes
    in the tree hierarchy over multiple iterations.

    Verification:
    - Zero deadlocks occur.
    - After all threads complete unlocking their holds, locked_descendant_count
      returns to exactly 0 at every single node in the tree hierarchy.
    """
    import random
    nodes = list(tm.node_lookup.keys())
    num_threads = 50
    barrier = threading.Barrier(num_threads)

    def worker(idx):
        agent_id = f"stress-bot-{idx}"
        barrier.wait()

        # Perform 5 lock-unlock cycles
        for _ in range(5):
            target = random.choice(nodes)
            res = tm.lock(target, agent_id)
            if res["success"]:
                # Unlock if acquired
                tm.unlock(target, agent_id)

    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(worker, i) for i in range(num_threads)]
        for f in as_completed(futures):
            f.result()

    # Final Invariant Check: Tree must be 100% free with all counters at 0
    for node_id, node in tm.node_lookup.items():
        assert node.is_locked is False, f"Node {node_id} remained locked after stress test"
        assert node.locked_descendant_count == 0, f"Node {node_id} has non-zero descendant counter: {node.locked_descendant_count}"
