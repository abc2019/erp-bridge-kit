# ERP Bridge Kit

Shohona ERP tizimidagi modullararo **ko'prik xizmatlari** (masalan
`production-sync`, kelajakdagi `finance-sync`) uchun umumiy kutubxona.
Har bir yangi ko'prik bir xil narsalarni (idempotentlik, xato boshqarish,
noaniqlik xavfsizligi) qaytadan yozmasligi uchun.

To'liq kontekst: `abc2019/inventory` repo'sidagi
`docs/erp_integration_plan.md`.

## Nima uchun kerak

- **`idempotency.build_source_id`** — barcha avtomatik yozuvlar uchun
  deterministik `source_id` qurish. Ombor (va boshqa modullar) buni
  duplicate himoyasi uchun ishlatadi.
- **`matching.best_name_match`** — "noaniqlik xavfsizligi" qoidasining
  yengil, tarmoqsiz standart amalga oshirilishi: ishonchli moslik
  topilmasa (yoki ikkita nomzod bir-biriga juda yaqin bo'lsa), avtomatik
  tanlov qilinmaydi. Kuchliroq moslashtiruvchi (masalan Analytics'ning
  `parser_core`) ulanganda, xuddi shu `MatchResult` shaklini qaytarsa —
  ko'prik xizmati o'zgarishsiz ishlayveradi.
- **`http_client.ModuleClient`** — istalgan modul (Ombor kabi) kontrakt
  API'siga so'rov yuborish uchun umumiy qatlam (xato turlari, timeout,
  autentifikatsiya header'lari bitta joyda).
- **`ombor.OmborBridgeClient`** — Ombor'ning kontraktlariga (`GET
  /products/by-code`, `POST /production-batches`, `POST
  /recipe-versions/by-code`) tayyor, testlangan wrapper.

## O'rnatish

```bash
pip install git+https://github.com/abc2019/erp-bridge-kit.git
```

Yoki lokal ishlab chiqish uchun:

```bash
pip install -e ".[dev]"
```

## Foydalanish namunasi

```python
from erp_bridge_kit import ModuleClient, OmborBridgeClient, build_source_id, best_name_match

client = ModuleClient(base_url="https://ombor.example.com", actor_name="production-sync")
ombor = OmborBridgeClient(client)

# 1. Matnni mahsulotga moslashtirish (noaniq bo'lsa avtomatik yozilmaydi)
match = best_name_match("Behi murabbosi qadoqlash", {"BEHI_MURABBO_05L": "Behi murabbosi 0.5L"})
if not match.ready:
    ...  # owner tasdig'iga navbatga qo'yiladi
    raise SystemExit

product = await ombor.get_product_by_code(match.matched_code)

# 2. Idempotent hodisa yuborish
source_id = build_source_id("hr-task", task_id)
await ombor.push_production_batch(
    source_id=source_id,
    finished_product_id=product["id"],
    batch_count=5,
)
```

## Testlar

```bash
pip install -e ".[dev]"
pytest -q
```

26 test: idempotentlik, moslashtirish (aniq/yaqin/noaniq/threshold),
HTTP mijoz (muvaffaqiyat/xato/ulanmagan holatlar, `httpx.MockTransport`
bilan — tarmoqqa chiqmasdan), Ombor wrapper.

## Ombor autentifikatsiyasi (v0.7.0)

`ModuleClient(base_url, api_token=...)` — `api_token` berilsa, har so'rovga
`Authorization: Bearer <token>` qo'shiladi. Berilmasa (yoki bo'sh bo'lsa) xatti-harakat
avvalgidek. `X-User-Role`/`X-User-Name` har doim yuboriladi (Ombor `legacy`/`permissive`
rejimida yoki orqaga qaytarilganda kerak). Token repr'ga va xato matniga chiqmaydi.

```python
ModuleClient(
    os.getenv("OMBOR_API_BASE_URL") or None,
    actor_name="production-sync",
    api_token=os.getenv("OMBOR_API_TOKEN"),   # ixtiyoriy
)
```
Ombor tomoni va o'tish tartibi: `abc2019/inventory` -> `docs/auth.md`.

## Tizim ogohlantirishlari (v0.8.0)

Ombor'ning `POST /system-alerts` (Ombor #61) - muammo haqida OWNER'ga Telegram
orqali xabar. Barcha ko'prik xizmatlari shu yagona usuldan foydalanadi:

```python
ok = await ombor.send_system_alert(
    source="production-sync", key="production-sync:cycle",
    level="error",            # error | warning | recovered
    message="3 marta ketma-ket xato ...",
)
```
- `send_system_alert` - hech qachon istisno ko'tarmaydi (Ombor ishlamasa - log, `False`).
- `push_system_alert` - xatoni ko'taradi (o'zingiz ushlamoqchi bo'lsangiz).
- Takrorlarni Ombor to'xtatadi (bir xil `key`+`message` - 24 soat).
- Talab: Ombor tokeni OWNER rolida.

## ERP mahsulot ma'lumotnomasi (v0.9.0)

Ombor - mahsulot identifikatsiyasining yagona manbai (Ombor #67). Mijoz o'z
kodlarini yuboradi, xaritani Ombor saqlaydi:

```python
from erp_bridge_kit.ombor import unmapped_codes

try:
    await ombor.push_sales_shipment_by_mapping(
        source_id="analytics-order:901", system="analytics", order_reference="901",
        items=[{"code": "palov", "quantity": 2}],
    )
except ModuleHTTPError as e:
    missing = unmapped_codes(e)   # ["somsa"] - Ombor'da bog'lanmagan; None - boshqa xato
```
- `get_product_mappings("analytics")` - joriy xarita (o'qish uchun).
- Xaritani OWNER Ombor botida boshqaradi: ⚙️ Sozlamalar → 🔗 Mahsulot kodlari.

## Ishlab chiqarish xarita orqali (v0.10.0)

```python
await ombor.push_production_by_mapping(
    source_id="hr-event:produced:plan_task:7", code="QOZON_KABOB",
    completed_units=300, event_type="PRODUCED",   # yoki "DEFECT"
)
```
Ombor kodni o'z xaritasi (`system=hr`) bo'yicha mahsulot(lar)ga aylantiradi —
tarkibli taom qismlarga bo'linadi. Xaritada yo'q kod — shu kodli Ombor mahsuloti.
