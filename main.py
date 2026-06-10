#!/usr/bin/env python3
"""
Medical Conditions Worker — database-driven processing for Medical condition content.

This module coordinates the processing pipeline: it promotes records from the
`RawData` table into structured `ProcessedData` entries and then creates
embeddings for downstream search from the resulting documents.

Key capabilities:
- Run the processor for every condition or a single condition with `--condition`.
- Discover available conditions directly from the `RawData` table via `--list-conditions`.
- Generate embeddings for each processed condition to populate the `documents` table.

Supporting assets live under:
- `services/` - business logic for processing and embedding generation.
- `repositories/` - database access layers for `RawData`, `ProcessedData`.
"""

import argparse
import sys
from services import DocumentService, ProcessedDataService
from repositories import processed_data_repository, raw_data_repository
document_service = DocumentService()
processed_data_service = ProcessedDataService()

def main():
    """Main function to handle command line arguments and dispatch to processing modules."""
    parser = argparse.ArgumentParser(
        description="Medical Conditions Worker - Process medical conditions data and generate embeddings"
    )
    parser.add_argument(
        "--condition",
        type=str,
        help="Process specific condition by name (e.g., 'allergies', 'acid-reflux-gerd')"
    )
    parser.add_argument(
        "--list-conditions",
        action="store_true",
        help="List all available conditions stored in the RawData table"
    )
    
    args, unknown = parser.parse_known_args()
    
    # Extract condition name from unknown args (flags like --depression)
    condition_name = None
    for arg in unknown:
        if arg.startswith('--'):
            condition_name = arg[2:]  # Remove the -- prefix
            break
    
    # List available conditions if requested
    if args.list_conditions:
        if raw_data_repository is None:
            print("Error: RawData repository not available. Cannot list conditions from database.")
            sys.exit(1)

        condition_names = raw_data_repository.list_condition_names()

        if not condition_names:
            print("❌ No conditions found in RawData table.")
            return

        print("Available conditions (from RawData table):")
        for condition in condition_names:
            print(f"  - {condition}")
        return
    
    try:

        # Process from RawData table
        # print("🔄 Processing data from RawData table to ProcessedData table using v5...")
        condition_filter = args.condition or condition_name
        processed_data_service.process_from_raw_data(condition_filter)

        # Now generate embeddings from the processed data
        print("\n🔄 Generating embeddings from ProcessedData table...")

        # Get all ProcessedData records
        processed_data_records = processed_data_repository.find_all()

        if not processed_data_records:
            print("❌ No ProcessedData records found for embedding generation.")
            return
        print(f"Found {len(processed_data_records)} ProcessedData records to process for embeddings...")

        for record in processed_data_records:
            # print(f"\n🔄 Generating embeddings for {record.condition_name} (ID: {record.id})...")
            document_service.generate_embeddings_from_processed_data(str(record.id))

    except ImportError as e:
        print(f"Error: Could not import required modules: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error during processing: {e}")
        sys.exit(1)
    
    print("\n🎉 Processing completed successfully!")


if __name__ == "__main__":
    main()