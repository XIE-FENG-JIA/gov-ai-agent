from src.knowledge.manager import KnowledgeBaseManager

def test_kb_add_and_search(tmp_path, mock_llm):
    """Test adding and searching documents in KB."""
    kb_dir = tmp_path / "kb_test"
    kb = KnowledgeBaseManager(str(kb_dir), mock_llm)
    
    # Test Stats (Empty)
    stats = kb.get_stats()
    assert stats["examples_count"] == 0

    # Test Add
    metadata = {"title": "Test Doc", "doc_type": "函"}
    doc_id = kb.add_example("This is a test content.", metadata)
    assert doc_id is not None
    assert kb.get_stats()["examples_count"] == 1

    # Test Search (Mocking the embedding query)
    # ChromaDB's query will run against the mock embedding [0.1, 0.1...]
    # Since we only have 1 doc, it should return it.
    results = kb.search_examples("query")
    assert len(results) == 1
    assert results[0]["metadata"]["title"] == "Test Doc"
