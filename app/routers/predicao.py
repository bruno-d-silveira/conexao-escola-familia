"""Rotas de saúde e de inferência."""
from fastapi import APIRouter, Request

from app.schemas import Saude

router = APIRouter(tags=["predição"])


@router.get("/health", response_model=Saude)
def saude(request: Request):
    servico = request.app.state.modelo
    return Saude(status="ok", modelo_carregado=servico.carregado,
                 modelo=servico.caminho.name if servico.carregado else None)
