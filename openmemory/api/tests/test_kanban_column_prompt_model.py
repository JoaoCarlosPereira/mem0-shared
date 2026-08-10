"""Testes unitários e de integração para o modelo KanbanColumnPrompt."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import KanbanColumnPrompt


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


class TestKanbanColumnPromptModel:
    def test_kanban_column_prompt_persistence_com_defaults(self, db_session):
        # 1. Criação e persistência com defaults
        prompt = KanbanColumnPrompt(
            column_status="em_andamento",
            prompt="Faça X, Y e Z.",
            updated_by="test-user",
        )
        db_session.add(prompt)
        db_session.commit()

        # Busca via query
        db_session.refresh(prompt)
        found = db_session.query(KanbanColumnPrompt).filter_by(column_status="em_andamento").one()
        assert found.column_status == "em_andamento"
        assert found.prompt == "Faça X, Y e Z."
        assert found.is_enabled is True
        assert found.updated_at is not None
        assert found.updated_by == "test-user"

    def test_kanban_column_prompt_limite_caracteres_sucesso(self, db_session):
        # 2. Prompt no limite exato de 5000 caracteres
        prompt_text = "a" * 5000
        prompt = KanbanColumnPrompt(
            column_status="revisao_codigo",
            prompt=prompt_text,
        )
        db_session.add(prompt)
        db_session.commit()

        db_session.refresh(prompt)
        found = db_session.query(KanbanColumnPrompt).filter_by(column_status="revisao_codigo").one()
        assert len(found.prompt) == 5000

    def test_kanban_column_prompt_limite_caracteres_excedido_falha(self, db_session):
        # 3. Prompt que excede o limite de 5000 caracteres (deve falhar a constraint)
        prompt_text = "a" * 5001
        prompt = KanbanColumnPrompt(
            column_status="fase_teste",
            prompt=prompt_text,
        )
        db_session.add(prompt)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_kanban_column_prompt_status_unico(self, db_session):
        # 4. Violação de unicidade da chave primária (column_status)
        p1 = KanbanColumnPrompt(column_status="concluido", prompt="Prompt 1")
        p2 = KanbanColumnPrompt(column_status="concluido", prompt="Prompt 2")
        db_session.add(p1)
        db_session.commit()

        db_session.add(p2)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()
