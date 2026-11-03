"""Deploydan keyingi tekshiruv: faqat GET (+ ataylab noto'g'ri yozish so'rovi auth uchun), shartnoma, token chiqmaydi."""
from datetime import date

import httpx

from erp_bridge_kit import contracts, smoke

TOK = {"ombor": "o" * 40, "finance": "f" * 40, "analytics": "a" * 40, "hr": "h" * 40}
ENV = {"OMBOR_API_BASE_URL": "https://ombor.test", "OMBOR_API_TOKEN": TOK["ombor"],
       "FINANCE_API_BASE_URL": "https://finance.test", "FINANCE_API_TOKEN": TOK["finance"],
       "ANALYTICS_API_BASE_URL": "https://analytics.test", "ANALYTICS_API_TOKEN": TOK["analytics"],
       "HR_INTERNAL_API_BASE_URL": "https://hr.test", "HR_INTERNAL_API_TOKEN": TOK["hr"]}


class Fake:
    def __init__(self, tokenless=401, write=403, mutate=None):
        self.requests, self.tokenless, self.write, self.mutate = [], tokenless, write, mutate

    def handler(self, req: httpx.Request) -> httpx.Response:
        self.requests.append(req)
        svc = req.url.host.split(".")[0]
        if req.headers.get("authorization") != f"Bearer {TOK[svc]}":
            return httpx.Response(self.tokenless, json={})
        if req.method != "GET":
            return httpx.Response(self.write, json={"detail": "x"})
        path = req.url.path
        if svc == "finance" and path.startswith("/cogs/"):
            path = "/cogs/{code}/full"
        if path not in contracts.endpoints(svc):
            return httpx.Response(404, json={})
        body = contracts.sample(svc, path)
        if self.mutate:
            body = self.mutate(svc, path, body)
        return httpx.Response(200, json=body)


def _run(fake):
    return smoke.run(ENV, httpx.MockTransport(fake.handler), today=date(2026, 11, 4))


def test_all_green():
    fake = Fake()
    rows = _run(fake)
    bad = [r for r in rows if not r.ok]
    assert not bad, bad
    assert any(r.path == "/cogs/{code}/full" and r.status == "200" for r in rows)       # katalog kodi bilan
    assert any(r.note == "aniq xabar id kerak" for r in rows)
    writes = [r for r in fake.requests if r.method != "GET"]
    assert {(r.url.host, r.url.path) for r in writes} == {("ombor.test", "/products"),
        ("finance.test", "/cash-transactions/__smoke__/category"), ("analytics.test", "/internal/orders/0/confirm")}
    assert all(r.content in (b"{}",) for r in writes)                                   # ataylab bo'sh tana


def test_params_are_sent():
    fake = Fake()
    _run(fake)
    s = next(r for r in fake.requests if r.url.path == "/internal/sales-summary" and r.headers.get("authorization"))
    assert s.url.params["since"] == "2026-11-03T00:00:00+09:00" and s.url.params["until"] == "2026-11-04T00:00:00+09:00"


def test_renamed_field_flagged():
    def mutate(svc, path, body):
        if (svc, path) == ("finance", "/cash-accounts"):
            for a in body:
                a["qoldiq"] = a.pop("balance")
        return body
    rows = _run(Fake(mutate=mutate))
    r = next(r for r in rows if r.service == "finance" and r.path == "/cash-accounts")
    assert not r.ok and r.contract.startswith("MOS EMAS") and "balance" in r.contract


def test_open_ombor_and_write_accepted_flagged():
    rows = _run(Fake(tokenless=200, write=422))
    o = next(r for r in rows if r.service == "ombor" and r.path.startswith("tokensiz"))
    assert not o.ok and "enforce EMAS" in o.note
    w = next(r for r in rows if r.service == "finance" and r.path.startswith("READ token"))
    assert not w.ok and w.status == "422"


def test_unconfigured_service_skipped_and_tokens_never_printed():
    env = {k: v for k, v in ENV.items() if not k.startswith("HR_")}
    rows = smoke.run(env, httpx.MockTransport(Fake().handler), today=date(2026, 11, 4))
    assert any(r.service == "hr" and r.path == "(sozlanmagan)" and r.ok for r in rows)
    out = smoke.render(rows, ENV)
    for t in TOK.values():
        assert t not in out
    assert "Jami:" in out


def test_main_exit_code(monkeypatch, capsys):
    monkeypatch.setattr(smoke, "run", lambda env: [smoke.Row("ombor", "/x", "500", "—", 3, False)])
    for k, v in ENV.items():
        monkeypatch.setenv(k, v)
    assert smoke.main() == 1
    out = capsys.readouterr().out
    assert "ombor.test" in out and TOK["ombor"] not in out
