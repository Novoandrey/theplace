#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
match_nomenclature.py — сопоставление строки накладной с номенклатурой Quick Resto.

PoC v0 для bot_invoice. Ищет позицию QR по ключевым словам названия и возвращает
кандидатов с артикулом, единицей, весом базовой единицы и группой. Сначала проверяет
таблицу соответствий (aliases.json), затем нечёткий матч по справочнику (nomenclature_qr.json).

CLI:
  python3 match_nomenclature.py "фарш говяж 70 30"
  python3 match_nomenclature.py --self-test     # прогон по 11 строкам EK-2029
"""
import json, re, sys, difflib, os

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")

def _norm(s): return re.sub(r"[^a-zа-я0-9 ]", " ", s.lower().replace("ё", "е")).split()

def load_nomenclature(path=None):
    path = path or os.path.join(DATA, "nomenclature_qr.json")
    items = json.load(open(path, encoding="utf-8"))["items"]
    for it in items:
        it["_t"] = set(_norm(it["name"]))
    return items

def load_aliases(path=None):
    path = path or os.path.join(DATA, "aliases.json")
    if not os.path.exists(path):
        return []
    return json.load(open(path, encoding="utf-8"))["aliases"]

def match(keywords, items, aliases=None, n=4):
    """keywords: список ключевых слов. Возвращает список (score, item) от лучших к худшим.
    score>=100 — точное соответствие из aliases."""
    keys = [k.lower() for k in keywords]
    out = []
    for a in (aliases or []):
        if all(k in [x.lower() for x in a["keywords"]] for k in keys) or \
           all(k in keys for k in [x.lower() for x in a["keywords"]]):
            hit = next((i for i in items if i["art"] == a["art"]), None)
            if hit:
                out.append((100.0, hit))
    if out:
        return out
    for it in items:
        name = it["name"].lower()
        sub = sum(1 for k in keys if k in name)
        tok = len(set(keys) & it["_t"])
        fuzz = max([difflib.SequenceMatcher(None, k, w).ratio()
                    for k in keys for w in it["_t"]] or [0])
        score = sub * 3 + tok * 2 + fuzz
        if score > 0:
            out.append((score, it))
    out.sort(key=lambda x: -x[0])
    return out[:n]

# Ключевые слова для 11 строк EK-2029 (для self-test и как пример извлечения ключей)
EK2029_KEYS = {
    1: ["фарш", "говяж", "70", "30"], 2: ["тунец"], 3: ["мука"],
    4: ["трюфел"], 5: ["горчица", "дижон"], 6: ["каперс"], 7: ["майонез"],
    8: ["бекон"], 9: ["лимон", "концентрат", "сок"], 10: ["демигл"], 11: ["подсолнеч"],
}

def _fmt(it): return f"арт {it['art']:>6} · {it['unit']:>2} · вес.ед {it['weight_kg']} · {it['group']} · {it['name']}"

# Порог уверенности нечёткого матча: ниже — «слабо», требует подтверждения/может быть «нет в номенклатуре».
MATCH_MIN = 4.0
def classify(score):
    if score >= 100: return "alias"
    if score >= MATCH_MIN: return "fuzzy"
    return "weak"   # вероятно нет в номенклатуре / спорно — спросить человека

def main():
    items = load_nomenclature(); aliases = load_aliases()
    if len(sys.argv) >= 2 and sys.argv[1] == "--self-test":
        for n, keys in EK2029_KEYS.items():
            res = match(keys, items, aliases)
            top = res[0] if res else None
            kind = classify(top[0]) if top else "нет"
            print(f"#{n:>2} {kind:>5} | {_fmt(top[1]) if top else '—'}")
        return 0
    if len(sys.argv) < 2:
        print('usage: match_nomenclature.py "ключевые слова" | --self-test'); return 2
    for sc, it in match(sys.argv[1].split(), items, aliases):
        print(f"[{sc:5.1f}] {_fmt(it)}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
