#!/usr/bin/env python3
"""qr_api_probe.py — read-only разведка открытого API Quick Resto (путь A).

ЗАЧЕМ. StoreHouse XML в QR закрыт (устарел). Доставку приходной делаем через открытое API
бэк-офиса: generic object-API (Basic Auth, JSON, GET/POST, объект по moduleName/className).
Объект приходной подтверждён доками QR: warehouse.documents.incoming / IncomingInvoice,
POST /api/update (upsert). Скрипт помогает снять недостающее (объект ПОЗИЦИЙ приходной,
id склада/поставщика) и реальную форму объекта. Делает ТОЛЬКО GET — ничего не пишет в QR.

ГДЕ ЗАПУСКАТЬ. На машине с доступом к {layer}.quickresto.ru (песочница Claude туда не ходит).
Зависимостей нет — только стандартная библиотека Python 3.

КРЕДЫ — только из окружения (в репозиторий/чат не попадают):
    QR_LAYER     — поддомен слоя (то, что до .quickresto.ru)
    QR_LOGIN     — логин API (Предприятие -> Настройки)
    QR_PASSWORD  — пароль API

PowerShell:
    $env:QR_LAYER="ВАШ_ЛЕЕР"; $env:QR_LOGIN="..."; $env:QR_PASSWORD="..."
    python qr_api_probe.py auth      # проверить авторизацию
    python qr_api_probe.py invoice   # прочитать существующую приходную, снять её форму
    python qr_api_probe.py refs      # id+названия складов и поставщиков (для payload)
    python qr_api_probe.py schema --module <moduleName> --class <className>   # любой объект

bash:
    QR_LAYER=... QR_LOGIN=... QR_PASSWORD=... python3 qr_api_probe.py auth
"""
import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

# Подтверждённые объекты (className — из доков QR; moduleName = пакет без имени класса).
NOMENCLATURE = (
    "warehouse.nomenclature.dish",
    "ru.edgex.quickresto.modules.warehouse.nomenclature.dish.Dish",
)
INCOMING = (
    "warehouse.documents.incoming",
    "ru.edgex.quickresto.modules.warehouse.documents.incoming.IncomingInvoice",
)
# moduleName складов/поставщиков выведен из className (правило пакета); при 404 — уточнить.
STORE = ("warehouse.store", "ru.edgex.quickresto.modules.warehouse.store.Store")
PROVIDER = ("warehouse.providers", "ru.edgex.quickresto.modules.warehouse.providers.Provider")


def _env():
    miss = [k for k in ("QR_LAYER", "QR_LOGIN", "QR_PASSWORD") if not os.environ.get(k)]
    if miss:
        sys.exit(f"Не заданы переменные окружения: {', '.join(miss)} (см. docstring).")
    return os.environ["QR_LAYER"], os.environ["QR_LOGIN"], os.environ["QR_PASSWORD"]


def _get(layer, login, password, module, class_name, timeout=30):
    """GET .../api/list?moduleName=..&className=.. с Basic Auth. Возвращает (status, body)."""
    base = f"https://{layer}.quickresto.ru/platform/online/api/list"
    qs = urllib.parse.urlencode({"moduleName": module, "className": class_name})
    token = base64.b64encode(f"{login}:{password}".encode()).decode()
    req = urllib.request.Request(f"{base}?{qs}", headers={
        "Authorization": f"Basic {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:500]
    except urllib.error.URLError as e:
        return None, f"URLError: {e.reason}"


def _skeleton(obj, depth=0, maxdepth=4):
    """Структура объекта без значений: имена полей и типы (значения/ПДн не печатаются)."""
    if depth >= maxdepth:
        return "<...>"
    if isinstance(obj, dict):
        return {k: _skeleton(v, depth + 1, maxdepth) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_skeleton(obj[0], depth + 1, maxdepth)] if obj else []
    if isinstance(obj, bool):
        return "<bool>"
    if isinstance(obj, int):
        return "<int>"
    if isinstance(obj, float):
        return "<float>"
    if isinstance(obj, str):
        return "<str>"
    return "<null>" if obj is None else f"<{type(obj).__name__}>"


def _load(layer, login, password, module, class_name):
    status, body = _get(layer, login, password, module, class_name)
    if status != 200:
        return status, None
    try:
        return status, json.loads(body)
    except json.JSONDecodeError:
        return status, None


def cmd_auth(layer, login, password):
    status, data = _load(layer, login, password, *NOMENCLATURE)
    print(f"auth (чтение номенклатуры): HTTP {status}")
    if status == 200:
        n = len(data) if isinstance(data, list) else 1
        print(f"OK — авторизация и доступ к API работают (объектов номенклатуры: {n}).")
    elif status == 401:
        print("401 — логин/пароль не подошли (проверьте QR_LOGIN/QR_PASSWORD).")
    elif status is None:
        print("Нет сети до слоя — проверьте QR_LAYER и доступ к слою quickresto.ru.")
    else:
        print("Неожиданный ответ — см. статус выше.")


def cmd_invoice(layer, login, password):
    status, data = _load(layer, login, password, *INCOMING)
    print(f"invoice ({INCOMING[0]}): HTTP {status}")
    if status != 200 or not isinstance(data, list):
        print("Не удалось прочитать приходные (см. статус) — проверьте права на чтение.")
        return
    print(f"приходных в системе: {len(data)}")
    if not data:
        print("Приходных пока нет — создайте одну в бэк-офисе вручную и повторите.")
        return
    print("ФОРМА существующей приходной (имена полей и типы, значения скрыты):")
    print(json.dumps(_skeleton(data[0]), ensure_ascii=False, indent=2))
    keys = list(data[0].keys()) if isinstance(data[0], dict) else []
    line_keys = ("item", "element", "row", "good", "position")
    line_like = [k for k in keys if any(t in k.lower() for t in line_keys)]
    note = line_like or "— не видно (значит позиции — отдельный объект)"
    print("\nПоля, похожие на строки документа:", note)


def _id_title(item):
    if not isinstance(item, dict):
        return str(item)
    name = item.get("title") or item.get("name") or item.get("itemTitle") or "?"
    return f"id={item.get('id')}  {name}"


def cmd_refs(layer, login, password):
    for label, obj in (("СКЛАДЫ", STORE), ("ПОСТАВЩИКИ", PROVIDER)):
        status, data = _load(layer, login, password, *obj)
        print(f"\n=== {label} ({obj[0]}): HTTP {status} ===")
        if status != 200 or not isinstance(data, list):
            print("  не прочитано (при 404 — уточнить moduleName; при 401 — права)")
            continue
        for item in data[:50]:
            print(" ", _id_title(item))
        if len(data) > 50:
            print(f"  … ещё {len(data) - 50}")


def cmd_schema(layer, login, password, module, class_name):
    status, data = _load(layer, login, password, module, class_name)
    print(f"schema ({module}): HTTP {status}")
    if status == 200 and isinstance(data, list) and data:
        print(json.dumps(_skeleton(data[0]), ensure_ascii=False, indent=2))
    elif status == 200:
        print("Ответ 200, но объектов нет (или не список).")
    else:
        print("Не 200 — проверьте moduleName/className и права.")


def main():
    ap = argparse.ArgumentParser(description="read-only разведка открытого API QR (путь A)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("auth", help="проверить авторизацию (чтение номенклатуры)")
    sub.add_parser("invoice", help="прочитать приходную и снять её форму")
    sub.add_parser("refs", help="id+названия складов и поставщиков (для payload)")
    sp = sub.add_parser("schema", help="снять форму любого объекта по moduleName/className")
    sp.add_argument("--module", required=True)
    sp.add_argument("--class", dest="class_name", required=True)
    a = ap.parse_args()
    layer, login, password = _env()
    if a.cmd == "auth":
        cmd_auth(layer, login, password)
    elif a.cmd == "invoice":
        cmd_invoice(layer, login, password)
    elif a.cmd == "refs":
        cmd_refs(layer, login, password)
    elif a.cmd == "schema":
        cmd_schema(layer, login, password, a.module, a.class_name)


if __name__ == "__main__":
    main()
