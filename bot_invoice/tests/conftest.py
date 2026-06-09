"""Общие фикстуры и доступ к инструментам bot_invoice для pytest.

Инструменты лежат в tools/ как самостоятельные скрипты (не пакет), поэтому их каталог
добавляется в sys.path, и тесты импортируют их по имени модуля (validate_invoice и т.д.).
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent      # bot_invoice/
TOOLS = ROOT / "tools"
DATA = ROOT / "data"
SAMPLES = ROOT / "samples"
sys.path.insert(0, str(TOOLS))


@pytest.fixture
def ek2029():
    """Канонический JSON извлечения EK-2029: сходится, 11 строк, все сопоставлены."""
    return json.loads((SAMPLES / "EK-2029_extracted.json").read_text(encoding="utf-8"))
