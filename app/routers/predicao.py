"""Rotas de saúde e de inferência."""
from fastapi import APIRouter, HTTPException, Request

from app.schemas import DadosEstudante, Predicao, Saude

router = APIRouter(tags=["predição"])


def checar_coerencia(dados: DadosEstudante) -> None:
    """Regra de negócio (400): os tipos e as faixas estão certos, mas a combinação não fecha."""
    if dados.disciplinas_1sem_aprovadas > dados.disciplinas_1sem_inscritas:
        raise HTTPException(400, "1º semestre: aprovadas não pode ser maior que inscritas.")
    if dados.disciplinas_2sem_aprovadas > dados.disciplinas_2sem_inscritas:
        raise HTTPException(400, "2º semestre: aprovadas não pode ser maior que inscritas.")


@router.get("/health", response_model=Saude)
def saude(request: Request):
    servico = request.app.state.modelo
    return Saude(status="ok", modelo_carregado=servico.carregado,
                 modelo=servico.caminho.name if servico.carregado else None)


@router.post("/v1/predict", response_model=Predicao)
def prever(dados: DadosEstudante, request: Request):
    checar_coerencia(dados)
    servico = request.app.state.modelo
    if not servico.carregado:
        raise HTTPException(500, "O modelo não está carregado. Rode `python treinar.py` e reinicie a API.")
    return servico.prever(dados)
