import pytest
from datetime import timedelta
from app.utils.governance_policy import validate_policy_document
from app.governance.ttl_prune import run_ttl_prune_job
from app.governance.dedup import run_dedup_job
from app.models import Memory, MemoryState
from app.utils.datetime_utc import utc_now_naive
from unittest.mock import MagicMock, patch

def test_policy_ttl_idle_days():
    # 1. Política consolidada com ttl_idle_days = 180.
    doc = validate_policy_document({})
    assert doc["ttl_idle_days"] == 180

@patch('app.governance.ttl_prune._last_access')
def test_ttl_prune_respects_idle_days(mock_last_access):
    # 2. TTL prune job não exclui memórias acessadas dentro de 180 dias.
    mock_db = MagicMock()
    mock_session_factory = MagicMock(return_value=mock_db)
    mock_engine = MagicMock()
    mock_engine.is_pinned.return_value = False
    
    now = utc_now_naive()
    
    # Must be older than ttl_max_age_days (365) to even be considered
    mem1 = Memory(id="1", state=MemoryState.active, created_at=now - timedelta(days=400))
    mem2 = Memory(id="2", state=MemoryState.active, created_at=now - timedelta(days=400))
    
    def mock_query(model):
        if model is Memory:
            q = MagicMock()
            q.filter.return_value.all.return_value = [mem1, mem2]
            return q
        else:
            q = MagicMock()
            q.join.return_value.filter.return_value.all.return_value = []
            return q
            
    mock_db.query.side_effect = mock_query
    
    def mock_last_access_fn(db, mem_id):
        if str(mem_id) == "1":
            return now - timedelta(days=100)
        return now - timedelta(days=200)
        
    mock_last_access.side_effect = mock_last_access_fn
    
    run_ttl_prune_job(project=None, job_id="test", session_factory=mock_session_factory, quarantine_engine=mock_engine)
    
    mock_engine.quarantine.assert_called_once_with("2", reason="ttl_prune", job_id="test")

@patch('app.governance.dedup.resolve_policy')
def test_dedup_similarity_score(mock_resolve_policy):
    # 3. Dedup job só quarentena quando confiança >= 0.99
    mock_db = MagicMock()
    mock_session_factory = MagicMock(return_value=mock_db)
    mock_engine = MagicMock()
    mock_engine.is_pinned.return_value = False
    
    now = utc_now_naive()
    mem1 = Memory(id="1", state=MemoryState.active, created_at=now, content="test", metadata_={"hash": "abc"})
    mem2 = Memory(id="2", state=MemoryState.active, created_at=now+timedelta(seconds=1), content="test", metadata_={"hash": "abc", "similarity_score": 0.98})
    mem3 = Memory(id="3", state=MemoryState.active, created_at=now+timedelta(seconds=2), content="test", metadata_={"hash": "abc", "similarity_score": 0.99})
    
    def mock_query(model):
        q = MagicMock()
        q.filter.return_value.limit.return_value.all.return_value = [mem1, mem2, mem3]
        return q
        
    mock_db.query.side_effect = mock_query
    
    mock_resolve_policy.return_value = MagicMock(batch_limit=500, max_memories_action="alert")
    
    run_dedup_job(project=None, job_id="test", session_factory=mock_session_factory, quarantine_engine=mock_engine)
    
    mock_engine.quarantine.assert_called_once_with("3", reason="dedup", job_id="test")

def test_deletion_guard():
    # 4. Deletion guard bloqueia deletes quando flags não ativadas.
    from app.utils.deletion_guard import assert_memory_delete_allowed, DeletionBlockedError
    import os
    if "MEM0_ALLOW_MEMORY_DELETE" in os.environ:
        del os.environ["MEM0_ALLOW_MEMORY_DELETE"]
        
    with pytest.raises(DeletionBlockedError):
        assert_memory_delete_allowed()
