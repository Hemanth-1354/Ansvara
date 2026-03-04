import os
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from app.models.database import get_db, ReferenceDocument, User
from app.api.auth import get_current_user
from app.services.parser import extract_text

router = APIRouter()

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


@router.post("/upload")
async def upload_reference_doc(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    allowed = {".pdf", ".docx", ".txt", ".xlsx", ".md"}
    # Use basename to prevent path traversal attacks
    safe_filename = os.path.basename(file.filename)
    ext = os.path.splitext(safe_filename)[1].lower()
    if ext not in allowed:
        raise HTTPException(400, f"File type {ext} not supported")

    file_bytes = await file.read()

    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(400, "File too large. Maximum size is 10 MB.")

    # Extract text in-memory — no file saved to disk
    content = extract_text(file_bytes, safe_filename)

    doc = ReferenceDocument(
        user_id=current_user.id,
        filename=safe_filename,
        content=content
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    return {
        "id": doc.id,
        "filename": doc.filename,
        "char_count": len(content),
        "created_at": doc.created_at.isoformat()
    }


@router.get("/")
def list_reference_docs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    docs = db.query(ReferenceDocument).filter(
        ReferenceDocument.user_id == current_user.id
    ).order_by(ReferenceDocument.created_at.desc()).all()
    return [
        {
            "id": d.id,
            "filename": d.filename,
            "char_count": len(d.content or ""),
            "created_at": d.created_at.isoformat()
        }
        for d in docs
    ]


@router.delete("/{doc_id}")
def delete_reference_doc(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    doc = db.query(ReferenceDocument).filter(
        ReferenceDocument.id == doc_id,
        ReferenceDocument.user_id == current_user.id
    ).first()
    if not doc:
        raise HTTPException(404, "Document not found")
    db.delete(doc)
    db.commit()
    return {"ok": True}
