"""Rotas de indicadores da base de treino."""
from fastapi import APIRouter, Request

from app.schemas import IndicadorMedias

router = APIRouter(prefix="/v1/indicadores", tags=["indicadores"])


@router.get("/medias", response_model=IndicadorMedias)
def medias(request: Request):
    """Média do 1º × média do 2º semestre de todos os estudantes da base, com o r de Pearson."""
    return request.app.state.medias
