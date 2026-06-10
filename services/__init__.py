"""
Services package for business logic layer.

This package contains service classes that encapsulate business logic
and provide a clean interface for operations throughout the application.
"""

__version__ = "1.0.0"
__author__ = "Medical Conditions Worker"

# Import service classes for easy access
from .svc_document import DocumentService
from .svc_processed_data import ProcessedDataService

# Export service classes
__all__ = [
    "DocumentService",
    "ProcessedDataService"
]