"""Unit tests for the Hybrid RAG pipeline and multilingual retrieval."""

from langchain_core.documents import Document

from backend.rag.hybrid_retriever import hybrid_retriever
from backend.rag.ingestion import split_legal_document


def test_split_legal_document_preserves_articles():
    """Verifies that legal splitter correctly segments text by Article / § boundaries."""
    raw_legal_text = """
    Article 5: Prohibited Practices
    Certain AI practices such as social scoring are prohibited.

    Article 6: High-Risk Classification
    AI systems in Annex III are classified as high risk.
    """
    chunks = split_legal_document(
        text=raw_legal_text,
        source_doc="EU AI Act Test",
        default_sec="Article 5",
        language="en",
    )

    assert len(chunks) >= 2
    assert any("Article 5" in doc.page_content for doc in chunks)
    assert any("Article 6" in doc.page_content for doc in chunks)


def test_bm25_language_separation():
    """Verifies that separate English and German BM25 indexes are maintained."""
    sample_docs = [
        Document(
            page_content="High-risk AI systems in banking require human oversight and risk management.",
            metadata={"language": "en", "source_document": "EU AI Act", "article_section_id": "Article 14"}
        ),
        Document(
            page_content="Institute müssen über angemessene Verfahren zur Steuerung von Modellrisiken verfügen.",
            metadata={"language": "de", "source_document": "MaRisk", "article_section_id": "AT 4.3.2"}
        ),
    ]

    hybrid_retriever.build_bm25_indexes(sample_docs)
    assert hybrid_retriever.bm25_en is not None
    assert hybrid_retriever.bm25_de is not None

    # English query should match English index
    en_results = hybrid_retriever.bm25_en.invoke("human oversight banking")
    assert len(en_results) > 0
    assert en_results[0].metadata["language"] == "en"

    # German query should match German index
    de_results = hybrid_retriever.bm25_de.invoke("Modellrisiken Steuerung Institute")
    assert len(de_results) > 0
    assert de_results[0].metadata["language"] == "de"
