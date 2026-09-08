import httpx
import pytest

from erp_bridge_kit.exceptions import ModuleHTTPError, ModuleNotConfigured, ModuleUnreachable
from erp_bridge_kit.http_client import ModuleClient


@pytest.mark.asyncio
async def test_get_not_configured_raises():
    client = ModuleClient(None)
    with pytest.raises(ModuleNotConfigured):
        await client.get("/products/by-code/X")


@pytest.mark.asyncio
async def test_post_not_configured_raises():
    client = ModuleClient(None)
    with pytest.raises(ModuleNotConfigured):
        await client.post("/production-batches", json={})


@pytest.mark.asyncio
async def test_get_success_and_headers():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["role"] = request.headers.get("X-User-Role")
        captured["name"] = request.headers.get("X-User-Name")
        captured["url"] = str(request.url)
        return httpx.Response(200, json={"id": "abc"})

    client = ModuleClient(
        "http://ombor.test",
        actor_name="production-sync",
        actor_role="OWNER",
        transport=httpx.MockTransport(handler),
    )
    result = await client.get("/products/by-code/SIRKA_1L")

    assert result == {"id": "abc"}
    assert captured["role"] == "OWNER"
    assert captured["name"] == "production-sync"
    assert captured["url"] == "http://ombor.test/products/by-code/SIRKA_1L"


@pytest.mark.asyncio
async def test_post_success():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(201, json={"id": "new-id", "duplicate": False})

    client = ModuleClient("http://ombor.test", transport=httpx.MockTransport(handler))
    result = await client.post("/production-batches", json={"batch_count": 3})
    assert result["id"] == "new-id"


@pytest.mark.asyncio
async def test_http_status_error_wrapped():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="not found")

    client = ModuleClient("http://ombor.test", transport=httpx.MockTransport(handler))
    with pytest.raises(ModuleHTTPError) as exc_info:
        await client.get("/missing")
    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.body


@pytest.mark.asyncio
async def test_connection_error_wrapped():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    client = ModuleClient("http://ombor.test", transport=httpx.MockTransport(handler))
    with pytest.raises(ModuleUnreachable):
        await client.get("/x")


def test_is_configured():
    assert ModuleClient(None).is_configured is False
    assert ModuleClient("").is_configured is False
    assert ModuleClient("http://ombor.test").is_configured is True


def test_base_url_trailing_slash_stripped():
    client = ModuleClient("http://ombor.test/")
    assert client.base_url == "http://ombor.test"
