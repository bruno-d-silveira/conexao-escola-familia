"""Rotas do mar e da chuva: a previsão da semana e o aviso que a coordenação manda a professores e pais."""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request

from app import clima
from app.routers.escola import coordenacao_logada
from app.schemas import AvisoDaSemana, Clima

router = APIRouter(prefix="/v1/clima", tags=["clima"])
VALIDADE = timedelta(hours=3)  # a previsão muda devagar: não precisa buscar a cada clique


def _previsao(request: Request, atualizar: bool = False) -> dict:
    """Busca nas fontes públicas e guarda por 3 horas. Fora do ar, responde 503 com a explicação."""
    guardada = getattr(request.app.state, "clima", None)
    if guardada and not atualizar and datetime.now() - guardada["em"] < VALIDADE:
        return guardada["dados"]
    try:
        dados = clima.previsao()
    except Exception as erro:  # rede, tempo esgotado ou formato novo numa das fontes
        raise HTTPException(503, f"Previsão indisponível agora ({type(erro).__name__}). Tente de novo mais tarde.")
    request.app.state.clima = {"em": datetime.now(), "dados": dados}
    return dados


@router.get("", response_model=Clima)
def previsao(request: Request, atualizar: bool = False, quem: dict = Depends(coordenacao_logada)):
    """Swell no mar aberto e onda na praia, maré, chuva e avisos do INMET para os próximos 7 dias."""
    return _previsao(request, atualizar)


@router.get("/aviso", response_model=AvisoDaSemana)
def aviso(request: Request, quem: dict = Depends(coordenacao_logada)):
    """O texto da semana para a coordenação imprimir ou mandar a professores e pais."""
    return clima.aviso_da_semana(_previsao(request))
