"""Own APIRouter (OAuth, account, sync, competitor CRUD) -- everything here
is self-contained within this module (no other app/modules/* import
needed), per app/modules/README.md. The one endpoint that DOES need
app.modules.ai (POST /competitor-videos/{id}/analyze) deliberately lives
outside this file, in the composition root
app/api/v1/endpoints/competitor_analysis.py.
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.exceptions import ExternalServiceError, NotFoundError, ValidationError
from app.db.session import get_db
from app.modules.competitor_intelligence import service, sync_job, tiktok_client
from app.modules.competitor_intelligence.schemas import (
    CompetitorVideoCreateIn,
    CompetitorVideoOut,
    OAuthAuthorizeUrlOut,
    SyncTriggerOut,
    TikTokAccountOut,
    TikTokVideoOut,
)

router = APIRouter()


def _require_tiktok_credentials(settings: Settings) -> tuple[str, str]:
    if not settings.tiktok_client_key or not settings.tiktok_client_secret or not settings.tiktok_redirect_uri:
        raise HTTPException(
            status_code=400,
            detail="Chua cau hinh TikTok Client Key/Secret/Redirect URI trong Settings.",
        )
    return settings.tiktok_client_key, settings.tiktok_client_secret


# -- OAuth ----------------------------------------------------------------


@router.get("/tiktok/oauth/authorize-url", response_model=OAuthAuthorizeUrlOut)
def get_authorize_url(settings: Settings = Depends(get_settings)):
    client_key, _ = _require_tiktok_credentials(settings)
    pkce = tiktok_client.generate_pkce_pair()
    state = service.start_oauth_state(pkce.code_verifier)
    url = tiktok_client.build_authorize_url(client_key, settings.tiktok_redirect_uri, state, pkce.code_challenge)
    return OAuthAuthorizeUrlOut(authorize_url=url)


def _landing_page(title: str, message: str) -> HTMLResponse:
    return HTMLResponse(
        f"<!doctype html><html><body style='font-family:sans-serif;padding:40px;text-align:center'>"
        f"<h2>{title}</h2><p>{message}</p><p>Ban co the dong tab nay va quay lai ung dung.</p>"
        f"</body></html>"
    )


@router.get("/tiktok/oauth/callback")
def oauth_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    if error:
        return _landing_page("Ket noi TikTok that bai", error_description or error)
    if not code or not state:
        return _landing_page("Ket noi TikTok that bai", "Thieu code/state tu TikTok.")

    code_verifier = service.pop_oauth_state(state)
    if code_verifier is None:
        return _landing_page("Ket noi TikTok that bai", "Phien OAuth khong hop le hoac da het han -- thu lai.")

    client_key, client_secret = _require_tiktok_credentials(settings)
    try:
        token_resp = tiktok_client.exchange_code_for_token(
            client_key, client_secret, code, settings.tiktok_redirect_uri, code_verifier
        )
        profile = tiktok_client.fetch_user_info(token_resp["access_token"])
        service.upsert_account_from_token(db, token_resp, profile)
    except ExternalServiceError as exc:
        return _landing_page("Ket noi TikTok that bai", str(exc))

    return _landing_page("Da ket noi TikTok thanh cong", "Tai khoan TikTok da duoc lien ket voi ung dung.")


# -- Account ----------------------------------------------------------------


@router.get("/tiktok/account", response_model=TikTokAccountOut | None)
def get_account(db: Session = Depends(get_db)):
    return service.get_active_account(db)


@router.delete("/tiktok/account")
def disconnect_account(db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    account = service.get_active_account(db)
    if account is None:
        raise HTTPException(status_code=404, detail="Chua co tai khoan TikTok nao duoc ket noi.")
    client_key = settings.tiktok_client_key or ""
    client_secret = settings.tiktok_client_secret or ""
    service.disconnect_account(db, account, client_key, client_secret)
    return {"disconnected": True}


# -- Sync ---------------------------------------------------------------


@router.post("/tiktok/sync", response_model=SyncTriggerOut)
def trigger_sync(db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    account = service.get_active_account(db)
    if account is None:
        raise HTTPException(status_code=404, detail="Chua co tai khoan TikTok nao duoc ket noi.")
    client_key, client_secret = _require_tiktok_credentials(settings)
    started = sync_job.start_sync_in_background(account.id, client_key, client_secret)
    return SyncTriggerOut(started=started, already_syncing=not started)


@router.get("/tiktok/videos", response_model=list[TikTokVideoOut])
def get_videos(db: Session = Depends(get_db)):
    account = service.get_active_account(db)
    if account is None:
        return []
    return service.list_videos(db, account.id)


# -- Competitor videos --------------------------------------------------


@router.post("/competitor-videos", response_model=CompetitorVideoOut)
def create_competitor_video(payload: CompetitorVideoCreateIn, db: Session = Depends(get_db)):
    try:
        return service.create_competitor_video(
            db, payload.source_url, payload.competitor_handle, payload.title_caption, payload.duration_sec, payload.notes
        )
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/competitor-videos", response_model=list[CompetitorVideoOut])
def list_competitor_videos(db: Session = Depends(get_db)):
    return service.list_competitor_videos(db)


@router.get("/competitor-videos/{video_id}", response_model=CompetitorVideoOut)
def get_competitor_video(video_id: int, db: Session = Depends(get_db)):
    try:
        return service.get_competitor_video(db, video_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/competitor-videos/{video_id}")
def delete_competitor_video(video_id: int, db: Session = Depends(get_db)):
    try:
        video = service.get_competitor_video(db, video_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    service.delete_competitor_video(db, video)
    return {"deleted": True}
