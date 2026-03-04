import os
import re
import json
import asyncio
import random
import math
from typing import List, Dict, Tuple
from groq import AsyncGroq, RateLimitError

# ---------------------------------------------------------------------------
# Groq client pool — supports multiple API keys (comma-separated) for load
# distribution across Groq's free-tier rate limits.
# ---------------------------------------------------------------------------
GROQ_API_KEYS = [k.strip() for k in os.getenv("GROQ_API_KEY", "").split(",") if k.strip()]
clients = [AsyncGroq(api_key=key) for key in GROQ_API_KEYS]

# Semaphore: max concurrent Groq requests across all keys.
# With batching (5 questions/call) this handles large questionnaires well.
concurrency_limit = asyncio.Semaphore(max(len(clients) * 3, 6))

BATCH_SIZE = 5          # questions per LLM call
TOP_K = 5               # chunks retrieved per question
MAX_TOKENS = 1200       # enough for 5 answers in one call


def get_client() -> AsyncGroq | None:
    if not clients:
        return None
    return random.choice(clients)


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def chunk_text(text: str, chunk_size: int = 400, overlap: int = 40) -> List[str]:
    """Split text into overlapping word-level chunks."""
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunks.append(" ".join(words[i: i + chunk_size]))
        i += chunk_size - overlap
    return chunks


def pre_chunk_docs(reference_docs: List[Dict]) -> List[Dict]:
    """Pre-chunk all reference documents once — reused for every question."""
    print(f"[RAG] Pre-chunking {len(reference_docs)} reference document(s)...")
    all_chunks = []
    for doc in reference_docs:
        chunks = chunk_text(doc.get("content", ""))
        print(f"  '{doc.get('name', '?')}' → {len(chunks)} chunks")
        for chunk in chunks:
            all_chunks.append({"doc_name": doc.get("name", "Unknown"), "chunk": chunk})
    print(f"[RAG] Total chunks: {len(all_chunks)}")
    return all_chunks


# ---------------------------------------------------------------------------
# BM25 retrieval — much better than plain TF-IDF keyword overlap.
# Handles term frequency saturation and document-length normalisation so
# short precise chunks are not penalised vs. large rambling ones.
# No extra dependencies — pure Python.
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> List[str]:
    return re.findall(r"\w+", text.lower())


def build_bm25_index(chunks: List[Dict]) -> Dict:
    """Build BM25 index from pre-chunked docs. Call once, reuse many times."""
    corpus = [_tokenize(c["chunk"]) for c in chunks]
    N = len(corpus)
    avg_dl = sum(len(d) for d in corpus) / max(N, 1)

    # Document frequency for each term
    df: Dict[str, int] = {}
    for doc_tokens in corpus:
        for term in set(doc_tokens):
            df[term] = df.get(term, 0) + 1

    return {"corpus": corpus, "N": N, "avg_dl": avg_dl, "df": df}


def bm25_scores(query: str, index: Dict, k1: float = 1.5, b: float = 0.75) -> List[float]:
    """Return BM25 score for each chunk in the index."""
    query_terms = _tokenize(query)
    corpus = index["corpus"]
    N = index["N"]
    avg_dl = index["avg_dl"]
    df = index["df"]
    scores = []

    for doc_tokens in corpus:
        dl = len(doc_tokens)
        tf_map: Dict[str, int] = {}
        for t in doc_tokens:
            tf_map[t] = tf_map.get(t, 0) + 1

        score = 0.0
        for term in query_terms:
            if term not in tf_map:
                continue
            tf = tf_map[term]
            idf = math.log((N - df.get(term, 0) + 0.5) / (df.get(term, 0) + 0.5) + 1)
            numerator = tf * (k1 + 1)
            denominator = tf + k1 * (1 - b + b * dl / max(avg_dl, 1))
            score += idf * numerator / denominator
        scores.append(score)

    return scores


def retrieve_relevant_chunks(
    question: str,
    pre_chunked_docs: List[Dict],
    bm25_index: Dict,
    top_k: int = TOP_K,
) -> List[Dict]:
    """BM25 retrieval — returns top_k most relevant chunks for a question."""
    if not pre_chunked_docs:
        return []

    scores = bm25_scores(question, bm25_index)
    ranked = sorted(zip(scores, pre_chunked_docs), key=lambda x: x[0], reverse=True)

    results = []
    for score, chunk_info in ranked[:top_k]:
        if score > 0:
            results.append({
                "doc_name": chunk_info["doc_name"],
                "chunk": chunk_info["chunk"],
                "score": score,
            })
    return results


def compute_confidence(retrieved_chunks: List[Dict]) -> float:
    if not retrieved_chunks:
        return 0.0
    top_score = retrieved_chunks[0]["score"]
    # BM25 scores are typically 0–15; normalise to 0–1
    confidence = min(top_score / 10.0, 1.0)
    return round(confidence, 2)


# ---------------------------------------------------------------------------
# Batched LLM answering — one API call answers BATCH_SIZE questions at once.
# The model responds with a JSON array so we can parse each answer out.
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a precise questionnaire-answering assistant.
Answer each question using ONLY the provided reference document excerpts.

Rules:
- Be concise and factual. 1-2 paragraphs maximum per answer.
- If a question cannot be answered from the context, write exactly: "Not found in references."
- Do not invent information.
- Respond ONLY with a valid JSON array — one object per question — in this exact format:
[
  {"index": 0, "answer": "..."},
  {"index": 1, "answer": "..."}
]
No extra text, no markdown fences."""


def _build_batch_prompt(questions_with_context: List[Dict]) -> str:
    """Build a single prompt for a batch of questions, each with its own context."""
    parts = []
    for item in questions_with_context:
        i = item["index"]
        q = item["question"]
        ctx = "\n\n".join(
            f"[{c['doc_name']}]: {c['chunk']}" for c in item["chunks"]
        )
        parts.append(f"--- Question {i} ---\nContext:\n{ctx}\n\nQuestion: {q}")
    return "\n\n".join(parts)


async def _call_llm_batch(
    questions_with_context: List[Dict],
    attempt_override: int = 0,
) -> List[Dict]:
    """
    Send a batch of questions to Groq in a single call.
    Returns list of {index, answer, is_found}.
    """
    prompt = _build_batch_prompt(questions_with_context)
    max_retries = 4
    base_delay = 1.5

    for attempt in range(max_retries):
        client = get_client()
        if not client:
            break

        try:
            async with concurrency_limit:
                response = await client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=MAX_TOKENS,
                    temperature=0.1,
                )

            raw = response.choices[0].message.content.strip()

            # Strip markdown fences if the model adds them despite instructions
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)

            parsed = json.loads(raw)
            results = []
            for item in parsed:
                answer = str(item.get("answer", "")).strip()
                is_found = answer.lower() != "not found in references."
                results.append({
                    "index": item["index"],
                    "answer": answer,
                    "is_found": is_found,
                })
            return results

        except RateLimitError:
            delay = base_delay * (2 ** attempt) + random.uniform(0.3, 1.0)
            print(f"  [batch] Rate limited — retrying in {delay:.1f}s (attempt {attempt+1})")
            await asyncio.sleep(delay)

        except (json.JSONDecodeError, KeyError) as e:
            print(f"  [batch] JSON parse error on attempt {attempt+1}: {e}")
            # Retry once more; if it keeps failing fall back below
            if attempt < max_retries - 1:
                await asyncio.sleep(0.5)

        except Exception as e:
            print(f"  [batch] Unexpected error: {type(e).__name__} — {e}")
            break

    # Fallback: return mock answers for all questions in this batch
    return [
        {
            "index": item["index"],
            "answer": item["chunks"][0]["chunk"][:200] + "..." if item["chunks"] else "Not found in references.",
            "is_found": bool(item["chunks"]),
        }
        for item in questions_with_context
    ]


# ---------------------------------------------------------------------------
# Public API — called from answers.py
# ---------------------------------------------------------------------------

async def process_all_questions(
    questions: List[str],
    pre_chunked_docs: List[Dict],
) -> List[Dict]:
    """
    Full pipeline for ALL questions at once:
      1. Build BM25 index once
      2. Retrieve top-k chunks per question (fast, in-process)
      3. Group into batches of BATCH_SIZE
      4. Fire all batches concurrently via asyncio.gather
      5. Return results in original question order
    """
    print(f"[RAG] Building BM25 index over {len(pre_chunked_docs)} chunks...")
    bm25_index = build_bm25_index(pre_chunked_docs)

    # Retrieve context for every question
    questions_with_context = []
    for i, question in enumerate(questions):
        chunks = retrieve_relevant_chunks(question, pre_chunked_docs, bm25_index)
        questions_with_context.append({
            "index": i,
            "question": question,
            "chunks": chunks,
        })

    # Split into batches
    batches = [
        questions_with_context[i: i + BATCH_SIZE]
        for i in range(0, len(questions_with_context), BATCH_SIZE)
    ]
    print(f"[RAG] {len(questions)} questions → {len(batches)} batch(es) of ≤{BATCH_SIZE} — firing concurrently...")

    # Fire all batches concurrently
    batch_results = await asyncio.gather(*[_call_llm_batch(batch) for batch in batches])

    # Flatten and sort by original index
    flat: Dict[int, Dict] = {}
    for batch_result in batch_results:
        for item in batch_result:
            flat[item["index"]] = item

    # Build final output list in original order
    output = []
    for i, question in enumerate(questions):
        result = flat.get(i, {"answer": "Error in pipeline.", "is_found": False})
        qwc = questions_with_context[i]
        retrieved = qwc["chunks"]

        if not result["is_found"] or not retrieved:
            output.append({
                "answer": result["answer"],
                "citations": [],
                "confidence": 0.0,
                "evidence_snippets": [],
                "is_found": False,
            })
        else:
            output.append({
                "answer": result["answer"],
                "citations": [
                    {"doc_name": c["doc_name"], "snippet": c["chunk"][:150] + "..."}
                    for c in retrieved[:2]
                ],
                "confidence": compute_confidence(retrieved),
                "evidence_snippets": [c["chunk"][:200] for c in retrieved[:2]],
                "is_found": True,
            })

    print(f"[RAG] Done. {sum(1 for r in output if r['is_found'])} answered, "
          f"{sum(1 for r in output if not r['is_found'])} not found.")
    return output


# Keep process_question for the regenerate endpoint (single question)
async def process_question(question: str, pre_chunked_docs: List[Dict]) -> Dict:
    """Single-question pipeline used by the regenerate endpoint."""
    bm25_index = build_bm25_index(pre_chunked_docs)
    retrieved = retrieve_relevant_chunks(question, pre_chunked_docs, bm25_index)
    results = await _call_llm_batch([{"index": 0, "question": question, "chunks": retrieved}])
    result = results[0] if results else {"answer": "Error.", "is_found": False}

    if not result["is_found"] or not retrieved:
        return {
            "answer": result["answer"],
            "citations": [],
            "confidence": 0.0,
            "evidence_snippets": [],
            "is_found": False,
        }
    return {
        "answer": result["answer"],
        "citations": [
            {"doc_name": c["doc_name"], "snippet": c["chunk"][:150] + "..."}
            for c in retrieved[:2]
        ],
        "confidence": compute_confidence(retrieved),
        "evidence_snippets": [c["chunk"][:200] for c in retrieved[:2]],
        "is_found": True,
    }

