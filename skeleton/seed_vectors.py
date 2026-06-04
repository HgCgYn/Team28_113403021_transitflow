"""
TransitFlow — pgvector Policy Document Seeder
Run once after starting Docker:
    python skeleton/seed_vectors.py

This script:
  1. Loads policy documents directly from train-mock-data/ JSON files
  2. Embeds each document using the configured LLM provider
  3. Stores the text + vector in PostgreSQL (policy_documents table)

Note: Gemini free tier has ~1500 requests/minute — this script makes ~13 calls, well within limits.

Students: To extend the assistant's knowledge, add entries to the JSON files in
train-mock-data/ and re-run this script.

# NOTE: This script dynamically adapts the vector column dimension and rebuilds
# the HNSW index to match the active LLM provider (768 for Ollama, 3072 for Gemini).
# This prevents the 'embedding dimension mismatch' error when switching providers.
"""

import json
import logging
import os
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s  %(message)s",
)
logger = logging.getLogger(__name__)

import psycopg2

sys.path.insert(0, ".")

from skeleton.config import PG_DSN
from skeleton.llm_provider import llm
from databases.relational.queries import store_policy_document

_DATA_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "train-mock-data")
)


def _load(filename):
    with open(os.path.join(_DATA_DIR, filename), encoding="utf-8") as f:
        return json.load(f)


def _text(data):
    return json.dumps(data, indent=2, ensure_ascii=False)


def build_documents():
    docs = []

    # refund_policy.json — one document per policy entry
    for policy in _load("refund_policy.json"):
        docs.append({
            "title": policy["label"],
            "category": "refund",
            "source_file": "refund_policy.json",
            "content": _text(policy),
        })

    # ticket_types.json — one document per ticket type
    for tt in _load("ticket_types.json"):
        docs.append({
            "title": f"Ticket Type: {tt['display_name']}",
            "category": "booking",
            "source_file": "ticket_types.json",
            "content": _text(tt),
        })

    # booking_rules.json — one document per network section
    br = _load("booking_rules.json")
    for section in ("national_rail", "metro", "general_rules"):
        if section in br:
            docs.append({
                "title": f"Booking Rules — {section.replace('_', ' ').title()}",
                "category": "booking",
                "source_file": "booking_rules.json",
                "content": _text({section: br[section]}),
            })

    # travel_policies.json — one document per network section
    tp = _load("travel_policies.json")
    for section in ("metro", "national_rail"):
        if section in tp:
            docs.append({
                "title": f"Travel Policies — {section.replace('_', ' ').title()}",
                "category": "conduct",
                "source_file": "travel_policies.json",
                "content": _text({section: tp[section]}),
            })

    return docs


def seed():
    documents = build_documents()

    if llm.embed_dim not in (768, 3072):
        raise ValueError(
            f"Unsupported embedding dimension: {llm.embed_dim}. "
            "Expected 768 for Ollama or 3072 for Gemini."
        )

    logger.info("Embedding %d policy documents using %s...", len(documents), llm.chat_provider)

    # Ensure script idempotency: clear existing policy documents and dynamically adapt embedding schema
    logger.info("Clearing existing policy documents and adapting embedding schema...")
    with psycopg2.connect(PG_DSN) as conn:
        with conn.cursor() as cur:
            # Step 1: Must truncate first—if old data exists and we alter the type, direct type conversion fails
            # RESTART IDENTITY resets the SERIAL id counter back to 1 for fresh sequence numbering
            cur.execute("TRUNCATE TABLE policy_documents RESTART IDENTITY;")
            
            # Step 2: Dynamically adjust column dimension (prevents crash when switching to Gemini 3072-dim vectors)
            # Drop index before altering column type
            cur.execute("DROP INDEX IF EXISTS idx_policy_documents_embedding;")
            cur.execute(f"ALTER TABLE policy_documents ALTER COLUMN embedding TYPE vector({llm.embed_dim});")
            
            # Step 3: Rebuild HNSW index (Note: pgvector's HNSW index supports max 2000 dimensions)
            # If embedding dimension exceeds 2000, skip HNSW and rely on exact search or IVFFlat
            if llm.embed_dim <= 2000:
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_policy_documents_embedding ON policy_documents USING hnsw (embedding vector_cosine_ops);"
                )
            else:
                logger.warning(
                    "Embedding dimension %d exceeds 2000 — pgvector HNSW index skipped. "
                    "Falling back to exact search.",
                    llm.embed_dim,
                )
        conn.commit()

    for i, doc in enumerate(documents):
        logger.info("[%d/%d] Embedding: %s", i + 1, len(documents), doc["title"])

        try:
            embedding = llm.embed(doc["content"])

            if len(embedding) != llm.embed_dim:
                logger.warning(
                    "Unexpected embedding dim: %d (expected %d). "
                    "Update GEMINI_EMBED_DIM or OLLAMA_EMBED_DIM in skeleton/config.py.",
                    len(embedding),
                    llm.embed_dim,
                )
                sys.exit(1)

            doc_id = store_policy_document(
                title=doc["title"],
                category=doc["category"],
                content=doc["content"],
                embedding=embedding,
                source_file=doc.get("source_file", ""),
            )
            logger.info("  OK  Stored as document id=%s", doc_id)

        except Exception as e:
            logger.error("Failed to embed/store document '%s': %s", doc["title"], e)
            raise

        if llm.chat_provider == "gemini" and i < len(documents) - 1:
            time.sleep(0.5)

    logger.info("All %d policy documents embedded and stored.", len(documents))
    logger.info(
        "Test with: query_policy_vector_search(llm.embed('can I get a refund for a delay?'))"
    )


if __name__ == "__main__":
    seed()
