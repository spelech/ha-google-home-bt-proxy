"""Common fixtures for tests."""

from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from aiohttp.test_utils import TestClient, TestServer
from habluetooth.central_manager import set_manager
from habluetooth.manager import BluetoothManager


@pytest_asyncio.fixture
async def aiohttp_client():
    """Fixture providing a test client for aiohttp applications."""
    clients = []

    async def _go(app):
        server = TestServer(app)
        client = TestClient(server)
        await client.start_server()
        clients.append(client)
        return client

    yield _go

    for client in clients:
        await client.close()


@pytest.fixture(autouse=True)
def mock_bluetooth_manager():
    """Ensure BluetoothManager is initialized for tests using habluetooth."""
    adapters = MagicMock()
    adapters.get_bluetooth_adapters.return_value = {}
    adapters.get_bluetooth_adapter_details.return_value = {}
    slot_manager = MagicMock()
    bm = BluetoothManager(bluetooth_adapters=adapters, slot_manager=slot_manager)
    set_manager(bm)
    yield bm
