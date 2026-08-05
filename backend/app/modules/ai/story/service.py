import json
import logging

import anthropic
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import ExternalServiceError, NotFoundError, ValidationError
from app.models.video import Video
from app.modules.ai import history
from app.modules.ai.claude_client import MODEL, call_structured
from app.modules.ai.story.models import StoryJob, StoryVersion

logger = logging.getLogger(__name__)

MAX_TOKENS = 4096
VERSIONS_PER_GENERATION = 2

# Prompt-only descriptions of each style preset, in Spanish, so the model's
# instructions and its output are both in the target language. The enum
# values persisted on StoryJob.style stay the stable English keys.
STYLE_DESCRIPTIONS = {
    "emotional": "emocional y conmovedor, que conecte con los sentimientos del espectador",
    "humorous": "humoristico y divertido, ligero y entretenido",
    "inspirational": "inspirador y motivador, que anime a la accion o a la reflexion",
    "dramatic": "dramatico e intenso, con tension narrativa",
    "educational": "educativo e informativo, claro y didactico",
    "sales": "persuasivo de venta/marketing, orientado a la conversion",
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


def _build_system_prompt(style: str) -> str:
    tone = STYLE_DESCRIPTIONS[style]
    return (
        "Eres un guionista experto en marketing de contenido en video para redes sociales, "
        "especializado en narraciones en espanol.\n\n"
        "Tu tarea: escribir un guion de narracion en ESPANOL para un video, basado unicamente "
        "en los metadatos que te proporcione el usuario. El guion debe:\n"
        "- Tener una duracion de narracion hablada de entre 30 y 90 segundos "
        "(aproximadamente 75-200 palabras a un ritmo natural).\n"
        f"- Usar un tono {tone}.\n"
        "- Basarse solo en los hechos y el tono sugeridos por los metadatos proporcionados -- "
        "no inventes hechos, cifras, nombres o eventos que no esten en los metadatos.\n"
        "- Estar escrito para ser leido en voz alta (narracion), no como texto para pantalla.\n"
        "- Estar completamente en espanol, sin mezclar idiomas.\n\n"
        f"Genera exactamente {VERSIONS_PER_GENERATION} variantes distintas del guion, cada una "
        "con un titulo corto y el texto del guion."
    )


def _build_user_message(video: Video) -> str:
    tag_names = ", ".join(t.name for t in video.tags) if video.tags else "N/A"
    return (
        f"Titulo del video: {video.title}\n"
        f"Tema: {video.category_name or 'N/A'}\n"
        f"Emocion: {video.emotion_name or 'N/A'}\n"
        f"Etiquetas: {tag_names}\n"
        f"Notas: {video.notes or 'N/A'}"
    )


class StoryService:
    def __init__(self, db: Session, api_key: str | None):
        self.db = db
        self.api_key = api_key

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

    def generate(self, video_id: int, style: str) -> StoryJob:
        video = self._get_video(video_id)

        if not self.api_key:
            raise ValidationError(
                "Chua cau hinh Anthropic API key. Vao Settings de nhap key truoc khi tao story."
            )

        system_prompt = _build_system_prompt(style)
        user_message = _build_user_message(video)

        def _fail(message: str, latency_ms: int = 0, raw: str | None = None) -> None:
            job = StoryJob(video_id=video_id, style=style, status="failed", error_message=message)
            self.db.add(job)
            history.record(
                self.db,
                kind="story",
                job_id=None,
                video_id=video_id,
                model=MODEL,
                prompt_system=system_prompt,
                prompt_user=user_message,
                response_raw=raw,
                latency_ms=latency_ms,
                error_message=message,
            )
            self.db.commit()

        try:
            result = call_structured(
                self.api_key,
                system=system_prompt,
                user_message=user_message,
                output_schema=OUTPUT_SCHEMA,
                max_tokens=MAX_TOKENS,
            )
        except anthropic.APIError as exc:
            _fail(f"Goi Anthropic API that bai: {exc}")
            raise ExternalServiceError(f"Goi Anthropic API that bai: {exc}") from exc

        response = result.response

        if response.stop_reason == "refusal":
            message = "Yeu cau bi tu choi boi bo loc an toan cua model."
            _fail(message, result.latency_ms)
            raise ExternalServiceError(message)

        text_block = next((b for b in response.content if b.type == "text"), None)
        if text_block is None:
            message = "Model khong tra ve noi dung van ban."
            _fail(message, result.latency_ms)
            raise ExternalServiceError(message)

        try:
            parsed = json.loads(text_block.text)
            variants = parsed["variants"]
            if len(variants) < VERSIONS_PER_GENERATION:
                raise ValueError(f"Expected {VERSIONS_PER_GENERATION} variants, got {len(variants)}")
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            message = f"Khong doc duoc ket qua tra ve tu model: {exc}"
            _fail(message, result.latency_ms, raw=text_block.text)
            raise ExternalServiceError(message) from exc

        job = StoryJob(video_id=video_id, style=style, status="completed")
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
            model=MODEL,
            prompt_system=system_prompt,
            prompt_user=user_message,
            response_raw=text_block.text,
            latency_ms=result.latency_ms,
            input_tokens=getattr(response.usage, "input_tokens", None),
            output_tokens=getattr(response.usage, "output_tokens", None),
        )

        self.db.commit()
        self.db.refresh(job)
        return job
