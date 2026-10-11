"""
LLM-объяснения для подозрительных транзакций.

Локальная языковая модель (через Ollama) пишет аналитику короткую записку
о транзакции: что в ней необычного и что проверить. Модель получает только
факты, посчитанные конвейером RiskLens, и не видит сырых данных.

После генерации текст проходит детерминированную проверку: каждое число
из ответа модели сверяется со справочкой фактов. Если модель назвала
число, которого в фактах нет, ответ помечается как непроверенный и
аналитик видит, какие именно числа не подтвердились.

Зависимостей нет — запрос к Ollama идёт через стандартный urllib.
"""

from __future__ import annotations

import json
import math
import os
import re
import socket
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from statistics import median
from typing import Any, Dict, List, Optional

OLLAMA_URL = os.getenv("RISKLENS_OLLAMA_URL", "http://127.0.0.1:11434")
# instruct-версия отвечает сразу; обычный тег qwen3:4b в Ollama — thinking-версия,
# которая сначала долго рассуждает и на процессоре ноутбука не укладывается в лимит.
DEFAULT_MODEL = os.getenv("RISKLENS_LLM_MODEL", "qwen3:4b-instruct")
TIMEOUT_SEC = float(os.getenv("RISKLENS_LLM_TIMEOUT", "300"))
# Сколько модель держится в памяти после запроса: без этого Ollama выгружает её
# через 5 минут, и следующий запрос снова ждёт загрузку.
KEEP_ALIVE = os.getenv("RISKLENS_LLM_KEEP_ALIVE", "30m")
# Ограничение длины ответа: записка короткая, а на процессоре каждый токен дорогой.
MAX_TOKENS = int(os.getenv("RISKLENS_LLM_MAX_TOKENS", "400"))

# Ollama работает локально, поэтому системный прокси или VPN обходим явно:
# иначе urllib на Windows может отправить запрос к localhost через прокси.
_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def ollama_get(path: str, timeout: float = 5) -> dict:
    with _opener.open(f"{OLLAMA_URL}{path}", timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))

RULE_NAMES_RU = {
    "jump_from_previous": "резкий скачок относительно предыдущей операции",
    "high_vs_average": "сумма сильно выше среднего по клиенту",
    "high_share_of_total": "большая доля в общем обороте клиента",
    "increasing_sequence": "три нарастающие операции подряд",
    "high_frequency": "много операций за сутки",
}

RISK_CLASS_RU = {
    "high_risk": "высокий",
    "medium_risk": "средний",
    "low_risk": "низкий",
}

SYSTEM_PROMPT = """Ты помощник аналитика службы внутреннего контроля банка.
Тебе дают факты о финансовой операции, посчитанные системой оценки риска.
Напиши короткую аналитическую записку на русском языке.

Правила:
- Используй только числа из фактов. Не придумывай новых чисел, дат и сумм.
- Не утверждай, что операция мошенническая. Система только оценивает риск.
- 3–5 предложений: что необычного в операции по сравнению с привычным поведением клиента
  и почему система подняла риск.
- В конце отдельной строкой начни с «Что проверить:» и дай 1–2 конкретных шага для аналитика.
- Без заголовков, списков и markdown."""


# ---------------------------------------------------------------------------
# Справка фактов
# ---------------------------------------------------------------------------

def _num(value: Any) -> Optional[float]:
    """Число или None, если значение пустое или NaN."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) or math.isinf(f) else f


def _rules_list(value: Any) -> List[str]:
    if isinstance(value, str):
        return [r.strip() for r in value.split(",") if r.strip()]
    if isinstance(value, (list, tuple)):
        return [str(r) for r in value]
    return []


def build_facts(tx: Dict[str, Any], history: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Собирает справку фактов по транзакции и предыдущей истории клиента.

    ``history`` — все кэшированные операции клиента; используются только
    те, что были раньше текущей, чтобы не подглядывать в будущее.
    """
    t_time = str(tx.get("transaction_time", ""))
    prev = [h for h in history if str(h.get("transaction_time", "")) < t_time]
    prev_amounts = [a for a in (_num(h.get("amount")) for h in prev) if a is not None]

    def r(x: Optional[float], nd: int = 2) -> Optional[float]:
        return None if x is None else round(x, nd)

    rules = _rules_list(tx.get("triggered_rules"))
    facts: Dict[str, Any] = {
        "id_операции": str(tx.get("transaction_id")),
        "клиент": str(tx.get("user_id")),
        "сумма": r(_num(tx.get("amount"))),
        "время": t_time.replace("T", " ")[:19],
        "итоговый_скор": r(_num(tx.get("final_score")), 3),
        "уровень_риска": RISK_CLASS_RU.get(str(tx.get("risk_class")), str(tx.get("risk_class"))),
        "скор_правил": r(_num(tx.get("rule_score")), 3),
        "поведенческий_скор": r(_num(tx.get("behavioral_risk_score")), 3),
        "скор_ML_модели": r(_num(tx.get("model_score")), 3),
        "во_сколько_раз_больше_предыдущей": r(_num(tx.get("amount_ratio_prev")), 1),
        "во_сколько_раз_больше_среднего_клиента": r(_num(tx.get("amount_ratio_avg")), 1),
        "доля_в_обороте_клиента_проц": r(
            None if _num(tx.get("share_of_total")) is None else _num(tx.get("share_of_total")) * 100, 1
        ),
        "операций_за_сутки": _num(tx.get("transactions_last_24_h")),
        "три_нарастающие_подряд": bool(_num(tx.get("is_increasing_3")) == 1),
        "сработавшие_правила": [RULE_NAMES_RU.get(x, x) for x in rules],
        "операций_в_истории_до_этой": len(prev),
        "медианная_сумма_клиента": r(median(prev_amounts)) if prev_amounts else None,
        "максимальная_прошлая_сумма": r(max(prev_amounts)) if prev_amounts else None,
    }
    return {k: v for k, v in facts.items() if v is not None and v != []}


# ---------------------------------------------------------------------------
# Проверка чисел
# ---------------------------------------------------------------------------

_TIME_RE = re.compile(r"\b\d{1,2}:\d{2}(?::\d{2})?\b")
_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
# число с пробелами-разделителями тысяч и запятой или точкой в дробной части
_NUM_RE = re.compile(r"(?<![\w.])\d{1,3}(?:[   ]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?")


def _parse_number(token: str) -> float:
    t = token.replace(" ", "").replace(" ", "").replace(" ", "").replace(",", ".")
    return float(t)


def _fact_numbers(facts: Dict[str, Any]) -> List[float]:
    nums: List[float] = []
    for v in facts.values():
        if isinstance(v, bool):
            continue
        if isinstance(v, (int, float)):
            nums.append(float(v))
        elif isinstance(v, str):
            nums.extend(_parse_number(m) for m in _NUM_RE.findall(_TIME_RE.sub(" ", _DATE_RE.sub(" ", v))))
    # проценты и доли — модель может написать 0.69 как 69
    nums += [n * 100 for n in nums if 0 < n <= 1]
    # «три нарастающие подряд» модель может записать цифрой
    if facts.get("три_нарастающие_подряд"):
        nums.append(3.0)
    return nums


def verify_numbers(text: str, facts: Dict[str, Any]) -> Dict[str, Any]:
    """Сверяет числа, даты и время в тексте модели со справкой фактов."""
    facts_text = " ".join(str(v) for v in facts.values())
    unverified: List[str] = []

    for pattern in (_DATE_RE, _TIME_RE):
        for m in pattern.findall(text):
            if m not in facts_text and m[:5] not in facts_text:
                unverified.append(m)
    cleaned = _TIME_RE.sub(" ", _DATE_RE.sub(" ", text))

    allowed = _fact_numbers(facts)
    checked = 0
    for token in _NUM_RE.findall(cleaned):
        x = _parse_number(token)
        if x in (1, 2):  # «1–2 шага», «в 2 раза» без точного значения — не проверяем
            continue
        checked += 1
        ok = any(abs(x - a) <= max(0.06 * abs(a), 0.05) for a in allowed)
        if not ok:
            unverified.append(token.strip())

    return {
        "numbers_checked": checked,
        "unverified": unverified,
        "verified": not unverified,
    }


# ---------------------------------------------------------------------------
# Вызов модели
# ---------------------------------------------------------------------------

class LLMUnavailable(RuntimeError):
    """Ollama не запущена или модель не скачана."""


def _strip_thinking(text: str) -> str:
    """Убирает рассуждения модели, если они попали в ответ.

    Бывает два вида: блок <think>...</think> целиком или только закрывающий тег,
    когда открывающий подставлен в шаблон промпта.
    """
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    if "</think>" in text:
        text = text.split("</think>")[-1]
    return text.strip()


def call_ollama(facts: Dict[str, Any], model: str = DEFAULT_MODEL) -> str:
    payload = {
        "model": model,
        "stream": False,
        "think": False,
        "keep_alive": KEEP_ALIVE,
        "options": {"temperature": 0, "num_predict": MAX_TOKENS},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "Факты об операции (JSON):\n"
                                        + json.dumps(facts, ensure_ascii=False, separators=(",", ":"))},
        ],
    }
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with _opener.open(req, timeout=TIMEOUT_SEC) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        raise LLMUnavailable(f"Ollama вернула {e.code}: {detail}") from e
    except (TimeoutError, socket.timeout) as e:
        raise LLMUnavailable(
            f"Модель {model} не ответила за {TIMEOUT_SEC:.0f} секунд. Первый запуск бывает "
            f"дольше — модель загружается в память. Попробуйте ещё раз."
        ) from e
    except (urllib.error.URLError, ConnectionError, OSError) as e:
        raise LLMUnavailable(
            f"Не удалось подключиться к Ollama по адресу {OLLAMA_URL}: {e}. "
            f"Запущена ли она и скачана ли модель {model}?"
        ) from e
    return _strip_thinking(data.get("message", {}).get("content", ""))


@dataclass
class Narrative:
    transaction_id: str
    model: str
    text: str
    facts: Dict[str, Any]
    verification: Dict[str, Any]
    latency_sec: float
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def explain(tx: Dict[str, Any], history: List[Dict[str, Any]], model: str = DEFAULT_MODEL) -> Narrative:
    facts = build_facts(tx, history)
    t0 = time.perf_counter()
    text = call_ollama(facts, model=model)
    latency = round(time.perf_counter() - t0, 2)
    check = verify_numbers(text, facts)

    warnings = []
    if not check["verified"]:
        warnings.append(
            "В тексте есть числа, которых нет в данных системы: "
            + ", ".join(check["unverified"])
            + ". Проверьте их перед использованием."
        )
    if facts.get("операций_в_истории_до_этой", 0) < 50:
        warnings.append(
            "У клиента меньше 50 операций в истории — поведенческие признаки по нему менее надёжны."
        )
    return Narrative(
        transaction_id=str(tx.get("transaction_id")),
        model=model,
        text=text,
        facts=facts,
        verification=check,
        latency_sec=latency,
        warnings=warnings,
    )
