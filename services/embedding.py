"""Turn passages into numbers: step 3 on https://medicalchatbot.demos.davieldev.com/worker
The meaning map on that page places every passage by its embedding.
"""

from functools import cache

import numpy as np
from fastembed import TextEmbedding

# Must stay identical to the API's query model (medical_conditions_api/app/core/embedding.py):
# passages are embedded here and questions there, and the two only compare in the same vector space.
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"  # 384 dimensions


@cache
def embedding_model() -> TextEmbedding:
    print(f"⏳ Loading the embedding model {EMBEDDING_MODEL}…")
    return TextEmbedding(EMBEDDING_MODEL)


def embed_passages(texts: list[str]) -> list[np.ndarray]:
    # batch_size=1: a batch pads every passage to the longest one in it,
    # which measured ~35% slower on this corpus.
    return list(embedding_model().passage_embed(texts, batch_size=1))
