import os
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from app.models.database import get_db, ReferenceDocument, User
from app.api.auth import get_current_user
from app.services.parser import extract_text

router = APIRouter()
UPLOAD_DIR = "/app/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/upload")
async def upload_reference_doc(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    allowed = {".pdf", ".docx", ".txt", ".xlsx", ".md"}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed:
        raise HTTPException(400, f"File type {ext} not supported")

    file_bytes = await file.read()
    save_path = f"{UPLOAD_DIR}/ref_{current_user.id}_{file.filename}"

    with open(save_path, "wb") as f:
        f.write(file_bytes)

    content = extract_text(file_bytes, file.filename)

    doc = ReferenceDocument(
        user_id=current_user.id,
        filename=file.filename,
        file_path=save_path,
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
