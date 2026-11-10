"""The worker's two phases: raw_data → processed_data, then processed_data → documents.

Re-running is safe: finished work is skipped. A new PROCESSOR_VERSION replaces older
records, and --reembed rebuilds documents after a chunking or model change.
"""

import time
from collections import Counter

from db.models import Document, RawData
from repositories import documents, processed_data, raw_data
from services.chunking import build_chunks
from services.embedding import embed_passages
from services.processing import PROCESSOR_VERSION, condition_name_of, process_page


def name_of(page: RawData) -> str:
    return condition_name_of(page.content, raw_data.slug_of(page))


def select_pages(condition: str | None = None) -> list[RawData]:
    """Every scraped page, or only the one whose slug or name is `condition` (any letter case)."""
    pages = raw_data.condition_pages()
    if condition is None:
        return pages
    wanted = condition.strip().lower()
    return [page for page in pages if wanted in (raw_data.slug_of(page), name_of(page).lower())]


def process_pages(pages: list[RawData]) -> Counter:
    """raw_data → processed_data. Pages already processed by this PROCESSOR_VERSION are
    skipped; an older version's record is replaced together with its documents."""
    print("🔄 Processing raw_data → processed_data")
    stats = Counter()
    for page in pages:
        name = name_of(page)
        stored_versions = processed_data.versions_for(page.id)
        if PROCESSOR_VERSION in stored_versions:
            stats["skipped"] += 1
            print(f"⏭️  {name}: already processed by {PROCESSOR_VERSION}")
            continue
        try:
            record_id = processed_data.replace(
                page.id,
                content=process_page(page.content),
                condition_name=name,
                processor_version=PROCESSOR_VERSION,
                processing_metadata={
                    "source": "raw_data_table",
                    "raw_data_id": str(page.id),
                    "processor": f"process_{PROCESSOR_VERSION}",
                    "replaced_versions": stored_versions,
                    "processed_at": time.time(),
                },
            )
        except Exception as error:  # one bad page must not stop the run
            stats["failed"] += 1
            print(f"❌ {name}: {error}")
            continue
        if stored_versions:
            stats["replaced"] += 1
            print(f"♻️  {name}: {', '.join(stored_versions)} → {PROCESSOR_VERSION} (id {record_id})")
        else:
            stats["processed"] += 1
            print(f"✅ {name} (id {record_id})")
    return stats


def embed_records(pages: list[RawData], reembed: bool = False) -> Counter:
    """processed_data → documents: cut each record into passages and embed them.
    Records that already have documents are skipped unless `reembed`."""
    print("\n🔄 Embedding processed_data → documents")
    already_embedded = set() if reembed else documents.embedded_record_ids()
    stats = Counter()
    for record in processed_data.for_pages([page.id for page in pages]):
        if record.id in already_embedded:
            stats["skipped"] += 1
            continue
        chunks = build_chunks(record.content, record.condition_name, record.processor_version)
        if not chunks:
            stats["skipped"] += 1
            print(f"⚠️  {record.condition_name}: nothing to embed")
            continue
        try:
            vectors = embed_passages([chunk.content for chunk in chunks])
            documents.replace_for(
                record.id,
                [
                    Document(
                        processed_data_id=record.id,
                        content=chunk.content,
                        content_type=chunk.content_type,
                        metadata_=chunk.metadata,
                        embedding=vector,
                    )
                    for chunk, vector in zip(chunks, vectors, strict=True)
                ],
            )
        except Exception as error:  # one bad record must not stop the run
            stats["errors"] += 1
            print(f"❌ {record.condition_name}: {error}")
            continue
        stats["created"] += len(chunks)
        kinds = Counter(chunk.content_type for chunk in chunks)
        print(
            f"✅ {record.condition_name}: {len(chunks)} chunks embedded "
            f"({kinds['symptom']} symptom, {kinds['paragraph']} paragraph, {kinds['list_item']} list)"
        )
    return stats
