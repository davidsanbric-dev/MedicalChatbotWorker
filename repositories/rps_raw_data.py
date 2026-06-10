"""
Raw Data Repository

This module provides data access operations for RawData entities.
It encapsulates database queries and provides a clean interface for
accessing raw medical condition data.
"""

from typing import List, Optional, Set

from db.models import RawData
from db.database import SessionLocal


class RawDataRepository:
    """
    Repository for RawData database operations.

    This class encapsulates all database operations related to RawData
    entities, providing a clean separation between business logic and data access.
    """

    def find_id_by_condition_name(self, condition_name: str) -> Optional[str]:
        """
        Find the RawData ID for a given condition name by trying different source patterns.

        Args:
            condition_name: The condition name to search for

        Returns:
            The UUID of the RawData record as a string, or None if not found
        """
        session = SessionLocal()
        try:
            # Try different source patterns
            source_patterns = [
                f"medical_conditions:{condition_name}",
                f"{condition_name}.json",
                condition_name
            ]

            for pattern in source_patterns:
                raw_data = session.query(RawData).filter(
                    RawData.source == pattern
                ).first()

                if raw_data:
                    return str(raw_data.id)

            print(f"⚠️ No RawData found for condition '{condition_name}'")
            return None

        except Exception as e:
            print(f"⚠️ Error finding RawData for '{condition_name}': {e}")
            return None
        finally:
            session.close()

    def find_by_id(self, raw_data_id) -> Optional["RawData"]:  # type: ignore
        """
        Find a RawData record by its ID.

        Args:
            raw_data_id: The UUID of the RawData record to find

        Returns:
            RawData: The found record, or None if not found
        """
        session = SessionLocal()
        try:
            raw_data = session.query(RawData).filter(
                RawData.id == raw_data_id
            ).first()

            return raw_data
        finally:
            session.close()

    def find_by_source(self, source: str) -> Optional["RawData"]:  # type: ignore
        """
        Find a RawData record by its source.

        Args:
            source: The source string to search for

        Returns:
            RawData: The found record, or None if not found
        """
        session = SessionLocal()
        try:
            raw_data = session.query(RawData).filter(
                RawData.source == source
            ).first()

            return raw_data
        finally:
            session.close()

    def find_all_for_processing(self) -> list:
        """
        Get all RawData records that can be processed (source starts with 'medical_conditions:').

        Returns:
            List of (id, source, content) tuples
        """
        session = SessionLocal()
        try:
            raw_data_records = session.query(RawData).filter(
                RawData.source.like("medical_conditions:%")
            ).all()

            return [(str(rd.id), rd.source, rd.content) for rd in raw_data_records]

        except Exception as e:
            print(f"⚠️ Error getting raw data for processing: {e}")
            return []
        finally:
            session.close()

    def list_condition_names(self) -> List[str]:
        """Return a sorted list of unique condition names derived from RawData sources."""
        session = SessionLocal()
        try:
            sources = session.query(RawData.source).all()

            condition_names: Set[str] = set()
            for (source,) in sources:
                if not source:
                    continue

                condition_name = self._normalize_source_to_condition(source)
                if condition_name:
                    condition_names.add(condition_name)

            return sorted(condition_names)

        except Exception as e:
            print(f"⚠️ Error listing condition names: {e}")
            return []
        finally:
            session.close()

    def find_all_content_titles(self) -> List[str]:
        """
        Extract all 'title' property values from the 'content' JSONB field of all RawData records.
        
        This method uses PostgreSQL's JSONB operator (->>) to extract the 'title' field
        from each content JSON object.
        
        Returns:
            List[str]: A list of title strings from all RawData records that have a title field.
                      Empty list if no titles are found or on error.
        """
        session = SessionLocal()
        try:
            # Use PostgreSQL JSONB operator ->> to extract the 'title' field as text
            # The query will return tuples, so we need to extract the first element
            results = session.query(RawData.content['title'].astext).filter(
                RawData.content['title'].astext.isnot(None)
            ).all()
            
            # Extract the title strings from the result tuples and filter out any None values
            titles = [title for (title,) in results if title]
            
            return titles
            
        except Exception as e:
            print(f"⚠️ Error extracting content titles: {e}")
            return []
        finally:
            session.close()

    @staticmethod
    def _normalize_source_to_condition(source: str) -> Optional[str]:
        """Normalize different source formats to a condition name."""
        source = source.strip()
        if not source:
            return None

        if source.startswith("medical_conditions:"):
            candidate = source.split(":", 1)[1]
        elif source.endswith(".json"):
            candidate = source[:-5]
        else:
            candidate = source

        candidate = candidate.strip()
        return candidate or None


# Singleton instance for easy access
raw_data_repository = RawDataRepository()
