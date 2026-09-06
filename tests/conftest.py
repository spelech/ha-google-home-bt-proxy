"""Common fixtures for tests."""
import pytest_asyncio
from aiohttp.test_utils import TestClient, TestServer


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
