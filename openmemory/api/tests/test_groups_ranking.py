"""Testes do fator de boost de grupo no ranqueamento (task_03 / ADR-003)."""

import importlib

import pytest

from app.utils import recency


@pytest.fixture(autouse=True)
def _reset_env(monkeypatch):
    # Garante o default de boost a menos que o teste sobrescreva.
    monkeypatch.delenv("MEM0_SEARCH_GROUP_BOOST", raising=False)
    yield


def test_group_match_factor_same_group_returns_boost():
    assert recency.group_match_factor("Equipe A", "Equipe A") == recency.SEARCH_GROUP_BOOST


def test_group_match_factor_different_group_is_neutral():
    assert recency.group_match_factor("Equipe A", "Equipe B") == 1.0


def test_group_match_factor_missing_groups_are_neutral():
    assert recency.group_match_factor(None, "Equipe A") == 1.0
    assert recency.group_match_factor("Equipe A", None) == 1.0
    assert recency.group_match_factor(None, None) == 1.0


def test_group_boost_env_overrides_multiplier(monkeypatch):
    monkeypatch.setenv("MEM0_SEARCH_GROUP_BOOST", "5.0")
    reloaded = importlib.reload(recency)
    try:
        assert reloaded.group_match_factor("X", "X") == 5.0
    finally:
        # Restaura o módulo no estado padrão para os demais testes.
        monkeypatch.delenv("MEM0_SEARCH_GROUP_BOOST", raising=False)
        importlib.reload(reloaded)


def test_same_group_result_outranks_higher_score_other_group(monkeypatch):
    # author hostname -> grupo
    mapping = {"host-a": "Equipe A", "host-b": "Equipe B"}
    monkeypatch.setattr(recency, "group_of_hostname", lambda h: mapping.get(h))
    # Desliga recência para isolar o efeito do grupo.
    monkeypatch.setattr(recency, "SEARCH_RECENCY_HALFLIFE_DAYS", 0.0)

    results = [
        {"id": "outro", "score": 0.80, "owner": "host-b"},   # outro grupo, score maior
        {"id": "meu", "score": 0.50, "owner": "host-a"},     # mesmo grupo, score menor
    ]
    recency.rank_search_results(results, requester_group="Equipe A")
    assert results[0]["id"] == "meu", "0.50 * 2.5 = 1.25 deve superar 0.80 * 1.0"
    # A memória de outro grupo continua presente nos resultados.
    assert {r["id"] for r in results} == {"meu", "outro"}


def test_without_requester_group_no_group_lookup(monkeypatch):
    calls = {"n": 0}

    def _spy(h):
        calls["n"] += 1
        return "Qualquer"

    monkeypatch.setattr(recency, "group_of_hostname", _spy)
    monkeypatch.setattr(recency, "SEARCH_RECENCY_HALFLIFE_DAYS", 0.0)

    results = [{"id": "a", "score": 0.9, "owner": "host-a"}]
    recency.rank_search_results(results, requester_group=None)
    assert calls["n"] == 0, "sem grupo do solicitante, não deve resolver grupo do autor"


def test_result_without_owner_is_not_penalized(monkeypatch):
    monkeypatch.setattr(recency, "group_of_hostname", lambda h: None if not h else "G")
    monkeypatch.setattr(recency, "SEARCH_RECENCY_HALFLIFE_DAYS", 0.0)

    results = [
        {"id": "sem_owner", "score": 0.70},                 # legada, sem owner
        {"id": "outro_grupo", "score": 0.65, "owner": "x"},  # owner resolve p/ "G"
    ]
    recency.rank_search_results(results, requester_group="Outro")
    # Nenhum recebe boost (sem_owner=None; outro_grupo="G" != "Outro"); ordena por score.
    assert results[0]["id"] == "sem_owner"
