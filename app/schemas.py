"""Contratos de dados da API (Pydantic): o que entra e o que sai."""
from typing import Literal

from pydantic import BaseModel, Field


class DadosEstudante(BaseModel):
    """O que o modelo usa. Nenhum nome, nenhum documento: só a trajetória acadêmica."""
    idade: int = Field(..., ge=17, le=70, description="Idade na matrícula (17 a 70 anos)")
    nota_admissao: float = Field(..., ge=95, le=190, description="Nota de admissão (escala 95 a 190)")
    disciplinas_1sem_inscritas: int = Field(..., ge=0, le=26)
    disciplinas_1sem_aprovadas: int = Field(..., ge=0, le=26)
    media_1sem: float = Field(..., ge=0, le=20, description="Média do 1º semestre (0 a 20)")
    disciplinas_2sem_inscritas: int = Field(..., ge=0, le=23)
    disciplinas_2sem_aprovadas: int = Field(..., ge=0, le=20)
    media_2sem: float = Field(..., ge=0, le=20, description="Média do 2º semestre (0 a 20)")
    disciplinas_2sem_sem_avaliacao: int = Field(..., ge=0, le=12,
                                                description="Disciplinas sem nenhuma avaliação feita")
    mensalidade_em_dia: bool
    devedor: bool
    bolsista: bool
    mora_longe_de_casa: bool
    turno_diurno: bool

    model_config = {"json_schema_extra": {"example": {
        "idade": 19, "nota_admissao": 125.0,
        "disciplinas_1sem_inscritas": 6, "disciplinas_1sem_aprovadas": 2, "media_1sem": 10.5,
        "disciplinas_2sem_inscritas": 6, "disciplinas_2sem_aprovadas": 1, "media_2sem": 9.8,
        "disciplinas_2sem_sem_avaliacao": 2,
        "mensalidade_em_dia": False, "devedor": True, "bolsista": False,
        "mora_longe_de_casa": True, "turno_diurno": False}}}


class Fator(BaseModel):
    fator: str = Field(..., description="Coluna do dado que mais empurrou o risco para cima")
    descricao: str
    peso: float


class Predicao(BaseModel):
    risco_evasao: float = Field(..., ge=0, le=1, description="Probabilidade estimada de evadir")
    nivel: Literal["baixo", "medio", "alto"]
    fatores_do_dado: list[Fator]
    pontos_cegos: list[str] = Field(..., description="O que o modelo NÃO enxerga")
    perguntas_para_conversa: list[str]


class Saude(BaseModel):
    status: Literal["ok"]
    modelo_carregado: bool
    modelo: str | None

