"""Task 05 -- AI quality scoring for a StoryVersion, run before the
(expensive) video-generation pipeline to decide whether a script is worth
producing. Lives inside app/modules/ai/story/ (not a new module) since it
only ever reads/writes this module's own StoryVersion -- no cross-module
import, no composition root needed.

Cost optimization: the prompt sends only the version's own title/script
text (see _build_user_message) -- never the Video's title/topic/emotion/
tags/notes that StoryService.generate() itself sends, since none of that
changes how good *this specific script* reads. max_tokens is 512 (the
output is 9 small integers + a short reasoning + a few short suggestions),
a fraction of story generation's own 4096. No cheaper model was
substituted for the configured one: app.modules.ai.llm_client hardcodes
exactly one model per provider today (ANTHROPIC_MODEL/OPENAI_MODEL), with
no second, cheaper tier wired into call_structured() to select from --
and OPENAI_MODEL was only just changed by explicit user request (see that
file's own comment), so silently reintroducing a cheaper model here would
second-guess a decision made outside this task's scope. If a real cheap
tier is added to llm_client.py later, this is the one call site that
should switch to it.

Does not create a new table -- see StoryVersion's own docstring
(app/modules/ai/story/models.py) for why the score lives directly on it.
"""

import json
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.exceptions import ExternalServiceError, NotFoundError, ValidationError
from app.modules.ai import history
from app.modules.ai.llm_client import ANTHROPIC_MODEL, OPENAI_MODEL, AICredentials, AIProviderError, call_structured
from app.modules.ai.story.models import QUALITY_PASS_THRESHOLD, QUALITY_SCORE_DIMENSIONS, StoryJob, StoryVersion

logger = logging.getLogger(__name__)

MAX_TOKENS = 512

SYSTEM_PROMPT = (
    "You are a strict, realistic quality evaluator for short-form social video scripts, judging whether a "
    "script is worth the cost of producing into video before that spend happens.\n\n"
    f"Score the script on exactly these {len(QUALITY_SCORE_DIMENSIONS)} dimensions, each an integer 0-10 "
    "(0 = completely absent/fails, 10 = exceptional): "
    f"{', '.join(QUALITY_SCORE_DIMENSIONS)}.\n"
    "Be strict: most real scripts should NOT score near-10 on every dimension -- reserve 9-10 for genuinely "
    "exceptional work.\n"
    "Also give ONE short overall reasoning (1-3 sentences) and 1-4 short, concrete improvement suggestions."
)


def _output_schema() -> dict:
    return {
        "type": "json_schema",
        "schema": {
            "type": "object",
            "properties": {
                "scores": {
                    "type": "object",
                    "properties": {dim: {"type": "integer"} for dim in QUALITY_SCORE_DIMENSIONS},
                    "required": list(QUALITY_SCORE_DIMENSIONS),
                    "additionalProperties": False,
                },
                "reasoning": {"type": "string"},
                "improvement_suggestions": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["scores", "reasoning", "improvement_suggestions"],
            "additionalProperties": False,
        },
    }


def _build_user_message(version: StoryVersion) -> str:
    return f"Title: {version.title}\n\nScript:\n{version.script_text}"


class StoryQualityService:
    def __init__(self, db: Session, credentials: AICredentials | None):
        self.db = db
        self.credentials = credentials

    def _get_version(self, version_id: int) -> StoryVersion:
        version = self.db.get(StoryVersion, version_id)
        if version is None:
            raise NotFoundError("Story version", version_id)
        return version

    def score(self, version_id: int) -> StoryVersion:
        """Scores one StoryVersion and overwrites its own quality_* columns
        on success. A failure (provider error/timeout, safety refusal,
        malformed JSON, out-of-range score) is recorded to
        ai_generation_history for audit but never touches
        quality_score/quality_recommendation/quality_breakdown -- a
        version that was already scored keeps its last valid verdict
        rather than silently losing it to a transient failure. Calling
        this again (after whatever caused a failure is resolved, or just
        to re-check after editing) fully replaces the prior verdict --
        there is no history of past scores kept, by design (see
        StoryVersion's own docstring for why).
        """
        version = self._get_version(version_id)
        job = self.db.get(StoryJob, version.story_job_id)
        if job is None:
            raise NotFoundError("Story job", version.story_job_id)

        if self.credentials is None:
            raise ValidationError(
                "Chua cau hinh AI provider. Vao Settings de chon provider va nhap key truoc khi cham diem."
            )

        user_message = _build_user_message(version)
        attempted_model = OPENAI_MODEL if self.credentials.provider == "openai" else ANTHROPIC_MODEL

        def _record_failure(message: str, latency_ms: int = 0, raw: str | None = None) -> None:
            history.record(
                self.db,
                kind="quality_score",
                job_id=version.id,
                video_id=job.video_id,
                model=attempted_model,
                provider=self.credentials.provider,
                prompt_system=SYSTEM_PROMPT,
                prompt_user=user_message,
                response_raw=raw,
                latency_ms=latency_ms,
                error_message=message,
            )
            self.db.commit()

        try:
            result = call_structured(
                self.credentials,
                system=SYSTEM_PROMPT,
                user_message=user_message,
                output_schema=_output_schema(),
                max_tokens=MAX_TOKENS,
                schema_name="quality_score",
            )
        except AIProviderError as exc:
            _record_failure(f"Goi AI provider that bai: {exc}")
            raise ExternalServiceError(f"Goi AI provider that bai: {exc}") from exc

        if result.refused:
            message = "Yeu cau bi tu choi boi bo loc an toan cua model."
            _record_failure(message, result.latency_ms)
            raise ExternalServiceError(message)

        if not result.text:
            message = "Model khong tra ve noi dung van ban."
            _record_failure(message, result.latency_ms)
            raise ExternalServiceError(message)

        try:
            parsed = json.loads(result.text)
            scores = {dim: int(parsed["scores"][dim]) for dim in QUALITY_SCORE_DIMENSIONS}
            for dim, value in scores.items():
                if not (0 <= value <= 10):
                    raise ValueError(f"{dim} score {value} out of range 0-10")
            reasoning = str(parsed["reasoning"])
            suggestions = [str(s) for s in parsed["improvement_suggestions"]]
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            message = f"Khong doc duoc ket qua tra ve tu model: {exc}"
            _record_failure(message, result.latency_ms, raw=result.text)
            raise ExternalServiceError(message) from exc

        total = sum(scores.values())
        recommendation = "pass" if total >= QUALITY_PASS_THRESHOLD else "fail"

        version.quality_score = total
        version.quality_recommendation = recommendation
        version.quality_breakdown = {
            "scores": scores,
            "reasoning": reasoning,
            "improvement_suggestions": suggestions,
            "provider": result.provider,
            "model": result.model,
        }
        version.quality_scored_at = datetime.now(timezone.utc)

        history.record(
            self.db,
            kind="quality_score",
            job_id=version.id,
            video_id=job.video_id,
            model=result.model,
            provider=result.provider,
            prompt_system=SYSTEM_PROMPT,
            prompt_user=user_message,
            response_raw=result.text,
            latency_ms=result.latency_ms,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
        )

        self.db.commit()
        self.db.refresh(version)
        return version
