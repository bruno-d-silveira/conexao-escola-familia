"""Testes da API: cada código de resposta que o edital pede, um teste."""
from fastapi.testclient import TestClient

from app.main import app
from app.schemas import DadosEstudante

EXEMPLO = DadosEstudante.model_config["json_schema_extra"]["example"]


def test_health_com_modelo_carregado():
    with TestClient(app) as cliente:
        resposta = cliente.get("/health")
    assert resposta.status_code == 200
    assert resposta.json()["modelo_carregado"] is True


def test_predict_200_devolve_risco_e_perguntas():
    with TestClient(app) as cliente:
        resposta = cliente.post("/v1/predict", json=EXEMPLO)
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert 0 <= corpo["risco_evasao"] <= 1
    assert corpo["nivel"] in {"baixo", "medio", "alto"}
    assert corpo["pontos_cegos"]
    assert corpo["perguntas_para_conversa"]


def test_predict_400_aprovadas_maior_que_inscritas():
    with TestClient(app) as cliente:
        resposta = cliente.post("/v1/predict", json={**EXEMPLO, "disciplinas_1sem_aprovadas": 7})
    assert resposta.status_code == 400


def test_predict_422_idade_fora_da_faixa():
    with TestClient(app) as cliente:
        resposta = cliente.post("/v1/predict", json={**EXEMPLO, "idade": 5})
    assert resposta.status_code == 422


def test_predict_500_sem_modelo():
    with TestClient(app) as cliente:
        app.state.modelo.pipeline = None
        resposta = cliente.post("/v1/predict", json=EXEMPLO)
    assert resposta.status_code == 500
