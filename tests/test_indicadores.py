"""Testes do indicador de médias (r de Pearson)."""
from fastapi.testclient import TestClient

from app.main import app


def test_medias_200_com_r_e_pontos_na_escala_0_a_10():
    with TestClient(app) as cliente:
        resposta = cliente.get("/v1/indicadores/medias")
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert -1 <= corpo["r"] <= 1
    assert corpo["n"] == len(corpo["pontos"]) > 0
    assert all(0 <= p["m1"] <= 10 and 0 <= p["m2"] <= 10 for p in corpo["pontos"])
