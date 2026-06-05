#!/usr/bin/env python3
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
import argparse
import json
import os
import sys
import xml.etree.ElementTree as ET
from xml.dom import minidom


def rub(kop): return f"{kop/100:.2f}"

def build_xml(doc):
    """v2 — структура по правилам модели StoreHouse (из доков r_keeper):
    ключ строки = код товара (=артикул QR); ведущая — сумма без НДС; цена расчётная (не шлём);
    № поставщика → «Номер ТТН», внутренний № SH присваивает сам. Имена тегов — всё ещё догадка,
    сделаны самоописательными для лёгкой правки по реакции QR."""
    d = doc["document"]
    sup = doc.get("supplier", {})
    tt = doc.get("totals", {})
    root = ET.Element("Document", {"type": "приходная накладная"})   # корень/тип — уточнить
    ET.SubElement(root, "Number").text = ""                          # внутренний № — SH присвоит
    ET.SubElement(root, "NumberTTN").text = str(d.get("number", "")) # № накладной поставщика
    ET.SubElement(root, "Date").text = str(d.get("date", ""))
    s = ET.SubElement(root, "Supplier", {"inn": str(sup.get("inn") or "")})
    s.text = sup.get("name", "")
    ET.SubElement(root, "Receiver").text = ""                        # подразделение-получатель
    content = ET.SubElement(root, "Content")
    skipped = []
    for it in doc["items"]:
        qr = it.get("qr") or {}
        art = qr.get("art")
        if not art:
            skipped.append(it["n"])
            continue
        item = ET.SubElement(content, "Item")
        ET.SubElement(item, "GoodCode").text = str(art)              # код товара = ключ
        ET.SubElement(item, "GoodName").text = qr.get("name", it["name"])
        ET.SubElement(item, "Unit").text = qr.get("unit", "кг")
        ET.SubElement(item, "Quantity").text = f"{qr['qty']:.3f}"
        ET.SubElement(item, "SumWithoutVAT").text = rub(it["sum_no_vat_kop"])  # ведущая
        ET.SubElement(item, "VATRate").text = str(it["vat_rate"])
        ET.SubElement(item, "SumWithVAT").text = rub(it["sum_with_vat_kop"])
    tot = ET.SubElement(root, "Totals")
    ET.SubElement(tot, "SumWithoutVAT").text = rub(tt.get("sum_no_vat_kop", 0))
    ET.SubElement(tot, "VATSum").text = rub(tt.get("vat_sum_kop", 0))
    ET.SubElement(tot, "SumWithVAT").text = rub(tt.get("sum_with_vat_kop", 0))
    return root, skipped

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("json")
    ap.add_argument("--out", default=None)
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
    print("⚠️  ЧЕРНОВИК StoreHouse XML — проверить пробным импортом.")
    n_written = len(doc["items"]) - len(skipped)
    print(f"Накладная {doc['document'].get('number', '')}: строк — {n_written}; "
          f"файл — {out} (кодировка {a.encoding}).")
    if skipped:
        print("Без артикула (в файл не попали):", skipped)
    print("Если QR не примет — пришли текст ошибки/скрин: поправлю теги/ключ/кодировку.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
