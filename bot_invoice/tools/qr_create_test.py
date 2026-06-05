#!/usr/bin/env python3
"""qr_create_test.py — путь A: создание ТЕСТОВОЙ приходной в Quick Resto через открытое API.

ЗАЧЕМ. Подтвердить, что POST /api/update принимает создание приходной (IncomingInvoice) с вложенными
позициями invoiceItems, какие поля обязательны, и формат ссылок product/measureUnit/provider/store.
Товар по умолчанию — Dish id=309 (unit_id=4, валидная позиция из накладной 136), склад id=1, поставщик — флаг --provider-id.

БЕЗОПАСНОСТЬ.
- По умолчанию dry-run: печатает JSON payload и URL, НИЧЕГО не отправляет.
- Запись (post/remove) требует флага --confirm. Без него — только показывает payload.
- Документ помечается тестовым (№ TEST-API-DELETE, не проведён) и удаляется командой remove.
- Креды только из окружения: QR_LAYER, QR_LOGIN, QR_PASSWORD (в репозиторий/чат не попадают).

ЗАПУСК (на машине с доступом к {layer}.quickresto.ru):
    $env:QR_LAYER="..."; $env:QR_LOGIN="..."; $env:QR_PASSWORD="..."
    python qr_create_test.py dry-run --provider-id 2
    python qr_create_test.py post --provider-id 2 --confirm      # реально создаёт
    python qr_create_test.py remove --id <id> --confirm          # удаляет тестовую приходную
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
CN_INVOICE = "ru.edgex.quickresto.modules.warehouse.documents.incoming.IncomingInvoice"
CN_ITEM = "ru.edgex.quickresto.modules.warehouse.documents.items.common.InvoiceItem"
# Подтверждено сырым read id=136: товар в приходной ссылается классом Dish (не SingleProduct),
# поставщик — Organization (не Provider). Эти значения сервер отдаёт в живом объекте.
CN_PRODUCT = "ru.edgex.quickresto.modules.warehouse.nomenclature.dish.Dish"
CN_UNIT = "ru.edgex.quickresto.modules.core.dictionaries.measureunits.MeasureUnit"
CN_PROVIDER = "ru.edgex.quickresto.modules.warehouse.providers.Organization"
CN_STORE = "ru.edgex.quickresto.modules.warehouse.store.Store"

TEST_DOC_NUMBER = "TEST-API-DELETE"


def _env():
    miss = [k for k in ("QR_LAYER", "QR_LOGIN", "QR_PASSWORD") if not os.environ.get(k)]
    if miss:
        sys.exit(f"Не заданы переменные окружения: {', '.join(miss)} (см. docstring).")
    return os.environ["QR_LAYER"], os.environ["QR_LOGIN"], os.environ["QR_PASSWORD"]


def _now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())


def _request(layer, login, password, endpoint, payload=None, query=None, timeout=30):
    """POST (если payload) или GET к /platform/online/api/{endpoint}. -> (status, body)."""
    base = f"https://{layer}.quickresto.ru/platform/online/api/{endpoint}"
    params = {"moduleName": MODULE, "className": CN_INVOICE}
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


def build_payload(args):
    now = _now_iso()
    return {
        "className": CN_INVOICE,
        "documentNumber": TEST_DOC_NUMBER,
        "invoiceDate": now,
        "paymentDate": now,
        "paid": False,
        "processed": False,
        "comment": "API test (путь A) — удалить",
        "provider": {"className": CN_PROVIDER, "id": args.provider_id},
        "store": {"className": CN_STORE, "id": args.store_id},
        "invoiceItems": [
            {
                "className": CN_ITEM,
                "product": {"className": CN_PRODUCT, "id": args.product_id},
                "measureUnit": {"className": CN_UNIT, "id": args.unit_id},
                "actualAmount": args.qty,
                "price": args.price,
                "priceWithVat": args.price,
            }
        ],
    }


def cmd_dry_run(args):
    payload = build_payload(args)
    print("DRY-RUN — ничего не отправлено. Это тело POST /api/update:")
    print(f"URL: .../platform/online/api/update?moduleName={MODULE}&className=IncomingInvoice")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if not args.provider_id:
        print("\nВНИМАНИЕ: --provider-id=0 — для реального post нужен реальный id поставщика.")


def cmd_post(args):
    if not args.confirm:
        print("Это ЗАПИСЬ в боевой бэк-офис. Запусти с --confirm, чтобы создать.")
        cmd_dry_run(args)
        return
    if not args.provider_id:
        sys.exit("Нужен --provider-id (реальный id поставщика из refs).")
    layer, login, password = _env()
    status, body = _request(layer, login, password, "update", payload=build_payload(args))
    print(f"POST /api/update: HTTP {status}")
    print(body[:1500])
    if status == 200:
        try:
            obj = json.loads(body)
            new_id = obj.get("id") if isinstance(obj, dict) else None
            print(f"\nСоздана тестовая приходная id={new_id}. Проверь в бэк-офисе, потом удали:")
            print(f"    python qr_create_test.py remove --id {new_id} --confirm")
        except json.JSONDecodeError:
            print("(ответ не JSON — посмотри тело выше)")


def cmd_remove(args):
    if not args.confirm:
        print(f"Удаление id={args.id}. Запусти с --confirm, чтобы выполнить.")
        return
    layer, login, password = _env()
    status, body = _request(layer, login, password, "remove", payload={"id": args.id})
    print(f"POST /api/remove id={args.id}: HTTP {status}")
    print(body[:800])


def _ref(obj, fallback_cn=None):
    """Свести подобъект к минимальной ссылке {className, id} (как ждёт upsert)."""
    if isinstance(obj, dict) and obj.get("id") is not None:
        return {"className": obj.get("className") or fallback_cn, "id": obj.get("id")}
    return obj


def transform_for_create(src, processed=False):
    """Из прочитанной приходной собрать payload для создания тестовой копии (без id/расчётных)."""
    items = []
    for it in src.get("invoiceItems") or []:
        item = {
            "className": it.get("className"),
            "product": _ref(it.get("product")),
            "measureUnit": _ref(it.get("measureUnit")),
            "actualAmount": it.get("actualAmount"),
            "price": it.get("price"),
            "priceWithVat": it.get("priceWithVat"),
        }
        # vat — небольшой объект {id,value,taxType} без className; переносим как есть
        # (нужен расчёту себестоимости PrimeCostCalculator; у Dish-позиций его не было).
        if it.get("vat") is not None:
            item["vat"] = it["vat"]
        items.append(item)
    now = _now_iso()
    return {
        "className": src.get("className"),
        "documentNumber": TEST_DOC_NUMBER,
        "invoiceDate": now,
        "paymentDate": now,
        "paid": False,
        "comment": "API test clone — удалить",
        "processed": processed,
        "provider": _ref(src.get("provider"), CN_PROVIDER),
        "store": _ref(src.get("store"), CN_STORE),
        "invoiceItems": items,
    }


def transform_full(src):
    """Полная копия как отдал сервер: убираем id документа/позиций и lastUpdateDate."""
    obj = dict(src)
    obj.pop("id", None)
    obj.pop("lastUpdateDate", None)
    obj["documentNumber"] = TEST_DOC_NUMBER
    obj["processed"] = False
    obj["comment"] = "API test full clone — удалить"
    for it in obj.get("invoiceItems") or []:
        if isinstance(it, dict):
            it.pop("id", None)
    return obj


def cmd_clone(args):
    layer, login, password = _env()
    status, body = _request(layer, login, password, "read", query={"objectId": args.from_id})
    if status != 200:
        print(f"read id={args.from_id}: HTTP {status}")
        print(body[:500])
        return
    try:
        src = json.loads(body)
    except json.JSONDecodeError:
        print("Источник не JSON — не могу клонировать.")
        return
    payload = transform_full(src) if args.full else transform_for_create(src, processed=getattr(args, "processed", False))
    if getattr(args, "no_items", False):
        payload["invoiceItems"] = []
    elif getattr(args, "items", 0):
        payload["invoiceItems"] = payload["invoiceItems"][: args.items]
    if not args.confirm:
        print(f"CLONE из приходной id={args.from_id} (dry-run, ничего не отправлено).")
        print(f"Позиций в теле: {len(payload['invoiceItems'])}")
        print("Это тело POST /api/update (упрощённая копия, № TEST-API-DELETE):")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        print("\nДля реального создания добавь --confirm.")
        return
    st, bd = _request(layer, login, password, "update", payload=payload)
    print(f"POST /api/update (clone из id={args.from_id}, позиций={len(payload['invoiceItems'])}): HTTP {st}")
    if st != 200:
        fn = f"qr_error_{time.strftime('%Y%m%d_%H%M%S')}.html"
        with open(fn, "w", encoding="utf-8") as f:
            f.write(bd)
        print(f"ПОЛНОЕ тело ошибки сохранено: {fn} ({len(bd)} символов). Пришли этот файл.")
        print("--- первые 3000 символов: ---")
        print(bd[:3000])
        return
    print(bd[:1500])
    if st == 200:
        try:
            new_id = json.loads(bd).get("id")
            print(f"\nСоздана тестовая приходная id={new_id}. Удалить:")
            print(f"    python qr_create_test.py remove --id {new_id} --confirm")
        except json.JSONDecodeError:
            print("(ответ не JSON — смотри тело выше)")


def main():
    ap = argparse.ArgumentParser(description="тест создания приходной QR (путь A)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("dry-run", "post"):
        sp = sub.add_parser(name)
        sp.add_argument("--provider-id", type=int, default=0)
        sp.add_argument("--store-id", type=int, default=1)
        sp.add_argument("--product-id", type=int, default=309)
        sp.add_argument("--unit-id", type=int, default=4)
        sp.add_argument("--qty", type=float, default=1.0)
        sp.add_argument("--price", type=float, default=10.0)
        if name == "post":
            sp.add_argument("--confirm", action="store_true")
    rp = sub.add_parser("remove")
    rp.add_argument("--id", type=int, required=True)
    rp.add_argument("--confirm", action="store_true")
    cp = sub.add_parser("clone")
    cp.add_argument("--from", dest="from_id", type=int, required=True)
    cp.add_argument("--confirm", action="store_true")
    cp.add_argument("--full", action="store_true")
    cp.add_argument("--items", type=int, default=0,
                    help="оставить только первые N позиций (0 = все) — для изоляции NPE")
    cp.add_argument("--processed", action="store_true",
                    help="создать ПРОВЕДЁННОЙ (processed=true) — затрагивает склад! удалить сразу после")
    cp.add_argument("--no-items", dest="no_items", action="store_true",
                    help="создать ШАПКУ без позиций (изоляция: проходит ли create без расчёта себестоимости)")
    args = ap.parse_args()
    if args.cmd == "dry-run":
        cmd_dry_run(args)
    elif args.cmd == "post":
        cmd_post(args)
    elif args.cmd == "remove":
        cmd_remove(args)
    elif args.cmd == "clone":
        cmd_clone(args)


if __name__ == "__main__":
    main()
