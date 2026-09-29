import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agents import run_question
from tools import BACKEND_URL, CALL_LOG, TOOLS, ToolClient, call_tool

app = FastAPI(title="POLARIS AI service", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"service": "POLARIS-ai", "status": "ok", "backend": BACKEND_URL}


@app.get("/ai/tools")
def list_tools():
    return [{"name": name, **meta} for name, meta in TOOLS.items()]


class CallRequest(BaseModel):
    tool: str
    args: dict = {}
    backend_token: str = ""


@app.post("/ai/call")
def call(req: CallRequest):
    try:
        result = call_tool(ToolClient(token=req.backend_token), req.tool, req.args)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"backend call failed: {exc}")
    return {"tool": req.tool, "result": result, "logged": CALL_LOG[-1] if CALL_LOG else None}


@app.get("/ai/calls")
def recent_calls(limit: int = 20):
    return CALL_LOG[-limit:]


class AskRequest(BaseModel):
    question: str
    backend_token: str = ""


@app.post("/ai/ask")
def ask(req: AskRequest):
    try:
        return run_question(req.question, ToolClient(token=req.backend_token))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"agent run failed: {exc}")
