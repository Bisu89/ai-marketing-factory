from datetime import datetime

from pydantic import BaseModel, ConfigDict, HttpUrl


class EnqueueRequest(BaseModel):
    url: HttpUrl


class DownloadJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    url: str
    status: str
    attempts: int
    error_message: str | None

    downloaded_bytes: int
    total_bytes: int | None
    progress_pct: float | None
    speed_bps: float | None
    eta_seconds: float | None

    created_at: datetime
    updated_at: datetime
