"""ERP deploydan keyingi tekshiruv (smoke test) - ERP yadrosi 2-bosqich, 2-vazifa.

Owner o'z kompyuterida ishga tushiradi (tokenlar - faqat muhit o'zgaruvchilaridan, hech qayerga yozilmaydi va
ekranga chiqmaydi). Har servisning har ichki endpointi - FAQAT GET; jadval: servis · yo'l · HTTP · shartnoma · ms.
Qo'shimcha auth tekshiruvlari (bazaga yetib bormaydigan qilib):
  - tokensiz GET -> 401 kutiladi (Ombor'da 200 bo'lsa - AUTH_MODE enforce emas!);
  - o'qish (READ) tokeni bilan YOZISH so'rovi -> 403 kutiladi; tana ataylab noto'g'ri ({} yoki yo'q id) -
    auth o'tib ketgan taqdirda ham 404/422 bo'ladi, hech narsa yozilmaydi.

Ishga tushirish:  python -m erp_bridge_kit.smoke        (yoki: erp-smoke)
O'zgaruvchilar (dashboard bilan bir xil nomlar; berilmagan servis - o'tkazib yuboriladi):
  OMBOR_API_BASE_URL, OMBOR_API_TOKEN          FINANCE_API_BASE_URL, FINANCE_API_TOKEN
  ANALYTICS_API_BASE_URL, ANALYTICS_API_TOKEN  HR_INTERNAL_API_BASE_URL, HR_INTERNAL_API_TOKEN
Chiqish kodi: 0 - hammasi joyida, 1 - kamida bitta muammo.
"""
from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass
from datetime import date, timedelta
from urllib.parse import urlsplit

import httpx

from erp_bridge_kit import contracts

ENV = {"ombor": ("OMBOR_API_BASE_URL", "OMBOR_API_TOKEN"), "finance": ("FINANCE_API_BASE_URL", "FINANCE_API_TOKEN"),
       "analytics": ("ANALYTICS_API_BASE_URL", "ANALYTICS_API_TOKEN"),
       "hr": ("HR_INTERNAL_API_BASE_URL", "HR_INTERNAL_API_TOKEN")}
# Parametr talab qiladigan va xavfsiz qiymat berib bo'lmaydigan yo'llar (aniq buyurtma/xabar id kerak)
SKIP = {("analytics", "/internal/orders/by-message"): "aniq xabar id kerak"}
# Auth tekshiruvi: (tokensiz GET yo'li, READ token bilan yozish so'rovi: metod, yo'l, tana)
AUTH = {
    "ombor": ("/products", ("POST", "/products", {})),
    "finance": ("/cash-accounts", ("POST", "/cash-transactions/__smoke__/category", {})),
    "analytics": ("/internal/sales-summary", ("POST", "/internal/orders/0/confirm", {})),
    "hr": ("/internal/today", None),          # HR ichki API'sida yozish yo'q
}


def params_for(service: str, path: str, today: date) -> dict:
    y = today - timedelta(days=1)
    monday = today - timedelta(days=today.weekday())
    first = today.replace(day=1)
    iso = lambda d: f"{d.isoformat()}T00:00:00+09:00"  # noqa: E731
    table = {
        "/internal/sales-summary": {"since": iso(y), "until": iso(today)},
        "/internal/accepted-orders": {"since": iso(y), "until": iso(today)},
        "/internal/receivables": {"since": iso(y), "until": iso(today)},
        "/internal/orders/changes": {"since": iso(y), "limit": "5"},
        "/sales-shipments/by-order": {"since": iso(y)},
        "/production-batches/summary": {"period_from": y.isoformat(), "period_to": today.isoformat()},
        "/production-batches/reconcile": {"date": y.isoformat()},
        "/internal/plan-week": {"week_start": monday.isoformat()},
        "/internal/planned-production": {"week_start": monday.isoformat()},
        "/internal/attendance-summary": {"from": first.isoformat(), "to": today.isoformat()},
        "/internal/production-month": {"month": f"{first:%Y-%m}"},
        "/internal/today": {"date": today.isoformat()},
        "/internal/production-sync-events": {"since_id": "0", "limit": "5"},
        "/pnl": {"period_from": first.isoformat(), "period_to": f"{today.isoformat()}T23:59:59"},
        "/gross-profit": {"period_from": first.isoformat(), "period_to": f"{today.isoformat()}T23:59:59"},
        "/raw-prices/history": {"months": "2"},
        "/receivables/customers": {"months": "1"},
        "/card-receipts/unlinked": {"days": "14"},
        "/cash-transactions/uncategorized": {"limit": "5"},
        "/products": {"only_active": "true"},
        "/low-stock": {"warehouse_type": "RAW"},
    }
    return dict(table.get(path, {}))


@dataclass
class Row:
    service: str
    path: str
    status: str            # HTTP kod yoki "—"
    contract: str          # "mos" | "MOS EMAS: ..." | "—"
    ms: int | None
    ok: bool
    note: str = ""


def _host(url: str) -> str:
    return urlsplit(url).netloc or url


def run(env: dict | None = None, transport: httpx.BaseTransport | None = None, today: date | None = None) -> list[Row]:
    env = os.environ if env is None else env
    today = today or date.today()
    rows: list[Row] = []
    cogs_code = _catalog_code(env, transport)        # Finance /cogs/{code}/full uchun haqiqiy mahsulot kodi
    for service, (url_var, token_var) in ENV.items():
        base, token = (env.get(url_var) or "").rstrip("/"), env.get(token_var) or ""
        if not base or not token:
            rows.append(Row(service, "(sozlanmagan)", "—", "—", None, True, f"{url_var}/{token_var} berilmagan"))
            continue
        auth = {"Authorization": f"Bearer {token}"}
        with httpx.Client(timeout=20, transport=transport) as client:
            for path in contracts.endpoints(service):
                if (service, path) in SKIP:
                    rows.append(Row(service, path, "—", "—", None, True, SKIP[(service, path)]))
                    continue
                real = path
                if "{code}" in path:
                    if not cogs_code:
                        rows.append(Row(service, path, "—", "—", None, True, "mahsulot kodi topilmadi (Ombor katalogi)"))
                        continue
                    real = path.replace("{code}", cogs_code)
                t0 = time.monotonic()
                try:
                    r = client.get(base + real, params=params_for(service, path, today), headers=auth)
                except httpx.HTTPError as e:
                    rows.append(Row(service, path, "—", "—", None, False, f"ulanib bo'lmadi: {type(e).__name__}"))
                    continue
                ms = int((time.monotonic() - t0) * 1000)
                if r.status_code != 200:
                    rows.append(Row(service, path, str(r.status_code), "—", ms, False,
                                    "endpoint yo'q (deploy qilinmagan?)" if r.status_code == 404 else ""))
                    continue
                try:
                    body = r.json()
                except ValueError:
                    rows.append(Row(service, path, "200", "JSON emas", ms, False))
                    continue
                errors = contracts.check(body, contracts.schema(service, path))
                rows.append(Row(service, path, "200", "mos" if not errors else "MOS EMAS: " + "; ".join(errors[:2]),
                                ms, not errors))
            # --- auth qatlami ---
            get_path, write = AUTH[service]
            try:
                r = client.get(base + get_path)
                good = r.status_code == 401
                note = "" if good else ("Ombor AUTH_MODE enforce EMAS - tokensiz ochiq!" if service == "ombor"
                                        and r.status_code == 200 else "401 kutilgan edi")
                rows.append(Row(service, f"tokensiz GET {get_path}", str(r.status_code), "401 kutiladi", None, good, note))
            except httpx.HTTPError as e:
                rows.append(Row(service, f"tokensiz GET {get_path}", "—", "—", None, False, type(e).__name__))
            if write:
                method, wpath, body = write
                try:
                    r = client.request(method, base + wpath, json=body, headers=auth)
                    good = r.status_code in (401, 403)
                    rows.append(Row(service, f"READ token bilan {method} {wpath}", str(r.status_code), "403 kutiladi",
                                    None, good, "" if good else "o'qish tokeni yozish so'roviga ruxsat oldi (tana noto'g'ri - hech narsa yozilmadi)"))
                except httpx.HTTPError as e:
                    rows.append(Row(service, f"READ token bilan {method} {wpath}", "—", "—", None, False, type(e).__name__))
    return rows


def _catalog_code(env, transport) -> str | None:
    base, token = (env.get("OMBOR_API_BASE_URL") or "").rstrip("/"), env.get("OMBOR_API_TOKEN") or ""
    if not base or not token:
        return None
    try:
        with httpx.Client(timeout=20, transport=transport) as client:
            cat = client.get(base + "/catalog", headers={"Authorization": f"Bearer {token}"}).json()
        return next((p["code"] for p in cat.get("products", []) if p.get("code") and p.get("has_recipe")), None)
    except Exception:  # noqa: BLE001 - kodsiz - cogs qatori o'tkazib yuboriladi
        return None


def render(rows: list[Row], env: dict | None = None) -> str:
    env = os.environ if env is None else env
    secrets = [v for k, v in env.items() if k.endswith("_TOKEN") and v]
    lines = [f"{'servis':<10} {'yo‘l':<52} {'HTTP':<5} {'shartnoma':<14} {'ms':>6}  izoh", "-" * 110]
    for r in rows:
        mark = "✅" if r.ok else "❌"
        line = f"{r.service:<10} {r.path[:52]:<52} {r.status:<5} {r.contract[:14]:<14} {r.ms if r.ms is not None else '':>6}  {mark} {r.note}"
        if r.contract.startswith("MOS EMAS"):
            line += "\n" + " " * 12 + r.contract[:200]
        lines.append(line)
    bad = sum(1 for r in rows if not r.ok)
    lines += ["-" * 110, f"Jami: {len(rows)} tekshiruv, {bad} muammo"]
    out = "\n".join(lines)
    for s in secrets:                       # himoya: token hech qachon chiqmasin
        out = out.replace(s, "[yashirildi]")
    return out


def main() -> int:
    env = os.environ
    hosts = ", ".join(f"{s}={_host(env.get(u, ''))}" for s, (u, _t) in ENV.items() if env.get(u))
    print(f"ERP smoke test · {date.today().isoformat()} · {hosts or 'hech qaysi servis sozlanmagan'}")
    rows = run(env)
    print(render(rows, env))
    return 0 if all(r.ok for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
