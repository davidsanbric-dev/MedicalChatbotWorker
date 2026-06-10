"""
Processed Data Repository

This module provides data access operations for ProcessedData entities.
It encapsulates database queries and provides a clean interface for
accessing processed medical condition data.
"""

from typing import Optional

from db.models import ProcessedData, RawData
from db.database import SessionLocal


class ProcessedDataRepository:
    """
    Repository for ProcessedData database operations.

    This class encapsulates all database operations related to ProcessedData
    entities, providing a clean separation between business logic and data access.
    """

    def find_by_id(self, processed_data_id) -> Optional["ProcessedData"]:  # type: ignore
        """
        Find a ProcessedData record by its ID.

        Args:
            processed_data_id: The UUID of the ProcessedData record to find

        Returns:
            ProcessedData: The found record, or None if not found
        """
        db_session = SessionLocal()
        try:
            processed_data = db_session.query(ProcessedData).filter(
                ProcessedData.id == processed_data_id
            ).first()

            return processed_data
        finally:
            db_session.close()

    def find_all_by_condition_name(self, condition_name: str) -> list["ProcessedData"]:  # type: ignore
        """
        Find all ProcessedData records for a specific condition.

        Args:
            condition_name: Name of the condition to search for

        Returns:
            list[ProcessedData]: List of matching records
        """
        db_session = SessionLocal()
        try:
            processed_data_list = db_session.query(ProcessedData).filter(
                ProcessedData.condition_name == condition_name
            ).all()

            return processed_data_list
        finally:
            db_session.close()

    def find_all_by_processor_version(self, processor_version: str) -> list["ProcessedData"]:  # type: ignore
        """
        Find all ProcessedData records processed with a specific version.

        Args:
            processor_version: Version of the processor to search for

        Returns:
            list[ProcessedData]: List of matching records
        """
        db_session = SessionLocal()
        try:
            processed_data_list = db_session.query(ProcessedData).filter(
                ProcessedData.processor_version == processor_version
            ).all()

            return processed_data_list
        finally:
            db_session.close()

    def find_all(self) -> list["ProcessedData"]:  # type: ignore
        """
        Find all ProcessedData records.

        Returns:
            list[ProcessedData]: List of all processed data records
        """
        db_session = SessionLocal()
        try:
            processed_data_list = db_session.query(ProcessedData).all()
            return processed_data_list
        finally:
            db_session.close()

    def exists_for_condition_name_and_processor_version(self, condition_name: str, processor_version: str) -> bool:
        """
        Check if processed data exists for a specific condition and processor version.

        Args:
            condition_name: Name of the condition to check
            processor_version: Version of the processor to check

        Returns:
            bool: True if processed data exists, False otherwise
        """
        session = SessionLocal()
        try:
            existing = session.query(ProcessedData).filter(
                ProcessedData.condition_name == condition_name,
                ProcessedData.processor_version == processor_version
            ).first()

            return existing is not None
        except Exception as e:
            print(f"⚠️ Error checking existing processed data for '{condition_name}' (v{processor_version}): {e}")
            return False
        finally:
            session.close()

    def save(self, content, condition_name: str, processor_version: str = "v5", 
              raw_data_id=None, processing_metadata=None):
        """
        Save a new ProcessedData record to the database.

        Args:
            content: The processed JSON content
            condition_name: Name of the condition
            processor_version: Version of the processor used
            raw_data_id: UUID of the source RawData record (optional)
            processing_metadata: Additional metadata about the processing (optional)

        Returns:
            ProcessedData: The saved record
        """
        session = SessionLocal()
        try:
            # If no raw_data_id provided, try to find it by condition name
            if not raw_data_id:
                # Import raw_data_repository here to avoid circular imports
                try:
                    from repositories import raw_data_repository
                    raw_data_id = raw_data_repository.find_id_by_condition_name(condition_name)
                except ImportError:
                    raw_data_id = None

            # Create ProcessedData record
            processed_data = ProcessedData(
                raw_data_id=raw_data_id,
                content=content,
                processor_version=processor_version,
                condition_name=condition_name,
                processing_metadata=processing_metadata or {}
            )

            session.add(processed_data)
            session.flush()
            processed_data_id = str(processed_data.id)
            session.commit()

            return processed_data_id
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def count_all(self) -> int:
        """
        Count all ProcessedData records.

        Returns:
            int: Total number of processed data records
        """
        db_session = SessionLocal()
        try:
            count = db_session.query(ProcessedData).count()
            return count
        finally:
            db_session.close()

    def count_all_for_processor_version(self, processor_version: str) -> int:
        """
        Count all ProcessedData records for a specific processor version.

        Args:
            processor_version: Version of the processor to count

        Returns:
            int: Number of matching records
        """
        db_session = SessionLocal()
        try:
            count = db_session.query(ProcessedData).filter(
                ProcessedData.processor_version == processor_version
            ).count()
            return count
        finally:
            db_session.close()

    def update_processing_metadata_by_id(self, processed_data_id: str, metadata: dict) -> bool:
        """
        Update processing metadata for a ProcessedData record by ID.

        Args:
            processed_data_id: UUID of the ProcessedData record
            metadata: Metadata to update

        Returns:
            True if successful, False otherwise
        """
        session = SessionLocal()
        try:
            processed_record = session.query(ProcessedData).filter(
                ProcessedData.id == processed_data_id
            ).first()

            if processed_record:
                # Merge with existing metadata
                existing_metadata = processed_record.processing_metadata or {}
                existing_metadata.update(metadata)
                processed_record.processing_metadata = existing_metadata

                session.commit()
                return True
            else:
                return False

        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()


# Singleton instance for easy access
processed_data_repository = ProcessedDataRepository()