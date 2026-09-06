"""Unit tests for round-robin scan orchestrator."""

import asyncio

import pytest

from custom_components.google_home_bt_proxy.const import (
    ORCHESTRATION_INDEPENDENT,
    ORCHESTRATION_ROUND_ROBIN,
)
from custom_components.google_home_bt_proxy.orchestrator import ScanOrchestrator


@pytest.mark.asyncio
async def test_orchestrator_independent_mode():
    """In independent mode, multiple speakers can acquire slots concurrently without queuing."""
    orchestrator = ScanOrchestrator(mode=ORCHESTRATION_INDEPENDENT)
    assert orchestrator.is_enabled is False
    assert orchestrator.queue_depth == 0
    assert orchestrator.current_speaker is None
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


@pytest.mark.asyncio
async def test_orchestrator_round_robin_serialization():
    """In round_robin mode, hardware scan slots are strictly serialized."""
    orchestrator = ScanOrchestrator(mode=ORCHESTRATION_ROUND_ROBIN)
    assert orchestrator.is_enabled is True

    execution_order = []

    async def worker(speaker_id: str, hold_duration: float):
        async with orchestrator.acquire_slot(speaker_id) as acquired:
            assert acquired is True
            assert orchestrator.current_speaker == speaker_id
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
