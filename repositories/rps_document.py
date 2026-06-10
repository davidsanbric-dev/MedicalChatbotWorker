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