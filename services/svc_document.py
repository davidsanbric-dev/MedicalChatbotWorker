"""
Documents Processing Task Module

This module contains document processing functionality for medical conditions
data, including generating embeddings from database records.

Key Class:
- DocumentService: Contains methods for document processing tasks

Dependencies:
- fastembed: For fast ONNX-based embedding generation
- Database service for PostgreSQL operations

Note: This module works with pre-processed data stored in the database.
"""

import threading
from typing import Optional

from repositories import processed_data_repository, document_repository
from services.chunking import build_chunks
from utils import show_progress_spinner
from fastembed import TextEmbedding

# Note: SessionLocal import removed as repositories handle session management

# Embedding model shared with the API. Must stay identical to the API's query
# model (medical_conditions_api/app/core/embedding.py): the corpus is embedded
# here with passage_embed() and queried there with query_embed(), so both sides
# must use the same model or vector distances are meaningless.
DEFAULT_EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"

class DocumentService:

    _cached_embedding_model: Optional[TextEmbedding] = None
    _cached_model_name: Optional[str] = None
    _embedding_model_lock = threading.Lock()

    @classmethod
    def _get_embedding_model(
        cls,
        embedding_model: Optional[TextEmbedding] = None,
        model_name: str = DEFAULT_EMBEDDING_MODEL,
    ) -> TextEmbedding:
        """Return a ready embedding model, lazily initializing and caching it."""
        if embedding_model is not None:
            return embedding_model

        with cls._embedding_model_lock:
            if (
                cls._cached_embedding_model is not None
                and cls._cached_model_name == model_name
            ):
                return cls._cached_embedding_model

            cls._cached_embedding_model = cls.initialize_embedding_model(model_name)
            cls._cached_model_name = model_name
            return cls._cached_embedding_model

    @classmethod
    def generate_embeddings_from_processed_data(
        cls,
        processed_data_id,
        embedding_model: Optional[TextEmbedding] = None,
        content_types=None,
        model_name: str = DEFAULT_EMBEDDING_MODEL,
        reembed: bool = False,
    ):
        """
        Chunk a ProcessedData record, embed the chunks and store them as Documents.

        Idempotent: a record that already has documents is skipped unless
        `reembed` is True, in which case its documents are replaced atomically
        (needed after changing the chunking rules or the embedding model).

        Args:
            processed_data_id: UUID of the ProcessedData record
            embedding_model: Optional pre-initialized TextEmbedding model
            content_types: Subset of ["symptoms", "paragraphs", "lists"] (default: all)
            model_name: Model used when lazily initializing the embedding model
            reembed: Replace existing documents instead of skipping the record

        Returns:
            dict: {"created": int, "errors": int, "skipped": int}
        """
        try:
            if not reembed and document_repository.exists_for_processed_data_id(processed_data_id):
                return {"created": 0, "errors": 0, "skipped": 1}

            processed_data = processed_data_repository.find_by_id(processed_data_id)
            if not processed_data:
                print(f"❌ ProcessedData record {processed_data_id} not found")
                return {"created": 0, "errors": 1, "skipped": 0}

            condition_name = processed_data.condition_name
            chunks = build_chunks(
                processed_data.content,
                condition_name,
                processed_data.processor_version,
                content_types,
            )
            if not chunks:
                print(f"⚠️  {condition_name}: nothing to embed")
                return {"created": 0, "errors": 0, "skipped": 1}

            embedding_model = cls._get_embedding_model(embedding_model, model_name)
            # Embed chunk by chunk: batching pads every chunk to the longest one
            # in the batch, which measured ~35% slower on this corpus.
            embeddings = [next(iter(embedding_model.passage_embed([c.content]))) for c in chunks]

            created = document_repository.replace_for_processed_data_id(
                processed_data_id,
                [
                    {
                        "content": chunk.content,
                        "content_type": chunk.content_type,
                        "embedding": embedding,
                        "metadata": chunk.metadata,
                    }
                    for chunk, embedding in zip(chunks, embeddings)
                ],
            )

            counts = {t: sum(c.content_type == t for c in chunks) for t in ("symptom", "paragraph", "list_item")}
            print(
                f"✅ {condition_name}: {created} chunks embedded "
                f"({counts['symptom']} symptom, {counts['paragraph']} paragraph, {counts['list_item']} list)"
            )
            return {"created": created, "errors": 0, "skipped": 0}

        except Exception as e:
            print(f"❌ Error generating embeddings for {processed_data_id}: {e}")
            return {"created": 0, "errors": 1, "skipped": 0}

    @staticmethod
    def initialize_embedding_model(model_name: str = DEFAULT_EMBEDDING_MODEL):
        """
        Initializes the embedding model with a visual progress bar.

        Args:
            model_name: Path to the ONNX model to load

        Returns:
            TextEmbedding: Initialized embedding model
        """
        print("Initializing embedding model...")

        # Progress bar that runs while model loads
        progress_done = [False]

        # Start progress bar in separate thread
        progress_thread = threading.Thread(
            target=show_progress_spinner,
            args=("Loading embedding model...", progress_done)
        )
        progress_thread.start()

        try:
            # Load the actual model
            embedding_model = TextEmbedding(model_name=model_name)

            # Stop progress bar
            progress_done[0] = True
            progress_thread.join()

            print("Embedding model initialized successfully.")
            print(f"Model ready: {type(embedding_model).__name__}")
            return embedding_model

        except Exception as e:
            # Stop progress bar on error
            progress_done = True
            progress_thread.join()
            print(f"Error initializing embedding model: {e}")
            raise


