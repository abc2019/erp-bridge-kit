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

    Autentifikatsiya:
      - `api_token` berilsa, har so'rovga `Authorization: Bearer <token>`
        qo'shiladi (Ombor'ning token asosidagi auth'i uchun; rol tokenga
        bog'langan, header'ga emas).
      - X-User-Role/X-User-Name HAR DOIM ham yuboriladi: Ombor hali
        `legacy`/`permissive` rejimda bo'lsa yoki orqaga qaytarilsa, ular
        kerak. `enforce` rejimida Ombor ularni e'tiborsiz qoldiradi.
      - `api_token` berilmasa (yoki bo'sh/probel bo'lsa) xatti-harakat
        avvalgidek - Authorization header yuborilmaydi.
    Token hech qachon repr'ga, xato matniga yoki log'ga chiqmaydi.
    """

    def __init__(
        self,
        base_url: str | None,
        *,
        actor_name: str = "erp-bridge",
        actor_role: str = "OWNER",
        timeout: float = 15.0,
        transport: httpx.BaseTransport | None = None,
        api_token: str | None = None,
    ):
        self.base_url = base_url.rstrip("/") if base_url else None
        self.actor_name = actor_name
        self.actor_role = actor_role
        self.timeout = timeout
        self._transport = transport  # testlarda httpx.MockTransport berish uchun
        token = (api_token or "").strip()
        self._api_token = token or None

    def __repr__(self) -> str:
        # api_token ataylab chiqarilmaydi
        return (
            f"ModuleClient(base_url={self.base_url!r}, actor_name={self.actor_name!r}, "
            f"has_token={self._api_token is not None})"
        )

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
        headers = {"X-User-Role": self.actor_role, "X-User-Name": self.actor_name}
        if self._api_token:
            headers["Authorization"] = f"Bearer {self._api_token}"
        return headers
