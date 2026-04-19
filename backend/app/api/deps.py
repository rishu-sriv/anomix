"""
Shared FastAPI dependencies.  Import these in route modules via:

    from app.api.deps import get_db, get_redis
"""

from app.core.database import get_db  # noqa: F401  (re-exported)
from app.core.redis import get_redis  # noqa: F401  (re-exported)

__all__ = ["get_db", "get_redis"]
