# server.py
import os, jwt
from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from agent_core_ollama import run_agent
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Agente InfoHub")

JWT_SECRET = os.getenv("JWT_SECRET", "troque-no-.env")
JWT_ALGOS = ["HS256"]

class ChatPayload(BaseModel):
    chatId: str = "sessao-123"
    message: str

def extract_user_id_from_auth(authorization: str | None) -> int:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Authorization Bearer token ausente")
    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=JWT_ALGOS)
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Token inválido")

    user_id = payload.get("id") or payload.get("id_usuario")
    if not user_id:
        raise HTTPException(401, "Token sem id do usuário")
    return int(user_id)

@app.post("/chat")
def chat(p: ChatPayload, authorization: str | None = Header(default=None)):
    if not p.message:
        raise HTTPException(400, "message é obrigatório")

    user_id = extract_user_id_from_auth(authorization)
    res = run_agent(p.message, p.chatId, user_id=user_id)

    return JSONResponse({"chatId": p.chatId, "reply": res["reply"]})
