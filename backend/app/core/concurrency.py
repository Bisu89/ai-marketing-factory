"""Process-wide concurrency limiters for external resources shared by more
than one composition root (Task 20 -- see
docs/features/46-factory-batch-engine.md). Lives in app.core (not a domain
module) so both app/api/v1/endpoints/batch_render.py's own batch
beat-generation and app/api/v1/endpoints/factory_pipeline.py's per-project
Beat stage can import the *same* limiter instead of each bounding their own
concurrent AI calls independently -- two independently-correct local bounds
would still let combined concurrency exceed settings.max_concurrent_ai_generation
if both flows happened to run at once.

Not a generic resource-scheduler (see Task 20 section 13/66's "do not build
a generic scheduler") -- one named semaphore for one named resource class
(AI calls), sized once from Settings at import time, the same "compute once
at import time from get_settings()" convention app/db/session.py already
uses for its own engine.
"""

import threading

from app.core.config import get_settings

# Anthropic's own client is not otherwise concurrency-limited by this
# codebase (app.modules.ai.claude_client.call_structured makes one
# synchronous request per call) -- this is the one place that caps how many
# such requests may be in flight across the whole process at once.
ai_generation_semaphore = threading.Semaphore(max(1, get_settings().max_concurrent_ai_generation))
