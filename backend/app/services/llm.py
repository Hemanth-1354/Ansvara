import os
import re
import asyncio
import random
import math
from typing import List, Dict
from groq import AsyncGroq, RateLimitError, APIStatusError

# ---------------------------------------------------------------------------
# Groq client pool — one semaphore PER KEY so keys never compete with each other.
# With 4 keys x 6,000 TPM = 24,000 TPM total.
# Round-robin assignment means Q0→key0, Q1→key1, Q2→key2, Q3→key3, Q4→key0...
# ---------------------------------------------------------------------------
GROQ_API_KEYS = [k.strip() for k in os.getenv("GROQ_API_KEY", "").split(",") if k.strip()]

KEY_POOL = [
    {"client": AsyncGroq(api_key=key), "sem": asyncio.Semaphore(1)}
    for key in GROQ_API_KEYS
] if GROQ_API_KEYS else []

TOP_K = 3            # BM25 chunks retrieved per question
CONTEXT_WORDS = 250  # words per chunk sent to LLM (~330 tokens/chunk)
MAX_TOKENS = 300     # answer length cap — concise = faster


def _get_key_for_index(i: int):
    if not KEY_POOL:
        return None
    return KEY_POOL[i % len(KEY_POOL)]


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def chunk_text(text: str, chunk_size: int = 400, overlap: int = 40) -> List[str]:
    words = text.split()
    chunks, i = [], 0
    while i < len(words):
        chunks.append(" ".join(words[i: i + chunk_size]))
        i += chunk_size - overlap
    return chunks


def pre_chunk_docs(reference_docs: List[Dict]) -> List[Dict]:
    print(f"[RAG] Pre-chunking {len(reference_docs)} reference document(s)...")
    all_chunks = []
    for doc in reference_docs:
        chunks = chunk_text(doc.get("content", ""))
        print(f"  '{doc.get('name', '?')}' -> {len(chunks)} chunks")
        for chunk in chunks:
            all_chunks.append({"doc_name": doc.get("name", "Unknown"), "chunk": chunk})
    print(f"[RAG] Total chunks: {len(all_chunks)}")
    return all_chunks


# ---------------------------------------------------------------------------
# BM25 retrieval — pure Python, no dependencies
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> List[str]:
    return re.findall(r"\w+", text.lower())


def build_bm25_index(chunks: List[Dict]) -> Dict:
    corpus = [_tokenize(c["chunk"]) for c in chunks]
    N = len(corpus)
    avg_dl = sum(len(d) for d in corpus) / max(N, 1)
    df: Dict[str, int] = {}
    for doc_tokens in corpus:
        for term in set(doc_tokens):
            df[term] = df.get(term, 0) + 1
    return {"corpus": corpus, "N": N, "avg_dl": avg_dl, "df": df}


def _bm25_scores(query: str, index: Dict, k1: float = 1.5, b: float = 0.75) -> List[float]:
    query_terms = _tokenize(query)
    corpus, N, avg_dl, df = index["corpus"], index["N"], index["avg_dl"], index["df"]
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
            score += idf * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * dl / max(avg_dl, 1)))
        scores.append(score)
    return scores


def retrieve_relevant_chunks(question: str, pre_chunked_docs: List[Dict], bm25_index: Dict) -> List[Dict]:
    if not pre_chunked_docs:
        return []
    scores = _bm25_scores(question, bm25_index)
    ranked = sorted(zip(scores, pre_chunked_docs), key=lambda x: x[0], reverse=True)
    return [
        {"doc_name": ci["doc_name"], "chunk": ci["chunk"], "score": sc}
        for sc, ci in ranked[:TOP_K] if sc > 0
    ]


def compute_confidence(chunks: List[Dict]) -> float:
    if not chunks:
        return 0.0
    return round(min(chunks[0]["score"] / 10.0, 1.0), 2)


def _trim(text: str, max_words: int = CONTEXT_WORDS) -> str:
    words = text.split()
    return " ".join(words[:max_words]) + ("..." if len(words) > max_words else "")


# ---------------------------------------------------------------------------
# Single-question LLM call — small prompt, pinned to one key
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are a precise questionnaire-answering assistant. "
    "Answer using ONLY the reference text provided. "
    "Be concise: 2 to 4 sentences maximum. "
    'If the answer is not in the text, reply exactly: "Not found in references." '
    "No preamble, no markdown."
)


def _build_prompt(question: str, chunks: List[Dict]) -> str:
    context = "\n\n".join(
        f"[{c['doc_name']}]:\n{_trim(c['chunk'])}" for c in chunks
    )
    return f"Reference text:\n{context}\n\nQuestion: {question}\n\nAnswer:"


async def _call_single(question: str, chunks: List[Dict], key_entry, question_index: int) -> Dict:
    """Call Groq for ONE question using its assigned key. Retries on rate limit."""
    if not chunks:
        return {"answer": "Not found in references.", "is_found": False}

    if key_entry is None:
        # No API keys configured — return raw snippet as fallback
        return {"answer": _trim(chunks[0]["chunk"], 60), "is_found": True}

    client = key_entry["client"]
    sem = key_entry["sem"]
    current_chunks = list(chunks)
    prompt = _build_prompt(question, current_chunks)
    max_retries = 5
    base_delay = 1.0

    for attempt in range(max_retries):
        try:
            async with sem:
                response = await client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=MAX_TOKENS,
                    temperature=0.1,
                )
            answer = response.choices[0].message.content.strip()
            is_found = answer.lower() != "not found in references."
            return {"answer": answer, "is_found": is_found}

        except RateLimitError:
            delay = base_delay * (2 ** attempt) + random.uniform(0.2, 0.8)
            key_num = question_index % len(KEY_POOL)
            print(f"  [Q{question_index}] Rate limit on key {key_num} — retry in {delay:.1f}s")
            await asyncio.sleep(delay)

        except APIStatusError as e:
            if e.status_code == 413:
                # Still too large — trim context harder and retry immediately
                current_chunks = [{**c, "chunk": _trim(c["chunk"], 100)} for c in current_chunks[:2]]
                prompt = _build_prompt(question, current_chunks)
                print(f"  [Q{question_index}] 413 too large — trimming context, retrying")
                continue
            print(f"  [Q{question_index}] API error {e.status_code}")
            break

        except Exception as e:
            print(f"  [Q{question_index}] Error: {type(e).__name__} — {e}")
            break

    return {
        "answer": _trim(current_chunks[0]["chunk"], 80) if current_chunks else "Not found in references.",
        "is_found": bool(current_chunks)
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def process_all_questions(questions: List[str], pre_chunked_docs: List[Dict]) -> List[Dict]:
    """
    Full pipeline:
      1. Build BM25 index once
      2. Retrieve relevant chunks per question  
      3. Assign each question to a key: Q0->key0, Q1->key1, Q2->key2, Q3->key3, Q4->key0...
      4. Fire ALL questions truly in parallel — no shared semaphore, no blocking
      5. Return results in original order

    With 4 keys and 12 questions:
      key0 handles Q0, Q4, Q8  (sequentially within key0)
      key1 handles Q1, Q5, Q9  (sequentially within key1)
      key2 handles Q2, Q6, Q10 (sequentially within key2)
      key3 handles Q3, Q7, Q11 (sequentially within key3)
    Total time = time for the slowest key (~3 sequential calls) instead of 12 sequential.
    """
    print(f"[RAG] Building BM25 index over {len(pre_chunked_docs)} chunks...")
    bm25_index = build_bm25_index(pre_chunked_docs)

    num_keys = len(KEY_POOL) or 1
    print(f"[RAG] Firing {len(questions)} questions across {num_keys} key(s) in parallel...")

    # Each question gets its chunks retrieved and is assigned to a key
    tasks = [
        _call_single(
            question,
            retrieve_relevant_chunks(question, pre_chunked_docs, bm25_index),
            _get_key_for_index(i),
            i
        )
        for i, question in enumerate(questions)
    ]

    raw_results = await asyncio.gather(*tasks)

    # Format final output
    output = []
    for i, (question, result) in enumerate(zip(questions, raw_results)):
        retrieved = retrieve_relevant_chunks(question, pre_chunked_docs, bm25_index)
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

    answered = sum(1 for r in output if r["is_found"])
    print(f"[RAG] Done. {answered} answered, {len(output) - answered} not found.")
    return output


async def process_question(question: str, pre_chunked_docs: List[Dict]) -> Dict:
    """Single-question pipeline for the regenerate endpoint."""
    bm25_index = build_bm25_index(pre_chunked_docs)
    chunks = retrieve_relevant_chunks(question, pre_chunked_docs, bm25_index)
    key_entry = KEY_POOL[0] if KEY_POOL else None
    result = await _call_single(question, chunks, key_entry, 0)

    if not result["is_found"] or not chunks:
        return {"answer": result["answer"], "citations": [], "confidence": 0.0, "evidence_snippets": [], "is_found": False}
    return {
        "answer": result["answer"],
        "citations": [{"doc_name": c["doc_name"], "snippet": c["chunk"][:150] + "..."} for c in chunks[:2]],
        "confidence": compute_confidence(chunks),
        "evidence_snippets": [c["chunk"][:200] for c in chunks[:2]],
        "is_found": True,
    }
