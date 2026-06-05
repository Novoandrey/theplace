#!/usr/bin/env python3
"""qr_api_probe.py — read-only разведка открытого API Quick Resto (путь A).

ЗАЧЕМ. StoreHouse XML в QR закрыт (устарел). Доставку приходной делаем через открытое API
бэк-офиса: generic object-API (Basic Auth, JSON, GET/POST, объект по moduleName/className).
Скрипт помогает снять схему объекта приходной для POST. Делает ТОЛЬКО GET — в QR не пишет.

ГДЕ ЗАПУСКАТЬ. На машине с доступом к {layer}.quickresto.ru (песочница Claude туда не ходит).
Зависимостей нет — только стандартная библиотека Python 3.

КРЕДЫ — только из окружения (в репозиторий/чат не попадают):
    QR_LAYER     — поддомен слоя (то, что до .quickresto.ru)
    QR_LOGIN     — логин API (Предприятие -> Настройки)
    QR_PASSWORD  — пароль API

PowerShell:
    $env:QR_LAYER="ВАШ_ЛЕЕР"; $env:QR_LOGIN="..."; $env:QR_PASSWORD="..."
    python qr_api_probe.py auth
    python qr_api_probe.py discover
    python qr_api_probe.py schema --module <moduleName> --class <className>

bash:
    QR_LAYER=... QR_LOGIN=... QR_PASSWORD=... python3 qr_api_probe.py auth

НАДЁЖНЕЕ ВСЕГО найти объект приходной так: открыть в браузере бэк-офис, раздел
Склад -> Приходные накладные, в DevTools -> Network посмотреть XHR к .../api/list и скопировать
параметры moduleName и className. Затем: python qr_api_probe.py schema --module ... --class ...
"""
import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

# Известный объект (для проверки авторизации) — из разбора rche.ru.
NOMENCLATURE = (
    "warehouse.nomenclature.dish",
    "ru.edgex.quickresto.modules.warehouse.nomenclature.dish.Dish",
)

# Кандидаты объекта приходной — это ДОГАДКИ по схеме именования edgex.
# Вернее взять moduleName/className из DevTools бэк-офиса (см. docstring).
SUPPLY_CANDIDATES = [
    ("warehouse.documents.supply",
     "ru.edgex.quickresto.modules.warehouse.documents.supply.SupplyStoreDocument"),
    ("warehouse.documents.supply",
     "ru.edgex.quickresto.modules.warehouse.documents.supply.Supply"),
    ("warehouse.documents",
     "ru.edgex.quickresto.modules.warehouse.documents.StoreDocument"),
]


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


def _print_result(title, status, body, show_skeleton):
    print(f"\n=== {title} ===")
    print(f"HTTP {status}")
    if status != 200:
        print(body[:500])
        return
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        print("(ответ не JSON)")
        print(body[:500])
        return
    n = len(data) if isinstance(data, list) else 1
    print(f"объектов: {n}")
    if show_skeleton and isinstance(data, list) and data:
        print("СХЕМА (имена полей и типы, значения скрыты):")
        print(json.dumps(_skeleton(data[0]), ensure_ascii=False, indent=2))


def cmd_auth(layer, login, password):
    status, body = _get(layer, login, password, *NOMENCLATURE)
    _print_result("auth: чтение номенклатуры", status, body, show_skeleton=False)
    if status == 200:
        print("Авторизация и доступ к API — OK.")
    elif status == 401:
        print("401 — логин/пароль не подошли (проверьте QR_LOGIN/QR_PASSWORD).")
    elif status is None:
        print("Нет сети до слоя — проверьте QR_LAYER и доступ к слою quickresto.ru.")


def cmd_discover(layer, login, password):
    print("Перебор кандидатов объекта приходной (это догадки; вернее взять из DevTools):")
    for module, class_name in SUPPLY_CANDIDATES:
        status, body = _get(layer, login, password, module, class_name)
        _print_result(f"{module} | {class_name}", status, body, show_skeleton=True)
    print("\nЕсли ни один не дал данных — возьмите moduleName/className из DevTools бэк-офиса "
          "(Склад -> Приходные накладные, Network -> XHR к /api/list) и запустите: "
          "python qr_api_probe.py schema --module ... --class ...")


def cmd_schema(layer, login, password, module, class_name):
    status, body = _get(layer, login, password, module, class_name)
    _print_result(f"schema: {module} | {class_name}", status, body, show_skeleton=True)


def main():
    ap = argparse.ArgumentParser(description="read-only разведка открытого API QR (путь A)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("auth", help="проверить авторизацию (чтение номенклатуры)")
    sub.add_parser("discover", help="перебрать кандидатов объекта приходной (best-effort)")
    sp = sub.add_parser("schema", help="снять схему объекта по moduleName/className")
    sp.add_argument("--module", required=True)
    sp.add_argument("--class", dest="class_name", required=True)
    a = ap.parse_args()
    layer, login, password = _env()
    if a.cmd == "auth":
        cmd_auth(layer, login, password)
    elif a.cmd == "discover":
        cmd_discover(layer, login, password)
    elif a.cmd == "schema":
        cmd_schema(layer, login, password, a.module, a.class_name)


if __name__ == "__main__":
    main()
