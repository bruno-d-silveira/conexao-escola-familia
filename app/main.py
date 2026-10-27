"""Ponto de entrada: ciclo de vida, rotas e tratamento de erros.

Rodar:  uvicorn app.main:app --reload
Docs:   http://127.0.0.1:8000/docs
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.escola import Escola
from app.routers import escola, predicao
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
    app.state.escola = Escola(RAIZ / "data" / "escola.db")
    app.state.escola.preparar()
    yield


app = FastAPI(
    title="Conexão Escola-Família: risco de evasão",
    description="Prevê o risco de evasão de um estudante e diz, com honestidade, o que o dado não vê.",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(predicao.router)
app.include_router(escola.router)
app.mount("/web", StaticFiles(directory=RAIZ / "web", html=True), name="web")


@app.get("/", include_in_schema=False)
def inicio():
    return RedirectResponse("/web/")


@app.exception_handler(Exception)
async def erro_interno(request: Request, exc: Exception):
    """Nada derruba a API: qualquer falha não prevista vira 500 com mensagem limpa."""
    log.exception("erro não tratado em %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Erro interno. A equipe foi avisada pelo log."})
