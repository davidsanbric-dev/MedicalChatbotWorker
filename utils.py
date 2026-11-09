"""
Utility functions for the tasks package.

This module contains shared utility functions used across task modules,
particularly for JSON processing, file validation, and data manipulation.
"""

import json
import time
from pathlib import Path
from collections import Counter
from typing import Any, Optional, Sequence, Set, Tuple


def load_json_data(file_path):
    """
    Load JSON data from a file.

    Args:
        file_path: Path to the JSON file

    Returns:
        dict: Parsed JSON data

    Raises:
        FileNotFoundError: If file doesn't exist
        json.JSONDecodeError: If JSON is invalid
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def validate_json_file_path(file_path):
    """
    Validate that a file path exists and is a JSON file.

    Args:
        file_path: Path to validate

    Returns:
        bool: True if valid

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file is not a JSON file
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    if path.suffix.lower() != '.json':
        raise ValueError(f"File is not a JSON file: {file_path}")
    return True


def validate_directory_path(dir_path):
    """
    Validate that a directory path exists and is a directory.

    Args:
        dir_path: Directory path to validate

    Returns:
        bool: True if valid directory
    """
    path = Path(dir_path)
    return path.exists() and path.is_dir()


def get_json_files_in_directory(directory):
    """
    Get all JSON files in a directory.

    Args:
        directory: Directory path to scan

    Returns:
        list: List of JSON filenames (not full paths)
    """
    path = Path(directory)
    if not path.exists():
        return []
    return [f.name for f in path.glob("*.json")]


def validate_json_property(data, prop_name, filename=None, raise_error=True):
    """
    Validate that a JSON object contains a specific property.

    Args:
        data: JSON object/dict to check
        prop_name: Property name to look for
        filename: Optional filename for error messages
        raise_error: Whether to raise exception if property missing

    Returns:
        bool: True if property exists

    Raises:
        ValueError: If property missing and raise_error=True
    """
    has_prop = prop_name in data
    if not has_prop and raise_error:
        raise ValueError(f"Property '{prop_name}' not found in {filename or 'data'}")
    return has_prop


def sort_by_frequency(items):
    """
    Sort items by their frequency in descending order.

    Args:
        items: Iterable of items to count

    Returns:
        list: List of (item, count) tuples sorted by count descending
    """
    return Counter(items).most_common()


def normalize_subitems_for_hashing(subitems: Sequence[Any]) -> Tuple[Any, ...]:
    """Normalize subitems for hashing/comparison.

    Args:
        subitems: Nested sequence of subitems that may include strings, dicts,
                  or two-item lists representing [text, nested_subitems].

    Returns:
        Tuple[Any, ...]: A normalized tuple suitable for hashing.
    """
    normalized = []
    for subitem in subitems:
        if isinstance(subitem, str):
            normalized.append(subitem.strip())
        elif isinstance(subitem, list) and len(subitem) == 2:
            text = subitem[0] if isinstance(subitem[0], str) else str(subitem[0])
            nested_tuple = normalize_subitems_for_hashing(subitem[1]) if isinstance(subitem[1], (list, tuple)) else ()
            normalized.append((text.strip(), nested_tuple))
        elif isinstance(subitem, dict):
            text = subitem.get("text", "").strip()
            if "subitems" in subitem:
                nested_tuple = normalize_subitems_for_hashing(subitem["subitems"])
                normalized.append((text, nested_tuple))
            else:
                normalized.append(text)

    return tuple(sorted(normalized, key=lambda x: str(x)))


def normalize_item_for_deduplication(item: Any) -> Optional[Any]:
    """Normalize an item for deduplication purposes."""
    if isinstance(item, list) and len(item) == 2:
        text = item[0] if isinstance(item[0], str) else str(item[0])
        subitems_tuple = normalize_subitems_for_hashing(item[1]) if isinstance(item[1], (list, tuple)) else ()
        return (text.strip(), subitems_tuple)
    if isinstance(item, dict):
        if "subitems" in item:
            text = item.get("text", "").strip()
            subitems_tuple = normalize_subitems_for_hashing(item["subitems"])
            return (text, subitems_tuple)
        return item.get("text", "").strip()
    if isinstance(item, str):
        return item.strip()
    return None


def collect_nested_subitem_lists(item: Any, subitem_lists: Set[Tuple[Any, ...]]) -> None:
    """Recursively collect all nested subitem lists."""
    if isinstance(item, dict) and "subitems" in item:
        subitems_tuple = normalize_subitems_for_hashing(item["subitems"])
        subitem_lists.add(subitems_tuple)
        for subitem in item["subitems"]:
            if isinstance(subitem, (dict, list)):
                collect_nested_subitem_lists(subitem, subitem_lists)
    elif isinstance(item, list) and len(item) == 2 and isinstance(item[1], list):
        subitems_tuple = normalize_subitems_for_hashing(item[1])
        subitem_lists.add(subitems_tuple)
        for subitem in item[1]:
            if isinstance(subitem, (dict, list)):
                collect_nested_subitem_lists(subitem, subitem_lists)


def check_if_duplicate_subitem_list(item: Any, subitem_lists: Set[Tuple[Any, ...]]) -> bool:
    """Check if a list item is a duplicate of a known subitem list."""
    if not isinstance(item, dict) or "items" not in item:
        return False

    items_list = item["items"]

    if all(isinstance(x, str) for x in items_list):
        standalone_tuple = tuple(sorted(x.strip() for x in items_list))
        return standalone_tuple in subitem_lists

    # Complex structures aren't handled yet; keep original list.
    return False


def deduplicate_lists(content_items: Sequence[Any]) -> list:
    """Remove duplicate list structures with improved handling of nested subitems."""
    if not content_items:
        return list(content_items)

    processed_items = []
    seen_structures: Set[Tuple[Any, ...]] = set()
    subitem_lists: Set[Tuple[Any, ...]] = set()

    for item in content_items:
        if isinstance(item, dict) and "items" in item:
            for subitem in item.get("items", []):
                collect_nested_subitem_lists(subitem, subitem_lists)

    for item in content_items:
        if isinstance(item, dict) and "items" in item:
            normalized_items = []
            for subitem in item.get("items", []):
                normalized = normalize_item_for_deduplication(subitem)
                if normalized is not None:
                    normalized_items.append(normalized)

            normalized_repr = tuple(sorted(normalized_items, key=lambda x: str(x)))
            is_duplicate_subitem = check_if_duplicate_subitem_list(item, subitem_lists)

            if normalized_repr not in seen_structures and not is_duplicate_subitem:
                processed_items.append(item)
                seen_structures.add(normalized_repr)
        else:
            processed_items.append(item)

    return processed_items


def show_progress_spinner(message="Loading...", done_flag=None):
    """
    Display a spinning progress indicator while an operation is running.

    This function runs in a separate thread and shows a spinning animation
    until the provided done_flag is set to True.

    Args:
        message: Message to display before the spinner (default: "Loading...")
        done_flag: A list or object with a boolean value that can be modified
                  by the calling thread to stop the spinner

    Example:
        progress_done = [False]
        progress_thread = threading.Thread(
            target=show_progress_spinner,
            args=("Loading model...", progress_done)
        )
        progress_thread.start()

        # Do some work...
        time.sleep(2)

        # Stop the spinner
        progress_done[0] = True
        progress_thread.join()
    """
    if done_flag is None:
        done_flag = [False]

    progress_chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    i = 0

    while not done_flag[0] if isinstance(done_flag, list) else not done_flag:
        spinner_char = progress_chars[i % len(progress_chars)]
        print(f"\r{message} {spinner_char}", end="", flush=True)
        time.sleep(0.1)
        i += 1

    # Clear the line when done
    print(f"\r{message} ✓" + " " * 20)


def print_processing_summary(stats):
    """
    Print a formatted processing summary with statistics.

    Args:
        stats: Dictionary containing processing statistics with keys:
               'processed', 'successful', 'failed', 'skipped'
    """
    print("\n📊 Processing summary:")
    print(f"   📁 Records processed: {stats['processed']}")
    print(f"   ✅ Successful: {stats['successful']}")
    print(f"   ❌ Failed: {stats['failed']}")
    print(f"   ⏭️  Skipped: {stats['skipped']}")
    if stats.get("replaced"):
        print(f"   ♻️  Replaced older processor output: {stats['replaced']}")
    return stats