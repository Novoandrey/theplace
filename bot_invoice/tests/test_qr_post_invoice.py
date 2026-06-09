"""Тесты постера приходной (qr_post_invoice) — бизнес-логика плана.

Проверяем: сопоставление всех 11 строк EK-2029, учётное кол-во каперсов (сухой вес),
карту ставок НДС (10%→2, 22%→3), привязку цены к сумме строки, сверку итогов,
и отказ при неизвестном артикуле / неподдерживаемой ставке НДС.
"""
import json
from pathlib import Path

import pytest
import qr_post_invoice as poster

DATA = Path(__file__).resolve().parent.parent / "data"


@pytest.fixture
def nmap():
    return json.loads((DATA / "nomenclature_map.json").read_text(encoding="utf-8"))


def test_all_lines_resolve_no_errors(ek2029, nmap):
    items, errors = poster.build_plan(ek2029, nmap)
    assert errors == []
    assert len(items) == 11


def test_capers_dry_weight_and_vat22(ek2029, nmap):
    items, _ = poster.build_plan(ek2029, nmap)
    cap = next(i for i in items if i["art"] == "31")
    assert cap["qty"] == 0.45          # сухой/отцеженный вес
    assert cap["vat_id"] == 3          # 22%
    assert cap["product_id"] == 33     # живой SingleProduct.id из карты


def test_minced_beef_vat10(ek2029, nmap):
    items, _ = poster.build_plan(ek2029, nmap)
    beef = next(i for i in items if i["art"] == "23")
    assert beef["vat_id"] == 2         # 10%
    assert beef["qty"] == 6.0


def test_line_price_with_vat_ties_to_sum(ek2029, nmap):
    items, _ = poster.build_plan(ek2029, nmap)
    for i in items:
        assert abs(i["qty"] * i["price_with_vat"] - i["sum_with_vat"]) < 0.01


def test_totals_reconcile(ek2029, nmap):
    items, _ = poster.build_plan(ek2029, nmap)
    t = poster.plan_totals(items)
    assert t["lines"] == 11
    assert t["sum_with_vat"] == 16652.13
    assert t["sum_no_vat"] == 14772.80


def test_all_units_kg(ek2029, nmap):
    items, _ = poster.build_plan(ek2029, nmap)
    assert all(i["unit_id"] == 2 for i in items)


def test_unmapped_article_is_error(ek2029, nmap):
    bad = json.loads(json.dumps(ek2029))
    bad["items"][0]["qr"]["art"] = "999999"
    items, errors = poster.build_plan(bad, nmap)
    assert len(items) == 10
    assert any("999999" in e for e in errors)


def test_unsupported_vat_rate_is_error(ek2029, nmap):
    bad = json.loads(json.dumps(ek2029))
    bad["items"][0]["vat_rate"] = 18
    _, errors = poster.build_plan(bad, nmap)
    assert any("18" in e for e in errors)


def test_zero_qty_is_error(ek2029, nmap):
    bad = json.loads(json.dumps(ek2029))
    bad["items"][0]["qr"]["qty"] = 0
    _, errors = poster.build_plan(bad, nmap)
    assert any("кол-во" in e for e in errors)
