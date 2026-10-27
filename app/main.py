"""Ponto de entrada: ciclo de vida, rotas e tratamento de erros.

Rodar:  uvicorn app.main:app --reload
Docs:   http://127.0.0.1:8000/docs
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.routers import predicao
from app.services import ServicoModelo

RAIZ = Path(__file__).resolve().parents[1]
log = logging.getLogger("evasao")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Carrega o modelo na memória UMA vez, quando a API sobe."""
    app.state.modelo = ServicoModelo(RAIZ / "models" / "modelo_evasao.joblib")
    try:
        app.state.modelo.carregar()
    except FileNotFoundError:
        log.error("models/modelo_evasao.joblib não existe: rode `python treinar.py`.")
    yield


app = FastAPI(
    title="Conexão Escola-Família: risco de evasão",
    description="Prevê o risco de evasão de um estudante e diz, com honestidade, o que o dado não vê.",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(predicao.router)


@app.exception_handler(Exception)
async def erro_interno(request: Request, exc: Exception):
    """Nada derruba a API: qualquer falha não prevista vira 500 com mensagem limpa."""
    log.exception("erro não tratado em %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Erro interno. A equipe foi avisada pelo log."})
