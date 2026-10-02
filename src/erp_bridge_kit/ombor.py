"""
Ombor moduli bilan gaplashadigan tayyor funksiyalar — production-sync va
kelajakdagi boshqa ko'prik xizmatlari shuni import qiladi, o'zi HTTP
detallarini bilishi shart emas.
"""
import json
import logging

from erp_bridge_kit.http_client import ModuleClient

logger = logging.getLogger(__name__)

ALERT_LEVELS = frozenset({"error", "warning", "recovered"})
ALERT_MAX_MESSAGE = 1900  # Ombor 2000 belgigacha qabul qiladi


class OmborBridgeClient:
    def __init__(self, client: ModuleClient):
        self._client = client

    @property
    def is_configured(self) -> bool:
        return self._client.is_configured

    async def get_product_by_code(self, external_code: str) -> dict:
        """Ombor'ning GET /products/by-code/{code} — mahsulotni kod orqali topadi."""
        return await self._client.get(f"/products/by-code/{external_code}")

    async def list_products(self, *, only_active: bool = True) -> list[dict]:
        """Ombor'ning GET /products — moslashtirish uchun to'liq katalog."""
        return await self._client.get("/products", params={"only_active": only_active})

    async def push_production_batch(
        self, *, source_id: str, finished_product_id: str, completed_units, event_type: str = "PRODUCED"
    ) -> dict:
        """Ombor'ning W4 kontrakti: POST /production-batches (dona-asoslangan).

        event_type: "PRODUCED" (standart) yoki "DEFECT" (brak chiqishi —
        faqat tayyor mahsulot qoldig'ini kamaytiradi, xomashyoga tegmaydi).
        """
        return await self._client.post(
            "/production-batches",
            json={
                "source_id": source_id,
                "finished_product_id": finished_product_id,
                "completed_units": str(completed_units),
                "event_type": event_type,
            },
        )

    async def push_recipe_version_by_code(self, payload: dict) -> dict:
        """Ombor'ning W3+ kontrakti: POST /recipe-versions/by-code."""
        return await self._client.post("/recipe-versions/by-code", json=payload)

    async def push_sales_shipment(self, payload: dict) -> dict:
        """Ombor'ning W5 kontrakti: POST /sales-shipments/by-code (Ombor kodlari bilan)."""
        return await self._client.post("/sales-shipments/by-code", json=payload)

    async def push_sales_shipment_by_mapping(
        self, *, source_id: str, system: str, items: list[dict], order_reference: str | None = None,
    ) -> dict:
        """POST /sales-shipments/by-mapping (Ombor #67): sotuv TASHQI tizim
        kodlari bilan - items=[{"code": "palov", "quantity": "2"}]. Ombor kodlarni
        o'z xaritasi (ERP mahsulot ma'lumotnomasi) bo'yicha mahsulotlarga
        aylantiradi; chaqiruvchi xarita saqlamaydi. Bog'lanmagan kod - 422,
        unmapped_codes(e) bilan aniqlash mumkin."""
        return await self._client.post("/sales-shipments/by-mapping", json={
            "source_id": source_id, "order_reference": order_reference, "system": system,
            "items": [{"code": str(i["code"]), "quantity": str(i["quantity"])} for i in items],
        })

    async def get_product_mappings(self, system: str) -> dict[str, list[dict]]:
        """GET /product-mappings/{system} -> {tashqi_kod: [mahsulotlar]} (Ombor - yagona manba)."""
        rows = await self._client.get(f"/product-mappings/{system}")
        return {row["code"]: row["products"] for row in rows}

    async def push_system_alert(self, *, source: str, key: str, level: str, message: str) -> dict:
        """Ombor'ning POST /system-alerts - muammo haqida OWNER'ga (Ombor Telegram
        boti orqali) xabar. Takrorlarni Ombor o'zi to'xtatadi (bir xil key+message
        24 soat ichida qayta yuborilmaydi; "recovered" - faqat oldin muammo
        yuborilgan bo'lsa). Xato bo'lsa istisno ko'taradi - jimgina yuborish
        uchun send_system_alert ishlating."""
        if level not in ALERT_LEVELS:
            raise ValueError(f"level {sorted(ALERT_LEVELS)} dan biri bo'lishi kerak: {level!r}")
        return await self._client.post("/system-alerts", json={
            "source": source, "key": key, "level": level, "message": message[:ALERT_MAX_MESSAGE],
        })

    async def send_system_alert(self, *, source: str, key: str, level: str, message: str) -> bool:
        """push_system_alert, lekin HECH QACHON istisno ko'tarmaydi: Ombor
        sozlanmagan/ishlamasa - faqat log, False. Sinxronizatsiya xizmatlari
        ogohlantirish sababli to'xtab qolmasligi uchun shuni ishlatadi."""
        if not self.is_configured:
            return False
        try:
            await self.push_system_alert(source=source, key=key, level=level, message=message)
            return True
        except Exception:  # noqa: BLE001
            logger.warning("Ogohlantirishni Ombor'ga yuborib bo'lmadi (%s): %s", key, message[:200], exc_info=True)
            return False


def unmapped_codes(error: Exception) -> list[str] | None:
    """push_sales_shipment_by_mapping 422 xatosidan bog'lanmagan kodlar ro'yxati;
    boshqa xato bo'lsa - None."""
    from erp_bridge_kit.exceptions import ModuleHTTPError
    if not isinstance(error, ModuleHTTPError) or error.status_code != 422:
        return None
    try:
        detail = json.loads(error.body).get("detail")
    except (ValueError, AttributeError):
        return None
    if isinstance(detail, dict) and isinstance(detail.get("unmapped_codes"), list):
        return [str(c) for c in detail["unmapped_codes"]]
    return None
