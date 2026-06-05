"""Тесты валидатора арифметики накладной (validate_invoice.validate).

Бизнес-логика: построчная сверка кол-во×цена=сумма, НДС, сумма с НДС = без НДС + НДС;
сверка итогов; допуски на округление; флаги confidence и отсутствие сопоставления.
"""
import pytest

import validate_invoice as vi


def _item(n=1, qty=2.0, price_kop=10000, no=20000, rate=10, vat=2000, wth=22000,
          confidence="high", note=None, match="X1", **extra):
    it = {
        "n": n, "qty": qty, "price_kop": price_kop,
        "sum_no_vat_kop": no, "vat_rate": rate, "vat_sum_kop": vat,
        "sum_with_vat_kop": wth, "places": 1, "mass_gross_kg": 0.0,
        "confidence": confidence, "note": note, "qr_nomenclature_match": match,
    }
    it.update(extra)
    return it


def _doc(items, totals=None):
    if totals is None:
        totals = {
            "sum_no_vat_kop": sum(i["sum_no_vat_kop"] for i in items),
            "vat_sum_kop": sum(i["vat_sum_kop"] for i in items),
            "sum_with_vat_kop": sum(i["sum_with_vat_kop"] for i in items),
            "places": sum(i["places"] for i in items),
            "qty": sum(i["qty"] for i in items),
            "mass_gross_kg": sum(i["mass_gross_kg"] for i in items),
        }
    return {"document": {"number": "T-1", "date": "2026-01-01"},
            "items": items, "totals": totals}


def test_ek2029_reconciles(ek2029):
    errs, warns, T = vi.validate(ek2029)
    assert errs == []
    assert warns == []
    assert T["sum_no"] == 1477280
    assert T["sum_vat"] == 187933
    assert T["sum_wth"] == 1665213
    assert T["places"] == 29
    assert T["qty"] == pytest.approx(33.0)


def test_clean_minimal_doc_has_no_errors():
    errs, warns, _ = vi.validate(_doc([_item()]))
    assert errs == []
    assert warns == []


def test_line_sum_mismatch_flagged():
    # qty*цена = 20000, но сумма без НДС = 25000 (вне допуска qty+1)
    errs, _, _ = vi.validate(_doc([_item(no=25000, vat=2500, wth=27500)]))
    assert any("сумма без НДС" in e for e in errs)


def test_vat_mismatch_flagged():
    # ожидаемый НДС 2000, передаём 3000; сумма с НДС согласована, чтобы изолировать НДС
    errs, _, _ = vi.validate(_doc([_item(vat=3000, wth=23000)]))
    assert any("НДС" in e and "не сходится" in e for e in errs)


def test_sum_with_vat_consistency_flagged():
    errs, _, _ = vi.validate(_doc([_item(wth=21999)]))
    assert any("сумма с НДС ≠" in e for e in errs)


def test_rounding_within_tolerance_ok():
    # печатная цена округлена: qty*цена=99999 при сумме 100000 → расхождение 1 коп (в допуске)
    it = _item(qty=3.0, price_kop=33333, no=100000, rate=10, vat=10000, wth=110000)
    errs, _, _ = vi.validate(_doc([it]))
    assert errs == []


def test_vat_rounding_within_one_kopeck_ok():
    # ожидаемый НДС round(10000*10/100)=1000; 1001 — в допуске 1 коп
    it = _item(qty=1.0, price_kop=10000, no=10000, rate=10, vat=1001, wth=11001)
    errs, _, _ = vi.validate(_doc([it]))
    assert errs == []


def test_totals_sum_mismatch_flagged():
    bad = _doc([_item()], totals={"sum_no_vat_kop": 999999, "vat_sum_kop": 2000,
                                  "sum_with_vat_kop": 22000, "places": 1,
                                  "qty": 2.0, "mass_gross_kg": 0.0})
    errs, _, _ = vi.validate(bad)
    assert any("сумма без НДС" in e and "накладной" in e for e in errs)


def test_totals_places_mismatch_flagged():
    bad = _doc([_item()], totals={"sum_no_vat_kop": 20000, "vat_sum_kop": 2000,
                                  "sum_with_vat_kop": 22000, "places": 99,
                                  "qty": 2.0, "mass_gross_kg": 0.0})
    errs, _, _ = vi.validate(bad)
    assert any("мест" in e for e in errs)


def test_confidence_low_is_error():
    errs, _, _ = vi.validate(_doc([_item(confidence="low")]))
    assert any("confidence=low" in e for e in errs)


def test_confidence_med_is_warning():
    errs, warns, _ = vi.validate(_doc([_item(confidence="med", note="плохая печать")]))
    assert errs == []
    assert any("confidence=med" in w for w in warns)


def test_missing_nomenclature_match_is_warning():
    errs, warns, _ = vi.validate(_doc([_item(match=None)]))
    assert errs == []
    assert any("нет сопоставления" in w for w in warns)
