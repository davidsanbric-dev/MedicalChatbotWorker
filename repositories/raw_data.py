"""raw_data: the pages the scraper saved, read-only for the worker."""

from sqlalchemy import select

from db.database import SessionLocal
from db.models import RawData

SOURCE_PREFIX = "medical_conditions:"  # raw_data.source = "medical_conditions:<slug>"


def condition_pages() -> list[RawData]:
    """Every scraped condition page, ordered by slug."""
    with SessionLocal() as session:
        query = select(RawData).where(RawData.source.startswith(SOURCE_PREFIX)).order_by(RawData.source)
        return list(session.scalars(query))


def slug_of(page: RawData) -> str:
    return page.source.removeprefix(SOURCE_PREFIX)
