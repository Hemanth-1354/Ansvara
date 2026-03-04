import os
import re
from typing import List, Dict, Tuple
from groq import Groq

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    """Split text into overlapping chunks."""
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i:i + chunk_size])
        chunks.append(chunk)
        i += chunk_size - overlap
    return chunks


def simple_tfidf_similarity(query: str, chunks: List[str]) -> List[float]:
    """Simple keyword-based relevance scoring without heavy dependencies."""
    query_words = set(re.findall(r'\w+', query.lower()))
    scores = []
    for chunk in chunks:
        chunk_words = re.findall(r'\w+', chunk.lower())
        chunk_word_set = set(chunk_words)
        if not chunk_words:
            scores.append(0.0)
            continue
        # TF-IDF approximation: intersection over chunk length
        intersection = query_words & chunk_word_set
        score = len(intersection) / (len(chunk_words) ** 0.5 + 1)
        scores.append(score)
    return scores


def retrieve_relevant_chunks(
    question: str,
    reference_docs: List[Dict],  # [{"name": str, "content": str}]
    top_k: int = 3
) -> List[Dict]:
    """Retrieve top-k relevant chunks from reference documents."""
    all_chunks = []
    for doc in reference_docs:
        chunks = chunk_text(doc["content"])
        for chunk in chunks:
            all_chunks.append({"doc_name": doc["name"], "chunk": chunk})

    if not all_chunks:
        return []

    texts = [c["chunk"] for c in all_chunks]
    scores = simple_tfidf_similarity(question, texts)

    ranked = sorted(zip(scores, all_chunks), key=lambda x: x[0], reverse=True)
    top = ranked[:top_k]

    results = []
    for score, chunk_info in top:
        if score > 0:
            results.append({
                "doc_name": chunk_info["doc_name"],
                "chunk": chunk_info["chunk"],
                "score": score
            })
    return results


def compute_confidence(retrieved_chunks: List[Dict]) -> float:
    """Compute confidence score from retrieval quality."""
    if not retrieved_chunks:
        return 0.0
    top_score = retrieved_chunks[0]["score"]
    # Normalize to 0-1 range with soft cap
    confidence = min(top_score * 2.5, 1.0)
    return round(confidence, 2)


def answer_question_with_llm(
    question: str,
    context_chunks: List[Dict]
) -> Tuple[str, bool]:
    """Use Groq LLM to answer a question given context chunks."""
    if not context_chunks:
        return "Not found in references.", False

    context = "\n\n".join([
        f"[Source: {c['doc_name']}]\n{c['chunk']}"
        for c in context_chunks
    ])

    system_prompt = """You are a precise questionnaire-answering assistant. 
Your job is to answer questions using ONLY the provided reference documents.
Rules:
- Answer concisely and factually based only on the context provided.
- If the context does not contain enough information to answer, respond with exactly: "Not found in references."
- Do not make up information.
- Keep answers 1-3 paragraphs maximum.
- Be specific and professional."""

    user_prompt = f"""Reference Documents:
{context}

Question: {question}

Answer based strictly on the reference documents above:"""

    if not client:
        return _mock_answer(question, context_chunks), True

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=400,
            temperature=0.1
        )
        answer = response.choices[0].message.content.strip()
        is_found = answer.lower() != "not found in references."
        return answer, is_found
    except Exception as e:
        print(f"Groq API error: {e}")
        return _mock_answer(question, context_chunks), True


def _mock_answer(question: str, chunks: List[Dict]) -> str:
    """Fallback mock answer when API key is not set."""
    if not chunks:
        return "Not found in references."
    snippet = chunks[0]["chunk"][:200]
    return f"Based on the reference documents: {snippet}..."


def process_question(
    question: str,
    reference_docs: List[Dict]
) -> Dict:
    """Full pipeline: retrieve → answer → format result."""
    retrieved = retrieve_relevant_chunks(question, reference_docs, top_k=3)
    answer, is_found = answer_question_with_llm(question, retrieved)

    if not is_found or not retrieved:
        return {
            "answer": "Not found in references.",
            "citations": [],
            "confidence": 0.0,
            "evidence_snippets": [],
            "is_found": False
        }

    citations = [
        {"doc_name": c["doc_name"], "snippet": c["chunk"][:150] + "..."}
        for c in retrieved[:2]
    ]
    evidence_snippets = [c["chunk"][:200] for c in retrieved[:2]]
    confidence = compute_confidence(retrieved)

    return {
        "answer": answer,
        "citations": citations,
        "confidence": confidence,
        "evidence_snippets": evidence_snippets,
        "is_found": True
    }
