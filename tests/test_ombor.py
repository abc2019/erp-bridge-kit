import httpx
import pytest

from erp_bridge_kit.http_client import ModuleClient
from erp_bridge_kit.ombor import OmborBridgeClient


@pytest.mark.asyncio
async def test_get_product_by_code_calls_correct_path():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        return httpx.Response(200, json={"id": "prod-1", "external_code": "SIRKA_1L"})

    client = ModuleClient("http://ombor.test", transport=httpx.MockTransport(handler))
    ombor = OmborBridgeClient(client)

    result = await ombor.get_product_by_code("SIRKA_1L")

    assert captured["path"] == "/products/by-code/SIRKA_1L"
    assert result["id"] == "prod-1"


@pytest.mark.asyncio
async def test_push_production_batch_sends_expected_payload():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json
        captured["body"] = json.loads(request.content)
        return httpx.Response(201, json={"id": "event-1", "duplicate": False})

    client = ModuleClient("http://ombor.test", transport=httpx.MockTransport(handler))
    ombor = OmborBridgeClient(client)

    result = await ombor.push_production_batch(
        source_id="hr-op:op-123", finished_product_id="prod-1", completed_units=312
    )

    assert result["id"] == "event-1"
    assert captured["body"] == {
        "source_id": "hr-op:op-123",
        "finished_product_id": "prod-1",
        "completed_units": "312",
    }


@pytest.mark.asyncio
async def test_push_recipe_version_by_code_passthrough_payload():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(201, json={"id": "rv-1"})

    client = ModuleClient("http://ombor.test", transport=httpx.MockTransport(handler))
    ombor = OmborBridgeClient(client)

    payload = {"source_id": "x", "finished_product_external_code": "CODE", "ingredients": []}
    result = await ombor.push_recipe_version_by_code(payload)
    assert result["id"] == "rv-1"


@pytest.mark.asyncio
async def test_push_sales_shipment_sends_payload():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(201, json={"id": "shipment-1"})

    client = ModuleClient("http://ombor.test", transport=httpx.MockTransport(handler))
    ombor = OmborBridgeClient(client)

    result = await ombor.push_sales_shipment({"source_id": "x", "items": []})
    assert result["id"] == "shipment-1"


def test_is_configured_reflects_underlying_client():
    configured = OmborBridgeClient(ModuleClient("http://ombor.test"))
    not_configured = OmborBridgeClient(ModuleClient(None))
    assert configured.is_configured is True
    assert not_configured.is_configured is False


@pytest.mark.asyncio
async def test_list_products_calls_correct_path():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["query"] = str(request.url.query)
        return httpx.Response(200, json=[{"id": "p1"}, {"id": "p2"}])

    client = ModuleClient("http://ombor.test", transport=httpx.MockTransport(handler))
    ombor = OmborBridgeClient(client)

    result = await ombor.list_products()

    assert captured["path"] == "/products"
    assert len(result) == 2
