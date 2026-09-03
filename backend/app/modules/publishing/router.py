"""YouTube channel connect (OAuth) + channel/upload CRUD. The actual
upload (which needs app.modules.beat + app.modules.video_composer to
resolve a project's final.mp4) lives in the composition root
app/api/v1/endpoints/publish_video.py.
"""

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse

from app.core.config import Settings, get_settings
from app.core.exceptions import ValidationError
from app.modules.publishing import service
from app.modules.publishing.schemas import (
    OAuthAuthorizeUrlOut,
    YouTubeChannelOut,
    YouTubeChannelUpdateIn,
    YouTubeUploadJobOut,
)

router = APIRouter()


def _channel_out(channel, counts: dict[int, int] | None = None) -> YouTubeChannelOut:
    out = YouTubeChannelOut.model_validate(channel)
    if counts is not None:
        out.upload_count = counts.get(channel.id, 0)
    return out


def _upload_out(job) -> YouTubeUploadJobOut:
    out = YouTubeUploadJobOut.model_validate(job)
    out.channel_title = job.channel.title if job.channel is not None else None
    out.watch_url = job.watch_url
    return out


def _landing(title: str, message: str) -> HTMLResponse:
    return HTMLResponse(
        "<!doctype html><html><body style='font-family:sans-serif;padding:40px;text-align:center'>"
        f"<h2>{title}</h2><p>{message}</p><p>Bạn có thể đóng tab này và quay lại ứng dụng.</p>"
        "</body></html>"
    )


# -- OAuth ----------------------------------------------------------


@router.get("/publishing/youtube/oauth/authorize-url", response_model=OAuthAuthorizeUrlOut)
def get_authorize_url(settings: Settings = Depends(get_settings)):
    return OAuthAuthorizeUrlOut(authorize_url=service.build_authorize_url(settings))


@router.get("/publishing/youtube/oauth/callback")
def oauth_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    settings: Settings = Depends(get_settings),
):
    if error:
        return _landing("Kết nối YouTube thất bại", error)
    if not code or not state:
        return _landing("Kết nối YouTube thất bại", "Thiếu code/state từ Google.")
    if not service.consume_oauth_state(state):
        return _landing("Kết nối YouTube thất bại", "Phiên OAuth không hợp lệ hoặc đã hết hạn — thử lại.")
    try:
        channel = service.connect_channel_from_code(settings, code)
    except (ValidationError, Exception) as exc:  # noqa: BLE001 -- always render a page, never a 500 in the browser tab
        return _landing("Kết nối YouTube thất bại", str(exc))
    return _landing("Đã kết nối YouTube", f'Kênh "{channel.title}" đã được liên kết.')


# -- Channels --------------------------------------------------


@router.get("/publishing/youtube/channels", response_model=list[YouTubeChannelOut])
def list_channels():
    counts = service.completed_upload_counts()
    return [_channel_out(c, counts) for c in service.list_channels()]


@router.patch("/publishing/youtube/channels/{channel_pk}", response_model=YouTubeChannelOut)
def update_channel(channel_pk: int, payload: YouTubeChannelUpdateIn):
    return _channel_out(service.update_channel(channel_pk, enabled=payload.enabled))


@router.delete("/publishing/youtube/channels/{channel_pk}", status_code=204)
def disconnect_channel(channel_pk: int):
    service.disconnect_channel(channel_pk)


# -- Uploads (read-only here; POST is in the composition root) --------


@router.get("/publishing/youtube/uploads", response_model=list[YouTubeUploadJobOut])
def list_uploads():
    return [_upload_out(j) for j in service.list_uploads()]


@router.get("/publishing/youtube/uploads/{job_id}", response_model=YouTubeUploadJobOut)
def get_upload(job_id: int):
    return _upload_out(service.get_upload(job_id))
