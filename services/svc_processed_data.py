import time
from typing import Any, Dict, Optional
from repositories import processed_data_repository, raw_data_repository
from services.chunking import normalize_content, normalize_text
from utils import deduplicate_lists, print_processing_summary

# Bump whenever the processed output changes, so stored records from an older
# processor are replaced on the next run instead of being kept as they are.
#   v5: restructure, merge and deduplicate
#   v6: + Unicode normalization (NFKC: non-breaking spaces become plain spaces)
PROCESSOR_VERSION = "v6"

class ProcessedDataService:
    def __init__(self):
        pass

    def extract_condition_name_from_title(self, title: str) -> str:
        """
        Extract and normalize the condition name from a title string.
        
        Removes common suffixes like " treatment online" and " advice and refills online",
        preserving the original letter case, then replaces spaces/hyphens with underscores.
        
        Args:
            title: The raw title string from the content object
            
        Returns:
            Normalized condition name with preserved case (e.g., "Acne", "Diabetes")
        """
        if not title:
            return ""
        
        # Remove common suffixes (case-insensitive)
        suffixes_to_remove = [
            " treatment online",
            " advice and refills online",
            " online",
            " | medical for patients",
            " - medical",
            " — online care",
        ]

        # Remove common prefixes (case-insensitive)
        prefixes_to_remove = [
            "online relief for ",
            "get telehealth care for ",
            "online care for ",
        ]
        
        cleaned_title = title.strip()
        cleaned_lower = cleaned_title.lower()
        
        for suffix in suffixes_to_remove:
            if cleaned_lower.endswith(suffix):
                cleaned_title = cleaned_title[:len(cleaned_title) - len(suffix)].strip()
                cleaned_lower = cleaned_title.lower()

        prefix_removed = False
        for prefix in prefixes_to_remove:
            if cleaned_lower.startswith(prefix):
                cleaned_title = cleaned_title[len(prefix):].strip()
                cleaned_lower = cleaned_title.lower()
                prefix_removed = True
        
        if prefix_removed and cleaned_title:
            cleaned_title = cleaned_title[0].upper() + cleaned_title[1:]
        
        # Replace spaces/hyphens with underscores while preserving case
        condition_name = cleaned_title
        
        return condition_name

    def create(self, processed_content, condition_name, processor_version=PROCESSOR_VERSION, raw_data_id=None, processing_metadata=None):
        """
        Create a new entry in the ProcessedDfor prefix in prefixes_to_remove:
            if cleaned_lower.startswith(prefix):
                cleaned_title = cleaned_title[]ata table.

        Args:
            processed_content: The processed JSON content
            condition_name: Name of the condition (e.g., "acne", "diabetes")
            processor_version: Version of the processor used (default: PROCESSOR_VERSION)
            raw_data_id: UUID of the source RawData record (optional)
            processing_metadata: Additional metadata about the processing (optional)

        Returns:
            str: UUID of the created ProcessedData record, or None if failed
        """

        try:
            # If no raw_data_id provided, try to find it by condition name
            if not raw_data_id and raw_data_repository:
                raw_data_id = raw_data_repository.find_id_by_condition_name(condition_name)

            # Use repository to save ProcessedData record
            processed_data_id = processed_data_repository.save(
                content=processed_content,
                condition_name=condition_name,
                processor_version=processor_version,
                raw_data_id=raw_data_id,
                processing_metadata=processing_metadata or {}
            )

            print(f"✅ Saved processed data for {condition_name} (version: {processor_version}, id: {processed_data_id})")
            return processed_data_id

        except Exception as e:
            print(f"❌ Error saving processed data for {condition_name}: {e}")
            return None
        

    ###############################################
    # Auxiliary methods for RawData processing
    ###############################################

    def process_from_raw_data(self, condition_filter: Optional[str] = None) -> Dict[str, int]:
        """
        Process data directly from RawData table records.

        Args:
            condition_filter: Filter by specific condition name (optional)

        Returns:
            Dictionary with processing statistics
        """
        print("🔄 Processing data from RawData table to ProcessedData table...")
        
        # Get all raw data records
        raw_data_records = raw_data_repository.find_all_for_processing()
        
        if not raw_data_records:
            print("❌ No RawData records found for processing")
            return {"processed": 0, "successful": 0, "failed": 0, "skipped": 0}

        stats = {"processed": 0, "successful": 0, "failed": 0, "skipped": 0, "replaced": 0}

        for raw_data_id, source, raw_content in raw_data_records:
            # Extract condition name from the title property in raw_content
            # Fall back to extracting from source if title is not available
            if isinstance(raw_content, dict) and "title" in raw_content:
                condition_name = normalize_text(self.extract_condition_name_from_title(raw_content["title"]))
            else:
                # Fallback: Extract condition name from source (format: medical_conditions:condition-name)
                condition_name = source.replace("medical_conditions:", "").replace("-", "_")

            # Apply condition filter if specified (case-insensitive comparison)
            if condition_filter and condition_name.lower() != condition_filter.lower():
                continue

            stats["processed"] += 1

            # Idempotency is keyed on the raw record: the current processor
            # version is skipped, an older one is replaced (with its documents).
            existing_versions = processed_data_repository.find_versions_by_raw_data_id(raw_data_id)
            if PROCESSOR_VERSION in existing_versions:
                print(f"⏭️  Skipping {condition_name} (already processed with {PROCESSOR_VERSION})")
                stats["skipped"] += 1
                continue

            try:
                processed_data = normalize_content(self.process_condition_data(raw_content))

                processing_metadata = {
                    "source": "raw_data_table",
                    "raw_data_id": raw_data_id,
                    "processor": f"process_{PROCESSOR_VERSION}",
                    "replaced_versions": existing_versions,
                    "processed_at": time.time()
                }

                processed_data_id = processed_data_repository.replace_for_raw_data_id(
                    raw_data_id=raw_data_id,
                    content=processed_data,
                    condition_name=condition_name,
                    processor_version=PROCESSOR_VERSION,
                    processing_metadata=processing_metadata,
                )

                stats["successful"] += 1
                if existing_versions:
                    stats["replaced"] += 1
                    print(f"♻️  {condition_name}: {', '.join(existing_versions)} → {PROCESSOR_VERSION} (ID: {processed_data_id})")
                else:
                    print(f"✅ {condition_name}: Processed from RawData (ID: {processed_data_id})")

            except Exception as e:
                stats["failed"] += 1
                print(f"❌ {condition_name}: Processing error - {e}")

        return print_processing_summary(stats)
    
    def process_content_item(self, content_item: Any) -> Any:
        """Process a single content item, converting paragraphs to string arrays."""
        if not isinstance(content_item, dict):
            return content_item

        # Check if this is a simple paragraph (only has "text" property or "text" and "type")
        if "text" in content_item and ("type" not in content_item or content_item.get("type") == "paragraph"):
            # Return the text directly instead of wrapping in a list
            return content_item["text"]

        processed_item = content_item.copy()  # Create a shallow copy of the content item

        # Remove the "type" property if it exists
        processed_item.pop("type", None)

        if "items" in content_item:
            processed_items = []
            seen_items = set()  # Track unique items

            for item in content_item["items"]:
                if isinstance(item, dict):
                    if "subitems" in item:
                        # Keep structured items but clean them up
                        text = item.get("text", "").strip()
                        if text and ":" in text:
                            text = text.split(":", 1)[0].strip() + ":"

                        # Recursively process subitems to handle nested structures
                        clean_subitems = self.process_subitems_recursively(item["subitems"], seen_items)

                        if clean_subitems:
                            processed_items.append([text, clean_subitems])
                            seen_items.add(text)
                        elif text:
                            processed_items.append(text)
                            seen_items.add(text)
                    else:
                        text = item.get("text", "").strip()
                        if text and text not in seen_items:
                            processed_items.append(text)
                            seen_items.add(text)
                elif isinstance(item, str):
                    clean_item = item.strip()
                    if clean_item and clean_item not in seen_items:
                        processed_items.append(clean_item)
                        seen_items.add(clean_item)

            processed_item["items"] = processed_items

        return processed_item

    def process_subitems_recursively(self, subitems: list, seen_items: set) -> list:
        """Recursively process subitems to handle nested structures."""
        clean_subitems = []

        for subitem in subitems:
            if isinstance(subitem, str):
                clean_subitem = subitem.strip()
                if clean_subitem and clean_subitem not in seen_items:
                    clean_subitems.append(clean_subitem)
                    seen_items.add(clean_subitem)
            elif isinstance(subitem, dict):
                if "subitems" in subitem:
                    # This subitem itself has subitems - preserve the nested structure
                    text = subitem.get("text", "").strip()
                    nested_clean_subitems = self.process_subitems_recursively(subitem["subitems"], seen_items)
                    if nested_clean_subitems:
                        clean_subitems.append([text, nested_clean_subitems])
                    elif text:
                        clean_subitems.append(text)
                else:
                    text = subitem.get("text", "").strip()
                    if text and text not in seen_items:
                        clean_subitems.append(text)
                        seen_items.add(text)
            elif isinstance(subitem, list):
                # Handle nested lists
                nested_clean = self.process_subitems_recursively(subitem, seen_items)
                if nested_clean:
                    clean_subitems.extend(nested_clean)

        return clean_subitems

    def merge_related_content(self, content_items: list) -> list:
        """Merge consecutive related content structures: paragraph+list, strong_paragraph+list, strong_paragraph+paragraph+list, strong_paragraph+paragraph+strong_paragraph(:)+list+strong_paragraph(:)+list, and strong_paragraph+paragraph."""
        if not content_items:
            return content_items

        merged_content = []
        i = 0

        while i < len(content_items):
            current_item = content_items[i]

            # Check for strong_paragraph + paragraph + strong_paragraph(:) + list + strong_paragraph(:) + list (six items)
            if (isinstance(current_item, dict) and "text" in current_item and
                i + 5 < len(content_items)):

                next_item = content_items[i + 1]
                next_next_item = content_items[i + 2]
                next_next_next_item = content_items[i + 3]
                next_next_next_next_item = content_items[i + 4]
                next_next_next_next_next_item = content_items[i + 5]

                # Check pattern: strong_paragraph + paragraph + strong_paragraph(:) + list + strong_paragraph(:) + list
                if (isinstance(next_item, str) and
                    isinstance(next_next_item, dict) and "text" in next_next_item and next_next_item["text"].strip().endswith(":") and
                    isinstance(next_next_next_item, dict) and "items" in next_next_next_item and
                    isinstance(next_next_next_next_item, dict) and "text" in next_next_next_next_item and next_next_next_next_item["text"].strip().endswith(":") and
                    isinstance(next_next_next_next_next_item, dict) and "items" in next_next_next_next_next_item):

                    # Merge into a structured format: [main_heading, description, {subheading1: list1, subheading2: list2}]
                    merged_item = [
                        current_item["text"],
                        next_item,
                        {
                            next_next_item["text"]: next_next_next_item,
                            next_next_next_next_item["text"]: next_next_next_next_next_item
                        }
                    ]
                    merged_content.append(merged_item)
                    i += 6  # Skip the next five items since they were merged
                    continue

            # Check for strong_paragraph + paragraph + list (three items)
            if (isinstance(current_item, dict) and "text" in current_item and
                i + 2 < len(content_items)):

                next_item = content_items[i + 1]
                next_next_item = content_items[i + 2]

                if (isinstance(next_item, str) and
                    isinstance(next_next_item, dict) and "items" in next_next_item):
                    # Merge strong_paragraph + paragraph + list
                    merged_item = [current_item["text"], next_item, next_next_item]
                    merged_content.append(merged_item)
                    i += 3  # Skip the next two items since they were merged
                    continue

            # Check for strong_paragraph + paragraph (two items, not followed by list)
            if (isinstance(current_item, dict) and "text" in current_item and
                i + 1 < len(content_items)):

                next_item = content_items[i + 1]

                if isinstance(next_item, str):
                    # Merge strong_paragraph + paragraph into a single text string
                    merged_text = f"{current_item['text']}: {next_item}"
                    merged_content.append(merged_text)
                    i += 2  # Skip the next item since it was merged
                    continue

            # Check for strong_paragraph + list (two items)
            if (isinstance(current_item, dict) and "text" in current_item and
                i + 1 < len(content_items)):

                next_item = content_items[i + 1]

                if isinstance(next_item, dict) and "items" in next_item:
                    # Merge strong_paragraph + list
                    merged_item = [current_item["text"], next_item]
                    merged_content.append(merged_item)
                    i += 2  # Skip the next item since it was merged
                    continue

            # Check for paragraph + list (original logic)
            if (isinstance(current_item, str) and i + 1 < len(content_items)):

                next_item = content_items[i + 1]

                # Check if next item is an object with "items" (list structure)
                if isinstance(next_item, dict) and "items" in next_item:
                    # Merge paragraph and list into a single list structure
                    merged_item = [current_item, next_item]
                    merged_content.append(merged_item)
                    i += 2  # Skip the next item since it was merged
                    continue

            # If no merge occurred, add current item as-is
            merged_content.append(current_item)
            i += 1

        return merged_content


    def process_condition_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process the entire condition data structure."""
        processed_data = data.copy()

        # Process symptoms to convert from object to list format
        if "symptoms" in data and isinstance(data["symptoms"], dict):
            symptoms_obj = data["symptoms"]
            if "heading" in symptoms_obj and "list" in symptoms_obj:
                # Convert to list format: [heading, list]
                processed_data["symptoms"] = [
                    symptoms_obj["heading"],
                    symptoms_obj["list"]
                ]

        # Process onlineDiagnosingAndTreating content
        if "onlineDiagnosingAndTreating" in data and "content" in data["onlineDiagnosingAndTreating"]:
            processed_content = []

            for content_item in data["onlineDiagnosingAndTreating"]["content"]:
                processed_item = self.process_content_item(content_item)
                processed_content.append(processed_item)

            # Merge consecutive related content structures
            processed_content = self.merge_related_content(processed_content)

            # Remove duplicate lists with improved deduplication
            processed_content = deduplicate_lists(processed_content)

            # Separate paragraphs and lists into object structure
            paragraphs = []
            lists = []

            for item in processed_content:
                if isinstance(item, str):
                    paragraphs.append(item)
                else:
                    # This should be the list structure (merged paragraph + list or standalone list)
                    lists.append(item)

            processed_data["onlineDiagnosingAndTreating"]["content"] = {
                "paragraphs": paragraphs,
                "lists": lists
            }

        return processed_data