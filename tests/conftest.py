import pytest


@pytest.fixture(autouse=True)
def _clear_mem0_logger_ctx():
    """Clear op_logger context after every test to avoid cross-test pollution."""
    from mem0.utils.logger import clear_op_ctx

    clear_op_ctx()
