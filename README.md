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
