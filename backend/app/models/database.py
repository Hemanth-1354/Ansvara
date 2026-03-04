from sqlalchemy import create_engine, Column, Integer, String, Text, Float, DateTime, ForeignKey, Boolean, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime, timezone
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://questuser:questpass@db:5432/questdb")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))

    questionnaires = relationship("Questionnaire", back_populates="owner")
    reference_docs = relationship("ReferenceDocument", back_populates="owner")


class Questionnaire(Base):
    __tablename__ = "questionnaires"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    filename = Column(String, nullable=False)
    title = Column(String)
    file_path = Column(String)
    status = Column(String, default="uploaded")  # uploaded, processing, done
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    




    owner = relationship("User", back_populates="questionnaires")
    runs = relationship("AnswerRun", back_populates="questionnaire")


class ReferenceDocument(Base):
    __tablename__ = "reference_documents"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    filename = Column(String, nullable=False)
    file_path = Column(String)
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))

    owner = relationship("User", back_populates="reference_docs")


class AnswerRun(Base):
    __tablename__ = "answer_runs"
    id = Column(Integer, primary_key=True, index=True)
    questionnaire_id = Column(Integer, ForeignKey("questionnaires.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    summary = Column(JSON)  # {total, answered, not_found}

    questionnaire = relationship("Questionnaire", back_populates="runs")
    answers = relationship("Answer", back_populates="run")


class Answer(Base):
    __tablename__ = "answers"
    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("answer_runs.id"), nullable=False)
    question_index = Column(Integer, nullable=False)
    question_text = Column(Text, nullable=False)
    answer_text = Column(Text)
    citations = Column(JSON)  # list of {doc_name, snippet}
    confidence = Column(Float)
    evidence_snippets = Column(JSON)  # list of strings
    is_found = Column(Boolean, default=True)
    edited = Column(Boolean, default=False)

    run = relationship("AnswerRun", back_populates="answers")
