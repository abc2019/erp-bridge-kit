"""
Ombor moduli bilan gaplashadigan tayyor funksiyalar — production-sync va
kelajakdagi boshqa ko'prik xizmatlari shuni import qiladi, o'zi HTTP
detallarini bilishi shart emas.
"""
from erp_bridge_kit.http_client import ModuleClient


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

    async def push_production_batch(self, *, source_id: str, finished_product_id: str, batch_count: int) -> dict:
        """Ombor'ning W4 kontrakti: POST /production-batches."""
        return await self._client.post(
            "/production-batches",
            json={
                "source_id": source_id,
                "finished_product_id": finished_product_id,
                "batch_count": batch_count,
            },
        )

    async def push_recipe_version_by_code(self, payload: dict) -> dict:
        """Ombor'ning W3+ kontrakti: POST /recipe-versions/by-code."""
        return await self._client.post("/recipe-versions/by-code", json=payload)
