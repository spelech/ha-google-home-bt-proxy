"""Unit tests for round-robin scan orchestrator and adaptive concurrency scaling."""

import asyncio

import pytest

from custom_components.google_home_bt_proxy.const import (
    ORCHESTRATION_INDEPENDENT,
    ORCHESTRATION_ROUND_ROBIN,
)
from custom_components.google_home_bt_proxy.orchestrator import (
    ScanOrchestrator,
    calculate_recommended_concurrency,
)


def test_calculate_recommended_concurrency():
    """Verify adaptive concurrency scales slots to stay within target scan cycle."""
    # 1 or 2 speakers with 4s scan + 4s interval (8s target cycle) -> 1 concurrent slot
    assert calculate_recommended_concurrency(1, scan_timeout=4, scan_interval=4) == 1
    assert calculate_recommended_concurrency(2, scan_timeout=4, scan_interval=4) == 1

    # 3 or 4 speakers with 4s scan + 4s interval -> 2 concurrent slots
    assert calculate_recommended_concurrency(3, scan_timeout=4, scan_interval=4) == 2
    assert calculate_recommended_concurrency(4, scan_timeout=4, scan_interval=4) == 2

    # 5 or 6 speakers -> 3 concurrent slots
    assert calculate_recommended_concurrency(5, scan_timeout=4, scan_interval=4) == 3
    assert calculate_recommended_concurrency(6, scan_timeout=4, scan_interval=4) == 3

    # 8 speakers -> 4 concurrent slots
    assert calculate_recommended_concurrency(8, scan_timeout=4, scan_interval=4) == 4


@pytest.mark.asyncio
async def test_orchestrator_independent_mode():
    """In independent mode, multiple speakers can acquire slots concurrently without queuing."""
    orchestrator = ScanOrchestrator(mode=ORCHESTRATION_INDEPENDENT)
    assert orchestrator.is_enabled is False
    assert orchestrator.queue_depth == 0
    assert orchestrator.current_speaker is None
    assert orchestrator.active_speakers == []
    assert orchestrator.total_scans == 0

    results = []

    async def worker(speaker_id: str, hold_duration: float):
        async with orchestrator.acquire_slot(speaker_id) as acquired:
            assert acquired is True
            results.append(f"{speaker_id}_started")
            await asyncio.sleep(hold_duration)
            results.append(f"{speaker_id}_finished")

    # Run two workers concurrently
    t1 = asyncio.create_task(worker("speaker_1", 0.05))
    t2 = asyncio.create_task(worker("speaker_2", 0.05))
    await asyncio.gather(t1, t2)

    # In independent mode, both start before either finishes
    assert results == [
        "speaker_1_started",
        "speaker_2_started",
        "speaker_1_finished",
        "speaker_2_finished",
    ]
    assert orchestrator.queue_depth == 0
    assert orchestrator.get_last_wait_duration("speaker_1") == 0.0


@pytest.mark.asyncio
async def test_orchestrator_round_robin_serialization():
    """In round_robin mode with 1-2 speakers (1 slot), hardware scan slots are serialized."""
    orchestrator = ScanOrchestrator(mode=ORCHESTRATION_ROUND_ROBIN, speaker_count=2)
    assert orchestrator.is_enabled is True
    assert orchestrator.max_concurrent == 1

    execution_order = []

    async def worker(speaker_id: str, hold_duration: float):
        async with orchestrator.acquire_slot(speaker_id) as acquired:
            assert acquired is True
            assert orchestrator.current_speaker == speaker_id
            assert speaker_id in orchestrator.active_speakers
            execution_order.append(f"{speaker_id}_start")
            await asyncio.sleep(hold_duration)
            execution_order.append(f"{speaker_id}_end")

    task1 = asyncio.create_task(worker("kitchen", 0.05))
    # Give task1 a tiny slice to acquire slot
    await asyncio.sleep(0.01)

    task2 = asyncio.create_task(worker("living_room", 0.05))
    await asyncio.sleep(0.01)

    # While task1 runs, living_room should be queued
    assert orchestrator.queue_depth == 1
    assert orchestrator.current_speaker == "kitchen"

    await asyncio.gather(task1, task2)

    # Verify strict serialization
    assert execution_order == [
        "kitchen_start",
        "kitchen_end",
        "living_room_start",
        "living_room_end",
    ]
    assert orchestrator.total_scans == 2
    assert orchestrator.queue_depth == 0
    assert orchestrator.current_speaker is None
    assert orchestrator.last_scan_time is not None
    assert orchestrator.get_last_wait_duration("living_room") >= 0.02


@pytest.mark.asyncio
async def test_orchestrator_adaptive_bounded_concurrency():
    """With 4 speakers (2 slots), 2 speakers scan concurrently while the 3rd queues."""
    orchestrator = ScanOrchestrator(
        mode=ORCHESTRATION_ROUND_ROBIN,
        speaker_count=4,
        scan_timeout=4,
        scan_interval=4,
    )
    assert orchestrator.max_concurrent == 2

    events = []

    async def worker(speaker_id: str, hold_duration: float):
        async with orchestrator.acquire_slot(speaker_id) as acquired:
            assert acquired is True
            events.append(f"{speaker_id}_start")
            await asyncio.sleep(hold_duration)
            events.append(f"{speaker_id}_end")

    t1 = asyncio.create_task(worker("spk_1", 0.06))
    t2 = asyncio.create_task(worker("spk_2", 0.06))
    await asyncio.sleep(0.01)

    # Both spk_1 and spk_2 should hold active slots simultaneously
    assert orchestrator.active_speakers == ["spk_1", "spk_2"]
    assert orchestrator.queue_depth == 0

    # Launch spk_3 while both slots are occupied
    t3 = asyncio.create_task(worker("spk_3", 0.02))
    await asyncio.sleep(0.01)
    assert orchestrator.queue_depth == 1

    await asyncio.gather(t1, t2, t3)
    assert events[:2] == ["spk_1_start", "spk_2_start"]
    assert "spk_3_start" in events[2:]
    assert orchestrator.total_scans == 3
    assert orchestrator.active_speakers == []


def test_orchestrator_update_scaling_and_explicit_override():
    """Verify update_scaling adjusts max_concurrent unless explicit max_concurrent was set."""
    orchestrator = ScanOrchestrator(mode=ORCHESTRATION_ROUND_ROBIN, speaker_count=2)
    assert orchestrator.max_concurrent == 1

    orchestrator.update_scaling(speaker_count=6, scan_timeout=4, scan_interval=4)
    assert orchestrator.max_concurrent == 3

    explicit_orch = ScanOrchestrator(
        mode=ORCHESTRATION_ROUND_ROBIN,
        speaker_count=6,
        max_concurrent=2,
    )
    assert explicit_orch.max_concurrent == 2
    explicit_orch.update_scaling(speaker_count=10, scan_timeout=4, scan_interval=4)
    assert explicit_orch.max_concurrent == 2


@pytest.mark.asyncio
async def test_orchestrator_timeout_handling():
    """Verify waiting speakers time out cleanly if another speaker holds the slot too long."""
    orchestrator = ScanOrchestrator(mode=ORCHESTRATION_ROUND_ROBIN)

    holder_running = asyncio.Event()

    async def slow_holder():
        async with orchestrator.acquire_slot("slow_speaker") as acquired:
            assert acquired is True
            holder_running.set()
            await asyncio.sleep(0.2)

    async def impatient_waiter():
        await holder_running.wait()
        # Attempt to acquire with very short timeout
        async with orchestrator.acquire_slot("impatient_speaker", timeout=0.05) as acquired:
            return acquired

    task_holder = asyncio.create_task(slow_holder())
    task_waiter = asyncio.create_task(impatient_waiter())

    acquired_result = await task_waiter
    assert acquired_result is False
    assert orchestrator.queue_depth == 0

    await task_holder
    assert orchestrator.current_speaker is None

    # After holder finishes, another acquisition succeeds
    async with orchestrator.acquire_slot("next_speaker") as acquired:
        assert acquired is True


@pytest.mark.asyncio
async def test_orchestrator_cancelled_waiter_cleans_up():
    """Verify a task cancelled while waiting in the queue removes itself and wakes next waiter."""
    orchestrator = ScanOrchestrator(mode=ORCHESTRATION_ROUND_ROBIN, max_concurrent=1)

    holder_ready = asyncio.Event()
    release_holder = asyncio.Event()

    async def holder():
        async with orchestrator.acquire_slot("holder"):
            holder_ready.set()
            await release_holder.wait()

    async def waiter(spk_id: str):
        async with orchestrator.acquire_slot(spk_id) as acquired:
            return acquired

    t_holder = asyncio.create_task(holder())
    await holder_ready.wait()

    t_wait1 = asyncio.create_task(waiter("wait_1"))
    await asyncio.sleep(0.01)
    t_wait2 = asyncio.create_task(waiter("wait_2"))
    await asyncio.sleep(0.01)
    assert orchestrator.queue_depth == 2

    # Cancel the head-of-line waiter
    t_wait1.cancel()
    with pytest.raises(asyncio.CancelledError):
        await t_wait1

    assert orchestrator.queue_depth == 1
    release_holder.set()
    await t_holder
    assert await t_wait2 is True


@pytest.mark.asyncio
async def test_orchestrator_exception_releases_lock():
    """Verify exceptions inside the context manager properly release the lock."""
    orchestrator = ScanOrchestrator(mode=ORCHESTRATION_ROUND_ROBIN)

    with pytest.raises(RuntimeError, match="Hardware scan failure"):
        async with orchestrator.acquire_slot("failing_speaker") as acquired:
            assert acquired is True
            raise RuntimeError("Hardware scan failure")

    assert orchestrator.current_speaker is None
    assert orchestrator.queue_depth == 0

    # Next speaker should acquire slot with zero deadlock
    async with orchestrator.acquire_slot("recovery_speaker") as acquired:
        assert acquired is True
        assert orchestrator.current_speaker == "recovery_speaker"


@pytest.mark.asyncio
async def test_orchestrator_acquire_without_timeout():
    """Verify acquire_slot works when timeout=None."""
    orchestrator = ScanOrchestrator(mode=ORCHESTRATION_ROUND_ROBIN)

    async with orchestrator.acquire_slot("speaker_no_timeout", timeout=None) as acquired:
        assert acquired is True
        assert orchestrator.current_speaker == "speaker_no_timeout"

    assert orchestrator.current_speaker is None
