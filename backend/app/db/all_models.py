"""Single import point that pulls every SQLAlchemy model onto
`app.db.base.Base.metadata`.

Model registration in this app otherwise relies on transitive imports
(`import app.models` for the core catalog; each `app/modules/*/models.py`
imported via its router/service in `app/main.py` / `app/api/v1/router.py`).
That is fine for the running app, but Alembic's `env.py` needs *all*
metadata loaded up front, deterministically, without importing FastAPI
routers or spinning up services. This module is that list -- import it and
`Base.metadata` is complete.

Keep this in sync when a new `app/modules/<x>/models.py` is added (add one
line). `noqa: F401` throughout -- the import *is* the point.
"""

# -- Core catalog -----------------------------------------------------------
import app.models  # noqa: F401

# -- Feature module tables ------------------------------------------------
import app.modules.affiliate.models  # noqa: F401
import app.modules.ai.hook.models  # noqa: F401
import app.modules.ai.story.models  # noqa: F401
import app.modules.asset.models  # noqa: F401
import app.modules.batch.models  # noqa: F401
import app.modules.beat.models  # noqa: F401
import app.modules.competitor_intelligence.models  # noqa: F401
import app.modules.content_batch.models  # noqa: F401
import app.modules.content_strategy.models  # noqa: F401
import app.modules.factory.models  # noqa: F401
import app.modules.news.models  # noqa: F401
import app.modules.publishing.models  # noqa: F401
import app.modules.scene_cutter.models  # noqa: F401
import app.modules.series.models  # noqa: F401
import app.modules.story.models  # noqa: F401
import app.modules.video_composer.models  # noqa: F401

from app.db.base import Base  # noqa: E402

__all__ = ["Base"]
