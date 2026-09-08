import pytest

from erp_bridge_kit.idempotency import build_source_id


def test_basic_source_id():
    assert build_source_id("hr-task", "12345") == "hr-task:12345"


def test_multi_part_source_id():
    assert build_source_id("hr-task", "12345", "banka") == "hr-task:12345:banka"


def test_deterministic_same_input_same_output():
    a = build_source_id("hr-task", "12345")
    b = build_source_id("hr-task", "12345")
    assert a == b


def test_strips_whitespace():
    assert build_source_id(" hr-task ", " 12345 ") == "hr-task:12345"


def test_empty_prefix_rejected():
    with pytest.raises(ValueError):
        build_source_id("", "12345")


def test_no_parts_rejected():
    with pytest.raises(ValueError):
        build_source_id("hr-task")


def test_blank_parts_filtered_out():
    assert build_source_id("hr-task", "12345", "  ", "x") == "hr-task:12345:x"
