#!/usr/bin/env python3
"""qr_post_invoice.py — QuickRestoSupplyPoster (T028): постинг приходной в QR (путь A).

Берёт извлечённую накладную (*_extracted.json) + карту артикул→id (data/nomenclature_map.json),
строит план и создаёт приходную в Quick Resto трёхшаговой схемой открытого API
(см. qr_create_test): create-header → add-item × N → recalc (пересчёт себестоимости).

БЕЗОПАСНОСТЬ.
- По умолчанию dry-run: печатает план (шапка + позиции + сверка итогов), НИЧЕГО не шлёт.
- Реальный постинг — только команда `post --confirm`.
- Любая ошибка сопоставления (артикул не в карте, плохая ставка НДС) отменяет постинг.
- При сбое на позиции печатается id частичной накладной и команда её удаления.
- Количество берётся из qr.qty (учётное: каперсы 0.45 кг по сухому весу уже сконвертированы).
- Креды только из окружения (QR_LAYER/QR_LOGIN/QR_PASSWORD) — через qr_create_test.

ЗАПУСК:
    python qr_post_invoice.py plan --extracted samples/EK-2029_extracted.json \
        --map data/nomenclature_map.json
    python qr_post_invoice.py post --extracted ... --map ... \
        --provider-id 2 --provider-class businessman --store-id 1 --number EK-2029 --confirm
"""
import argparse
import json
import sys

import qr_create_test as qr  # общий клиент open API (_env/_request/_save_error/build_recalc/конст.)

# Ставки НДС (%) → id словаря core.dictionaries.vat (подтверждено /api/tree, 2026-06-09)
VAT_ID_BY_PERCENT = {0: 1, 5: 4, 10: 2, 22: 3}


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_plan(extracted, nmap):
    """Собрать позиции для постинга из извлечённой накладной + карты артикул→id.

    -> (items, errors). items — список словарей-позиций; errors — список строк (если не пусто,
    постинг отменяется). Цены: priceWithVat = сумма_с_ндс / кол-во (ведущая, из накладной);
    price = сумма_без_ндс / кол-во.
    """
    items, errors = [], []
    for it in extracted.get("items", []):
        n = it.get("n")
        qr_ref = it.get("qr") or {}
        art = qr_ref.get("art")
        qty = qr_ref.get("qty")
        rate = it.get("vat_rate")
        rec = nmap.get(str(art)) if art is not None else None
        if rec is None:
            errors.append(f"стр.{n}: артикул {art!r} не найден в карте номенклатуры")
            continue
        if not isinstance(qty, (int, float)) or qty <= 0:
            errors.append(f"стр.{n} (арт.{art}): некорректное кол-во {qty!r}")
            continue
        if rate not in VAT_ID_BY_PERCENT:
            rates = list(VAT_ID_BY_PERCENT)
            errors.append(f"стр.{n} (арт.{art}): ставка НДС {rate!r}% не в карте {rates}")
            continue
        sum_with = it.get("sum_with_vat_kop", 0) / 100
        sum_no = it.get("sum_no_vat_kop", 0) / 100
        items.append({
            "n": n,
            "art": str(art),
            "name": rec.get("name") or qr_ref.get("name"),
            "product_id": rec["id"],
            "unit_id": rec.get("unit"),
            "qty": qty,
            "price": round(sum_no / qty, 5),
            "price_with_vat": round(sum_with / qty, 5),
            "vat_id": VAT_ID_BY_PERCENT[rate],
            "vat_rate": rate,
            "sum_no_vat": round(sum_no, 2),
            "sum_with_vat": round(sum_with, 2),
        })
    return items, errors


def plan_totals(items):
    return {
        "lines": len(items),
        "sum_no_vat": round(sum(i["sum_no_vat"] for i in items), 2),
        "sum_with_vat": round(sum(i["sum_with_vat"] for i in items), 2),
    }


def find_duplicate(invoices, number):
    """Среди списка приходных найти id документа с таким documentNumber (или None)."""
    for it in invoices:
        if isinstance(it, dict) and str(it.get("documentNumber")) == str(number):
            return it.get("id")
    return None


def check_existing(layer, login, password, number):
    """Проверить через /api/list, нет ли уже приходной с таким номером.

    -> (ok, dup_id): ok=False если список получить не удалось; dup_id — id дубля или None.
    """
    st, bd = qr._request(layer, login, password, "list")
    if st != 200:
        return False, None
    try:
        data = json.loads(bd)
    except json.JSONDecodeError:
        return False, None
    if not isinstance(data, list):
        return False, None
    return True, find_duplicate(data, number)


def make_header_payload(number, date, provider_id, provider_class, store_id):
    return {
        "className": qr.CN_INVOICE,
        "documentNumber": number,
        "invoiceDate": date or qr._now_iso(),
        "paid": False,
        "provider": {"className": qr.PROVIDER_CLASSES[provider_class], "id": provider_id},
        "store": {"className": qr.CN_STORE, "id": store_id},
    }


def make_item_payload(invoice_id, item):
    return {
        "className": qr.CN_ITEM,
        "extraExpenses": 0,
        "actualAmount": item["qty"],
        "price": item["price"],
        "priceWithVat": item["price_with_vat"],
        "product": {"className": qr.CN_SINGLEPRODUCT, "id": item["product_id"]},
        "measureUnit": {"className": qr.CN_UNIT, "id": item["unit_id"]},
        "vat": {"id": item["vat_id"]},
        "parentItem": {"className": qr.CN_INVOICE, "id": invoice_id},
    }


def print_plan(extracted, items, errors, args):
    doc = extracted.get("document", {})
    print(f"Накладная {doc.get('number')} от {doc.get('date')} → Quick Resto (путь A)")
    print(f"Поставщик (из накладной): {extracted.get('supplier', {}).get('name')}")
    print(f"Постинг как: provider id={args.provider_id} ({args.provider_class}), "
          f"store id={args.store_id}, № «{args.number or doc.get('number')}»")
    print(f"Позиций: {len(items)}")
    print(f"{'стр':>3} {'арт':>6} {'id':>5} {'кол-во':>8} {'цена с НДС':>11} "
          f"{'НДС':>5} {'сумма с НДС':>12}  наименование")
    for i in items:
        print(f"{i['n']:>3} {i['art']:>6} {i['product_id']:>5} {i['qty']:>8} "
              f"{i['price_with_vat']:>11.5f} {str(i['vat_rate']) + '%':>5} "
              f"{i['sum_with_vat']:>12.2f}  {str(i['name'])[:30]}")
    t = plan_totals(items)
    print(f"ИТОГО: без НДС {t['sum_no_vat']:.2f} · с НДС {t['sum_with_vat']:.2f}")
    exp = extracted.get("totals", {})
    if exp:
        print(f"Сверка с накладной: без НДС {exp.get('sum_no_vat_kop', 0) / 100:.2f} · "
              f"с НДС {exp.get('sum_with_vat_kop', 0) / 100:.2f}")
    if errors:
        print("\nОШИБКИ (постинг невозможен):")
        for e in errors:
            print(f"  - {e}")


def cmd_plan(args):
    items, errors = build_plan(load_json(args.extracted), load_json(args.map))
    print_plan(load_json(args.extracted), items, errors, args)
    print("\nDRY-RUN (команда plan): ничего не отправлено.")


def cmd_post(args):
    extracted = load_json(args.extracted)
    items, errors = build_plan(extracted, load_json(args.map))
    print_plan(extracted, items, errors, args)
    if errors:
        sys.exit("\nЕсть ошибки сопоставления — постинг отменён.")
    if not args.confirm:
        print("\nDRY-RUN: ничего не отправлено. Для реального постинга добавь --confirm.")
        return

    layer, login, password = qr._env()
    number = args.number or extracted.get("document", {}).get("number") or qr.TEST_DOC_NUMBER
    # По умолчанию дата приходной = реальный момент постинга (now, UTC); QR покажет в поясе кафе.
    # Чтобы проставить дату/время документа — флаг --date "ГГГГ-ММ-ДДTчч:мм:сс.000Z".
    date = args.date  # None → header подставит текущий момент (qr._now_iso)

    ok, dup_id = check_existing(layer, login, password, number)
    if dup_id is not None and not args.allow_duplicate:
        sys.exit(f"\nВ QR уже есть приходная № «{number}» (id={dup_id}). Постинг отменён, "
                 "чтобы не задвоить приход. Если всё же нужно — добавь --allow-duplicate.")
    if not ok:
        print("⚠ Не удалось проверить дубликаты (list ≠ 200) — продолжаю.")

    print("\n=== ПОСТИНГ ===")
    st, bd = qr._request(layer, login, password, "create", module=qr.MODULE,
                         payload=make_header_payload(number, date, args.provider_id,
                                                     args.provider_class, args.store_id),
                         with_classname=False)
    print(f"Шапка: HTTP {st}")
    if st != 200:
        qr._save_error(bd)
        sys.exit("Шапка не создана — постинг прерван.")
    invoice_id = json.loads(bd)["id"]
    print(f"  накладная id={invoice_id}")

    for it in items:
        st, bd = qr._request(layer, login, password, "create", module=qr.MODULE_ITEM,
                             payload=make_item_payload(invoice_id, it), with_classname=False)
        if st != 200:
            qr._save_error(bd)
            sys.exit(f"Позиция стр.{it['n']} (арт.{it['art']}): HTTP {st}. "
                     f"Частичная накладная id={invoice_id} — удали:\n"
                     f"    python qr_create_test.py remove --id {invoice_id} --confirm")
        print(f"  + стр.{it['n']:>2} {str(it['name'])[:28]:<28} id={json.loads(bd).get('id')}")

    src = json.loads(qr._request(layer, login, password, "read",
                                 query={"objectId": invoice_id})[1])
    st, bd = qr._request(layer, login, password, "update", module=qr.MODULE,
                         payload=qr.build_recalc(src), with_classname=False)
    print(f"Пересчёт (recalc): HTTP {st}")
    if st != 200:
        qr._save_error(bd)
        sys.exit(f"Пересчёт не прошёл. Накладная id={invoice_id} создана с позициями — "
                 "проверь вручную.")
    res = json.loads(bd)
    print(f"\nГОТОВО. Накладная id={invoice_id} № «{number}»: "
          f"с НДС {res.get('totalSum')} · без НДС {res.get('totalSumWoNds')}")
    print("Не проведена — проверь и проведи в бэк-офисе. "
          f"Откатить: python qr_create_test.py remove --id {invoice_id} --confirm")


def main():
    ap = argparse.ArgumentParser(description="QuickRestoSupplyPoster (T028) — постинг приходной")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("plan", "post"):
        h = "план (dry-run)" if name == "plan" else "постинг (--confirm)"
        sp = sub.add_parser(name, help=h)
        sp.add_argument("--extracted", required=True, help="*_extracted.json")
        sp.add_argument("--map", required=True, help="data/nomenclature_map.json")
        sp.add_argument("--provider-id", type=int, default=0)
        sp.add_argument("--provider-class", choices=qr.PROVIDER_CLASSES, default="organization")
        sp.add_argument("--store-id", type=int, default=1)
        sp.add_argument("--number", default=None)
        sp.add_argument("--date", default=None, help="ISO дата документа; по умолчанию — момент постинга")
        if name == "post":
            sp.add_argument("--confirm", action="store_true")
            sp.add_argument("--allow-duplicate", dest="allow_duplicate", action="store_true",
                            help="не прерываться, если приходная с таким № уже есть в QR")
    args = ap.parse_args()
    if args.cmd == "post" and args.confirm and not args.provider_id:
        sys.exit("Для --confirm нужен реальный --provider-id (см. probe refs).")
    (cmd_plan if args.cmd == "plan" else cmd_post)(args)


if __name__ == "__main__":
    main()
