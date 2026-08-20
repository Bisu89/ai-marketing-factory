from sqlalchemy.orm import Session

from app.modules.content_strategy.models import ContentPillar

# Starter set from this task's brief. Formats are deliberately NOT seeded
# here -- the brief gives format examples (Betrayal, Hidden Message, Mother
# Story, ...) but never states which Pillar each belongs to, and a Format
# row requires a real pillar_id. Guessing that mapping would be inventing
# business data the task never specified; seeding it is left to whoever
# defines that mapping (a future task or the API this task deliberately
# doesn't build yet).
PILLARS = ["Love", "Marriage", "Family", "Female Self-worth", "Self-care", "Lifestyle"]


def seed_default_pillars(db: Session) -> None:
    """Idempotent: safe to call on every startup, same shape as
    app.db.seed.seed_initial_data.
    """
    existing = {p.name for p in db.query(ContentPillar).all()}
    for name in PILLARS:
        if name not in existing:
            db.add(ContentPillar(name=name))
    db.commit()
