"""ERP shartnomalari: namunalar o'z shakliga mos; maydon olib tashlansa/nomi o'zgarsa - tekshiruv ushlaydi."""
import pytest

from erp_bridge_kit import contracts as c

ALL = [(s, p) for s in c.SERVICES for p in c.endpoints(s)]


@pytest.mark.parametrize("service,path", ALL)
def test_sample_matches_schema(service, path):
    c.assert_matches(service, path, c.sample(service, path))


@pytest.mark.parametrize("service,path", ALL)
def test_every_endpoint_has_consumer_and_nonempty_sample(service, path):
    e = c.endpoints(service)[path]
    assert e["consumers"], (service, path)
    assert e["sample"] not in ([], {}, None), (service, path)


def _first_object(value):
    if isinstance(value, dict) and value:
        return value
    if isinstance(value, list) and value:
        return _first_object(value[0])
    return None


@pytest.mark.parametrize("service,path", ALL)
def test_removed_or_renamed_required_field_is_caught(service, path):
    """Har endpoint: birinchi MAJBURIY maydonni olib tashlash va nomini o'zgartirish - xato beradi."""
    spec = c.schema(service, path)
    target_spec = spec["items"] if isinstance(spec, dict) and spec.get("type") == "list" else spec
    if not isinstance(target_spec, dict) or target_spec.get("type") != "object":
        pytest.skip("obyekt emas")
    required = [k for k, v in target_spec["fields"].items()
                if not (isinstance(v, str) and (v.endswith("?") or v == "any")) and not (isinstance(v, dict) and v.get("nullable"))]
    if not required:
        pytest.skip("majburiy maydon yo'q")
    field = required[0]
    data = c.sample(service, path)
    obj = _first_object(data)
    obj[field + "_yangi"] = obj.pop(field)
    with pytest.raises(AssertionError, match=field):
        c.assert_matches(service, path, data)


def test_consumers_lookup():
    sales = c.samples_for("sales-sync")
    assert ("analytics", "/internal/orders/changes") in sales and ("analytics", "/internal/orders/by-message") in sales
    assert ("hr", "/internal/production-sync-events") in c.samples_for("production-sync")
    assert ("analytics", "/internal/receivables") in c.samples_for("abc2019-finance")
    assert len(c.samples_for("erp-dashboard")) >= 40


def test_sample_is_a_copy():
    a = c.sample("ombor", "/products")
    a[0]["name"] = "o'zgardi"
    assert c.sample("ombor", "/products")[0]["name"] != "o'zgardi"
