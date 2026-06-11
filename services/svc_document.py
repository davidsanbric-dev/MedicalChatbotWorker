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
from utils import show_progress_spinner
from fastembed import TextEmbedding

# Note: SessionLocal import removed as repositories handle session management

class DocumentService:

    _cached_embedding_model: Optional[TextEmbedding] = None
    _cached_model_name: Optional[str] = None
    _embedding_model_lock = threading.Lock()

    @classmethod
    def _get_embedding_model(
        cls,
        embedding_model: Optional[TextEmbedding] = None,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
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
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
    ):
        """
        Generate embeddings from a ProcessedData record and save to Document table.

        Args:
            processed_data_id: UUID of the ProcessedData record
            embedding_model: Optional pre-initialized TextEmbedding model
            content_types: List of content types to process ["symptoms", "paragraphs", "lists"] (default: all)
            model_name: Model path used when lazily initializing the embedding model (ONNX model path)

        Returns:
            dict: {"created": int, "errors": int}
        """

        if content_types is None:
            content_types = ["symptoms", "paragraphs", "lists"]

        embedding_model = cls._get_embedding_model(embedding_model, model_name)

        try:
            # Get the ProcessedData record
            processed_data = processed_data_repository.find_by_id(processed_data_id)

            if not processed_data:
                print(f"❌ ProcessedData record {processed_data_id} not found")
                return {"created": 0, "errors": 1}

            content = processed_data.content
            condition_name = processed_data.condition_name

            created_count = 0
            error_count = 0

            print(f"🔄 Generating embeddings for {condition_name} (processed_data_id: {processed_data_id})")

            # Process symptoms
            if "symptoms" in content_types and "symptoms" in content:
                try:
                    symptoms_data = content["symptoms"]
                    if isinstance(symptoms_data, list) and len(symptoms_data) >= 2:
                        description = symptoms_data[0]
                        symptom_list = symptoms_data[1]
                        symptoms_text = f"{description} {', '.join(symptom_list)}" if isinstance(symptom_list, list) else str(description)

                        # Generate embedding
                        # embedding = embedding_model.encode([symptoms_text])[0]
                        embedding = list(embedding_model.passage_embed([symptoms_text]))[0]

                        # Create Document record using repository
                        document_repository.save(
                            processed_data_id=processed_data_id,
                            content=symptoms_text,
                            content_type="symptom",
                            embedding=embedding,
                            metadata={
                                "condition": condition_name,
                                "source": "symptoms",
                                "processor_version": processed_data.processor_version
                            }
                        )
                        created_count += 1
                        print("  ✅ Created symptom embedding")

                except Exception as e:
                    print(f"  ❌ Error processing symptoms: {e}")
                    error_count += 1

            # Process paragraphs
            if "paragraphs" in content_types and "onlineDiagnosingAndTreating" in content:
                try:
                    content_section = content["onlineDiagnosingAndTreating"].get("content", {})
                    paragraphs = content_section.get("paragraphs", [])

                    for i, paragraph in enumerate(paragraphs):
                        if isinstance(paragraph, str) and paragraph.strip():
                            # Generate embedding
                            # embedding = embedding_model.encode([paragraph])[0]
                            embedding = list(embedding_model.passage_embed([paragraph]))[0]

                            # Create Document record using repository
                            document_repository.save(
                                processed_data_id=processed_data_id,
                                content=paragraph,
                                content_type="paragraph",
                                embedding=embedding,
                                metadata={
                                    "condition": condition_name,
                                    "source": "paragraph",
                                    "paragraph_index": i,
                                    "processor_version": processed_data.processor_version
                                }
                            )
                            created_count += 1

                    if paragraphs:
                        print(f"  ✅ Created {len(paragraphs)} paragraph embeddings")

                except Exception as e:
                    print(f"  ❌ Error processing paragraphs: {e}")
                    error_count += 1

            # Process lists
            if "lists" in content_types and "onlineDiagnosingAndTreating" in content:
                try:
                    content_section = content["onlineDiagnosingAndTreating"].get("content", {})
                    lists = content_section.get("lists", [])

                    for i, list_item in enumerate(lists):
                        # Convert list structure to text
                        if isinstance(list_item, list) and len(list_item) >= 2:
                            # Format: [heading, content]
                            heading = list_item[0]
                            list_content = list_item[1]

                            if isinstance(list_content, dict) and "items" in list_content:
                                items_text = ", ".join([str(item) for item in list_content["items"]])
                                full_text = f"{heading}: {items_text}"
                            else:
                                full_text = f"{heading}: {str(list_content)}"

                            # Generate embedding
                            # embedding = embedding_model.encode([full_text])[0]
                            embedding = list(embedding_model.passage_embed([full_text]))[0]

                            # Create Document record using repository
                            document_repository.save(
                                processed_data_id=processed_data_id,
                                content=full_text,
                                content_type="list_item",
                                embedding=embedding,
                                metadata={
                                    "condition": condition_name,
                                    "source": "list",
                                    "list_index": i,
                                    "processor_version": processed_data.processor_version
                                }
                            )
                            created_count += 1

                    if lists:
                        print(f"  ✅ Created {len(lists)} list item embeddings")

                except Exception as e:
                    print(f"  ❌ Error processing lists: {e}")
                    error_count += 1

            # All documents created via repositories, no session management needed

            print(f"🎉 Embedding generation complete: {created_count} created, {error_count} errors")
            return {"created": created_count, "errors": error_count}

        except Exception as e:
            print(f"❌ Error generating embeddings: {e}")
            return {"created": 0, "errors": 1}

    @staticmethod
    def initialize_embedding_model(model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
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


