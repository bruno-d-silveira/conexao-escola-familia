"""Testes do fluxo da escola: login do professor, registro, aprovação e documento."""
import shutil

import pytest
from fastapi.testclient import TestClient

import app.main as main
from gerar_professores_ficticios import SENHA_DEMO


@pytest.fixture()
def cliente(tmp_path, monkeypatch):
    # Banco temporário: o teste não suja o data/escola.db da demonstração.
    shutil.copytree(main.RAIZ / "models", tmp_path / "models")
    shutil.copytree(main.RAIZ / "data", tmp_path / "data", ignore=shutil.ignore_patterns("escola.db"))
    monkeypatch.setattr(main, "RAIZ", tmp_path)
    with TestClient(main.app) as c:
        yield c


def test_professores_sem_hash_de_senha(cliente):
    r = cliente.get("/v1/professores")
    assert r.status_code == 200
    assert r.json() and all(set(p) == {"id", "nome"} for p in r.json())


def test_senha_errada_401_e_nada_registrado(cliente):
    r = cliente.post("/v1/registros", json={"aluno_id": "A0008", "professor_id": "P001", "senha": "errada",
                                           "acompanhamento": "Tentativa com a senha errada."})
    assert r.status_code == 401
    assert cliente.get("/v1/registros").json() == []


def test_aluno_inexistente_404(cliente):
    r = cliente.post("/v1/registros", json={"aluno_id": "A9999", "professor_id": "P001", "senha": SENHA_DEMO,
                                           "acompanhamento": "Teste de aluno inexistente."})
    assert r.status_code == 404


def test_fluxo_professor_coordenacao(cliente):
    r = cliente.post("/v1/registros", json={"aluno_id": "A0008", "professor_id": "P001", "senha": SENHA_DEMO,
                                           "acompanhamento": "Faltou às duas últimas provas."})
    assert r.status_code == 201
    reg = r.json()
    assert reg["status"] == "aguardando_coordenacao"
    assert reg["professor"] == "Prof.ª Helena Costa"
    assert cliente.get(f"/v1/registros/{reg['id']}/documento").status_code == 400
    r = cliente.post(f"/v1/registros/{reg['id']}/aprovar", json={"coordenador": "Coord. Teste"})
    assert r.status_code == 200 and r.json()["status"] == "aprovado"
    assert cliente.post(f"/v1/registros/{reg['id']}/aprovar", json={"coordenador": "X1"}).status_code == 400
    doc = cliente.get(f"/v1/registros/{reg['id']}/documento").json()
    assert doc["para"].endswith("@example.com")
    assert "não é um diagnóstico" in doc["texto"]
