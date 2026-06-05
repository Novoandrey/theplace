#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
to_storehouse_xml.py — сборка приходной в StoreHouse XML из канонического JSON.

⚠️ ЧЕРНОВИК / ПРЕДПОЛОЖЕНИЕ. Точная схема импорта Quick Resto в открытом виде не найдена.
Структура здесь — обоснованная догадка по тому, что известно о StoreHouse (документ-заголовок +
строки содержимого; ключ строки — артикул; исторически кодировка windows-1251). Файл нужно проверить
ПРОБНЫМ ИМПОРТОМ в тестовую приходную: по реакции QR (принял / какая ошибка / какие поля ждёт) теги,
ключ и кодировку поправим. Имена тегов сделаны самоописательными, чтобы переименование было простым.

Берёт тот же канонический JSON (с сопоставлением `qr` на строку), что и to_qr_import.py.
Деньги в файл — в рублях (2 знака), количество — 3 знака. Цена — «с НДС» (ведущая).

CLI:
  python3 to_storehouse_xml.py samples/EK-2029_extracted.json --out samples/EK-2029_storehouse.xml
  опции: --encoding windows-1251|utf-8  (по умолчанию windows-1251)
"""
import json, sys, argparse, os
import xml.etree.ElementTree as ET
from xml.dom import minidom

def rub(kop): return f"{kop/100:.2f}"

def build_xml(doc):
    d = doc["document"]; sup = doc.get("supplier", {}); tt = doc.get("totals", {})
    root = ET.Element("StoreHouseDocument", {
        "version": "1",
        "type": "приходная накладная",   # тип документа — уточнить по образцу
    })
    h = ET.SubElement(root, "Header")
    ET.SubElement(h, "Number").text = str(d.get("number", ""))
    ET.SubElement(h, "Date").text = str(d.get("date", ""))
    s = ET.SubElement(h, "Supplier", {"inn": str(sup.get("inn") or "")})
    s.text = sup.get("name", "")
    ET.SubElement(h, "Currency").text = "RUB"
    goods = ET.SubElement(root, "Goods")
    skipped = []
    for it in doc["items"]:
        qr = it.get("qr") or {}
        art = qr.get("art")
        if not art:
            skipped.append(it["n"]); continue
        qty = qr["qty"]
        g = ET.SubElement(goods, "Good")
        ET.SubElement(g, "Article").text = str(art)          # ключ сопоставления (предположение)
        ET.SubElement(g, "Barcode").text = ""                # на случай, если QR матчит по штрихкоду
        ET.SubElement(g, "Name").text = qr.get("name", it["name"])
        ET.SubElement(g, "Unit").text = qr.get("unit", "кг")
        ET.SubElement(g, "Quantity").text = f"{qty:.3f}"
        ET.SubElement(g, "PriceWithVAT").text = f"{(it['sum_with_vat_kop']/100)/qty:.2f}"
        ET.SubElement(g, "SumWithoutVAT").text = rub(it["sum_no_vat_kop"])
        ET.SubElement(g, "VATRate").text = str(it["vat_rate"])
        ET.SubElement(g, "VATSum").text = rub(it["vat_sum_kop"])
        ET.SubElement(g, "SumWithVAT").text = rub(it["sum_with_vat_kop"])
    tot = ET.SubElement(root, "Totals")
    ET.SubElement(tot, "SumWithoutVAT").text = rub(tt.get("sum_no_vat_kop", 0))
    ET.SubElement(tot, "VATSum").text = rub(tt.get("vat_sum_kop", 0))
    ET.SubElement(tot, "SumWithVAT").text = rub(tt.get("sum_with_vat_kop", 0))
    return root, skipped

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("json"); ap.add_argument("--out", default=None)
    ap.add_argument("--encoding", default="windows-1251")
    a = ap.parse_args()
    doc = json.load(open(a.json, encoding="utf-8"))
    out = a.out or os.path.splitext(a.json)[0] + "_storehouse.xml"
    root, skipped = build_xml(doc)
    rough = ET.tostring(root, encoding="unicode")
    pretty = minidom.parseString(rough).toprettyxml(indent="  ")
    body = "\n".join(line for line in pretty.split("\n") if line.strip())
    # своя XML-декларация с нужной кодировкой
    body = body.split("\n", 1)[1] if body.startswith("<?xml") else body
    text = f'<?xml version="1.0" encoding="{a.encoding}"?>\n' + body
    with open(out, "w", encoding=a.encoding, errors="xmlcharrefreplace") as f:
        f.write(text)
    print(f"⚠️  ЧЕРНОВИК StoreHouse XML — проверить пробным импортом.")
    print(f"Накладная {doc['document'].get('number','')}: строк — {len(doc['items'])-len(skipped)}; "
          f"файл — {out} (кодировка {a.encoding}).")
    if skipped:
        print("Без артикула (в файл не попали):", skipped)
    print("Если QR не примет — пришли текст ошибки/скрин: поправлю теги/ключ/кодировку.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
