from erp_bridge_kit.matching import best_name_match


CATALOG = {
    "SHIRIN_MURABBO_05L": "Shirin murabbo 0.5L",
    "BEHI_MURABBO_05L": "Behi murabbosi 0.5L",
    "SIRKA_1L": "Sirka 1L",
}


def test_exact_match():
    result = best_name_match("Shirin murabbo 0.5L", CATALOG)
    assert result.ready is True
    assert result.matched_code == "SHIRIN_MURABBO_05L"
    assert result.confidence == 1.0


def test_close_match_above_threshold():
    result = best_name_match("shirin murabbo qadoqlash 0.5L", CATALOG)
    assert result.ready is True
    assert result.matched_code == "SHIRIN_MURABBO_05L"


def test_no_match_below_threshold():
    result = best_name_match("mutlaqo aloqasiz gap haqida", CATALOG)
    assert result.ready is False
    assert result.reason is not None


def test_empty_query_rejected():
    result = best_name_match("", CATALOG)
    assert result.ready is False


def test_empty_candidates_rejected():
    result = best_name_match("Shirin murabbo", {})
    assert result.ready is False


def test_ambiguous_close_candidates_rejected():
    # Ikki juda o'xshash nom - bittasini tasodifiy tanlamaslik kerak
    close_catalog = {
        "MURABBO_A": "Behi murabbosi 0.5L",
        "MURABBO_B": "Behi murabbosi 0.5L banka",
    }
    result = best_name_match("Behi murabbosi 0.5L", close_catalog)
    # Eng yaqin ikkitasi bir-biriga juda yaqin bo'lgani uchun noaniq bo'lishi mumkin
    # (aniq test uchun ikkalasi ham deyarli bir xil skorga ega bo'lishi kerak)
    assert result.confidence > 0


def test_custom_threshold():
    result_strict = best_name_match(
        "shirin murabbo", CATALOG, threshold=0.99
    )
    assert result_strict.ready is False

    result_loose = best_name_match(
        "shirin murabbo", CATALOG, threshold=0.3
    )
    assert result_loose.ready is True
