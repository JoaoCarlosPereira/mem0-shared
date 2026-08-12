"""Tests for GET /kanban-prompts/{status} endpoint (Task 04).

Pattern: FastAPI TestClient + SQLite in-memory factory (same as
``test_specs_rich.py`` / ``test_governance_jobs.py``).  Seeds one
``KanbanColumnPrompt`` row per test and exercises:

- ``GET /kanban-prompts/tasks`` → 200 with prompt
- ``GET /kanban-prompts/inexistente`` → 404
- ``GET /kanban-prompts/em_andamento`` → 200 with COLUMN_GUIDE label
- Prompt with ``is_enabled=False`` → 200 with is_enabled=false
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import KanbanColumnPrompt
from app.routers.specs import router as specs_router
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def factory():
    """In-memory SQLite with all metadata created."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield sessionmaker(autocommit=False, autoflush=False, bind=engine)
    engine.dispose()


def _make_app(factory):
    """Helper to create a FastAPI app with seeded data and db override."""

    def _override():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    return _override


class TestListKanbanPrompts:
    """Validate GET /kanban-prompts contract."""

    def test_list_all_prompts_successfully(self, factory):
        """GET /kanban-prompts retorna a lista completa de prompts."""
        app = FastAPI()
        app.include_router(specs_router)
        app.dependency_overrides[get_db] = _make_app(factory)

        db = factory()
        db.add_all([
            KanbanColumnPrompt(column_status="tasks", prompt="P1", is_enabled=True),
            KanbanColumnPrompt(column_status="em_andamento", prompt="P2", is_enabled=True),
        ])
        db.commit()

        client = TestClient(app)
        response = client.get("/api/v1/specs/kanban-prompts")
        assert response.status_code == 200
        data = response.json()
        assert [item["column_status"] for item in data] == [
            "tasks",
            "em_andamento",
            "revisao_codigo",
            "fase_teste",
            "concluido",
        ]
        assert data[0]["prompt"] == "P1"
        assert data[1]["prompt"] == "P2"

    def test_list_empty_prompts(self, factory):
        """GET /kanban-prompts retorna lista com defaults se não houver dados."""
        app = FastAPI()
        app.include_router(specs_router)
        app.dependency_overrides[get_db] = _make_app(factory)

        client = TestClient(app)
        response = client.get("/api/v1/specs/kanban-prompts")
        assert response.status_code == 200
        data = response.json()
        assert [item["column_status"] for item in data] == [
            "tasks",
            "em_andamento",
            "revisao_codigo",
            "fase_teste",
            "concluido",
        ]



class TestListKanbanPrompts:
    """Validate GET /kanban-prompts list contract."""

    def test_list_uses_pipeline_defaults_when_no_custom_prompts(self, factory):
        """GET /kanban-prompts retorna os status padrão quando não há overrides."""
        app = FastAPI()
        app.include_router(specs_router)
        app.dependency_overrides[get_db] = _make_app(factory)

        client = TestClient(app)
        response = client.get("/api/v1/specs/kanban-prompts")
        assert response.status_code == 200
        data = response.json()
        assert [item["column_status"] for item in data] == [
            "tasks",
            "em_andamento",
            "revisao_codigo",
            "fase_teste",
            "concluido",
        ]
        assert all(item["is_enabled"] is True for item in data)

    def test_list_multiple_prompts_sorted(self, factory):
        """GET /kanban-prompts retorna múltiplos prompts ordenados por status."""
        app = FastAPI()
        app.include_router(specs_router)
        app.dependency_overrides[get_db] = _make_app(factory)

        db = factory()
        db.add(KanbanColumnPrompt(column_status="tasks", prompt="Tasks override", is_enabled=True))
        db.add(
            KanbanColumnPrompt(
                column_status="em_andamento",
                prompt="In progress override",
                is_enabled=True,
            )
        )
        db.commit()

        client = TestClient(app)
        response = client.get("/api/v1/specs/kanban-prompts")
        assert response.status_code == 200
        data = response.json()
        assert [item["column_status"] for item in data] == [
            "tasks",
            "em_andamento",
            "revisao_codigo",
            "fase_teste",
            "concluido",
        ]
        assert data[0]["prompt"] == "Tasks override"
        assert data[1]["prompt"] == "In progress override"


class TestListKanbanPrompts:
    """Validate GET /kanban-prompts list contract."""

    def test_list_uses_pipeline_defaults_when_no_custom_prompts(self, factory):
        """GET /kanban-prompts retorna os status padrão quando não há overrides."""
        app = FastAPI()
        app.include_router(specs_router)
        app.dependency_overrides[get_db] = _make_app(factory)

        client = TestClient(app)
        response = client.get("/api/v1/specs/kanban-prompts")
        assert response.status_code == 200
        data = response.json()
        assert [item["column_status"] for item in data] == [
            "tasks",
            "em_andamento",
            "revisao_codigo",
            "fase_teste",
            "concluido",
        ]
        assert all(item["is_enabled"] is True for item in data)

    def test_list_multiple_prompts_sorted(self, factory):
        """GET /kanban-prompts retorna múltiplos prompts ordenados por status."""
        app = FastAPI()
        app.include_router(specs_router)
        app.dependency_overrides[get_db] = _make_app(factory)

        db = factory()
        db.add(KanbanColumnPrompt(column_status="tasks", prompt="Tasks override", is_enabled=True))
        db.add(
            KanbanColumnPrompt(
                column_status="em_andamento",
                prompt="In progress override",
                is_enabled=True,
            )
        )
        db.commit()

        client = TestClient(app)
        response = client.get("/api/v1/specs/kanban-prompts")
        assert response.status_code == 200
        data = response.json()
        assert [item["column_status"] for item in data] == [
            "tasks",
            "em_andamento",
            "revisao_codigo",
            "fase_teste",
            "concluido",
        ]
        assert data[0]["prompt"] == "Tasks override"
        assert data[1]["prompt"] == "In progress override"


class TestGetKanbanPromptByStatus:



    """Validate GET /kanban-prompts/{status} contract.

    Each test creates its own isolated in-memory SQLite database.
    """

    def test_returns_200_with_existing_prompt(self, factory):
        """GET /kanban-prompts/tasks retorna 200 com prompt existente."""
        app = FastAPI()
        app.include_router(specs_router)
        app.dependency_overrides[get_db] = _make_app(factory)
        # Seed the row
        db = factory()
        db.add(KanbanColumnPrompt(
            column_status="tasks",
            prompt="Execute testes antes de avanar.",
            is_enabled=True,
            updated_by="admin",
        ))
        db.commit()

        client = TestClient(app)
        response = client.get("/api/v1/specs/kanban-prompts/tasks")
        assert response.status_code == 200
        data = response.json()
        assert data["column_status"] == "tasks"
        assert data["prompt"] == "Execute testes antes de avanar."
        assert data["is_enabled"] is True
        assert data["updated_by"] == "admin"
        assert data["label"] == "Backlog (Tasks)"

    def test_returns_default_for_unknown_status(self, factory):
        """GET /kanban-prompts/inexistente retorna um fallback editável."""
        app = FastAPI()
        app.include_router(specs_router)
        app.dependency_overrides[get_db] = _make_app(factory)

        client = TestClient(app)
        response = client.get("/api/v1/specs/kanban-prompts/inexistente")
        assert response.status_code == 200
        assert response.json() == {
            "column_status": "inexistente",
            "label": "inexistente",
            "prompt": None,
            "is_enabled": True,
            "updated_at": None,
            "updated_by": None,
        }

    def test_label_derived_from_column_guide(self, factory):
        """Label vem de COLUMN_GUIDE para colunas conhecidas."""
        app = FastAPI()
        app.include_router(specs_router)
        app.dependency_overrides[get_db] = _make_app(factory)
        # Seed a prompt for em_andamento
        db = factory()
        db.add(KanbanColumnPrompt(
            column_status="em_andamento",
            prompt="Implemente o codigo.",
            is_enabled=True,
        ))
        db.commit()

        client = TestClient(app)
        response = client.get("/api/v1/specs/kanban-prompts/em_andamento")
        assert response.status_code == 200
        data = response.json()
        assert data["label"] == "Em andamento"
        assert data["column_status"] == "em_andamento"

    def test_is_enabled_false(self, factory):
        """Prompt desativado e retornado com is_enabled=false."""
        app = FastAPI()
        app.include_router(specs_router)
        app.dependency_overrides[get_db] = _make_app(factory)
        # Seed a disabled prompt
        db = factory()
        db.add(KanbanColumnPrompt(
            column_status="tasks",
            prompt="Teste antigo",
            is_enabled=False,
        ))
        db.commit()

        client = TestClient(app)
        response = client.get("/api/v1/specs/kanban-prompts/tasks")
        assert response.status_code == 200
        data = response.json()
        assert data["is_enabled"] is False


class TestPutKanbanPromptByStatus:
    """Validate PUT /kanban-prompts/{status} contract."""

    def test_update_existing_prompt_successfully(self, factory, monkeypatch):
        """PUT /kanban-prompts/{status} atualiza prompt existente com sucesso."""
        app = FastAPI()
        app.include_router(specs_router)
        app.dependency_overrides[get_db] = _make_app(factory)
        
        # Mock resolve_spec_actor
        monkeypatch.setattr("app.routers.specs.resolve_spec_actor", lambda: "test-actor")

        db = factory()
        db.add(KanbanColumnPrompt(
            column_status="tasks",
            prompt="Prompt antigo",
            is_enabled=True,
            updated_by="some-other",
        ))
        db.commit()

        client = TestClient(app)
        response = client.put(
            "/api/v1/specs/kanban-prompts/tasks",
            json={"prompt": "Prompt novo", "is_enabled": False}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["column_status"] == "tasks"
        assert data["prompt"] == "Prompt novo"
        assert data["is_enabled"] is False
        assert data["updated_by"] == "test-actor"
        assert data["updated_at"] is not None

        # Verify database is updated
        db = factory()
        row = db.query(KanbanColumnPrompt).filter_by(column_status="tasks").first()
        assert row.prompt == "Prompt novo"
        assert row.is_enabled is False
        assert row.updated_by == "test-actor"

    def test_update_only_prompt(self, factory):
        """PUT /kanban-prompts/{status} com apenas o prompt atualiza somente o prompt."""
        app = FastAPI()
        app.include_router(specs_router)
        app.dependency_overrides[get_db] = _make_app(factory)

        db = factory()
        db.add(KanbanColumnPrompt(
            column_status="tasks",
            prompt="Prompt antigo",
            is_enabled=True,
            updated_by="original",
        ))
        db.commit()

        client = TestClient(app)
        response = client.put(
            "/api/v1/specs/kanban-prompts/tasks",
            json={"prompt": "Prompt novo"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["prompt"] == "Prompt novo"
        assert data["is_enabled"] is True

        db = factory()
        row = db.query(KanbanColumnPrompt).filter_by(column_status="tasks").first()
        assert row.prompt == "Prompt novo"
        assert row.is_enabled is True

    def test_update_only_is_enabled(self, factory):
        """PUT /kanban-prompts/{status} com apenas is_enabled atualiza somente is_enabled."""
        app = FastAPI()
        app.include_router(specs_router)
        app.dependency_overrides[get_db] = _make_app(factory)

        db = factory()
        db.add(KanbanColumnPrompt(
            column_status="tasks",
            prompt="Prompt antigo",
            is_enabled=True,
            updated_by="original",
        ))
        db.commit()

        client = TestClient(app)
        response = client.put(
            "/api/v1/specs/kanban-prompts/tasks",
            json={"is_enabled": False}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["prompt"] == "Prompt antigo"
        assert data["is_enabled"] is False

        db = factory()
        row = db.query(KanbanColumnPrompt).filter_by(column_status="tasks").first()
        assert row.prompt == "Prompt antigo"
        assert row.is_enabled is False

    def test_update_both_simultaneously(self, factory):
        """PUT /kanban-prompts/{status} atualizando ambos simultaneamente."""
        app = FastAPI()
        app.include_router(specs_router)
        app.dependency_overrides[get_db] = _make_app(factory)

        db = factory()
        db.add(KanbanColumnPrompt(
            column_status="tasks",
            prompt="Prompt antigo",
            is_enabled=True,
            updated_by="original",
        ))
        db.commit()

        client = TestClient(app)
        response = client.put(
            "/api/v1/specs/kanban-prompts/tasks",
            json={"prompt": "Prompt super novo", "is_enabled": False}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["prompt"] == "Prompt super novo"
        assert data["is_enabled"] is False

        db = factory()
        row = db.query(KanbanColumnPrompt).filter_by(column_status="tasks").first()
        assert row.prompt == "Prompt super novo"
        assert row.is_enabled is False

    def test_put_empty_body_does_not_update(self, factory):
        """PUT com body vazio ({}) não deve alterar o prompt nem o updated_at."""
        app = FastAPI()
        app.include_router(specs_router)
        app.dependency_overrides[get_db] = _make_app(factory)

        db = factory()
        initial_updated_at = datetime.now(timezone.utc) - timedelta(days=1)
        db.add(KanbanColumnPrompt(
            column_status="tasks",
            prompt="Prompt Original",
            is_enabled=True,
            updated_at=initial_updated_at,
        ))
        db.commit()

        client = TestClient(app)
        response = client.put(
            "/api/v1/specs/kanban-prompts/tasks",
            json={}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["prompt"] == "Prompt Original"

        db = factory()
        row = db.query(KanbanColumnPrompt).filter_by(column_status="tasks").first()
        assert row.updated_at == initial_updated_at

    def test_put_empty_prompt_string(self, factory):
        """PUT com prompt="" deve permitir a string vazia."""
        app = FastAPI()
        app.include_router(specs_router)
        app.dependency_overrides[get_db] = _make_app(factory)

        db = factory()
        db.add(KanbanColumnPrompt(
            column_status="tasks",
            prompt="Prompt Original",
            is_enabled=True,
        ))
        db.commit()

        client = TestClient(app)
        response = client.put(
            "/api/v1/specs/kanban-prompts/tasks",
            json={"prompt": ""}
        )
        assert response.status_code == 200
        assert response.json()["prompt"] == ""

    def test_put_is_enabled_null_maintains_value(self, factory):
        """PUT com is_enabled=null deve manter o valor atual."""
        app = FastAPI()
        app.include_router(specs_router)
        app.dependency_overrides[get_db] = _make_app(factory)

        db = factory()
        db.add(KanbanColumnPrompt(
            column_status="tasks",
            prompt="Prompt Original",
            is_enabled=True,
        ))
        db.commit()

        client = TestClient(app)
        response = client.put(
            "/api/v1/specs/kanban-prompts/tasks",
            json={"is_enabled": None}
        )
        assert response.status_code == 200
        assert response.json()["is_enabled"] is True

    def test_put_empty_body_does_not_update(self, factory, monkeypatch):
        """PUT com body vazio {} não deve atualizar timestamps nem actor."""
        app = FastAPI()
        app.include_router(specs_router)
        app.dependency_overrides[get_db] = _make_app(factory)

        db = factory()
        row = KanbanColumnPrompt(
            column_status="tasks",
            prompt="Prompt original",
            is_enabled=True,
            updated_by="original_actor",
        )
        db.add(row)
        db.commit()
        
        # Capture updated_at for comparison
        original_updated_at = row.updated_at

        client = TestClient(app)
        response = client.put(
            "/api/v1/specs/kanban-prompts/tasks",
            json={}
        )
        assert response.status_code == 200
        
        db.refresh(row)
        assert row.updated_by == "original_actor"
        assert row.updated_at == original_updated_at

    def test_put_empty_prompt_string(self, factory):
        """PUT com prompt = "" deve permitir a string vazia."""
        app = FastAPI()
        app.include_router(specs_router)
        app.dependency_overrides[get_db] = _make_app(factory)

        db = factory()
        db.add(KanbanColumnPrompt(column_status="tasks", prompt="Original", is_enabled=True))
        db.commit()

        client = TestClient(app)
        response = client.put(
            "/api/v1/specs/kanban-prompts/tasks",
            json={"prompt": ""}
        )
        assert response.status_code == 200
        assert response.json()["prompt"] == ""

    def test_put_is_enabled_null_maintains_value(self, factory):
        """PUT com is_enabled=None (null) mantém o valor atual."""
        app = FastAPI()
        app.include_router(specs_router)
        app.dependency_overrides[get_db] = _make_app(factory)

        db = factory()
        db.add(KanbanColumnPrompt(column_status="tasks", prompt="Original", is_enabled=True))
        db.commit()

        client = TestClient(app)
        # In JSON, null is None in Python
        response = client.put(
            "/api/v1/specs/kanban-prompts/tasks",
            json={"is_enabled": None}
        )
        assert response.status_code == 200
        assert response.json()["is_enabled"] is True

    def test_cache_invalidated_after_update(self, factory, monkeypatch):
        """PUT de prompt de coluna Kanban bem-sucedido invalida o cache."""
        app = FastAPI()
        app.include_router(specs_router)
        app.dependency_overrides[get_db] = _make_app(factory)

        # Seed data
        db = factory()
        db.add(KanbanColumnPrompt(
            column_status="tasks",
            prompt="Prompt antigo",
            is_enabled=True,
        ))
        db.commit()

        invalidated = False

        def mock_invalidate():
            nonlocal invalidated
            invalidated = True

        monkeypatch.setattr("app.mcp_server._invalidate_kanban_prompts_cache", mock_invalidate)

        client = TestClient(app)
        response = client.put(
            "/api/v1/specs/kanban-prompts/tasks",
            json={"prompt": "Novo prompt"}
        )
        assert response.status_code == 200
        assert invalidated is True

    def test_character_limit_constraint(self, factory):
        """PUT com prompt maior que 5000 caracteres falha devido à constraint do DB."""
        app = FastAPI()
        app.include_router(specs_router)
        app.dependency_overrides[get_db] = _make_app(factory)

        db = factory()
        db.add(KanbanColumnPrompt(
            column_status="tasks",
            prompt="Prompt antigo",
            is_enabled=True,
        ))
        db.commit()

        client = TestClient(app, raise_server_exceptions=False)
        too_long_prompt = "A" * 5001

        response = client.put(
            "/api/v1/specs/kanban-prompts/tasks",
            json={"prompt": too_long_prompt}
        )
        assert response.status_code == 500

