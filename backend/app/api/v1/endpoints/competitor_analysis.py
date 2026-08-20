"""Task 11 -- Competitor Content Analyzer. Composition root: the one place
allowed to import app.modules.competitor_intelligence together with
app.modules.ai.llm_client, per app/modules/README.md (a module's own
service.py must never import another module directly -- see
competitor_intelligence/service.py's own docstring). Same
"module builds the prompt, composition root calls call_structured()" split
content_generate.py/beat_generate.py already use.

Never persists the competitor's original script/caption verbatim as an
"analysis" -- competitor_intelligence.service.parse_analysis_response only
accepts the 6 abstract pattern fields + a short reasoning string (see
that module's own ANALYSIS_SCHEMA), per this task's explicit "Do NOT copy
competitor scripts / extract abstract patterns only" instruction.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.concurrency import ai_generation_semaphore
from app.core.config import Settings, get_settings
from app.core.exceptions import ExternalServiceError, NotFoundError, ValidationError
from app.db.session import get_db
from app.modules.ai.llm_client import AIProviderError, AIProviderTimeoutError, call_structured, resolve_ai_credentials
from app.modules.competitor_intelligence import service
from app.modules.competitor_intelligence.schemas import CompetitorVideoOut

logger = logging.getLogger(__name__)
router = APIRouter()

MAX_TOKENS = 512


@router.post("/competitor-videos/{video_id}/analyze", response_model=CompetitorVideoOut)
def analyze_competitor_video(video_id: int, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    try:
        video = service.get_competitor_video(db, video_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    credentials = resolve_ai_credentials(settings)
    if credentials is None:
        raise HTTPException(status_code=400, detail="Chua cau hinh AI provider (Anthropic/OpenAI) trong Settings.")

    try:
        system_prompt, user_message = service.build_analysis_prompt(video)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        with ai_generation_semaphore:
            result = call_structured(
                credentials,
                system=system_prompt,
                user_message=user_message,
                output_schema=service.ANALYSIS_SCHEMA,
                max_tokens=MAX_TOKENS,
                schema_name="competitor_analysis",
            )
    except AIProviderTimeoutError as exc:
        raise HTTPException(status_code=504, detail=f"AI provider timeout: {exc}") from exc
    except AIProviderError as exc:
        raise HTTPException(status_code=502, detail=f"AI provider error: {exc}") from exc

    if result.refused:
        raise HTTPException(status_code=422, detail="AI provider tu choi phan tich video nay.")

    try:
        parsed = service.parse_analysis_response(result.text)
    except ExternalServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return service.persist_analysis(
        db, video, parsed, provider=result.provider, model=result.model,
        input_tokens=result.input_tokens, output_tokens=result.output_tokens,
    )
