"""
Document Repository

This module provides data access operations for Document entities.
It encapsulates database queries and provides a clean interface for
accessing document embeddings and related data.
"""

from db.models import Document
from db.database import SessionLocal


class DocumentRepository:
    """
    Repository for Document database operations.

    This class encapsulates all database operations related to Document
    entities, providing a clean separation between business logic and data access.
    """

    def save(self, processed_data_id: str, content: str, content_type: str,
              embedding, metadata=None):
        """
        Save a new Document record to the database.

        Args:
            processed_data_id: ID of the associated ProcessedData record
            content: The text content of the document
            content_type: Type of content (e.g., "symptom", "paragraph", "list_item")
            embedding: Vector embedding of the content
            metadata: Additional metadata about the document

        Returns:
            Document: The saved document record
        """
        db_session = SessionLocal()
        try:
            # Create Document record
            document = Document(
                processed_data_id=processed_data_id,
                content=content,
                content_type=content_type,
                embedding=embedding,
                metadata_=metadata or {}
            )

            db_session.add(document)
            db_session.commit()

            return document
        except Exception as e:
            db_session.rollback()
            raise e
        finally:
            db_session.close()

    def find_by_processed_data_id(self, processed_data_id: str):
        """
        Find all Document records for a specific ProcessedData record.

        Args:
            processed_data_id: ID of the ProcessedData record

        Returns:
            List[Document]: List of matching document records
        """
        db_session = SessionLocal()
        try:
            documents = db_session.query(Document).filter(
                Document.processed_data_id == processed_data_id
            ).all()

            return documents
        finally:
            db_session.close()

    def exists_for_processed_data_id(self, processed_data_id: str) -> bool:
        """Return True if any Document already belongs to this ProcessedData record."""
        db_session = SessionLocal()
        try:
            return db_session.query(
                db_session.query(Document.id)
                .filter(Document.processed_data_id == processed_data_id)
                .exists()
            ).scalar()
        finally:
            db_session.close()

    def replace_for_processed_data_id(self, processed_data_id: str, rows: list[dict]) -> int:
        """Atomically replace every Document of a ProcessedData record.

        Deletes the record's existing documents and inserts `rows` (dicts with
        content, content_type, embedding, metadata) in one transaction, so a
        re-run can never leave duplicates or a half-embedded record behind.

        Returns:
            int: Number of documents inserted
        """
        db_session = SessionLocal()
        try:
            db_session.query(Document).filter(
                Document.processed_data_id == processed_data_id
            ).delete(synchronize_session=False)
            db_session.add_all(
                Document(
                    processed_data_id=processed_data_id,
                    content=row["content"],
                    content_type=row["content_type"],
                    embedding=row["embedding"],
                    metadata_=row.get("metadata") or {},
                )
                for row in rows
            )
            db_session.commit()
            return len(rows)
        except Exception:
            db_session.rollback()
            raise
        finally:
            db_session.close()

    def find_by_content_type(self, content_type: str):
        """
        Find all Document records of a specific content type.

        Args:
            content_type: Type of content to search for

        Returns:
            List[Document]: List of matching document records
        """
        db_session = SessionLocal()
        try:
            documents = db_session.query(Document).filter(
                Document.content_type == content_type
            ).all()

            return documents
        finally:
            db_session.close()


# Singleton instance for easy access
document_repository = DocumentRepository()