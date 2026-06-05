#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
to_qr_import.py — сборка файла импорта приходной Quick Resto из канонического JSON.

PoC v0 для bot_invoice. Берёт извлечённую накладную (канонический JSON, обогащённый
сопоставлением `qr` на каждую строку) и пишет файл в раскладке ПН135 (xlsx + csv).
Цена «с НДС» ведущая: Цена с НДС = Сумма с НДС ÷ Кол-во; суммы без НДС/НДС — из накладной.
Деньги в JSON — в копейках; в файл — в рублях. Сверяет итоги файла с итогами накладной.

Каждая строка JSON должна иметь объект `qr`:
  {"art": "23", "name": "Фарш говяжий 70/30", "unit": "кг", "qty": 6.0, "note": null}
Строки без `qr.art` в файл не попадают и выводятся как нерешённые.

CLI:
  python3 to_qr_import.py samples/EK-2029_extracted.json --out samples/EK-2029_qr_import
Код возврата: 0 — файл собран и итоги сходятся; 1 — есть нерешённые строки или итоги не сходятся.
"""
import json, sys, csv, argparse, os

COLS = ["№", "Артикул", "Тип продукта", "Наименование", "Кол-во, ед. изм.", "",
        "Цена с НДС, руб.", "Сумма без НДС, руб.", "НДС", "Сумма НДС, руб.", "Сумма с НДС, руб."]

def rub(kop): return round(kop / 100, 2)

def build(doc):
    rows, unresolved, flags = [], [], []
    t_no = t_vat = t_wth = 0
    for it in doc["items"]:
        qr = it.get("qr") or {}
        art = qr.get("art")
        if not art:
            unresolved.append(it["n"]); continue
        qty = qr["qty"]; unit = qr.get("unit", "кг")
        no, vat, wth, rate = (it["sum_no_vat_kop"], it["vat_sum_kop"],
                              it["sum_with_vat_kop"], it["vat_rate"])
        price = round(rub(wth) / qty, 2)                     # цена с НДС за ед.
        rows.append([it["n"], art, qr.get("type", "Ингредиент"), qr.get("name", it["name"]),
                     round(qty, 3), unit, price, rub(no), f"{rate}.0 %", rub(vat), rub(wth)])
        t_no += no; t_vat += vat; t_wth += wth
        if qr.get("note"):
            flags.append(f"стр.{it['n']}: {qr['note']}")
    tt = doc.get("totals", {})
    recon = {
        "без НДС": (t_no, tt.get("sum_no_vat_kop")),
        "НДС":     (t_vat, tt.get("vat_sum_kop")),
        "с НДС":   (t_wth, tt.get("sum_with_vat_kop")),
    }
    return rows, unresolved, flags, recon

def write_files(rows, out):
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out + ".csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter="\t"); w.writerow(COLS); [w.writerow(r) for r in rows]
    from openpyxl import Workbook
    from openpyxl.styles import Font
    wb = Workbook(); ws = wb.active; ws.title = "import"
    ws.append(COLS); [ws.append(r) for r in rows]
    for c in ws[1]: c.font = Font(name="Arial", bold=True)
    for col, wd in zip("ABCDEFGHIJK", [5, 9, 12, 34, 12, 6, 13, 15, 8, 13, 14]):
        ws.column_dimensions[col].width = wd
    wb.save(out + ".xlsx")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("json"); ap.add_argument("--out", default=None)
    a = ap.parse_args()
    doc = json.load(open(a.json, encoding="utf-8"))
    out = a.out or os.path.splitext(a.json)[0] + "_qr_import"
    rows, unresolved, flags, recon = build(doc)
    if rows:
        write_files(rows, out)
    num = doc["document"]["number"]
    print(f"Накладная {num}: строк в файл — {len(rows)}; файл — {out}.{{csv,xlsx}}")
    ok = True
    print("Сверка итогов (файл vs накладная):")
    for label, (got, exp) in recon.items():
        mark = "OK" if (exp is not None and got == exp) else "‼"
        if mark == "‼": ok = False
        print(f"  {label:7}: {rub(got):>10} | {('—' if exp is None else rub(exp)):>10}  {mark}")
    if flags:
        print("Подтвердить (перенесено в файл как есть):")
        for f in flags: print("  ⚑", f)
    if unresolved:
        ok = False
        print("НЕ сопоставлены (нет qr.art) — в файл не попали:", unresolved)
    print("Готово." if ok else "Есть замечания (см. выше).")
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main())
