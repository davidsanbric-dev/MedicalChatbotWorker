from sqlalchemy import Column, String, Text, TIMESTAMP, UUID, ForeignKey, Index, DDL, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
import uuid
from .database import Base

class RawData(Base):
    __tablename__ = "raw_data"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content = Column(JSONB, nullable=False)
    source = Column(String, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    # Relationship to processed data
    processed_data = relationship("ProcessedData", back_populates="raw_data")

    def __repr__(self):
        return f"<RawData(id={self.id}, source='{self.source}')>"

class ProcessedData(Base):
    __tablename__ = "processed_data"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    raw_data_id = Column(UUID(as_uuid=True), ForeignKey("raw_data.id"), nullable=False)
    content = Column(JSONB, nullable=False)
    processor_version = Column(String, nullable=False)  # e.g., "v5", "v4"
    condition_name = Column(String, nullable=False)  # e.g., "acne", "diabetes"
    processing_metadata = Column(JSONB)  # Processing stats, errors, etc.
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    # Relationships
    raw_data = relationship("RawData", back_populates="processed_data")
    documents = relationship("Document", back_populates="processed_data")

    def __repr__(self):
        return f"<ProcessedData(id={self.id}, condition='{self.condition_name}', version='{self.processor_version}')>"

class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    processed_data_id = Column(UUID(as_uuid=True), ForeignKey("processed_data.id", ondelete="SET NULL"), nullable=True)
    content = Column(Text, nullable=False)
    content_type = Column(String, nullable=False)  # "symptom", "paragraph", "list_item"
    metadata_ = Column(JSONB)
    embedding = Column(Vector(384))  # 384 dimensions for sentence-transformers model
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    # Relationship back to processed data
    processed_data = relationship("ProcessedData", back_populates="documents")

    __table_args__ = (
        Index('documents_embedding_idx', 'embedding', postgresql_using='ivfflat', postgresql_ops={'vector_cosine_ops'}, postgresql_with={'lists': 100}),
    )

    def __repr__(self):
        return f"<Document(id={self.id}, content='{self.content[:50]}...', type='{self.content_type}')>"

class ChatHistory(Base):
    __tablename__ = "chat_history"

    session_id = Column(String, primary_key=True)
    history = Column(JSONB, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<ChatHistory(session_id={self.session_id}, updated_at={self.updated_at})>"

# DDL for PostgreSQL-specific features
ddl_vector_extension = DDL("CREATE EXTENSION IF NOT EXISTS vector;")
event.listen(Base.metadata, 'after_create', ddl_vector_extension.execute_if(dialect='postgresql'))

ddl_search_function = DDL("""
CREATE OR REPLACE FUNCTION search_similar_documents(query_embedding vector(384), top_k integer)
RETURNS TABLE(id uuid, content text, metadata_ jsonb, similarity_score float)
LANGUAGE sql STABLE
AS $$
    SELECT
        d.id,
        d.content,
        d.metadata_,
        1 - (d.embedding <-> query_embedding) AS similarity_score
    FROM documents d
    ORDER BY d.embedding <-> query_embedding
    LIMIT top_k;
$$;
""")
event.listen(Base.metadata, 'after_create', ddl_search_function.execute_if(dialect='postgresql'))
