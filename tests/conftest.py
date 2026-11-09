import os
import sys
from pathlib import Path

# Importing the services package builds the SQLAlchemy engine, which needs a
# URL; no connection is opened by the pure chunking tests.
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:1/test")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
