import json
import logging

from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import ExternalServiceError, NotFoundError, ValidationError
from app.models.video import Video
from app.modules.ai import history
from app.modules.ai.caption.models import CaptionJob, CaptionVersion
from app.modules.ai.llm_client import ANTHROPIC_MODEL, OPENAI_MODEL, AICredentials, AIProviderError, call_structured

logger = logging.getLogger(__name__)

MAX_TOKENS = 3072
VERSIONS_PER_GENERATION = 2

SYSTEM_PROMPT = (
    "Eres un experto en marketing de contenido en redes sociales, especializado en "
    "escribir captions y descripciones listas para publicar.\n\n"
    "Tu tarea: para un video, generar contenido de publicacion en ESPANOL basado "
    "unicamente en los metadatos proporcionados:\n"
    "- facebook_caption: caption para Facebook (2-4 frases, tono cercano).\n"
    "- instagram_caption: caption para Instagram (mas corto, con 3-5 hashtags relevantes "
    "al final).\n"
    "- youtube_description: descripcion para YouTube (mas larga, 3-5 frases, orientada a SEO).\n"
    "- pinned_comment: un comentario corto para fijar, que invite a interactuar (pregunta o "
    "CTA suave).\n"
    "- cta: una frase corta de llamada a la accion (ej: seguir, compartir, comentar, visitar "
    "enlace).\n\n"
    "No inventes hechos, cifras o eventos que no esten en los metadatos. Todo el texto en "
    "espanol.\n\n"
    f"Genera exactamente {VERSIONS_PER_GENERATION} variantes distintas, cada una con los "
    "5 campos."
)

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
                        "facebook_caption": {"type": "string"},
                        "instagram_caption": {"type": "string"},
                        "youtube_description": {"type": "string"},
                        "pinned_comment": {"type": "string"},
                        "cta": {"type": "string"},
                    },
                    "required": [
                        "facebook_caption",
                        "instagram_caption",
                        "youtube_description",
                        "pinned_comment",
                        "cta",
                    ],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["variants"],
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


class CaptionService:
    def __init__(self, db: Session, credentials: AICredentials | None):
        self.db = db
        self.credentials = credentials

    def _get_video(self, video_id: int) -> Video:
        video = self.db.get(Video, video_id)
        if video is None:
            raise NotFoundError("Video", video_id)
        return video

    def _get_job(self, job_id: int) -> CaptionJob:
        job = (
            self.db.query(CaptionJob)
            .options(selectinload(CaptionJob.versions))
            .filter(CaptionJob.id == job_id)
            .first()
        )
        if job is None:
            raise NotFoundError("Caption job", job_id)
        return job

    def list_jobs(self, video_id: int | None = None) -> list[CaptionJob]:
        query = self.db.query(CaptionJob).options(selectinload(CaptionJob.versions))
        if video_id is not None:
            query = query.filter(CaptionJob.video_id == video_id)
        return query.order_by(CaptionJob.id.desc()).all()

    def get_job(self, job_id: int) -> CaptionJob:
        return self._get_job(job_id)

    def delete_job(self, job_id: int) -> None:
        job = self._get_job(job_id)
        self.db.query(CaptionVersion).filter(CaptionVersion.caption_job_id == job.id).delete()
        self.db.delete(job)
        self.db.commit()

    def select_version(self, job_id: int, version_id: int) -> CaptionJob:
        job = self._get_job(job_id)
        target = next((v for v in job.versions if v.id == version_id), None)
        if target is None:
            raise NotFoundError("Caption version", version_id)
        for version in job.versions:
            version.is_selected = version.id == version_id
        self.db.commit()
        self.db.refresh(job)
        return job

    def generate(self, video_id: int) -> CaptionJob:
        video = self._get_video(video_id)

        if self.credentials is None:
            raise ValidationError(
                "Chua cau hinh AI provider. Vao Settings de chon provider va nhap key truoc khi tao caption."
            )

        user_message = _build_user_message(video)
        # A failed attempt still names which model it was attempting to use
        # (self.credentials is already known not to be None here) --
        # result.model isn't available yet in the AIProviderError branch
        # below, since the call itself is what failed.
        attempted_model = OPENAI_MODEL if self.credentials.provider == "openai" else ANTHROPIC_MODEL

        def _fail(message: str, latency_ms: int = 0, raw: str | None = None) -> None:
            job = CaptionJob(video_id=video_id, status="failed", error_message=message)
            self.db.add(job)
            history.record(
                self.db,
                kind="caption",
                job_id=None,
                video_id=video_id,
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
                output_schema=OUTPUT_SCHEMA,
                max_tokens=MAX_TOKENS,
                schema_name="caption_variants",
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

        job = CaptionJob(video_id=video_id, status="completed")
        self.db.add(job)
        self.db.flush()

        for index, variant in enumerate(variants[:VERSIONS_PER_GENERATION]):
            self.db.add(
                CaptionVersion(
                    caption_job_id=job.id,
                    version_index=index,
                    facebook_caption=variant["facebook_caption"],
                    instagram_caption=variant["instagram_caption"],
                    youtube_description=variant["youtube_description"],
                    pinned_comment=variant["pinned_comment"],
                    cta=variant["cta"],
                )
            )

        history.record(
            self.db,
            kind="caption",
            job_id=job.id,
            video_id=video_id,
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
        self.db.refresh(job)
        return job
