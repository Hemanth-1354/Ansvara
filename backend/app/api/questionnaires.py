import os
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from app.models.database import get_db, Questionnaire, User
from app.api.auth import get_current_user
from app.services.parser import extract_text, parse_questions
from pydantic import BaseModel

router = APIRouter()

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


class QuestionnaireOut(BaseModel):
    id: int
    filename: str
    title: str | None
    status: str
    created_at: str

    class Config:
        from_attributes = True


@router.post("/upload")
async def upload_questionnaire(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    allowed = {".pdf", ".docx", ".txt", ".xlsx"}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed:
        raise HTTPException(400, f"File type {ext} not supported")

    file_bytes = await file.read()

    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(400, "File too large. Maximum size is 10 MB.")

    # Extract text in-memory — no file saved to disk
    text = extract_text(file_bytes, file.filename)
    questions = parse_questions(text)

    q = Questionnaire(
        user_id=current_user.id,
        filename=file.filename,
        title=file.filename.rsplit(".", 1)[0].replace("_", " ").title(),
        content=text,
        status="uploaded"
    )
    db.add(q)
    db.commit()
    db.refresh(q)

    return {
        "id": q.id,
        "filename": q.filename,
        "title": q.title,
        "status": q.status,
        "questions": questions,
        "question_count": len(questions),
        "created_at": q.created_at.isoformat()
    }


@router.get("/")
def list_questionnaires(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    qs = db.query(Questionnaire).filter(
        Questionnaire.user_id == current_user.id
    ).order_by(Questionnaire.created_at.desc()).all()
    return [
        {
            "id": q.id,
            "filename": q.filename,
            "title": q.title,
            "status": q.status,
            "created_at": q.created_at.isoformat()
        }
        for q in qs
    ]


@router.delete("/{q_id}")
def delete_questionnaire(
    q_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    q = db.query(Questionnaire).filter(
        Questionnaire.id == q_id, Questionnaire.user_id == current_user.id
    ).first()
    if not q:
        raise HTTPException(404, "Questionnaire not found")
    # Cascade delete handles all runs + answers automatically
    db.delete(q)
    db.commit()
    return {"ok": True}
