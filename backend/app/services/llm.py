import os
import re
import asyncio
import random
import math
from typing import List, Dict
from groq import AsyncGroq, RateLimitError, APIStatusError

# ---------------------------------------------------------------------------
# Groq client pool — one semaphore PER KEY so keys never compete.
# Round-robin: Q0→key0, Q1→key1, Q2→key2, Q3→key3, Q4→key0 ...
# With 4 keys x 6,000 TPM = 24,000 TPM total available.
# ---------------------------------------------------------------------------
GROQ_API_KEYS = [k.strip() for k in os.getenv("GROQ_API_KEY", "").split(",") if k.strip()]

KEY_POOL = [
    {"client": AsyncGroq(api_key=key), "sem": asyncio.Semaphore(1)}
    for key in GROQ_API_KEYS
] if GROQ_API_KEYS else []

TOP_K = 3        # chunks retrieved per question
MAX_TOKENS = 150 # hard cap — prevents runaway repetition loops


def _get_key_for_index(i: int):
    if not KEY_POOL:
        return None
    return KEY_POOL[i % len(KEY_POOL)]


# ---------------------------------------------------------------------------
# Chunking — 150 words per chunk so each section of a policy doc gets its
# own chunk. Prevents the answer being cut off by a trim mid-chunk.
# 150 words ≈ 200 tokens — 3 chunks as context = ~600 tokens, well under limit.
# ---------------------------------------------------------------------------

def chunk_text(text: str, chunk_size: int = 150, overlap: int = 20) -> List[str]:
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
# TF-IDF retrieval
# For each chunk: score = |query_words ∩ chunk_words| / sqrt(chunk_length)
# Simple, fast, no dependencies, and works well with small focused chunks.
# ---------------------------------------------------------------------------

def _tfidf_scores(query: str, chunks: List[str]) -> List[float]:
    query_words = set(re.findall(r"\w+", query.lower()))
    scores = []
    for chunk in chunks:
        chunk_words = re.findall(r"\w+", chunk.lower())
        if not chunk_words:
            scores.append(0.0)
            continue
        intersection = query_words & set(chunk_words)
        scores.append(len(intersection) / (len(chunk_words) ** 0.5 + 1))
    return scores


def retrieve_relevant_chunks(question: str, pre_chunked_docs: List[Dict]) -> List[Dict]:
    if not pre_chunked_docs:
        return []
    texts = [c["chunk"] for c in pre_chunked_docs]
    scores = _tfidf_scores(question, texts)
    ranked = sorted(zip(scores, pre_chunked_docs), key=lambda x: x[0], reverse=True)
    return [
        {"doc_name": ci["doc_name"], "chunk": ci["chunk"], "score": sc}
        for sc, ci in ranked[:TOP_K] if sc > 0
    ]


def compute_confidence(chunks: List[Dict]) -> float:
    if not chunks:
        return 0.0
    # TF-IDF scores typically 0.0–1.0; normalise with a soft cap
    return round(min(chunks[0]["score"] * 2.5, 1.0), 2)


# ---------------------------------------------------------------------------
# Single-question LLM call — pinned to one API key via round-robin assignment
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are a precise questionnaire-answering assistant. "
    "Answer using ONLY the reference text provided. "
    "Write 2 to 4 sentences maximum. Stop after 4 sentences. "
    "Never repeat yourself. Never list the same item twice. "
    'If the answer is not in the text, reply exactly: "Not found in references." '
    "No preamble, no markdown, no bullet points."
)


def _build_prompt(question: str, chunks: List[Dict]) -> str:
    context = "\n\n".join(
        f"[{c['doc_name']}]:\n{c['chunk']}" for c in chunks
    )
    return f"Reference text:\n{context}\n\nQuestion: {question}\n\nAnswer:"


async def _call_single(question: str, chunks: List[Dict], key_entry, question_index: int) -> Dict:
    """
    Call Groq for ONE question using its assigned key.
    Retries up to 5 times with exponential backoff on rate limit.
    On 413 (still too large), falls back to top-1 chunk only.
    """
    if not chunks:
        return {"answer": "Not found in references.", "is_found": False}

    if key_entry is None:
        # No API keys — return raw snippet as fallback
        return {"answer": chunks[0]["chunk"][:300], "is_found": True}

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
                    temperature=0.0,
                    frequency_penalty=1.0,  # penalises repeated tokens — kills looping
                )
            answer = response.choices[0].message.content.strip()
            is_found = answer.lower() != "not found in references."
            return {"answer": answer, "is_found": is_found}

        except RateLimitError:
            delay = base_delay * (2 ** attempt) + random.uniform(0.2, 0.8)
            key_num = question_index % max(len(KEY_POOL), 1)
            print(f"  [Q{question_index}] Rate limit key{key_num} — retry in {delay:.1f}s")
            await asyncio.sleep(delay)

        except APIStatusError as e:
            if e.status_code == 413:
                # Still too large — fall back to top-1 chunk only
                current_chunks = current_chunks[:1]
                prompt = _build_prompt(question, current_chunks)
                print(f"  [Q{question_index}] 413 — falling back to top-1 chunk")
                continue
            print(f"  [Q{question_index}] API error {e.status_code}")
            break

        except Exception as e:
            print(f"  [Q{question_index}] Error: {type(e).__name__} — {e}")
            break

    return {
        "answer": current_chunks[0]["chunk"][:200] if current_chunks else "Not found in references.",
        "is_found": bool(current_chunks)
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def process_all_questions(questions: List[str], pre_chunked_docs: List[Dict]) -> List[Dict]:
    """
    Full pipeline:
      1. TF-IDF retrieval per question (fast, in-process)
      2. Assign each question to a specific API key round-robin
         Q0->key0, Q1->key1, Q2->key2, Q3->key3, Q4->key0 ...
      3. Fire ALL questions truly in parallel via asyncio.gather
         Each key handles its own queue — no cross-key contention
      4. Return results in original order

    With 4 keys and 12 questions:
      key0: Q0, Q4, Q8   key1: Q1, Q5, Q9
      key2: Q2, Q6, Q10  key3: Q3, Q7, Q11
    Total time ≈ 3 sequential LLM calls (~6-8 seconds) not 12.
    """
    num_keys = len(KEY_POOL) or 1
    print(f"[RAG] Firing {len(questions)} questions across {num_keys} key(s) in parallel...")

    tasks = [
        _call_single(
            question,
            retrieve_relevant_chunks(question, pre_chunked_docs),
            _get_key_for_index(i),
            i
        )
        for i, question in enumerate(questions)
    ]

    raw_results = await asyncio.gather(*tasks)

    output = []
    for i, (question, result) in enumerate(zip(questions, raw_results)):
        retrieved = retrieve_relevant_chunks(question, pre_chunked_docs)
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
    chunks = retrieve_relevant_chunks(question, pre_chunked_docs)
    key_entry = KEY_POOL[0] if KEY_POOL else None
    result = await _call_single(question, chunks, key_entry, 0)

    if not result["is_found"] or not chunks:
        return {"answer": result["answer"], "citations": [], "confidence": 0.0,
                "evidence_snippets": [], "is_found": False}
    return {
        "answer": result["answer"],
        "citations": [{"doc_name": c["doc_name"], "snippet": c["chunk"][:150] + "..."} for c in chunks[:2]],
        "confidence": compute_confidence(chunks),
        "evidence_snippets": [c["chunk"][:200] for c in chunks[:2]],
        "is_found": True,
    }
