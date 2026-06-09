"""Тесты сопоставления с номенклатурой (match_nomenclature).

Бизнес-логика: нормализация ключей, пороги классификации (alias/fuzzy/weak),
точный матч по aliases и нечёткий по справочнику; регрессия 11 строк EK-2029.
"""
import pytest

import match_nomenclature as mn

# Ожидаемые артикулы QR для 11 строк EK-2029 (фиксируем связку матчер+aliases+справочник)
EXPECTED_ARTS = {
    1: "23", 2: "38", 3: "94", 4: "90024", 5: "90033", 6: "31",
    7: "83", 8: "21", 9: "90022", 10: "90237", 11: "90017",
}


@pytest.fixture
def nomenclature():
    return mn.load_nomenclature()


@pytest.fixture
def aliases():
    return mn.load_aliases()


def test_norm_lowercases_and_normalizes_yo():
    assert mn._norm("Гречка ЁЖИК") == ["гречка", "ежик"]
    assert mn._norm("Мука В/С «Царь» 10") == ["мука", "в", "с", "царь", "10"]


def test_classify_thresholds():
    assert mn.classify(100) == "alias"
    assert mn.classify(50) == "fuzzy"
    assert mn.classify(mn.MATCH_MIN) == "fuzzy"
    assert mn.classify(mn.MATCH_MIN - 0.1) == "weak"


def test_alias_exact_match(nomenclature, aliases):
    res = mn.match(["тунец"], nomenclature, aliases)
    assert res
    score, item = res[0]
    assert score == 100.0
    assert item["art"] == "38"
    assert mn.classify(score) == "alias"


def test_fuzzy_match_without_aliases(nomenclature):
    res = mn.match(["мука"], nomenclature, aliases=[])
    assert res
    assert mn.classify(res[0][0]) == "fuzzy"
    assert "94" in [it["art"] for _, it in res]


def test_unknown_keywords_are_weak(nomenclature):
    res = mn.match(["xyzqwk"], nomenclature, aliases=[])
    # либо ничего, либо верхний кандидат «слабый» — нет уверенного сопоставления
    assert not res or mn.classify(res[0][0]) == "weak"


def test_ek2029_all_lines_resolve_to_expected_alias(nomenclature, aliases):
    for n, keys in mn.EK2029_KEYS.items():
        res = mn.match(keys, nomenclature, aliases)
        assert res, f"строка {n}: нет кандидатов"
        score, item = res[0]
        assert mn.classify(score) == "alias", f"строка {n}: не alias"
        assert item["art"] == EXPECTED_ARTS[n], f"строка {n}: {item['art']} != {EXPECTED_ARTS[n]}"
