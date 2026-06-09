#!/usr/bin/env python3
"""qr_api_probe.py — read-only разведка открытого API Quick Resto (путь A).

ЗАЧЕМ. StoreHouse XML в QR закрыт (устарел). Доставку приходной делаем через открытое API
бэк-офиса: generic object-API (Basic Auth, JSON, GET/POST, объект по moduleName/className).
Объект приходной подтверждён доками QR: warehouse.documents.incoming / IncomingInvoice
(GET /api/list, GET /api/read?objectId=N — «с подобъектами», POST /api/update — upsert,
POST /api/remove). Цель скрипта — увидеть, где у приходной ПОЗИЦИИ (строки), и снять id
склада/поставщика для payload. Делает ТОЛЬКО GET — ничего не пишет в QR.

ГДЕ ЗАПУСКАТЬ. На машине с доступом к {layer}.quickresto.ru (песочница Claude туда не ходит).
Зависимостей нет — только стандартная библиотека Python 3.

КРЕДЫ — только из окружения (в репозиторий/чат не попадают):
    QR_LAYER     — поддомен слоя (то, что до .quickresto.ru)
    QR_LOGIN     — логин API (Предприятие -> Настройки)
    QR_PASSWORD  — пароль API

PowerShell:
    $env:QR_LAYER="ВАШ_ЛЕЕР"; $env:QR_LOGIN="..."; $env:QR_PASSWORD="..."
    python qr_api_probe.py auth                     # проверить авторизацию
    python qr_api_probe.py invoice                  # список приходных с id (выбрать одну)
    python qr_api_probe.py read --id <objectId>     # объект С ПОДОБЪЕКТАМИ — увидеть позиции
    python qr_api_probe.py refs                     # id+названия складов и поставщиков
    python qr_api_probe.py schema --module M --class C   # форма любого объекта
    python qr_api_probe.py map --module M --class C      # id+article+unit номенклатуры

bash:
    QR_LAYER=... QR_LOGIN=... QR_PASSWORD=... python3 qr_api_probe.py auth
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
INGREDIENT = (
    "warehouse.nomenclature.singleproduct",
    "ru.edgex.quickresto.modules.warehouse.nomenclature.singleproduct.SingleProduct",
)
# Класс групп ингредиентов (parentContextClassName при выборке детей через data/select).
SINGLE_CATEGORY = "ru.edgex.quickresto.modules.warehouse.nomenclature.singleproduct.SingleCategory"


def _env():
    miss = [k for k in ("QR_LAYER", "QR_LOGIN", "QR_PASSWORD") if not os.environ.get(k)]
    if miss:
        sys.exit(f"Не заданы переменные окружения: {', '.join(miss)} (см. docstring).")
    return os.environ["QR_LAYER"], os.environ["QR_LOGIN"], os.environ["QR_PASSWORD"]


def _get(layer, login, password, module, class_name, endpoint="list", extra=None, timeout=30):
    """GET .../api/{endpoint}?moduleName=..&className=..[&extra] с Basic Auth. -> (status, body)."""
    base = f"https://{layer}.quickresto.ru/platform/online/api/{endpoint}"
    params = {"moduleName": module, "className": class_name}
    if extra:
        params.update(extra)
    qs = urllib.parse.urlencode(params)
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


def _load(layer, login, password, module, class_name, endpoint="list", extra=None):
    status, body = _get(layer, login, password, module, class_name, endpoint=endpoint, extra=extra)
    if status != 200:
        return status, None
    try:
        return status, json.loads(body)
    except json.JSONDecodeError:
        return status, None


def _select_children(layer, login, password, module, parent_id, parent_class, timeout=30):
    """GET /platform/data/{module}/select?parentContextId=.. — дети группы (как грузит бэк-офис)."""
    base = f"https://{layer}.quickresto.ru/platform/data/{module}/select"
    params = {
        "parentContextId": parent_id,
        "parentContextClassName": parent_class,
        "parentContext_Level": 0,
        "regTime": int(time.time() * 1000),
        "businessDayOffsetInMs": 0,
        "timeZone": 0,
    }
    token = base64.b64encode(f"{login}:{password}".encode()).decode()
    req = urllib.request.Request(
        f"{base}?{urllib.parse.urlencode(params)}",
        headers={"Authorization": f"Basic {token}", "Accept": "application/json"},
    )
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
        out = {}
        for k, v in obj.items():
            if k == "className" and isinstance(v, str):
                out[k] = v  # тип объекта (не ПДн) — показываем для маппинга
            else:
                out[k] = _skeleton(v, depth + 1, maxdepth)
        return out
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


def cmd_invoice(layer, login, password, number=None):
    status, data = _load(layer, login, password, *INCOMING)
    print(f"invoice/list ({INCOMING[0]}): HTTP {status}")
    if status != 200 or not isinstance(data, list):
        print("Не удалось прочитать список приходных (см. статус) — проверьте права.")
        return
    print(f"приходных в системе: {len(data)}")
    if not data:
        print("Приходных пока нет — создайте одну в бэк-офисе вручную и повторите.")
        return
    if number:
        hits = [it for it in data if isinstance(it, dict)
                and str(it.get("documentNumber")) == str(number)]
        if hits:
            for it in hits:
                print(f"  НАЙДЕНО: id={it.get('id')}  № {it.get('documentNumber')}")
        else:
            print(f"  № «{number}» не найден среди {len(data)} приходных.")
        return
    print("Существующие приходные (для команды read --id):")
    for it in data[:15]:
        if isinstance(it, dict):
            print(f"  id={it.get('id')}  № {it.get('documentNumber')}")
    print("\nФорма из list (объекты «плоские», вложенные ссылки пустые):")
    print(json.dumps(_skeleton(data[0]), ensure_ascii=False, indent=2))
    print("\nПозиции в list не приходят. Дальше: python qr_api_probe.py read --id <objectId> "
          "— read отдаёт объект С ПОДОБЪЕКТАМИ, там и проверим строки.")


def cmd_read(layer, login, password, object_id, module=None, class_name=None,
             raw=False, out=None):
    mod, cls = (module, class_name) if (module and class_name) else INCOMING
    status, data = _load(layer, login, password, mod, cls,
                         endpoint="read", extra={"objectId": object_id})
    print(f"read objectId={object_id} ({mod}): HTTP {status}")
    if status != 200 or not isinstance(data, dict):
        print("Не 200 / не объект — проверьте objectId и права.")
        return
    if raw or out:
        blob = json.dumps(data, ensure_ascii=False, indent=2)
        if out:
            with open(out, "w", encoding="utf-8") as f:
                f.write(blob)
            print(f"Сырой JSON сохранён: {out} ({len(blob)} символов)")
        if raw:
            print("ПОЛНЫЙ СЫРОЙ JSON (для реконструкции create):")
            print(blob)
        return
    print("ПОЛНАЯ форма С ПОДОБЪЕКТАМИ (значения скрыты, className виден):")
    print(json.dumps(_skeleton(data, 0, 5), ensure_ascii=False, indent=2))
    arrays = [k for k, v in data.items() if isinstance(v, list)]
    print("\nПоля-массивы (дети/позиции):", arrays or "— нет")


def _id_title(item):
    if not isinstance(item, dict):
        return str(item)
    name = (item.get("title") or item.get("name") or item.get("shortName")
            or item.get("itemTitle") or "?")
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


def cmd_map(layer, login, password, module, class_name):
    status, data = _load(layer, login, password, module, class_name)
    n = len(data) if isinstance(data, list) else "—"
    print(f"map ({module}): HTTP {status}; объектов: {n}")
    if status != 200 or not isinstance(data, list):
        print("Не прочитано — проверьте module/class и права.")
        return
    for it in data:
        if not isinstance(it, dict):
            continue
        mu = it.get("measureUnit") if isinstance(it.get("measureUnit"), dict) else {}
        print(f"  id={it.get('id')} art={it.get('article')} "
              f"unit_id={mu.get('id')}({mu.get('name')}) {it.get('name')}")


def cmd_children(layer, login, password, parent, module, class_name):
    mod = module or INGREDIENT[0]
    cat = class_name or SINGLE_CATEGORY
    status, body = _select_children(layer, login, password, mod, parent, cat)
    print(f"children parentId={parent} via /platform/data/{mod}/select: HTTP {status}")
    if status != 200:
        print(body[:500])
        return
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        print("(ответ не JSON):")
        print(body[:400])
        return
    if isinstance(data, dict):
        items = data.get("items") or data.get("data") or data.get("rows") or []
    else:
        items = data
    if not isinstance(items, list):
        print("Структура ответа иная — вот её скелет:")
        print(json.dumps(_skeleton(data, 0, 4), ensure_ascii=False, indent=2))
        return
    print(f"детей: {len(items)}")
    for it in items[:20]:
        if isinstance(it, dict):
            mu = it.get("measureUnit") if isinstance(it.get("measureUnit"), dict) else {}
            print(f"  id={it.get('id')} art={it.get('article')} "
                  f"unit_id={mu.get('id')} pid={it.get('parentId')} {it.get('name')}")


def cmd_tree(layer, login, password, module, out=None, map_out=None):
    """GET /api/tree?moduleName=<module> — плоский список номенклатуры (без групп)."""
    base = f"https://{layer}.quickresto.ru/platform/online/api/tree"
    qs = urllib.parse.urlencode({"moduleName": module})
    token = base64.b64encode(f"{login}:{password}".encode()).decode()
    req = urllib.request.Request(f"{base}?{qs}", headers={
        "Authorization": f"Basic {token}",
        "Content-Type": "application/json",
        "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            status, body = r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        status, body = e.code, e.read().decode("utf-8", "replace")[:500]
    print(f"tree (moduleName={module}): HTTP {status}")
    if status != 200:
        print(body[:500])
        return
    data = json.loads(body)
    nodes = data if isinstance(data, list) else data.get("items") or data.get("children") or []
    rows = []
    for n in nodes:
        if not isinstance(n, dict) or n.get("id") is None:
            continue
        art = n.get("article")
        if art in (None, ""):  # группы/категории без артикула пропускаем
            continue
        mu = n.get("measureUnit")
        unit = mu.get("id") if isinstance(mu, dict) else None
        rows.append({"id": n["id"], "art": str(art), "name": n.get("name"), "unit": unit})
    print(f"позиций с артикулом: {len(rows)} (всего узлов: {len(nodes)})")
    for r in rows[:20]:
        print(f"  art {r['art']:>6} | id {r['id']:>5} | unit {r['unit']} | {str(r['name'])[:32]}")
    if len(rows) > 20:
        print(f"  … ещё {len(rows) - 20}")
    if out:
        with open(out, "w", encoding="utf-8") as f:
            f.write(body)
        print(f"Сырой ответ сохранён: {out}")
    if map_out:
        amap = {r["art"]: {"id": r["id"], "unit": r["unit"], "name": r["name"]} for r in rows}
        with open(map_out, "w", encoding="utf-8") as f:
            json.dump(amap, f, ensure_ascii=False, indent=2)
        print(f"Карта артикул→id сохранена: {map_out} ({len(amap)} записей)")


def main():
    ap = argparse.ArgumentParser(description="read-only разведка открытого API QR (путь A)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("auth", help="проверить авторизацию (чтение номенклатуры)")
    inv_p = sub.add_parser("invoice", help="список приходных с id")
    inv_p.add_argument("--number", default=None, help="найти id приходной по номеру документа")
    sr = sub.add_parser("read", help="read объекта С ПОДОБЪЕКТАМИ по id (по умолчанию приходная)")
    sr.add_argument("--id", dest="object_id", type=int, required=True)
    sr.add_argument("--module", default=None)
    sr.add_argument("--class", dest="class_name", default=None)
    sr.add_argument("--raw", action="store_true",
                    help="печать ПОЛНОГО сырого JSON (для реконструкции create)")
    sr.add_argument("--out", default=None, help="сохранить сырой JSON в файл")
    sub.add_parser("refs", help="id+названия складов и поставщиков (для payload)")
    sp = sub.add_parser("schema", help="снять форму любого объекта по moduleName/className")
    sp.add_argument("--module", required=True)
    sp.add_argument("--class", dest="class_name", required=True)
    smp = sub.add_parser("map", help="id+article+name+unit номенклатуры (для product:{id})")
    smp.add_argument("--module", required=True)
    smp.add_argument("--class", dest="class_name", required=True)
    sc = sub.add_parser("children", help="дети группы номенклатуры по parentId (data/select)")
    sc.add_argument("--parent", type=int, required=True)
    sc.add_argument("--module", default=None)
    sc.add_argument("--class", dest="class_name", default=None)
    st = sub.add_parser("tree", help="плоский список номенклатуры через /api/tree")
    st.add_argument("--module", default="warehouse.nomenclature.singleproduct")
    st.add_argument("--out", default=None, help="сохранить сырой ответ в файл")
    st.add_argument("--map-out", dest="map_out", default=None,
                    help="сохранить карту артикул→id в JSON")
    a = ap.parse_args()
    layer, login, password = _env()
    if a.cmd == "auth":
        cmd_auth(layer, login, password)
    elif a.cmd == "invoice":
        cmd_invoice(layer, login, password, getattr(a, "number", None))
    elif a.cmd == "read":
        cmd_read(layer, login, password, a.object_id, a.module, a.class_name,
                 raw=a.raw, out=a.out)
    elif a.cmd == "refs":
        cmd_refs(layer, login, password)
    elif a.cmd == "schema":
        cmd_schema(layer, login, password, a.module, a.class_name)
    elif a.cmd == "map":
        cmd_map(layer, login, password, a.module, a.class_name)
    elif a.cmd == "children":
        cmd_children(layer, login, password, a.parent, a.module, a.class_name)
    elif a.cmd == "tree":
        cmd_tree(layer, login, password, a.module, out=a.out, map_out=a.map_out)


if __name__ == "__main__":
    main()
