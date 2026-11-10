"""Worker CLI: station 2 of the medical chatbot pipeline.

Turns the scraper's raw pages into clean records, cuts them into passages and
embeds every passage for search. How it works, visually:
https://medicalchatbot.demos.davieldev.com/worker
"""

import argparse
import sys

from pipeline import embed_records, name_of, process_pages, select_pages
from repositories.raw_data import slug_of


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Process the scraped pages and embed them for search.")
    parser.add_argument(
        "--condition",
        metavar="NAME",
        help="only this condition, by page slug or by name (e.g. acid-reflux-gerd or 'Acid reflux & GERD')",
    )
    parser.add_argument("--list-conditions", action="store_true", help="list the scraped conditions and exit")
    parser.add_argument(
        "--reembed",
        action="store_true",
        help="rebuild documents that already exist (after changing the chunking rules or the embedding model)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    pages = select_pages(args.condition)
    if args.list_conditions:
        print("Scraped conditions (--condition takes either column):")
        for page in pages:
            print(f"  {slug_of(page):<34} {name_of(page)}")
        return 0
    if not pages:
        print(f"❌ No scraped page matches '{args.condition}'. See --list-conditions." if args.condition
              else "❌ raw_data has no pages yet: run the scraper first.")
        return 1

    processing = process_pages(pages)
    embedding = embed_records(pages, reembed=args.reembed)

    print("\n📊 Summary")
    print(f"   processed_data: {processing['processed']} new, {processing['replaced']} replaced, "
          f"{processing['skipped']} already current, {processing['failed']} failed")
    print(f"   documents:      {embedding['created']} created, {embedding['skipped']} records skipped, "
          f"{embedding['errors']} errors")
    return 1 if processing["failed"] or embedding["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
