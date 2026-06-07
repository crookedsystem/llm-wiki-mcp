import asyncio

from personal_kb_mcp.vector.index import IndexedNote, NullVectorIndex, VectorSearchResult


def test_null_vector_index_accepts_index_and_delete_without_results() -> None:
    async def exercise_index() -> None:
        index = NullVectorIndex()
        note = IndexedNote(path="daily/today.md", content="Body", content_hash="abc")

        await index.upsert(note)
        results = await index.search("Body", limit=5)
        await index.delete("daily/today.md")

        assert results == []

    asyncio.run(exercise_index())


def test_vector_search_result_shape_is_stable() -> None:
    result = VectorSearchResult(path="daily/today.md", score=0.5, content_hash="abc")

    assert result.path == "daily/today.md"
    assert result.score == 0.5
    assert result.content_hash == "abc"
