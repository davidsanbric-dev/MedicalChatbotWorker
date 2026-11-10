"""processed_data: one clean record per scraped page."""

import uuid
from typing import Any

from sqlalchemy import delete, select

from db.database import SessionLocal
from db.models import Document, ProcessedData


def versions_for(raw_data_id: uuid.UUID) -> list[str]:
    """Processor versions already stored for a page."""
    with SessionLocal() as session:
        query = select(ProcessedData.processor_version).where(ProcessedData.raw_data_id == raw_data_id)
        return list(session.scalars(query))


def for_pages(raw_data_ids: list[uuid.UUID]) -> list[ProcessedData]:
    with SessionLocal() as session:
        query = (
            select(ProcessedData)
            .where(ProcessedData.raw_data_id.in_(raw_data_ids))
            .order_by(ProcessedData.condition_name)
        )
        return list(session.scalars(query))


def replace(
    raw_data_id: uuid.UUID,
    *,
    content: dict[str, Any],
    condition_name: str,
    processor_version: str,
    processing_metadata: dict[str, Any],
) -> uuid.UUID:
    """Store a page's new clean record in one transaction, deleting its older records
    and their documents, which were built from outdated text.

    Exactly one record per page is what the API's insight queries assume.
    """
    with SessionLocal.begin() as session:
        outdated = select(ProcessedData.id).where(ProcessedData.raw_data_id == raw_data_id)
        session.execute(delete(Document).where(Document.processed_data_id.in_(outdated)))
        session.execute(delete(ProcessedData).where(ProcessedData.raw_data_id == raw_data_id))
        record = ProcessedData(
            raw_data_id=raw_data_id,
            content=content,
            condition_name=condition_name,
            processor_version=processor_version,
            processing_metadata=processing_metadata,
        )
        session.add(record)
        session.flush()  # assigns record.id
        return record.id
