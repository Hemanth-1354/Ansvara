import os
import re
import asyncio
import random
from typing import List, Dict, Tuple
from groq import AsyncGroq, RateLimitError

# Load multiple API keys if provided (comma-separated)
GROQ_API_KEYS = [k.strip() for k in os.getenv(
    "GROQ_API_KEY", "").split(",") if k.strip()]
clients = [AsyncGroq(api_key=key) for key in GROQ_API_KEYS]

# Semaphore to limit total concurrent requests to Groq (across all keys)
# With 3 keys, 9 is a safe number (3 per key) to avoid hitting TPM limits.
concurrency_limit = asyncio.Semaphore(9)


def get_client():
    """Get a random client from the pool to distribute load."""
    if not clients:
        return None
    return random.choice(clients)


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


def pre_chunk_docs(reference_docs: List[Dict]) -> List[Dict]:
    """Pre-chunk all reference documents into a flat list of chunks."""
    print(
        f"[RAG Pipeline] Pre-chunking {len(reference_docs)} reference documents...")
    all_chunks = []
    for doc in reference_docs:
        chunks = chunk_text(doc.get("content", ""))
        print(
            f"  - Document '{doc.get('name', 'Unknown')}' split into {len(chunks)} chunks.")
        for chunk in chunks:
            all_chunks.append({"doc_name": doc.get(
                "name", "Unknown"), "chunk": chunk})
    print(f"[RAG Pipeline] Total chunks created: {len(all_chunks)}")
    return all_chunks


def retrieve_relevant_chunks(
    question: str,
    pre_chunked_docs: List[Dict],  # List of {"doc_name": str, "chunk": str}
    top_k: int = 3
) -> List[Dict]:
    """Retrieve top-k relevant chunks from pre-chunked documents."""
    print(
        f"[RAG Pipeline] Retrieving relevant chunks for: '{question[:50]}...'")
    if not pre_chunked_docs:
        print("  - WARNING: No pre-chunked documents available for retrieval.")
        return []

    texts = [c["chunk"] for c in pre_chunked_docs]
    scores = simple_tfidf_similarity(question, texts)

    ranked = sorted(zip(scores, pre_chunked_docs),
                    key=lambda x: x[0], reverse=True)
    top = ranked[:top_k]

    results = []
    for score, chunk_info in top:
        if score > 0:
            results.append({
                "doc_name": chunk_info["doc_name"],
                "chunk": chunk_info["chunk"],
                "score": score
            })

    print(
        f"  - Found {len(results)} relevant chunks (Top score: {results[0]['score'] if results else 0.0})")
    return results


def compute_confidence(retrieved_chunks: List[Dict]) -> float:
    """Compute confidence score from retrieval quality."""
    if not retrieved_chunks:
        return 0.0
    top_score = retrieved_chunks[0]["score"]
    # Normalize to 0-1 range with soft cap
    confidence = min(top_score * 2.5, 1.0)
    return round(confidence, 2)


async def answer_question_with_llm(
    question: str,
    context_chunks: List[Dict]
) -> Tuple[str, bool]:
    """Use Groq LLM to answer a question given context chunks with retries and concurrency control."""
    print(f"[LLM Service] Start processing question: '{question[:60]}...'")

    if not context_chunks:
        print(f"  - WARNING: No context chunks found for '{question[:30]}'.")
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

    max_retries = 3
    base_delay = 2

    for attempt in range(max_retries):
        client = get_client()
        if not client:
            print(f"  - ERROR: No Groq API keys found. Cannot generate answer.")
            return await _mock_answer(question, context_chunks), True

        try:
            print(f"  - Attempt {attempt + 1}: Waiting for semaphore...")
            # Small random jitter to stagger requests even within the semaphore
            await asyncio.sleep(random.uniform(0.1, 0.5))

            async with concurrency_limit:
                print(f"  - Attempt {attempt + 1}: Sending to Groq API...")
                response = await client.chat.completions.create(
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
                print(
                    f"  - Attempt {attempt + 1}: Success! (Found: {is_found})")
                return answer, is_found

        except RateLimitError:
            delay = base_delay * (2 ** attempt) + random.uniform(0.5, 1.5)
            print(
                f"  - Attempt {attempt + 1}: Rate limited. Retrying in {delay:.2f}s...")
            await asyncio.sleep(delay)
            continue

        except Exception as e:
            print(
                f"  - ERROR on Attempt {attempt + 1}: {type(e).__name__} - {str(e)}")
            # Fall back to mock if it's a persistent error
            return await _mock_answer(question, context_chunks), True

    print(f"  - Final: All {max_retries} retries exhausted for question.")
    return await _mock_answer(question, context_chunks), True


async def _mock_answer(question: str, chunks: List[Dict]) -> str:
    """Fallback mock answer when API key is not set."""
    await asyncio.sleep(0.1)  # Simulate some processing
    if not chunks:
        return "Not found in references."
    snippet = chunks[0]["chunk"][:200]
    return f"Based on the reference documents: {snippet}..."


async def process_question(
    question: str,
    pre_chunked_docs: List[Dict]
) -> Dict:
    """Full pipeline: retrieve → answer → format result."""
    try:
        retrieved = retrieve_relevant_chunks(
            question, pre_chunked_docs, top_k=3)
        answer_result = await answer_question_with_llm(question, retrieved)

        # answer_result should be a tuple (answer_text, is_found)
        if answer_result is None or not isinstance(answer_result, (tuple, list)):
            print(
                f"  - ERROR: answer_question_with_llm returned invalid type: {type(answer_result)}")
            answer, is_found = "Error in generation.", False
        else:
            answer, is_found = answer_result

        if not is_found or not retrieved:
            return {
                "answer": answer if not is_found else "Not found in references.",
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
    except Exception as e:
        print(f"  - CRITICAL ERROR in process_question pipeline: {str(e)}")
        return {
            "answer": "Error in generation pipeline.",
            "citations": [],
            "confidence": 0.0,
            "evidence_snippets": [],
            "is_found": False
        }
