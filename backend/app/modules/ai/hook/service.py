import json
import logging

import anthropic
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import ExternalServiceError, NotFoundError, ValidationError
from app.models.video import Video
from app.modules.ai import history
from app.modules.ai.claude_client import MODEL, call_structured
from app.modules.ai.hook.models import HookJob, HookVersion

logger = logging.getLogger(__name__)

MAX_TOKENS = 2048
MIN_HOOKS = 5
MAX_HOOKS = 10

SYSTEM_PROMPT = (
    "Eres un experto en marketing de contenido en video para redes sociales, "
    "especializado en escribir 'hooks' (las primeras 1-2 frases que enganchan al "
    "espectador en los primeros segundos).\n\n"
    f"Tu tarea: generar entre {MIN_HOOKS} y {MAX_HOOKS} hooks distintos en ESPANOL para "
    "un video, basados unicamente en los metadatos proporcionados. Cada hook debe:\n"
    "- Ser una frase corta (maximo ~15 palabras), lista para usarse como texto en pantalla "
    "o primera linea de narracion.\n"
    "- Generar curiosidad, sorpresa o conexion emocional inmediata.\n"
    "- Basarse solo en los hechos sugeridos por los metadatos -- no inventes hechos, cifras "
    "o eventos que no esten en los metadatos.\n"
    "- Estar completamente en espanol."
)

OUTPUT_SCHEMA = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "properties": {
            "hooks": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["hooks"],
        "additionalProperties": False,
    },
}


def _build_user_message(video: Video) -> str:
    tag_names = ", ".join(t.name for t in video.tags) if video.tags else "N/A"
    return (
        f"Titulo del video: {video.title}\n"
        f"Tema: {video.category_name or 'N/A'}\n"
        f"Emocion: {video.emotion_name or 'N/A'}\n"
        f"Etiquetas: {tag_names}\n"
        f"Notas: {video.notes or 'N/A'}"
    )


class HookService:
    def __init__(self, db: Session, api_key: str | None):
        self.db = db
        self.api_key = api_key

    def _get_video(self, video_id: int) -> Video:
        video = self.db.get(Video, video_id)
        if video is None:
            raise NotFoundError("Video", video_id)
        return video

    def _get_job(self, job_id: int) -> HookJob:
        job = (
            self.db.query(HookJob)
            .options(selectinload(HookJob.hooks))
            .filter(HookJob.id == job_id)
            .first()
        )
        if job is None:
            raise NotFoundError("Hook job", job_id)
        return job

    def list_jobs(self, video_id: int | None = None) -> list[HookJob]:
        query = self.db.query(HookJob).options(selectinload(HookJob.hooks))
        if video_id is not None:
            query = query.filter(HookJob.video_id == video_id)
        return query.order_by(HookJob.id.desc()).all()

    def get_job(self, job_id: int) -> HookJob:
        return self._get_job(job_id)

    def delete_job(self, job_id: int) -> None:
        job = self._get_job(job_id)
        self.db.query(HookVersion).filter(HookVersion.hook_job_id == job.id).delete()
        self.db.delete(job)
        self.db.commit()

    def toggle_favorite(self, job_id: int, hook_id: int) -> HookJob:
        job = self._get_job(job_id)
        target = next((h for h in job.hooks if h.id == hook_id), None)
        if target is None:
            raise NotFoundError("Hook", hook_id)
        target.is_favorite = not target.is_favorite
        self.db.commit()
        self.db.refresh(job)
        return job

    def generate(self, video_id: int) -> HookJob:
        video = self._get_video(video_id)

        if not self.api_key:
            raise ValidationError(
                "Chua cau hinh Anthropic API key. Vao Settings de nhap key truoc khi tao hook."
            )

        user_message = _build_user_message(video)

        def _fail(message: str, latency_ms: int = 0, raw: str | None = None) -> None:
            job = HookJob(video_id=video_id, status="failed", error_message=message)
            self.db.add(job)
            history.record(
                self.db,
                kind="hook",
                job_id=None,
                video_id=video_id,
                model=MODEL,
                prompt_system=SYSTEM_PROMPT,
                prompt_user=user_message,
                response_raw=raw,
                latency_ms=latency_ms,
                error_message=message,
            )
            self.db.commit()

        try:
            result = call_structured(
                self.api_key,
                system=SYSTEM_PROMPT,
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
            hooks_list = parsed["hooks"]
            if len(hooks_list) < MIN_HOOKS:
                raise ValueError(f"Expected at least {MIN_HOOKS} hooks, got {len(hooks_list)}")
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            message = f"Khong doc duoc ket qua tra ve tu model: {exc}"
            _fail(message, result.latency_ms, raw=text_block.text)
            raise ExternalServiceError(message) from exc

        job = HookJob(video_id=video_id, status="completed")
        self.db.add(job)
        self.db.flush()

        for index, hook_text in enumerate(hooks_list[:MAX_HOOKS]):
            self.db.add(HookVersion(hook_job_id=job.id, hook_index=index, text=hook_text))

        history.record(
            self.db,
            kind="hook",
            job_id=job.id,
            video_id=video_id,
            model=MODEL,
            prompt_system=SYSTEM_PROMPT,
            prompt_user=user_message,
            response_raw=text_block.text,
            latency_ms=result.latency_ms,
            input_tokens=getattr(response.usage, "input_tokens", None),
            output_tokens=getattr(response.usage, "output_tokens", None),
        )

        self.db.commit()
        self.db.refresh(job)
        return job
