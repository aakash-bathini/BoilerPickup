from pathlib import Path
_env = Path(__file__).resolve().parent.parent / ".env"
if _env.exists():
    from dotenv import load_dotenv
    load_dotenv(_env)

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import engine, Base, get_db
from app.routers import users, games, stats, messages, challenges, moderation, assistant

Base.metadata.create_all(bind=engine)


def _migrate_add_email_verification():
    """Add email verification columns for existing databases."""
    if "sqlite" not in str(engine.url):
        return
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN email_verified BOOLEAN DEFAULT 1"))
            conn.commit()
        except Exception:
            conn.rollback()
        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN verification_code VARCHAR(6)"))
            conn.commit()
        except Exception:
            conn.rollback()
        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN verification_code_expires DATETIME"))
            conn.commit()
        except Exception:
            conn.rollback()


_migrate_add_email_verification()

app = FastAPI(
    title="Boiler Pickup API",
    description="AI-powered pickup basketball matchmaking for Purdue CoRec",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://*.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users.router)
app.include_router(games.router)


app.include_router(stats.router)
app.include_router(messages.router)
app.include_router(challenges.router)
app.include_router(moderation.router)
app.include_router(assistant.router)


@app.post("/api/train-predictor")
def train_win_predictor(db: Session = Depends(get_db)):
    """Dynamically Train the win predictor on NBA + App completed games."""
    from app.ai.win_predictor import online_train
    return online_train(db)


@app.get("/api/train-predictor")
def train_predictor_help():
    """Use POST to train. Run: curl -X POST http://localhost:8000/api/train-predictor"""
    return {"message": "Use POST to train. Run: curl -X POST http://localhost:8000/api/train-predictor"}


@app.get("/")
def root():
    return RedirectResponse(url="/docs")


@app.get("/api/health")
def health_check():
    return {"status": "healthy", "app": "Boiler Pickup", "version": "2.0.0"}
