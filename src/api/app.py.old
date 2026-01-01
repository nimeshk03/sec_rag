from fastapi import FastAPI
from pydantic import BaseModel
import os

app = FastAPI(
    title="RAG Safety Checker API",
    description="SEC filing analysis for portfolio risk detection",
    version="1.0.0"
)

class HealthResponse(BaseModel):
    status: str
    message: str
    supabase_configured: bool
    llm_configured: bool
    llm_provider: str
    llm_model: str

@app.get("/")
async def root():
    return {
        "service": "RAG Safety Checker API",
        "status": "running",
        "version": "1.0.0",
        "llm_provider": os.getenv("LLM_PROVIDER", "groq")
    }

@app.get("/health", response_model=HealthResponse)
async def health_check():
    supabase_url = os.getenv("SUPABASE_URL")
    groq_key = os.getenv("GROQ_API_KEY")
    llm_provider = os.getenv("LLM_PROVIDER", "groq")
    llm_model = os.getenv("LLM_MODEL", "llama-3.1-70b-versatile")
    
    return HealthResponse(
        status="healthy",
        message="Service is running with FREE Groq LLM. Awaiting full implementation.",
        supabase_configured=bool(supabase_url and supabase_url != "https://your-project.supabase.co"),
        llm_configured=bool(groq_key and groq_key != "your-groq-api-key-here"),
        llm_provider=llm_provider,
        llm_model=llm_model
    )
