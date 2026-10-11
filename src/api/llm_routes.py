"""
Эндпоинты LLM-объяснений.

GET /explain/{transaction_id}   Записка аналитику от локальной модели + проверка чисел
GET /explain/status             Доступна ли Ollama и какие модели скачаны
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.dependencies import AppState, get_state
from src.llm import narrator
from src.llm.narrator import DEFAULT_MODEL, LLMUnavailable, explain

llm_router = APIRouter()

# Кэш готовых объяснений: (transaction_id, model) -> dict
_cache: dict = {}


def _find_transaction(state: AppState, transaction_id: str):
    for user_id, txs in state.user_cache.items():
        for tx in txs:
            if str(tx.get("transaction_id")) == transaction_id:
                return tx, state.get_user(user_id)
    return None, []


@llm_router.get("/explain/status", summary="Проверить, доступна ли локальная LLM")
def llm_status():
    try:
        models = [m["name"] for m in narrator.ollama_get("/api/tags")["models"]]
        return {"available": True, "url": narrator.OLLAMA_URL, "default_model": DEFAULT_MODEL,
                "default_model_installed": DEFAULT_MODEL in models, "models": models}
    except Exception as e:
        return {"available": False, "url": narrator.OLLAMA_URL, "default_model": DEFAULT_MODEL,
                "models": [], "error": f"{type(e).__name__}: {e}"}


@llm_router.get("/explain/{transaction_id}", summary="LLM-записка аналитику по транзакции")
def explain_transaction(
    transaction_id: str,
    model: Optional[str] = Query(None, description="Модель Ollama, по умолчанию из настроек"),
    refresh: bool = Query(False, description="Сгенерировать заново, игнорируя кэш"),
    state: AppState = Depends(get_state),
):
    model = model or DEFAULT_MODEL
    key = (transaction_id, model)
    if key in _cache and not refresh:
        return _cache[key]

    tx, history = _find_transaction(state, transaction_id)
    if tx is None:
        raise HTTPException(
            status_code=404,
            detail=f"Транзакция '{transaction_id}' не найдена. Сначала запустите анализ.",
        )
    try:
        result = explain(tx, history, model=model).to_dict()
    except LLMUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e))

    _cache[key] = result
    return result
