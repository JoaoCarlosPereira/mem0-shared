import pytest
from pydantic import ValidationError
from datetime import datetime, timezone
from app.routers.specs import KanbanPromptUpdate, KanbanPromptRead


def test_kanban_prompt_update_valid():
    # Deve aceitar campos opcionais e nulos
    update = KanbanPromptUpdate(prompt="Teste de prompt", is_enabled=True)
    assert update.prompt == "Teste de prompt"
    assert update.is_enabled is True

    update_empty = KanbanPromptUpdate()
    assert update_empty.prompt is None
    assert update_empty.is_enabled is None

    update_null = KanbanPromptUpdate(prompt=None, is_enabled=None)
    assert update_null.prompt is None
    assert update_null.is_enabled is None


def test_kanban_prompt_update_limit_characters():
    # Pydantic schema em si não valida o limite de 5000 no model, 
    # mas deve aceitar strings grandes. A validação de 5000 caracteres
    # é um requisito da API ou do banco de dados (será testado no endpoint).
    long_prompt = "a" * 5000
    update = KanbanPromptUpdate(prompt=long_prompt)
    assert len(update.prompt) == 5000


def test_kanban_prompt_read_valid():
    now = datetime.now(timezone.utc)
    read = KanbanPromptRead(
        column_status="em_andamento",
        label="Em andamento",
        prompt="Execute testes",
        is_enabled=True,
        updated_at=now,
        updated_by="admin"
    )
    assert read.column_status == "em_andamento"
    assert read.label == "Em andamento"
    assert read.prompt == "Execute testes"
    assert read.is_enabled is True
    assert read.updated_at == now
    assert read.updated_by == "admin"


def test_kanban_prompt_read_missing_required():
    # column_status, label, is_enabled são obrigatórios
    with pytest.raises(ValidationError):
        KanbanPromptRead(label="Teste", is_enabled=True)

    with pytest.raises(ValidationError):
        KanbanPromptRead(column_status="tasks", is_enabled=True)

    with pytest.raises(ValidationError):
        KanbanPromptRead(column_status="tasks", label="Teste")
