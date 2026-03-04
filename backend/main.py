# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import auth, questionnaires, documents, answers
from app.models.database import engine, Base
import os

# -----------------------------
# Initialize Database Tables
# -----------------------------
# Ensures all SQLAlchemy models are created in the DB
Base.metadata.create_all(bind=engine)

# -----------------------------
# FastAPI App Initialization
# -----------------------------
app = FastAPI(title="Ansvara Tool API", version="1.0.0")

# -----------------------------
# CORS Configuration
# -----------------------------
# Frontend origins: local dev + Vercel production
_raw_origins = os.getenv(
    "ALLOWED_ORIGINS",
    "https://ansvara.vercel.app"
)
allowed_origins = [origin.strip() for origin in _raw_origins.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,   # Only allow frontend domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# Include API Routers
# -----------------------------
# All routes are prefixed with /api
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(questionnaires.router, prefix="/api/questionnaires", tags=["questionnaires"])
app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
app.include_router(answers.router, prefix="/api/answers", tags=["answers"])

# -----------------------------
# Root and Health Endpoints
# -----------------------------
@app.get("/", tags=["root"])
def root():
    return {"message": "Ansvara API is running 🚀"}

@app.get("/health", tags=["root"])
def health_check():
    return {"status": "ok"}

# -----------------------------
# Optional: Startup & Shutdown Events
# -----------------------------
@app.on_event("startup")
async def startup_event():
    print("Starting Ansvara API...")

@app.on_event("shutdown")
async def shutdown_event():
    print("Shutting down Ansvara API...")