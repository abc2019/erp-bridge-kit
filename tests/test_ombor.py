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
        "event_type": "PRODUCED",
    }


@pytest.mark.asyncio
async def test_push_production_batch_defect_event_type():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json
        captured["body"] = json.loads(request.content)
        return httpx.Response(201, json={"id": "event-2", "duplicate": False})

    client = ModuleClient("http://ombor.test", transport=httpx.MockTransport(handler))
    ombor = OmborBridgeClient(client)

    await ombor.push_production_batch(
        source_id="hr-op:op-124", finished_product_id="prod-1",
        completed_units=10, event_type="DEFECT",
    )
    assert captured["body"]["event_type"] == "DEFECT"


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


# --- v0.8.0: tizim ogohlantirishlari ---
@pytest.mark.asyncio
async def test_push_system_alert_payload_and_truncation():
    import json
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        return httpx.Response(201, json={"id": "a1", "notified": True})

    ombor = OmborBridgeClient(ModuleClient("http://ombor.test", transport=httpx.MockTransport(handler)))
    result = await ombor.push_system_alert(source="sales-sync", key="k", level="warning", message="x" * 3000)
    assert captured["path"] == "/system-alerts"
    assert captured["body"]["source"] == "sales-sync" and captured["body"]["level"] == "warning"
    assert len(captured["body"]["message"]) == 1900
    assert result["notified"] is True


@pytest.mark.asyncio
async def test_push_system_alert_rejects_unknown_level():
    ombor = OmborBridgeClient(ModuleClient("http://ombor.test", transport=httpx.MockTransport(
        lambda r: httpx.Response(201, json={}))))
    with pytest.raises(ValueError):
        await ombor.push_system_alert(source="s", key="k", level="panic", message="m")


@pytest.mark.asyncio
async def test_send_system_alert_never_raises():
    def boom(request):
        raise httpx.ConnectError("Ombor ishlamayapti")

    ombor = OmborBridgeClient(ModuleClient("http://ombor.test", transport=httpx.MockTransport(boom)))
    assert await ombor.send_system_alert(source="s", key="k", level="error", message="m") is False

    ok = OmborBridgeClient(ModuleClient("http://ombor.test", transport=httpx.MockTransport(
        lambda r: httpx.Response(201, json={}))))
    assert await ok.send_system_alert(source="s", key="k", level="error", message="m") is True

    unconfigured = OmborBridgeClient(ModuleClient(""))
    assert await unconfigured.send_system_alert(source="s", key="k", level="error", message="m") is False


# --- v0.9.0: ERP mahsulot ma'lumotnomasi ---
@pytest.mark.asyncio
async def test_push_sales_shipment_by_mapping_payload():
    import json
    captured = {}

    def handler(request):
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        return httpx.Response(201, json={"id": "e1", "lines": [], "duplicate": False})

    ombor = OmborBridgeClient(ModuleClient("http://ombor.test", transport=httpx.MockTransport(handler)))
    await ombor.push_sales_shipment_by_mapping(source_id="analytics-order:9", system="analytics",
                                              order_reference="9", items=[{"code": "palov", "quantity": 2}])
    assert captured["path"] == "/sales-shipments/by-mapping"
    assert captured["body"] == {"source_id": "analytics-order:9", "order_reference": "9", "system": "analytics",
                                "items": [{"code": "palov", "quantity": "2"}]}


@pytest.mark.asyncio
async def test_unmapped_codes_extracted_from_422_only():
    from erp_bridge_kit.exceptions import ModuleHTTPError
    from erp_bridge_kit.ombor import unmapped_codes

    def handler(request):
        return httpx.Response(422, json={"detail": {"message": "m", "unmapped_codes": ["somsa", "manti"]}})

    ombor = OmborBridgeClient(ModuleClient("http://ombor.test", transport=httpx.MockTransport(handler)))
    with pytest.raises(ModuleHTTPError) as exc:
        await ombor.push_sales_shipment_by_mapping(source_id="s", system="analytics", items=[{"code": "x", "quantity": 1}])
    assert unmapped_codes(exc.value) == ["somsa", "manti"]
    assert unmapped_codes(ModuleHTTPError(422, '{"detail": [{"loc": ["body"]}]}')) is None  # validatsiya xatosi
    assert unmapped_codes(ModuleHTTPError(400, '{"detail": {"unmapped_codes": ["a"]}}')) is None
    assert unmapped_codes(ModuleHTTPError(422, "not json")) is None
    assert unmapped_codes(RuntimeError("x")) is None


@pytest.mark.asyncio
async def test_get_product_mappings():
    def handler(request):
        assert request.url.path == "/product-mappings/analytics"
        return httpx.Response(200, json=[{"system": "analytics", "code": "palov",
                                          "products": [{"product_id": "p1", "external_code": "PALOV", "name": "Palov",
                                                        "warehouse_type": "FINISHED"}]}])

    ombor = OmborBridgeClient(ModuleClient("http://ombor.test", transport=httpx.MockTransport(handler)))
    mapping = await ombor.get_product_mappings("analytics")
    assert list(mapping) == ["palov"] and mapping["palov"][0]["external_code"] == "PALOV"


# --- v0.10.0: ishlab chiqarish xarita orqali ---
@pytest.mark.asyncio
async def test_push_production_by_mapping_payload():
    import json
    captured = {}

    def handler(request):
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        return httpx.Response(201, json={"code": "QOZON_KABOB", "events": [], "duplicate": False})

    ombor = OmborBridgeClient(ModuleClient("http://ombor.test", transport=httpx.MockTransport(handler)))
    await ombor.push_production_by_mapping(source_id="hr-event:1", code="QOZON_KABOB", completed_units=300,
                                          event_type="DEFECT")
    assert captured["path"] == "/production-batches/by-mapping"
    assert captured["body"] == {"source_id": "hr-event:1", "event_type": "DEFECT", "system": "hr",
                                "code": "QOZON_KABOB", "completed_units": "300"}
