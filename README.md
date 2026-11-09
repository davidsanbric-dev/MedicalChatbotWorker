# Medical Conditions Worker

The **Medical Conditions Worker** is a database-driven processing module that transforms raw scraped medical condition data into structured, searchable content with vector embeddings. This worker is part of a multi-stage ETL pipeline that processes data from the `raw_data` table through to the `documents` table with pgvector embeddings.

## 🏗️ Architecture Overview

The worker is part of a **3-stage ETL pipeline architecture**:

1. **medical_conditions_scraper/**: Data collection → `raw_data` table
2. **medical_conditions_worker/**: Data processing → `processed_data` → `documents` table (this component)
3. **medical_conditions_api/**: API service for RAG-powered queries

```
PostgreSQL Database Pipeline:
├── raw_data              # Stage 1: Raw scraped JSON from Medical
│   └── [Scraper writes here]
├── processed_data        # Stage 2: Cleaned, structured data (processor v6)
│   └── [Worker processes from raw_data]
└── documents             # Stage 3: Text chunks with vector embeddings
    └── [Worker generates embeddings from processed_data]
```

## 🚀 Features

### Database-Driven Processing
- **RawData → ProcessedData**: Transforms raw JSON into structured, cleaned, Unicode-normalized data (processor `v6`)
- **Automatic Discovery**: Lists available conditions directly from `raw_data` table
- **Versioned & Idempotent**: Raw records already processed by the current processor version are skipped; output of an older version is replaced (with its documents) in one transaction
- **Condition Filtering**: Process all conditions or target specific ones

### Embedding Generation
- **ProcessedData → Documents**: Generates vector embeddings for all processed content
- **Structure-Aware Chunking**: One chunk for the symptom list, one per paragraph and one per list; nested lists are rendered as readable indented bullets (`services/chunking.py`, unit-tested)
- **Idempotent**: Records that already have documents are skipped; `--reembed` replaces a record's documents atomically
- **fastembed (ONNX, CPU)**: `BAAI/bge-small-en-v1.5` (384 dimensions), the same model the API uses for queries
- **Lazy Model Loading**: Caches embedding model for performance

### Service Architecture
- **Service Layer**: Business logic in `services/` (DocumentService, ProcessedDataService)
- **Repository Layer**: Database access in `repositories/` (raw_data, processed_data, document)
- **Utility Functions**: Shared helpers in `utils.py` for data processing
- **Thread-Safe**: Embedding model caching with thread locks

### Database Integration
- **PostgreSQL with pgvector**: Native vector similarity search support
- **Shared Database Models**: Uses same models as db service via volume mount
- **Service Dependencies**: Waits for postgres health and db migrations

## 📦 Installation

### Prerequisites
- Python 3.12+
- Docker and Docker Compose (recommended)
- PostgreSQL with pgvector extension

### Docker Setup (Recommended)

1. **Build the worker container**:
   ```bash
   docker compose build worker
   ```

2. **Verify installation**:
   ```bash
   docker compose run --rm worker python main.py --help
   ```

### Local Development Setup

1. **Navigate to worker directory**:
   ```bash
   cd medical_conditions_worker
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Set environment variables**:
   ```bash
   export DATABASE_URL="postgresql://postgres:password@localhost:5434/medical_conditions_db"
   ```

4. **Verify installation**:
   ```bash
   python main.py --help
   ```

## 🖥️ Usage

### Command Line Interface

#### List Available Conditions
```bash
# List all conditions from raw_data table
python main.py --list-conditions

# Docker
docker compose run --rm worker python main.py --list-conditions
```

#### Process All Conditions
```bash
# Process all conditions from raw_data → processed_data → documents
python main.py

# Docker
docker compose run --rm worker python main.py
```

#### Re-embed After Changing Chunking or the Embedding Model
```bash
# Replace existing documents instead of skipping already-embedded records
python main.py --reembed
python main.py --reembed --condition Acne
```

#### Process Specific Condition
```bash
# Process specific condition by name
python main.py --condition acne
python main.py --condition "acid-reflux-gerd"

# Alternative flag syntax
python main.py --allergies

# Docker
docker compose run --rm worker python main.py --condition acne
```

### Docker Integration

The worker runs as part of the Docker Compose stack with proper dependencies:

```bash
# Run full pipeline: scraper → worker → api → frontend
docker compose up

# Run worker only (after postgres and db migrations)
docker compose up postgres db
docker compose run --rm worker python main.py
```

**Service Dependencies** (from docker-compose.yml):
```yaml
worker:
  depends_on:
    postgres:
      condition: service_healthy
    db:
      condition: service_completed_successfully
```

### Programmatic Usage

#### Using Services

```python
from services import DocumentService, ProcessedDataService
from repositories import raw_data_repository, processed_data_repository

# Initialize services
document_service = DocumentService()
processed_data_service = ProcessedDataService()

# List available conditions
conditions = raw_data_repository.list_condition_names()
print(f"Available conditions: {conditions}")

# Process specific condition from raw_data
stats = processed_data_service.process_from_raw_data(condition_filter="acne")
print(f"Processed: {stats['successful']}, Failed: {stats['failed']}")

# Generate embeddings for all processed data
processed_records = processed_data_repository.find_all()
for record in processed_records:
    result = document_service.generate_embeddings_from_processed_data(str(record.id))
    print(f"{record.condition_name}: Created {result['created']} documents")
```

#### Direct Repository Access

```python
from repositories import raw_data_repository, processed_data_repository, document_repository

# Get raw data
raw_data = raw_data_repository.find_by_condition_name("acne")

# Get processed data
processed_data = processed_data_repository.find_by_condition_name("acne")

# Query documents
documents = document_repository.find_by_processed_data_id(processed_data.id)
```

## 📊 Data Flow

### Complete ETL Pipeline

```
1. Web Scraping (Scraper)
   ├─→ Medical Website
   └─→ raw_data table (PostgreSQL)
       ├─ id: UUID
       ├─ content: JSONB (raw HTML/JSON)
       ├─ source: VARCHAR (condition slug)
       └─ created_at: TIMESTAMP

2. Data Processing (Worker - ProcessedDataService)
   ├─→ Read from raw_data table
   ├─→ Apply the v6 processor (normalize, clean, structure, deduplicate)
   └─→ processed_data table (PostgreSQL)
       ├─ id: UUID
       ├─ raw_data_id: UUID (foreign key)
       ├─ content: JSONB (structured data)
       ├─ processor_version: VARCHAR ("v6")
       ├─ condition_name: VARCHAR
       ├─ processing_metadata: JSONB
       └─ created_at: TIMESTAMP

3. Embedding Generation (Worker - DocumentService)
   ├─→ Read from processed_data table
   ├─→ Chunk content (symptoms, paragraphs, lists)
   ├─→ Generate embeddings (fastembed, bge-small-en-v1.5)
   └─→ documents table (PostgreSQL + pgvector)
       ├─ id: UUID
       ├─ processed_data_id: UUID (foreign key)
       ├─ content: TEXT (chunk text)
       ├─ content_type: VARCHAR (symptom/paragraph/list_item)
       ├─ metadata_: JSONB
       ├─ embedding: VECTOR(384)
       └─ created_at: TIMESTAMP

4. API Consumption (API Service)
   ├─→ Query documents table with vector similarity
   ├─→ RAG-powered responses using embeddings
   └─→ HTTP endpoints for frontend
```

## 🔧 Configuration

### Processing Version

`PROCESSOR_VERSION` in `services/svc_processed_data.py` is currently **v6**. Bump it whenever the
processed output changes: on the next run every raw record processed by an older version is
re-processed, and its old `processed_data` row and documents are replaced in one transaction.

- **v6**: Unicode normalization (NFKC), so non-breaking spaces become plain spaces
- **v5**: title normalization and condition name extraction
- Nested list deduplication
- Paragraph and content item processing
- Metadata extraction and cleaning
- Processing statistics tracking

### Embedding Configuration

```python
# Default embedding model (must match medical_conditions_api/app/core/embedding.py)
DEFAULT_EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIMENSION = 384

# Supported content types
CONTENT_TYPES = ["symptoms", "paragraphs", "lists"]
```

### Database Configuration

Configured via environment variables:
```env
DATABASE_URL=postgresql://postgres:password@postgres:5432/medical_conditions_db
```

**Shared Database Models**: Worker uses the same database models via volume mount:
```dockerfile
# From docker-compose.yml
volumes:
  - ./medical_conditions_db:/app/database
```

## 📁 Directory Structure

```
medical_conditions_worker/
├── main.py                        # Main CLI entry point
├── requirements.txt               # Python dependencies
├── Dockerfile                     # Container configuration
├── README.md                      # This documentation
├── utils.py                       # Shared utility functions
├── services/                      # Business logic layer
│   ├── __init__.py               # Service exports
│   ├── svc_processed_data.py    # ProcessedData business logic
│   └── svc_document.py          # Document embedding logic
└── repositories/                  # Data access layer
    ├── __init__.py               # Repository exports
    ├── rps_raw_data.py          # RawData database access
    ├── rps_processed_data.py    # ProcessedData database access
    └── rps_document.py          # Document database access

# Shared database configuration (mounted from medical_conditions_db)
/app/database/                     # Volume-mounted shared database module
├── database.py                    # Database connection and SessionLocal
└── models.py                      # SQLAlchemy models (RawData, ProcessedData, Document)
```

## 🔄 Integration with Main System

### Service Architecture

```
Docker Compose Dependency Chain:
postgres (healthy) → db (migrations) → worker → api → frontend
```

### Shared Components

1. **Database Models**: Via volume mount from `medical_conditions_db/`
   - `models.py`: RawData, ProcessedData, Document, ChatHistory
   - `database.py`: SessionLocal, engine configuration

2. **Environment Variables**: Shared `.env` configuration
   - DATABASE_URL for PostgreSQL connection
   - Consistent configuration across all services

### Data Consistency

- **Single Source of Truth**: All services use the same PostgreSQL database
- **Foreign Key Relationships**: Maintains referential integrity across tables
- **Atomic Operations**: Repository layer ensures transaction consistency

### Execution Flow

1. **Scraper** populates `raw_data` table
2. **Worker** processes `raw_data` → `processed_data`
3. **Worker** generates embeddings → `documents` table
4. **API** queries `documents` for RAG responses
5. **Frontend** displays results to users

## 🚨 Error Handling

### Common Issues and Solutions

#### Database Connection Errors
```bash
# Problem: Cannot connect to PostgreSQL
# Solution: Ensure postgres service is running and healthy
docker compose up -d postgres
docker compose ps postgres

# Check DATABASE_URL environment variable
echo $DATABASE_URL
```

#### Missing Dependencies
```bash
# Problem: ImportError for langchain_huggingface or sentence-transformers
# Solution: Reinstall dependencies
pip install -r requirements.txt

# For Docker
docker compose build worker
```

#### Processing Errors
```bash
# Problem: No conditions found in raw_data table
# Solution: Run scraper first to populate raw_data
docker compose run --rm scraper python main.py --all --database

# Check raw_data table
docker compose exec postgres psql -U postgres -d medical_conditions_db -c "SELECT COUNT(*) FROM raw_data;"
```

#### Re-running and Reprocessing
```bash
# Re-running is safe: processed records at the current version and
# already-embedded records are skipped, so nothing is duplicated.
python main.py

# Rebuild the documents (e.g. after changing chunking rules or the model)
python main.py --reembed

# Reprocess everything: bump PROCESSOR_VERSION, then run normally
```

## 🧪 Tests

```bash
uv run pytest        # chunking and normalization rules (no database needed)
```

## 📈 Performance Considerations

### CPU vs GPU
- **Default**: CPU-optimized for broad compatibility
- **GPU Support**: Modify requirements.txt for CUDA support:
  ```
  torch>=2.0.0,<2.5.0+cu118  # For CUDA 11.8
  ```
- **Memory Usage**: ~1-2GB RAM for embedding model

### Processing Performance
- **Batch Processing**: Processes all conditions sequentially
- **Duplicate Skip**: Automatically skips already-processed conditions
- **Database Transactions**: Individual commits for data integrity
- **Embedding Caching**: Model is loaded once and reused (thread-safe)

### Scaling Strategies
- **Horizontal**: Run multiple worker instances with condition filters
  ```bash
  docker compose run --rm worker python main.py --condition acne
  docker compose run --rm worker python main.py --condition diabetes
  ```
- **Vertical**: Increase memory/CPU allocation in docker-compose.yml
- **Parallel Processing**: Process different conditions in separate containers

### Database Indexing
- **pgvector HNSW (cosine)**: Created by the API at startup. Unlike ivfflat it needs no rebuild after the worker loads embeddings. At the current size Postgres still prefers an exact scan.
- **Foreign Keys**: Indexed relationships between tables
- **UUID Primary Keys**: Fast lookups and relationships

## 🧪 Testing

### Manual Testing

```bash
# 1. Test listing conditions
docker compose run --rm worker python main.py --list-conditions

# 2. Test processing specific condition
docker compose run --rm worker python main.py --condition acne

# 3. Verify processed_data table
docker compose exec postgres psql -U postgres -d medical_conditions_db \
  -c "SELECT condition_name, processor_version, created_at FROM processed_data;"

# 4. Verify documents table with embeddings
docker compose exec postgres psql -U postgres -d medical_conditions_db \
  -c "SELECT COUNT(*), content_type FROM documents GROUP BY content_type;"

# 5. Test vector similarity search
docker compose exec postgres psql -U postgres -d medical_conditions_db \
  -c "SELECT content FROM documents WHERE content_type='symptom' LIMIT 5;"
```

### Integration Testing

```bash
# Full pipeline test
docker compose up -d postgres db
docker compose run --rm scraper python main.py --condition acne --database
docker compose run --rm worker python main.py --condition acne
docker compose up -d api
curl http://localhost:8000/health
```

## 🤝 Contributing

### Development Setup
1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Set up PostgreSQL with pgvector extension
4. Configure DATABASE_URL environment variable
5. Run migrations: `docker compose up db`
6. Make changes and test thoroughly

### Code Style
- Follow PEP 8 guidelines
- Use type hints for function parameters and returns
- Document functions with descriptive docstrings
- Implement proper error handling and logging
- Use repository pattern for database access
- Keep services focused on business logic

### Architecture Patterns
- **Service Layer**: Business logic and orchestration
- **Repository Layer**: Database operations and queries
- **Utilities**: Shared helper functions
- **Dependency Injection**: Services use repositories, not direct DB access

## 📝 License

This project is part of the Medical Conditions system and follows the same licensing terms as the parent project.

## 🆘 Support

For issues, questions, or contributions:
1. Check the database connection and ensure postgres is healthy
2. Verify environment variables are correctly set
3. Review Docker logs: `docker compose logs worker`
4. Check PostgreSQL logs: `docker compose logs postgres`
5. Test with a single condition first before processing all
6. Provide detailed error messages and logs when reporting issues

### Useful Debug Commands

```bash
# Check worker service status
docker compose ps worker

# View worker logs
docker compose logs worker -f

# Access database
docker compose exec postgres psql -U postgres -d medical_conditions_db

# Count records in each table
docker compose exec postgres psql -U postgres -d medical_conditions_db \
  -c "SELECT 'raw_data' as table, COUNT(*) FROM raw_data 
      UNION ALL 
      SELECT 'processed_data', COUNT(*) FROM processed_data 
      UNION ALL 
      SELECT 'documents', COUNT(*) FROM documents;"
```

---

**Note**: This worker is a critical component of the database-driven ETL pipeline, transforming raw scraped data into searchable vector embeddings for RAG-powered medical condition queries.