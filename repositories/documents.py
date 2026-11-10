"""documents: the searchable passages, each with its embedding."""

import uuid

from sqlalchemy import delete, select

from db.database import SessionLocal
from db.models import Document


def embedded_record_ids() -> set[uuid.UUID]:
    """Processed records that already have documents."""
    with SessionLocal() as session:
        return set(session.scalars(select(Document.processed_data_id).distinct()))


def replace_for(processed_data_id: uuid.UUID, passages: list[Document]) -> None:
    """Swap a record's documents in one transaction, so a re-run never leaves
    duplicates or a half-embedded record behind."""
    with SessionLocal.begin() as session:
        session.execute(delete(Document).where(Document.processed_data_id == processed_data_id))
        session.add_all(passages)
