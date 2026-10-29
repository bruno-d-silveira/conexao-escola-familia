"""Testes do fluxo da escola: login do professor, registro, aprovação e documento."""
import re
import shutil

import pytest
from fastapi.testclient import TestClient

import app.main as main
from gerar_coordenacao_ficticia import SENHA_DEMO as SENHA_COORD
from gerar_professores_ficticios import SENHA_DEMO


@pytest.fixture()
def cliente(tmp_path, monkeypatch):
    # Banco temporário: o teste não suja o data/escola.db da demonstração.
    shutil.copytree(main.RAIZ / "models", tmp_path / "models")
    shutil.copytree(main.RAIZ / "data", tmp_path / "data", ignore=shutil.ignore_patterns("escola.db"))
    monkeypatch.setattr(main, "RAIZ", tmp_path)
    with TestClient(main.app) as c:
        yield c


def passe(cliente) -> dict:
    """Faz o login da coordenação e devolve o cabeçalho com o passe."""
    r = cliente.post("/v1/coordenacao/login", json={"coordenador_id": "C001", "senha": SENHA_COORD})
    return {"Authorization": f"Bearer {r.json()['passe']}"}


def test_professores_sem_hash_de_senha(cliente):
    r = cliente.get("/v1/professores")
    assert r.status_code == 200
    assert r.json() and all(set(p) == {"id", "nome"} for p in r.json())


def test_senha_errada_401_e_nada_registrado(cliente):
    r = cliente.post("/v1/registros", json={"aluno_id": "A0008", "professor_id": "P001", "senha": "errada",
                                           "acompanhamento": "Tentativa com a senha errada."})
    assert r.status_code == 401
    assert cliente.get("/v1/registros", headers=passe(cliente)).json() == []


def test_aluno_inexistente_404(cliente):
    r = cliente.post("/v1/registros", json={"aluno_id": "A9999", "professor_id": "P001", "senha": SENHA_DEMO,
                                           "acompanhamento": "Teste de aluno inexistente."})
    assert r.status_code == 404


def test_fluxo_professor_coordenacao(cliente):
    r = cliente.post("/v1/registros", json={"aluno_id": "A0008", "professor_id": "P001", "senha": SENHA_DEMO,
                                           "acompanhamento": "Faltou às duas últimas provas."})
    assert r.status_code == 201
    assert "predicao" not in r.json()  # o professor não recebe a previsão
    h = passe(cliente)
    reg = cliente.get("/v1/registros", headers=h).json()[0]
    assert reg["status"] == "aguardando_coordenacao"
    assert reg["professor"] == "Prof.ª Helena Costa"
    assert cliente.get(f"/v1/registros/{reg['id']}/documento", headers=h).status_code == 400
    r = cliente.post(f"/v1/registros/{reg['id']}/aprovar", headers=h)
    assert r.status_code == 200 and r.json()["aprovado_por"] == "Coord.ª Lúcia Ramos"
    assert cliente.post(f"/v1/registros/{reg['id']}/aprovar", headers=h).status_code == 400
    doc = cliente.get(f"/v1/registros/{reg['id']}/documento", headers=h).json()
    assert doc["para"].endswith("@example.com")
    assert "Queremos marcar uma conversa" in doc["texto"] and "diagnóstico" not in doc["texto"]
    assert re.search(r"\d{2}/\d{2}/\d{4}$", doc["texto"])  # data no padrão brasileiro
    # O relato do professor fica na ficha; não vai para a família.
    assert "Faltou às duas últimas provas" not in doc["texto"] and "Boletim" not in doc["texto"]
    com_boletim = cliente.get(f"/v1/registros/{reg['id']}/documento?modelo=convite_boletim", headers=h).json()
    assert "Boletim" in com_boletim["texto"] and "frequência" in com_boletim["texto"]
    assert "Faltou às duas últimas provas" not in com_boletim["texto"]
    assert cliente.get(f"/v1/registros/{reg['id']}/documento?modelo=outro", headers=h).status_code == 422


def test_coordenacao_sem_passe_401(cliente):
    for rota in ["/v1/registros", "/v1/registros/1", "/v1/registros/1/documento", "/v1/alunos/A0001/acessos"]:
        assert cliente.get(rota).status_code == 401
    assert cliente.post("/v1/registros/1/aprovar").status_code == 401
    assert cliente.get("/v1/registros", headers={"Authorization": "Bearer inventado"}).status_code == 401


def test_login_coordenacao_senha_errada_401(cliente):
    r = cliente.post("/v1/coordenacao/login", json={"coordenador_id": "C001", "senha": "errada"})
    assert r.status_code == 401
    assert all(set(p) == {"id", "nome"} for p in cliente.get("/v1/coordenacao").json())


def test_trilha_de_auditoria_registra_cada_acesso(cliente):
    r = cliente.post("/v1/registros", json={"aluno_id": "A0003", "professor_id": "P002", "senha": SENHA_DEMO,
                                           "acompanhamento": "Chegou atrasado três vezes na semana."})
    rid = r.json()["id"]
    h = passe(cliente)
    assert cliente.get(f"/v1/registros/{rid}", headers=h).status_code == 200
    cliente.post(f"/v1/registros/{rid}/aprovar", headers=h)
    cliente.get(f"/v1/registros/{rid}/documento", headers=h)
    trilha = cliente.get("/v1/alunos/A0003/acessos", headers=h).json()
    assert [a["acao"] for a in trilha] == ["relatorio_enviado", "ficha_aberta", "aprovado", "documento_gerado"]
    # O "quem" vem do login, não de um nome digitado.
    assert [a["quem"] for a in trilha] == ["Prof. Marcos Vieira"] + ["Coord.ª Lúcia Ramos"] * 3
