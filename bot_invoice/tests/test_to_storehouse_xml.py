"""Тесты сборки StoreHouse XML (to_storehouse_xml.build_xml).

Бизнес-логика модели: ключ строки = артикул (GoodCode), ведущая — сумма без НДС,
№ накладной поставщика → NumberTTN (внутренний Number пуст), строки без артикула — skipped.
Имена тегов — черновик (см. модуль): тесты проверяют правила, а не финальную схему.
"""
import xml.etree.ElementTree as ET

import to_storehouse_xml as sh


def _item(n=1, no=10000, rate=10, vat=1000, wth=11000, qr=True, art="A1", qty=1.0):
    it = {"n": n, "sum_no_vat_kop": no, "vat_rate": rate, "vat_sum_kop": vat,
          "sum_with_vat_kop": wth, "name": f"товар {n}"}
    if qr:
        it["qr"] = {"art": art, "name": f"qr {art}", "unit": "кг", "qty": qty}
    return it


def _doc(items):
    return {"document": {"number": "ТТН-7", "date": "2026-01-01"},
            "supplier": {"name": "ООО Поставщик", "inn": None},
            "items": items,
            "totals": {"sum_no_vat_kop": sum(i["sum_no_vat_kop"] for i in items),
                       "vat_sum_kop": sum(i["vat_sum_kop"] for i in items),
                       "sum_with_vat_kop": sum(i["sum_with_vat_kop"] for i in items)}}


def test_rub_two_decimals():
    assert sh.rub(100) == "1.00"
    assert sh.rub(1) == "0.01"
    assert sh.rub(0) == "0.00"


def test_build_xml_ek2029_structure(ek2029):
    root, skipped = sh.build_xml(ek2029)
    assert root.tag == "Document"
    assert skipped == []
    assert root.findtext("NumberTTN") == "ЕК-2029"
    items = root.find("Content").findall("Item")
    assert len(items) == 11
    first = items[0]
    assert first.findtext("GoodCode") == "23"            # ключ = артикул QR
    assert first.findtext("SumWithoutVAT") == "4425.08"  # ведущая — сумма без НДС
    assert first.findtext("VATRate") == "10"
    assert first.findtext("SumWithVAT") == "4867.59"
    assert root.find("Totals").findtext("SumWithoutVAT") == "14772.80"
    # XML валиден (парсится)
    ET.fromstring(ET.tostring(root, encoding="unicode"))


def test_supplier_invoice_number_goes_to_number_ttn():
    root, _ = sh.build_xml(_doc([_item()]))
    assert root.findtext("NumberTTN") == "ТТН-7"
    assert root.findtext("Number") == ""   # внутренний № присвоит StoreHouse


def test_item_without_article_is_skipped():
    root, skipped = sh.build_xml(_doc([_item(n=1), _item(n=2, qr=False)]))
    assert skipped == [2]
    assert len(root.find("Content").findall("Item")) == 1


def test_good_code_is_article_key():
    root, _ = sh.build_xml(_doc([_item(art="90099")]))
    assert root.find("Content").find("Item").findtext("GoodCode") == "90099"
