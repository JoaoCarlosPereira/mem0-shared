"""OpenMemory API application package."""

import datetime as _datetime

# ``datetime.UTC`` exists only on Python 3.11+; keep imports working on 3.10.
if not hasattr(_datetime, "UTC"):
    _datetime.UTC = _datetime.timezone.utc  # type: ignore[attr-defined]