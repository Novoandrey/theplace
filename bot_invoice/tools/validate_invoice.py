#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate_invoice.py — проверка извлечённой накладной (канонический JSON v0.1).

PoC v0 для bot_invoice. Сверяет арифметику построчно и по итогам, чтобы поймать
ошибки распознавания ДО импорта в Quick Resto. Деньги — в копейках.

Допуски (обычные артефакты бумажных накладных):
  • цена/ед. печатается округлённой → |qty*price - sum_no_vat| <= qty копеек + 1;
  • НДС округляется до копейки → |sum_no_vat*rate/100 - vat_sum| <= 1 коп.

Использование:
  python3 validate_invoice.py samples/EK-2029_extracted.json
Код возврата 0 — расхождений нет; 1 — есть жёсткие расхождения (вне допуска).
"""
import json, sys

def rub(k): return f"{k/100:,.2f}".replace(",", " ")

def validate(doc):
    items = doc["items"]; errs = []; warns = []
    sum_no = sum_vat = sum_wth = 0
    places = 0; qty = 0.0; gross = 0.0
    for it in items:
        n = it["n"]
        d_sum = it["sum_no_vat_kop"] - round(it["qty"] * it["price_kop"])
        if abs(d_sum) > it["qty"] + 1:
            errs.append(f"стр.{n}: qty*цена ≠ сумма без НДС ({d_sum:+d} коп)")
        d_vat = it["vat_sum_kop"] - round(it["sum_no_vat_kop"] * it["vat_rate"] / 100)
        if abs(d_vat) > 1:
            errs.append(f"стр.{n}: НДС {it['vat_rate']}% не сходится ({d_vat:+d} коп)")
        if it["sum_with_vat_kop"] != it["sum_no_vat_kop"] + it["vat_sum_kop"]:
            errs.append(f"стр.{n}: сумма с НДС ≠ без НДС + НДС")
        if it.get("confidence") == "med":
            warns.append(f"стр.{n}: confidence=med — {it.get('note') or 'проверить по бумаге'}")
        if it.get("confidence") == "low":
            errs.append(f"стр.{n}: confidence=low — обязательная ручная проверка")
        if it.get("qr_nomenclature_match") in (None, ""):
            warns.append(f"стр.{n}: нет сопоставления с номенклатурой Quick Resto")
        sum_no += it["sum_no_vat_kop"]; sum_vat += it["vat_sum_kop"]
        sum_wth += it["sum_with_vat_kop"]
        places += it["places"]; qty += it["qty"]; gross += it["mass_gross_kg"]

    t = doc["totals"]
    def cmp_money(label, got, exp):
        if exp is not None and got != exp:
            errs.append(f"итог «{label}»: из строк {rub(got)} ≠ в накладной {rub(exp)}")
    cmp_money("сумма без НДС", sum_no, t.get("sum_no_vat_kop"))
    cmp_money("сумма НДС", sum_vat, t.get("vat_sum_kop"))
    cmp_money("сумма с НДС", sum_wth, t.get("sum_with_vat_kop"))
    if t.get("places") is not None and places != t["places"]:
        errs.append(f"итог «мест»: {places} ≠ {t['places']}")
    if t.get("qty") is not None and abs(qty - t["qty"]) > 1e-6:
        errs.append(f"итог «кол-во»: {qty} ≠ {t['qty']}")
    if t.get("mass_gross_kg") is not None and abs(gross - t["mass_gross_kg"]) > 1e-3:
        errs.append(f"итог «масса брутто»: {gross:.3f} ≠ {t['mass_gross_kg']}")
    return errs, warns, dict(sum_no=sum_no, sum_vat=sum_vat, sum_wth=sum_wth,
                             places=places, qty=qty, gross=gross)

def main():
    if len(sys.argv) != 2:
        print("usage: validate_invoice.py <invoice.json>"); return 2
    doc = json.load(open(sys.argv[1], encoding="utf-8"))
    errs, warns, T = validate(doc)
    print(f"Накладная {doc['document']['number']} от {doc['document']['date']} — "
          f"{len(doc['items'])} строк")
    print(f"  из строк: без НДС {rub(T['sum_no'])} | НДС {rub(T['sum_vat'])} | "
          f"с НДС {rub(T['sum_wth'])} | мест {T['places']} | кол-во {T['qty']:.3f}")
    if warns:
        print("\nПРЕДУПРЕЖДЕНИЯ (ручная проверка):")
        for w in warns: print("  •", w)
    if errs:
        print("\nРАСХОЖДЕНИЯ (исправить до импорта):")
        for e in errs: print("  ‼", e)
        return 1
    print("\nАрифметика сходится: жёстких расхождений нет.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
