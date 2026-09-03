from sqlalchemy.orm import Session

from app.modules.news.models import NewsSource

# A small Vietnamese starter set so "Fetch all" works the moment the page is
# opened -- the user adds/removes/disables freely afterward. These are the
# publishers' own public RSS endpoints (VnExpress, Tuoi Tre). Nothing is
# fetched automatically: the background poll loop is off by default
# (settings.news_poll_interval_minutes == 0), so these sit idle until the
# user clicks "Fetch" or turns the poll interval on.
DEFAULT_SOURCES = [
    ("VnExpress - Tin mới nhất", "https://vnexpress.net/rss/tin-moi-nhat.rss", "Tổng hợp", "vi"),
    ("VnExpress - Thế giới", "https://vnexpress.net/rss/the-gioi.rss", "Thế giới", "vi"),
    ("VnExpress - Kinh doanh", "https://vnexpress.net/rss/kinh-doanh.rss", "Kinh tế", "vi"),
    ("Tuổi Trẻ - Tin mới nhất", "https://tuoitre.vn/rss/tin-moi-nhat.rss", "Tổng hợp", "vi"),
]


def seed_default_news_sources(db: Session) -> None:
    """Idempotent -- safe on every startup, same shape as
    app.modules.content_strategy.seed.seed_default_pillars.
    """
    existing = {s.feed_url for s in db.query(NewsSource).all()}
    for name, feed_url, category, language in DEFAULT_SOURCES:
        if feed_url not in existing:
            db.add(NewsSource(name=name, feed_url=feed_url, category=category, language=language, enabled=True))
    db.commit()
