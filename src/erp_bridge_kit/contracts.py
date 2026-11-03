"""ERP API shartnomalari (kontraktlar) - YAGONA manba (ERP yadrosi 2-bosqich, 3-vazifa).

`contracts/<servis>.json` - har ichki endpoint uchun: javob SHAKLI (`schema`), NAMUNA javob (`sample`) va kim
ishlatadi (`consumers`). Ishlab chiqaruvchi (Ombor, Finance, Analytics, HR) o'z haqiqiy javobini `assert_matches`
bilan tekshiradi; iste'molchi (dashboard, Finance, sales-sync, production-sync) o'z kodini `sample` bilan ishlatib
ko'radi. Maydon olib tashlansa yoki nomi o'zgarsa - IKKALA tomonda test yiqiladi.

Shakl: "str" | "number" (int, float yoki raqamli matn - Decimal JSON'da matn) | "bool" | "any"; oxirida "?" -
null yoki umuman yo'q bo'lishi mumkin; {"type": "object", "fields": {...}} | {"type": "list", "items": ...} |
{"type": "map", "values": ...} (o'zgaruvchan kalitlar). Yangi (qo'shimcha) maydon - buzilish emas.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

CONTRACTS = Path(__file__).resolve().parent / "contracts"
_NUM = re.compile(r"^-?\d+(\.\d+)?$")


def _scalar_ok(value, kind: str) -> bool:
    if kind == "any":
        return True
    if kind == "str":
        return isinstance(value, str)
    if kind == "bool":
        return isinstance(value, bool)
    if kind == "number":
        return (isinstance(value, (int, float)) and not isinstance(value, bool)) or (
            isinstance(value, str) and bool(_NUM.match(value)))
    raise ValueError(f"noma'lum tur: {kind}")


def check(value, spec, path: str = "$") -> list[str]:
    """Xatolar ro'yxati (bo'sh - mos)."""
    if isinstance(spec, str):
        nullable = spec.endswith("?")
        kind = spec.rstrip("?")
        if value is None:
            return [] if nullable or kind == "any" else [f"{path}: null bo'lmasligi kerak ({kind})"]
        return [] if _scalar_ok(value, kind) else [f"{path}: {kind} kutilgan, {type(value).__name__} keldi"]
    if value is None:
        return [] if spec.get("nullable") else [f"{path}: null bo'lmasligi kerak ({spec['type']})"]
    if spec["type"] == "list":
        if not isinstance(value, list):
            return [f"{path}: ro'yxat kutilgan, {type(value).__name__} keldi"]
        errs: list[str] = []
        for i, item in enumerate(value):
            errs += check(item, spec.get("items", "any"), f"{path}[{i}]")
        return errs
    if spec["type"] == "map":
        if not isinstance(value, dict):
            return [f"{path}: obyekt kutilgan, {type(value).__name__} keldi"]
        errs = []
        for k, v in value.items():
            errs += check(v, spec.get("values", "any"), f"{path}.{k}")
        return errs
    if spec["type"] == "object":
        if not isinstance(value, dict):
            return [f"{path}: obyekt kutilgan, {type(value).__name__} keldi"]
        errs = []
        for name, sub in spec.get("fields", {}).items():
            if name not in value:
                optional = sub.endswith("?") or sub == "any" if isinstance(sub, str) else sub.get("nullable")
                if not optional:
                    errs.append(f"{path}.{name}: maydon yo'q")
            else:
                errs += check(value[name], sub, f"{path}.{name}")
        return errs
    raise ValueError(spec)


SERVICES = ("ombor", "finance", "analytics", "hr")


def load(service: str) -> dict:
    """{"service", "version", "endpoints": {yo'l: {"schema", "sample", "consumers"}}}."""
    return json.loads((CONTRACTS / f"{service}.json").read_text(encoding="utf-8"))


def endpoints(service: str) -> dict:
    return load(service)["endpoints"]


def schema(service: str, path: str):
    return endpoints(service)[path]["schema"]


def sample(service: str, path: str):
    """Namuna javob (yangi nusxa - test o'zgartirsa ham boshqasiga ta'sir qilmaydi)."""
    return json.loads(json.dumps(endpoints(service)[path]["sample"]))


def samples_for(consumer: str) -> dict:
    """Iste'molchi (masalan "sales-sync") ishlatadigan barcha (servis, yo'l) -> namuna."""
    out = {}
    for s in SERVICES:
        for path, e in endpoints(s).items():
            if consumer in e.get("consumers", []):
                out[(s, path)] = sample(s, path)
    return out


def assert_matches(service: str, path: str, value) -> None:
    """Ishlab chiqaruvchi testlari uchun: haqiqiy javob shartnomaga mos bo'lmasa - AssertionError (sabablar bilan)."""
    errors = check(value, schema(service, path))
    if errors:
        raise AssertionError(f"{service} {path} shartnomaga mos emas:\n  " + "\n  ".join(errors[:20]))
