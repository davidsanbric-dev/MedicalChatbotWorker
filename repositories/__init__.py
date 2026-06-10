"""
Repositories package for data access layer.

This package contains repository classes that encapsulate database operations
and provide a clean interface for data access throughout the application.
"""

__version__ = "1.0.0"
__author__ = "Medical Conditions Worker"

# Import repository instances for easy access
from .rps_processed_data import processed_data_repository
from .rps_raw_data import raw_data_repository
from .rps_document import document_repository

# Export repository instances
__all__ = [
    "processed_data_repository",
    "raw_data_repository",
    "document_repository"
]