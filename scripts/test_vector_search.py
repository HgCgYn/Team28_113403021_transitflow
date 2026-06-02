# TASK 6 EXTENSION: Test script for verifying vector search retrieval
import json
import sys
import os

# Ensure repo root is on sys.path when executed from scripts/
sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..")))

from skeleton.llm_provider import llm
from databases.relational.queries import query_policy_vector_search

q = "Can I get a refund for a delay?"
emb = llm.embed(q)
res = query_policy_vector_search(emb, top_k=5)
print(json.dumps(res, indent=2, default=str))
