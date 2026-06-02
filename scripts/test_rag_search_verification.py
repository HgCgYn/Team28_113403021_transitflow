#!/usr/bin/env python3
"""
TASK 6 EXTENSION: Test script for verifying RAG search through the agent layer
This simulates how the UI would interact with the search_policy tool
"""
import json
import sys
import os

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..")))

from skeleton.llm_provider import llm
from databases.relational.queries import query_policy_vector_search
from skeleton.config import VECTOR_SIMILARITY_THRESHOLD, VECTOR_TOP_K

def test_search_through_agent_layer():
    """Simulate how agent.py's search_policy tool works"""
    
    print("=" * 70)
    print("RAG SEARCH VERIFICATION TEST")
    print("=" * 70)
    print()
    
    # Test queries that should match refund policies
    test_queries = [
        "Can I get a refund for a delay?",
        "What is my compensation if the train is late?",
        "How much will I get back if my ticket is cancelled?",
        "Unrelated query about pizza recipes",  # Should return no results or low similarity
    ]
    
    for query_idx, query in enumerate(test_queries, 1):
        print(f"Test {query_idx}: '{query}'")
        print("-" * 70)
        
        # Step 1: Embed query using current LLM
        try:
            embedding = llm.embed(query)
            print(f"✓ Embedding generated ({len(embedding)} dimensions)")
        except Exception as e:
            print(f"✗ Embedding failed: {e}")
            continue
        
        # Step 2: Search with vector search
        try:
            docs = query_policy_vector_search(embedding)
            print(f"✓ Query executed (top_k={VECTOR_TOP_K})")
        except Exception as e:
            print(f"✗ Search failed: {e}")
            continue
        
        # Step 3: Verify results
        print(f"\nResults ({len(docs)} document(s) found with similarity > {VECTOR_SIMILARITY_THRESHOLD}):")
        
        if not docs:
            print("  (No results above threshold)")
        else:
            for i, doc in enumerate(docs, 1):
                similarity = doc.get("similarity", 0)
                title = doc.get("title", "N/A")
                category = doc.get("category", "N/A")
                
                # Verify threshold constraint
                if similarity <= VECTOR_SIMILARITY_THRESHOLD:
                    print(f"  [{i}] ✗ THRESHOLD VIOLATION: similarity {similarity:.3f} ≤ {VECTOR_SIMILARITY_THRESHOLD}")
                else:
                    print(f"  [{i}] ✓ {title} (category: {category}, similarity: {similarity:.3f})")
        
        print()
    
    # Summary statistics
    print("=" * 70)
    print("VERIFICATION SUMMARY")
    print("=" * 70)
    print(f"LLM Provider: {llm.chat_provider}")
    print(f"Embedding Dimension: {llm.embed_dim}")
    print(f"VECTOR_TOP_K: {VECTOR_TOP_K}")
    print(f"VECTOR_SIMILARITY_THRESHOLD: {VECTOR_SIMILARITY_THRESHOLD}")
    print()
    print("✅ All tests completed. Verify:")
    print("   1. All returned results have similarity > 0.5")
    print("   2. Related queries return multiple relevant documents")
    print("   3. Unrelated queries return few or no results")

if __name__ == "__main__":
    test_search_through_agent_layer()
