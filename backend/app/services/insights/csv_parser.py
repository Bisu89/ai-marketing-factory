import csv
import io
from datetime import datetime

# Maps the exact Vietnamese column headers Meta Business Suite exports (the
# "Content" / "Nội dung" report) to our internal snake_case field names.
_HEADER_MAP = {
    "ID bài viết": "post_id",
    "ID Trang": "page_id",
    "Tên Trang": "page_name",
    "Tiêu đề": "title",
    "Thời lượng (giây)": "duration_sec",
    "Thời gian đăng": "posted_at",
    "Liên kết vĩnh viễn": "permalink",
    "Loại bài viết": "post_type",
    "Bình luận về dữ liệu": "data_comment",
    "Ngày": "period_label",
    "Số Giây xem trung bình": "avg_seconds_viewed",
    "Bình luận": "comments",
    "Lượt phân phối": "distribution",
    "Lượt hiển thị": "impressions",
    "Lượt tương tác": "interactions",
    "Số người theo dõi thực": "real_followers",
    "Cảm xúc": "reactions",
    "Lượt lưu": "saves",
    "Lượt chia sẻ": "shares",
    "Số Giây xem": "total_seconds_viewed",
    "Người xem": "viewers",
    "Lượt xem": "views",
}

# Columns kept as plain strings (id-like, free text, or non-numeric formats
# such as "-2.7x" for distribution / "Trọn Đời" for period_label) -- anything
# else in _HEADER_MAP is coerced to a number.
_STRING_FIELDS = {
    "post_id",
    "page_id",
    "page_name",
    "title",
    "permalink",
    "post_type",
    "data_comment",
    "period_label",
    "distribution",
}
_FLOAT_FIELDS = {"duration_sec", "avg_seconds_viewed", "total_seconds_viewed"}
# Everything else in _HEADER_MAP.values() not listed above is an int field.

_REQUIRED_HEADERS = {"ID bài viết", "Tên Trang", "Lượt xem"}


class InsightCsvError(Exception):
    """Raised when the uploaded file isn't a recognizable Meta Business Suite export."""


def _looks_mojibake(text: str) -> bool:
    return "Ã" in text or "â€" in text or "�" in text


def _repair_mojibake(text: str) -> str:
    try:
        repaired = text.encode("latin-1").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        return text
    return repaired if not _looks_mojibake(repaired) else text


def decode_csv_bytes(raw: bytes) -> str:
    text = raw.decode("utf-8-sig", errors="replace")
    if _looks_mojibake(text):
        text = _repair_mojibake(text)
    # A mojibake'd BOM (bytes EF BB BF misread as the 3 chars "ï»¿") round-trips
    # back into a literal U+FEFF character rather than being stripped, since
    # only utf-8-sig (not a plain utf-8 decode) strips BOM bytes -- and by the
    # time the repair runs, decoding already happened.
    return text.lstrip("﻿")


def _to_int(value: str) -> int:
    try:
        return int(float(value.strip()))
    except (ValueError, AttributeError):
        return 0


def _to_float(value: str) -> float:
    try:
        return float(value.strip())
    except (ValueError, AttributeError):
        return 0.0


def _to_datetime(value: str) -> datetime | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, "%m/%d/%Y %H:%M")
    except ValueError:
        return None


def parse_insight_csv(raw: bytes) -> tuple[list[dict], int]:
    """Returns (rows, skipped_count). Rows missing a post_id are skipped
    rather than aborting the whole upload -- one malformed line in a
    115-row export shouldn't block the other 114.
    """
    text = decode_csv_bytes(raw)
    reader = csv.DictReader(io.StringIO(text))

    headers = set(reader.fieldnames or [])
    if not _REQUIRED_HEADERS.issubset(headers):
        raise InsightCsvError(
            "File CSV không đúng định dạng xuất 'Nội dung' từ Meta Business Suite (thiếu cột bắt buộc)."
        )

    rows: list[dict] = []
    skipped = 0
    for raw_row in reader:
        row: dict = {}
        for header, field in _HEADER_MAP.items():
            value = raw_row.get(header, "") or ""
            if field == "posted_at":
                row[field] = _to_datetime(value)
            elif field in _STRING_FIELDS:
                row[field] = value.strip()
            elif field in _FLOAT_FIELDS:
                row[field] = _to_float(value)
            else:
                row[field] = _to_int(value)

        if not row.get("post_id"):
            skipped += 1
            continue
        rows.append(row)

    return rows, skipped
