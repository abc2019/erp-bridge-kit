"""
Ombor (va kelajakda boshqa modullar) kontrakt API'lariga so'rov yuboruvchi
umumiy qatlam. Barcha ko'prik xizmatlari shu orqali gaplashadi — shuning
uchun xato boshqarish, timeout, header'lar bir joyda, bir marta yozilgan.
"""
import httpx

from erp_bridge_kit.exceptions import ModuleHTTPError, ModuleNotConfigured, ModuleUnreachable


class ModuleClient:
    """
    Ixtiyoriy kontrakt modul (Ombor kabi) bilan gaplashish uchun yupqa qatlam.

    Autentifikatsiya hozircha oddiy header-asosida (X-User-Role/X-User-Name) —
    W1-W4'da Ombor'ning o'zida ishlatilgan vaqtinchalik naqsh bilan bir xil.
    Kelajakda haqiqiy auth qo'shilsa, faqat shu klass ichida o'zgaradi —
    iste'molchilar (production-sync va h.k.) o'zgarishi shart emas.
    """

    def __init__(
        self,
        base_url: str | None,
        *,
        actor_name: str = "erp-bridge",
        actor_role: str = "OWNER",
        timeout: float = 15.0,
        transport: httpx.BaseTransport | None = None,
    ):
        self.base_url = base_url.rstrip("/") if base_url else None
        self.actor_name = actor_name
        self.actor_role = actor_role
        self.timeout = timeout
        self._transport = transport  # testlarda httpx.MockTransport berish uchun

    @property
    def is_configured(self) -> bool:
        return bool(self.base_url)

    def _require_configured(self) -> str:
        if not self.base_url:
            raise ModuleNotConfigured("base_url sozlanmagan")
        return self.base_url

    async def get(self, path: str, *, params: dict | None = None) -> dict:
        base_url = self._require_configured()
        async with httpx.AsyncClient(timeout=self.timeout, transport=self._transport) as client:
            try:
                resp = await client.get(
                    f"{base_url}{path}", params=params, headers=self._headers()
                )
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPStatusError as e:
                raise ModuleHTTPError(e.response.status_code, e.response.text)
            except httpx.HTTPError as e:
                raise ModuleUnreachable(str(e))

    async def post(self, path: str, *, json: dict) -> dict:
        base_url = self._require_configured()
        async with httpx.AsyncClient(timeout=self.timeout, transport=self._transport) as client:
            try:
                resp = await client.post(
                    f"{base_url}{path}", json=json, headers=self._headers()
                )
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPStatusError as e:
                raise ModuleHTTPError(e.response.status_code, e.response.text)
            except httpx.HTTPError as e:
                raise ModuleUnreachable(str(e))

    def _headers(self) -> dict:
        return {"X-User-Role": self.actor_role, "X-User-Name": self.actor_name}
