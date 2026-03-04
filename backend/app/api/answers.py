import os
import asyncio
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel
import io

from app.models.database import get_db, Questionnaire, ReferenceDocument, AnswerRun, Answer, User
from app.api.auth import get_current_user
from app.services.parser import extract_text, parse_questions
from app.services.llm import process_question, pre_chunk_docs
from app.services.exporter import export_to_docx, export_to_pdf

router = APIRouter()


class GenerateRequest(BaseModel):
    questionnaire_id: int


class EditAnswerRequest(BaseModel):
    answer_text: str


class RegenerateRequest(BaseModel):
    answer_ids: List[int]


@router.post("/generate")
async def generate_answers(
    req: GenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    print(
        f"\n[API /generate] Starting new generation run for Questionnaire ID: {req.questionnaire_id}")
    q = db.query(Questionnaire).filter(
        Questionnaire.id == req.questionnaire_id,
        Questionnaire.user_id == current_user.id
    ).first()
    if not q:
        print(f"  - Error: Questionnaire {req.questionnaire_id} not found.")
        raise HTTPException(404, "Questionnaire not found")

    ref_docs = db.query(ReferenceDocument).filter(
        ReferenceDocument.user_id == current_user.id
    ).all()
    if not ref_docs:
        print("  - Error: No reference documents found for user.")
        raise HTTPException(400, "No reference documents uploaded")

    # Read questionnaire file
    print(f"  - Reading questionnaire file: {q.filename}")
    with open(q.file_path, "rb") as f:
        file_bytes = f.read()
    text = extract_text(file_bytes, q.filename)
    questions = parse_questions(text)

    if not questions:
        print("  - Error: Parser found 0 questions.")
        raise HTTPException(400, "No questions found in questionnaire")
    print(f"  - Parser found {len(questions)} questions.")

    # Build reference docs list and pre-chunk them
    docs = [{"name": d.filename, "content": d.content or ""} for d in ref_docs]
    pre_chunked_docs = pre_chunk_docs(docs)

    # Create run
    run = AnswerRun(questionnaire_id=q.id, user_id=current_user.id)
    db.add(run)
    db.flush()
    print(f"  - Created AnswerRun ID: {run.id}")

    # Process all questions in parallel
    print(f"  - Dispatching {len(questions)} questions to LLM pipeline...")
    tasks = [process_question(question, pre_chunked_docs)
             for question in questions]
    results = await asyncio.gather(*tasks)
    print(f"  - LLM pipeline completed all {len(questions)} tasks.")

    answers = []
    answered = 0
    not_found = 0

    print("  - Saving results to database...")
    for idx, result in enumerate(results):
        answer = Answer(
            run_id=run.id,
            question_index=idx,
            question_text=questions[idx],
            answer_text=result["answer"],
            citations=result["citations"],
            confidence=result["confidence"],
            evidence_snippets=result["evidence_snippets"],
            is_found=result["is_found"]
        )
        db.add(answer)
        if result["is_found"]:
            answered += 1
        else:
            not_found += 1
        answers.append(answer)

    summary = {"total": len(questions),
               "answered": answered, "not_found": not_found}
    run.summary = summary
    db.commit()
    print(f"[API /generate] Run {run.id} finished. Summary: {summary}\n")

    return {
        "run_id": run.id,
        "summary": summary,
        "answers": [
            {
                "id": a.id,
                "question_index": a.question_index,
                "question_text": a.question_text,
                "answer_text": a.answer_text,
                "citations": a.citations,
                "confidence": a.confidence,
                "evidence_snippets": a.evidence_snippets,
                "is_found": a.is_found,
                "edited": a.edited
            }
            for a in answers
        ]
    }


@router.get("/runs")
def list_runs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    runs = db.query(AnswerRun).filter(
        AnswerRun.user_id == current_user.id
    ).order_by(AnswerRun.created_at.desc()).all()
    return [
        {
            "id": r.id,
            "questionnaire_id": r.questionnaire_id,
            "questionnaire_name": r.questionnaire.title if r.questionnaire else "",
            "summary": r.summary,
            "created_at": r.created_at.isoformat()
        }
        for r in runs
    ]


@router.get("/runs/{run_id}")
def get_run(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    run = db.query(AnswerRun).filter(
        AnswerRun.id == run_id,
        AnswerRun.user_id == current_user.id
    ).first()
    if not run:
        raise HTTPException(404, "Run not found")

    answers = db.query(Answer).filter(
        Answer.run_id == run_id).order_by(Answer.question_index).all()
    return {
        "run_id": run.id,
        "questionnaire_id": run.questionnaire_id,
        "questionnaire_name": run.questionnaire.title if run.questionnaire else "",
        "summary": run.summary,
        "created_at": run.created_at.isoformat(),
        "answers": [
            {
                "id": a.id,
                "question_index": a.question_index,
                "question_text": a.question_text,
                "answer_text": a.answer_text,
                "citations": a.citations,
                "confidence": a.confidence,
                "evidence_snippets": a.evidence_snippets,
                "is_found": a.is_found,
                "edited": a.edited
            }
            for a in answers
        ]
    }


@router.patch("/answers/{answer_id}")
def edit_answer(
    answer_id: int,
    req: EditAnswerRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    answer = db.query(Answer).join(AnswerRun).filter(
        Answer.id == answer_id,
        AnswerRun.user_id == current_user.id
    ).first()
    if not answer:
        raise HTTPException(404, "Answer not found")
    answer.answer_text = req.answer_text
    answer.edited = True
    db.commit()
    return {"ok": True}


@router.post("/runs/{run_id}/regenerate")
async def regenerate_answers(
    run_id: int,
    req: RegenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    run = db.query(AnswerRun).filter(
        AnswerRun.id == run_id, AnswerRun.user_id == current_user.id
    ).first()
    if not run:
        raise HTTPException(404, "Run not found")

    ref_docs = db.query(ReferenceDocument).filter(
        ReferenceDocument.user_id == current_user.id
    ).all()
    docs = [{"name": d.filename, "content": d.content or ""} for d in ref_docs]
    pre_chunked_docs = pre_chunk_docs(docs)

    answers_to_update = []
    for answer_id in req.answer_ids:
        answer = db.query(Answer).filter(
            Answer.id == answer_id, Answer.run_id == run_id
        ).first()
        if answer:
            answers_to_update.append(answer)

    if not answers_to_update:
        return {"updated": []}

    # Process regenerations in parallel
    tasks = [process_question(a.question_text, pre_chunked_docs)
             for a in answers_to_update]
    results = await asyncio.gather(*tasks)

    updated_ids = []
    for answer, result in zip(answers_to_update, results):
        answer.answer_text = result["answer"]
        answer.citations = result["citations"]
        answer.confidence = result["confidence"]
        answer.evidence_snippets = result["evidence_snippets"]
        answer.is_found = result["is_found"]
        answer.edited = False
        updated_ids.append(answer.id)

    # Update summary
    all_answers = db.query(Answer).filter(Answer.run_id == run_id).all()
    answered = sum(1 for a in all_answers if a.is_found)
    not_found = sum(1 for a in all_answers if not a.is_found)
    run.summary = {"total": len(all_answers),
                   "answered": answered, "not_found": not_found}
    db.commit()

    return {"updated": updated_ids}


@router.delete("/runs/{run_id}")
def delete_run(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    run = db.query(AnswerRun).filter(
        AnswerRun.id == run_id,
        AnswerRun.user_id == current_user.id
    ).first()
    if not run:
        raise HTTPException(404, "Run not found")

    # Delete all answers in the run
    db.query(Answer).filter(Answer.run_id == run_id).delete()

    # Delete the run itself
    db.delete(run)
    db.commit()
    return {"ok": True}


@router.get("/runs/{run_id}/export")
def export_run(
    run_id: int,
    format: str = "docx",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    run = db.query(AnswerRun).filter(
        AnswerRun.id == run_id, AnswerRun.user_id == current_user.id
    ).first()
    if not run:
        raise HTTPException(404, "Run not found")

    answers = db.query(Answer).filter(
        Answer.run_id == run_id).order_by(Answer.question_index).all()
    answers_data = [
        {
            "question_text": a.question_text,
            "answer_text": a.answer_text,
            "citations": a.citations,
            "confidence": a.confidence,
            "is_found": a.is_found
        }
        for a in answers
    ]
    run_data = {"summary": run.summary}

    if format == "pdf":
        file_bytes = export_to_pdf(run_data, answers_data)
        media_type = "application/pdf"
        filename = f"questionnaire_answers_run{run_id}.pdf"
    else:
        file_bytes = export_to_docx(run_data, answers_data)
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        filename = f"questionnaire_answers_run{run_id}.docx"

    return StreamingResponse(
        io.BytesIO(file_bytes),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
