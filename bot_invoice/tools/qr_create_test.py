#!/usr/bin/env python3
"""qr_create_test.py — путь A: создание ТЕСТОВОЙ приходной в Quick Resto через открытое API.

СХЕМА СОЗДАНИЯ (подтверждена поддержкой QR, 2026-06-08) — в ТРИ шага, не одним объектом:
  1) шапка:   POST /api/create?moduleName=warehouse.documents.incoming
              {documentNumber, invoiceDate, provider{id,className}, store{id,className}, paid}
              → в ответе id созданного документа.
  2) позиция: POST /api/create?moduleName=warehouse.documents.items.incoming  (отдельный модуль!)
              {className=InvoiceItem, product, measureUnit, actualAmount, price, priceWithVat,
               vat, extraExpenses, parentItem{id=<id шапки>, className=IncomingInvoice}}
              — по одной позиции на запрос.
  3) пересчёт: POST /api/update на накладную → сервер пересчитывает себестоимость.
Ранее провал был из-за вложенных invoiceItems в одном update: PrimeCostCalculator падал на
несохранённой позиции. Раздельное создание это обходит.

БЕЗОПАСНОСТЬ.
- По умолчанию dry-run: печатает JSON payload и URL, НИЧЕГО не отправляет.
- Любая запись требует --confirm. Полное тело ошибки сохраняется в qr_error_*.html.
- Тестовый документ: № TEST-API-DELETE, не проведён; удаляется командой remove.
- Креды только из окружения: QR_LAYER, QR_LOGIN, QR_PASSWORD.

ЗАПУСК (на машине с доступом к {layer}.quickresto.ru):
    $env:QR_LAYER="..."; $env:QR_LOGIN="..."; $env:QR_PASSWORD="..."
    # шаг 1 — шапка (provider 2 = ИП → класс Businessman; ООО → Organization):
    python qr_create_test.py create-header --provider-id 2 --provider-class businessman
    python qr_create_test.py create-header --provider-id 2 --provider-class businessman --confirm
    # шаг 2 — позиция (id шапки из ответа шага 1); product = SingleProduct (ингредиент):
    python qr_create_test.py add-item --invoice-id <ID> --product-id 9 --unit-id 2 \
        --amount 2.46 --price 328.57143 --price-vat 345.0 --vat-id 4 --confirm
    # шаг 3 — пересчёт себестоимости:
    python qr_create_test.py recalc --invoice-id <ID> --confirm
    # проверить и удалить:
    python qr_create_test.py remove --id <ID> --confirm
"""
import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

MODULE = "warehouse.documents.incoming"
MODULE_ITEM = "warehouse.documents.items.incoming"
CN_INVOICE = "ru.edgex.quickresto.modules.warehouse.documents.incoming.IncomingInvoice"
CN_ITEM = "ru.edgex.quickresto.modules.warehouse.documents.items.common.InvoiceItem"
CN_SINGLEPRODUCT = "ru.edgex.quickresto.modules.warehouse.nomenclature.singleproduct.SingleProduct"
CN_DISH = "ru.edgex.quickresto.modules.warehouse.nomenclature.dish.Dish"
CN_UNIT = "ru.edgex.quickresto.modules.core.dictionaries.measureunits.MeasureUnit"
CN_STORE = "ru.edgex.quickresto.modules.warehouse.store.Store"
CN_NATURALPERSON = "ru.edgex.quickresto.modules.warehouse.providers.NaturalPerson"
PROVIDER_CLASSES = {
    "organization": "ru.edgex.quickresto.modules.warehouse.providers.Organization",
    "businessman": "ru.edgex.quickresto.modules.warehouse.providers.Businessman",
    "naturalperson": CN_NATURALPERSON,  # «Чеки (подотчёт)» — закупка по кассовым чекам
}
PRODUCT_CLASSES = {"singleproduct": CN_SINGLEPRODUCT, "dish": CN_DISH}

TEST_DOC_NUMBER = "TEST-API-DELETE"


def _env():
    miss = [k for k in ("QR_LAYER", "QR_LOGIN", "QR_PASSWORD") if not os.environ.get(k)]
    if miss:
        sys.exit(f"Не заданы переменные окружения: {', '.join(miss)} (см. docstring).")
    return os.environ["QR_LAYER"], os.environ["QR_LOGIN"], os.environ["QR_PASSWORD"]


def _now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())


def _request(layer, login, password, endpoint, module=MODULE, payload=None,
             query=None, with_classname=True, timeout=30):
    """GET/POST к /platform/online/api/{endpoint}?moduleName=.. -> (status, body)."""
    base = f"https://{layer}.quickresto.ru/platform/online/api/{endpoint}"
    params = {"moduleName": module}
    if with_classname:
        params["className"] = CN_INVOICE
    if query:
        params.update(query)
    url = f"{base}?{urllib.parse.urlencode(params)}"
    token = base64.b64encode(f"{login}:{password}".encode()).decode()
    headers = {"Authorization": f"Basic {token}", "Content-Type": "application/json",
               "Accept": "application/json"}
    data = json.dumps(payload).encode() if payload is not None else None
    method = "POST" if payload is not None else "GET"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except urllib.error.URLError as e:
        return None, f"URLError: {e.reason}"


def _save_error(body):
    fn = f"qr_error_{time.strftime('%Y%m%d_%H%M%S')}.html"
    with open(fn, "w", encoding="utf-8") as f:
        f.write(body or "")
    print(f"ПОЛНОЕ тело ошибки сохранено: {fn} ({len(body or '')} символов). Пришли этот файл.")
    print("--- первые 2000 символов: ---")
    print((body or "")[:2000])


def _ref(obj, fallback_cn=None):
    """Свести подобъект к минимальной ссылке {className, id}."""
    if isinstance(obj, dict) and obj.get("id") is not None:
        return {"className": obj.get("className") or fallback_cn, "id": obj.get("id")}
    return obj


# ---------- шаг 1: шапка ----------
def build_header(args):
    return {
        "className": CN_INVOICE,
        "documentNumber": args.number or TEST_DOC_NUMBER,
        "invoiceDate": args.date or _now_iso(),
        "paid": False,
        "provider": {"className": PROVIDER_CLASSES[args.provider_class], "id": args.provider_id},
        "store": {"className": CN_STORE, "id": args.store_id},
    }


def cmd_create_header(args):
    payload = build_header(args)
    if not args.confirm:
        print("DRY-RUN шаг 1 (шапка). POST /api/create?moduleName=" + MODULE)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        print("\nДля создания добавь --confirm.")
        return
    if not args.provider_id:
        sys.exit("Нужен реальный --provider-id.")
    layer, login, password = _env()
    st, bd = _request(layer, login, password, "create", module=MODULE,
                      payload=payload, with_classname=False)
    print(f"POST /api/create (шапка): HTTP {st}")
    if st != 200:
        _save_error(bd)
        return
    print(bd[:1200])
    try:
        new_id = json.loads(bd).get("id")
        print(f"\nСоздана шапка id={new_id}. Шаг 2 — добавить позицию:")
        print(f"    python qr_create_test.py add-item --invoice-id {new_id} "
              "--product-id 9 --unit-id 2 --amount 2.46 --price 328.57143 "
              "--price-vat 345.0 --vat-id 4 --confirm")
    except json.JSONDecodeError:
        print("(ответ не JSON — смотри тело выше)")


# ---------- шаг 2: позиция ----------
def build_item(args):
    if args.vat_id == -1:
        vat = {"id": -1, "title": "<без НДС>"}
    else:
        vat = {"id": args.vat_id}
    return {
        "className": CN_ITEM,
        "extraExpenses": 0,
        "actualAmount": args.amount,
        "price": args.price,
        "priceWithVat": args.price_vat if args.price_vat is not None else args.price,
        "product": {"className": PRODUCT_CLASSES[args.product_class], "id": args.product_id},
        "measureUnit": {"className": CN_UNIT, "id": args.unit_id},
        "vat": vat,
        "parentItem": {"className": CN_INVOICE, "id": args.invoice_id},
    }


def cmd_add_item(args):
    payload = build_item(args)
    if not args.confirm:
        print("DRY-RUN шаг 2 (позиция). POST /api/create?moduleName=" + MODULE_ITEM)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        print("\nДля создания добавь --confirm.")
        return
    layer, login, password = _env()
    st, bd = _request(layer, login, password, "create", module=MODULE_ITEM,
                      payload=payload, with_classname=False)
    print(f"POST /api/create (позиция, parentItem={args.invoice_id}): HTTP {st}")
    if st != 200:
        _save_error(bd)
        return
    print(bd[:1200])
    try:
        item_id = json.loads(bd).get("id")
        print(f"\nДобавлена позиция id={item_id}. После всех позиций — шаг 3:")
        print(f"    python qr_create_test.py recalc --invoice-id {args.invoice_id} --confirm")
    except json.JSONDecodeError:
        print("(ответ не JSON — смотри тело выше)")


# ---------- шаг 3: пересчёт себестоимости ----------
def build_recalc(src):
    """Из read накладной собрать безопасный update: шапка + позиции ссылками по id."""
    items = [{"className": CN_ITEM, "id": it["id"]}
             for it in (src.get("invoiceItems") or []) if it.get("id") is not None]
    return {
        "className": CN_INVOICE,
        "id": src.get("id"),
        "documentNumber": src.get("documentNumber"),
        "invoiceDate": src.get("invoiceDate"),
        "paid": src.get("paid", False),
        "processed": src.get("processed", False),
        "provider": _ref(src.get("provider")),
        "store": _ref(src.get("store"), CN_STORE),
        "invoiceItems": items,
    }


def cmd_recalc(args):
    layer, login, password = _env()
    st, bd = _request(layer, login, password, "read", query={"objectId": args.invoice_id})
    if st != 200:
        print(f"read id={args.invoice_id}: HTTP {st}")
        print(bd[:500])
        return
    src = json.loads(bd)
    payload = build_recalc(src)
    if not args.confirm:
        print(f"DRY-RUN шаг 3 (пересчёт). POST /api/update, позиций={len(payload['invoiceItems'])}")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        print("\nДля пересчёта добавь --confirm.")
        return
    st, bd = _request(layer, login, password, "update", module=MODULE,
                      payload=payload, with_classname=False)
    print(f"POST /api/update (пересчёт id={args.invoice_id}): HTTP {st}")
    if st != 200:
        _save_error(bd)
        return
    print(bd[:1500])
    print(f"\nГотово. Проверь накладную, затем удали: "
          f"python qr_create_test.py remove --id {args.invoice_id} --confirm")


def cmd_remove(args):
    if not args.confirm:
        print(f"Удаление id={args.id}. Запусти с --confirm, чтобы выполнить.")
        return
    layer, login, password = _env()
    st, bd = _request(layer, login, password, "remove", payload={"id": args.id})
    print(f"POST /api/remove id={args.id}: HTTP {st}")
    print(bd[:800])


def main():
    ap = argparse.ArgumentParser(description="создание приходной QR через open API (3 шага)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    h = sub.add_parser("create-header", help="шаг 1: создать шапку приходной")
    h.add_argument("--provider-id", type=int, required=True)
    h.add_argument("--provider-class", choices=PROVIDER_CLASSES, default="organization")
    h.add_argument("--store-id", type=int, default=1)
    h.add_argument("--number", default=TEST_DOC_NUMBER)
    h.add_argument("--date", default=None, help="ISO, по умолчанию now")
    h.add_argument("--confirm", action="store_true")

    it = sub.add_parser("add-item", help="шаг 2: добавить одну позицию в приходную")
    it.add_argument("--invoice-id", type=int, required=True)
    it.add_argument("--product-id", type=int, required=True)
    it.add_argument("--product-class", choices=PRODUCT_CLASSES, default="singleproduct")
    it.add_argument("--unit-id", type=int, required=True)
    it.add_argument("--amount", type=float, required=True)
    it.add_argument("--price", type=float, required=True, help="цена без НДС")
    it.add_argument("--price-vat", dest="price_vat", type=float, default=None,
                    help="цена с НДС (по умолчанию = --price)")
    it.add_argument("--vat-id", type=int, default=-1, help="id ставки НДС; -1 = без НДС")
    it.add_argument("--confirm", action="store_true")

    rc = sub.add_parser("recalc", help="шаг 3: update накладной для пересчёта себестоимости")
    rc.add_argument("--invoice-id", type=int, required=True)
    rc.add_argument("--confirm", action="store_true")

    rp = sub.add_parser("remove", help="удалить приходную по id")
    rp.add_argument("--id", type=int, required=True)
    rp.add_argument("--confirm", action="store_true")

    args = ap.parse_args()
    {"create-header": cmd_create_header, "add-item": cmd_add_item,
     "recalc": cmd_recalc, "remove": cmd_remove}[args.cmd](args)


if __name__ == "__main__":
    main()
