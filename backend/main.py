from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import auth, questionnaires, documents, answers
from app.models.database import engine, Base
import os

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Ansvara Tool API", version="1.0.0")

# CORS: read allowed origins from env (comma-separated) — defaults to localhost for dev
_raw_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173")
allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(questionnaires.router, prefix="/api/questionnaires", tags=["questionnaires"])
app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
app.include_router(answers.router, prefix="/api/answers", tags=["answers"])

@app.get("/health")
def health_check():
    return {"status": "ok"}
