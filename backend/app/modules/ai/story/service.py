import json
import logging

from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import ExternalServiceError, NotFoundError, ValidationError
from app.models.video import Video
from app.modules.ai import history
from app.modules.ai.llm_client import ANTHROPIC_MODEL, OPENAI_MODEL, AICredentials, AIProviderError, call_structured
from app.modules.ai.story.models import StoryJob, StoryVersion

logger = logging.getLogger(__name__)

MAX_TOKENS = 4096
VERSIONS_PER_GENERATION = 2

# Tone description per style preset. Written in English -- this only feeds
# the *instructions* to Claude, not the generated script, so it doesn't need
# to match STORY_LANGUAGES. The enum values persisted on StoryJob.style stay
# the stable English keys.
STYLE_DESCRIPTIONS = {
    "emotional": "emotional and moving, connecting with the viewer's feelings",
    "humorous": "humorous and fun, light and entertaining",
    "inspirational": "inspirational and motivating, encouraging action or reflection",
    "dramatic": "dramatic and intense, with narrative tension",
    "educational": "educational and informative, clear and instructive",
    "sales": "persuasive sales/marketing copy, geared toward conversion",
}

# Display name for the target script language, used both in the prompt and
# to remind the model not to mix languages. Keys are STORY_LANGUAGES.
LANGUAGE_NAMES = {
    "english": "English",
    "spanish": "Spanish",
    "vietnamese": "Vietnamese",
}

OUTPUT_SCHEMA = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "properties": {
            "variants": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "script_text": {"type": "string"},
                    },
                    "required": ["title", "script_text"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["variants"],
        "additionalProperties": False,
    },
}


def _build_system_prompt(style: str, language: str) -> str:
    tone = STYLE_DESCRIPTIONS[style]
    language_name = LANGUAGE_NAMES[language]
    return (
        "You are an expert scriptwriter for social-media video content marketing.\n\n"
        f"Your task: write a video narration script entirely in {language_name}, based only on "
        "the metadata the user provides. The script must:\n"
        "- Run 30-90 seconds when read aloud (roughly 75-200 words at a natural pace).\n"
        f"- Use a {tone} tone.\n"
        "- Stick only to the facts and tone suggested by the provided metadata -- do not invent "
        "facts, figures, names, or events that aren't in the metadata.\n"
        "- Be written to be read aloud (narration), not as on-screen text.\n"
        f"- Be entirely in {language_name}, with no mixing of languages.\n\n"
        f"Generate exactly {VERSIONS_PER_GENERATION} distinct variants of the script, each with "
        "a short title and the script text."
    )


def _build_user_message(video: Video) -> str:
    tag_names = ", ".join(t.name for t in video.tags) if video.tags else "N/A"
    return (
        f"Video title: {video.title}\n"
        f"Topic: {video.category_name or 'N/A'}\n"
        f"Emotion: {video.emotion_name or 'N/A'}\n"
        f"Tags: {tag_names}\n"
        f"Notes: {video.notes or 'N/A'}"
    )


class StoryService:
    def __init__(self, db: Session, credentials: AICredentials | None):
        self.db = db
        self.credentials = credentials

    def _get_video(self, video_id: int) -> Video:
        video = self.db.get(Video, video_id)
        if video is None:
            raise NotFoundError("Video", video_id)
        return video

    def _get_job(self, job_id: int) -> StoryJob:
        job = (
            self.db.query(StoryJob)
            .options(selectinload(StoryJob.versions))
            .filter(StoryJob.id == job_id)
            .first()
        )
        if job is None:
            raise NotFoundError("Story job", job_id)
        return job

    def list_jobs(self, video_id: int | None = None) -> list[StoryJob]:
        query = self.db.query(StoryJob).options(selectinload(StoryJob.versions))
        if video_id is not None:
            query = query.filter(StoryJob.video_id == video_id)
        return query.order_by(StoryJob.id.desc()).all()

    def get_job(self, job_id: int) -> StoryJob:
        return self._get_job(job_id)

    def delete_job(self, job_id: int) -> None:
        job = self._get_job(job_id)
        self.db.query(StoryVersion).filter(StoryVersion.story_job_id == job.id).delete()
        self.db.delete(job)
        self.db.commit()

    def select_version(self, job_id: int, version_id: int) -> StoryJob:
        job = self._get_job(job_id)
        target = next((v for v in job.versions if v.id == version_id), None)
        if target is None:
            raise NotFoundError("Story version", version_id)
        for version in job.versions:
            version.is_selected = version.id == version_id
        self.db.commit()
        self.db.refresh(job)
        return job

    def generate(self, video_id: int, style: str, language: str = "english") -> StoryJob:
        video = self._get_video(video_id)

        if self.credentials is None:
            raise ValidationError(
                "Chua cau hinh AI provider. Vao Settings de chon provider va nhap key truoc khi tao story."
            )

        system_prompt = _build_system_prompt(style, language)
        user_message = _build_user_message(video)
        attempted_model = OPENAI_MODEL if self.credentials.provider == "openai" else ANTHROPIC_MODEL

        def _fail(message: str, latency_ms: int = 0, raw: str | None = None) -> None:
            job = StoryJob(video_id=video_id, style=style, language=language, status="failed", error_message=message)
            self.db.add(job)
            history.record(
                self.db,
                kind="story",
                job_id=None,
                video_id=video_id,
                model=attempted_model,
                provider=self.credentials.provider,
                prompt_system=system_prompt,
                prompt_user=user_message,
                response_raw=raw,
                latency_ms=latency_ms,
                error_message=message,
            )
            self.db.commit()

        try:
            result = call_structured(
                self.credentials,
                system=system_prompt,
                user_message=user_message,
                output_schema=OUTPUT_SCHEMA,
                max_tokens=MAX_TOKENS,
                schema_name="story_variants",
            )
        except AIProviderError as exc:
            _fail(f"Goi AI provider that bai: {exc}")
            raise ExternalServiceError(f"Goi AI provider that bai: {exc}") from exc

        if result.refused:
            message = "Yeu cau bi tu choi boi bo loc an toan cua model."
            _fail(message, result.latency_ms)
            raise ExternalServiceError(message)

        if not result.text:
            message = "Model khong tra ve noi dung van ban."
            _fail(message, result.latency_ms)
            raise ExternalServiceError(message)

        try:
            parsed = json.loads(result.text)
            variants = parsed["variants"]
            if len(variants) < VERSIONS_PER_GENERATION:
                raise ValueError(f"Expected {VERSIONS_PER_GENERATION} variants, got {len(variants)}")
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            message = f"Khong doc duoc ket qua tra ve tu model: {exc}"
            _fail(message, result.latency_ms, raw=result.text)
            raise ExternalServiceError(message) from exc

        job = StoryJob(video_id=video_id, style=style, language=language, status="completed")
        self.db.add(job)
        self.db.flush()

        for index, variant in enumerate(variants[:VERSIONS_PER_GENERATION]):
            self.db.add(
                StoryVersion(
                    story_job_id=job.id,
                    version_index=index,
                    title=variant["title"],
                    script_text=variant["script_text"],
                )
            )

        history.record(
            self.db,
            kind="story",
            job_id=job.id,
            video_id=video_id,
            model=result.model,
            provider=result.provider,
            prompt_system=system_prompt,
            prompt_user=user_message,
            response_raw=result.text,
            latency_ms=result.latency_ms,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
        )

        self.db.commit()
        self.db.refresh(job)
        return job
