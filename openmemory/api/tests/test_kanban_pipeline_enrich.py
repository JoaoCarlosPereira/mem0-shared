"""Testes da injeção de column_prompt em enrich_status_payload."""

import pytest
from app.utils.kanban_pipeline import enrich_status_payload, _get_kanban_prompts_cache

def test_enrich_status_payload_with_enabled_prompt(monkeypatch):
    # Mock do cache global do mcp_server
    cache_mock = {
        "tasks": {"prompt": "Prompt customizado para backlog", "is_enabled": True},
        "em_andamento": {"prompt": "Prompt em andamento desabilitado", "is_enabled": False},
        "revisao_codigo": {"prompt": "", "is_enabled": True},
    }
    
    monkeypatch.setattr("app.utils.kanban_pipeline._get_kanban_prompts_cache", lambda: cache_mock)
    
    # 1. Status com prompt habilitado
    payload = {"some": "data"}
    res = enrich_status_payload(payload, "tasks")
    assert res["some"] == "data"
    assert res["kanban"]["column_prompt"] == "Prompt customizado para backlog"
    
    # 2. Status com prompt desabilitado
    res = enrich_status_payload(payload, "em_andamento")
    assert res["kanban"]["column_prompt"] is None
    
    # 3. Status com prompt vazio
    res = enrich_status_payload(payload, "revisao_codigo")
    assert res["kanban"]["column_prompt"] is None

def test_enrich_status_payload_with_missing_status(monkeypatch):
    cache_mock = {
        "tasks": {"prompt": "Prompt customizado para backlog", "is_enabled": True},
    }
    monkeypatch.setattr("app.utils.kanban_pipeline._get_kanban_prompts_cache", lambda: cache_mock)
    
    # 4. Status que não está no cache
    payload = {}
    res = enrich_status_payload(payload, "concluido")
    assert res["kanban"]["column_prompt"] is None

def test_enrich_status_payload_with_empty_cache(monkeypatch):
    monkeypatch.setattr("app.utils.kanban_pipeline._get_kanban_prompts_cache", lambda: {})
    
    # 5. Cache totalmente vazio
    payload = {}
    res = enrich_status_payload(payload, "tasks")
    assert res["kanban"]["column_prompt"] is None

def test_enrich_status_payload_with_none_cache(monkeypatch):
    monkeypatch.setattr("app.utils.kanban_pipeline._get_kanban_prompts_cache", lambda: None)
    
    # 6. Cache é None (ex.: falha ao inicializar)
    payload = {}
    res = enrich_status_payload(payload, "tasks")
    assert res["kanban"]["column_prompt"] is None

def test_enrich_status_payload_complex_prompts(monkeypatch):
    """Testa prompts com caracteres especiais, emojis, quebras de linha e tamanho longo."""
    long_prompt = "A" * 5000
    complex_prompt = "Prompt com 🚀 emojis, \n quebras de linha e \t tabs. Unicode: ⚡️"
    
    cache_mock = {
        "tasks": {"prompt": long_prompt, "is_enabled": True},
        "em_andamento": {"prompt": complex_prompt, "is_enabled": True},
    }
    monkeypatch.setattr("app.utils.kanban_pipeline._get_kanban_prompts_cache", lambda: cache_mock)
    
    # Prompt longo
    res = enrich_status_payload({}, "tasks")
    assert res["kanban"]["column_prompt"] == long_prompt
    
    # Prompt complexo
    res = enrich_status_payload({}, "em_andamento")
    assert res["kanban"]["column_prompt"] == complex_prompt

def test_enrich_status_payload_immutability(monkeypatch):
    """Verifica que o payload original não é modificado."""
    cache_mock = {"tasks": {"prompt": "test", "is_enabled": True}}
    monkeypatch.setattr("app.utils.kanban_pipeline._get_kanban_prompts_cache", lambda: cache_mock)
    
    original_payload = {"key": "value"}
    # Copia profunda para garantir a comparação
    payload_copy = dict(original_payload)
    
    res = enrich_status_payload(original_payload, "tasks")
    
    assert res is not original_payload
    assert original_payload == payload_copy
    assert "kanban" not in original_payload

def test_enrich_status_payload_preserves_guide_info(monkeypatch):
    """Verifica que as informações do guide_for são preservadas ao injetar o prompt."""
    cache_mock = {"tasks": {"prompt": "custom prompt", "is_enabled": True}}
    monkeypatch.setattr("app.utils.kanban_pipeline._get_kanban_prompts_cache", lambda: cache_mock)
    
    res = enrich_status_payload({}, "tasks")
    
    # Deve conter o prompt
    assert res["kanban"]["column_prompt"] == "custom prompt"
    # Deve conter campos do guide (COLUMN_GUIDE)
    assert "label" in res["kanban"]
    assert "means" in res["kanban"]
    assert "do_now" in res["kanban"]
    assert "pipeline" in res["kanban"]
