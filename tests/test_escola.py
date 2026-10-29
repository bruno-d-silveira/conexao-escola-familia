"""Testes do fluxo da escola: login do professor, registro, aprovação e documento."""
import re
import shutil
import sqlite3

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


def passe(cliente, coordenador_id="C001") -> dict:
    """Faz o login da coordenação e devolve o cabeçalho com o passe."""
    r = cliente.post("/v1/coordenacao/login", json={"coordenador_id": coordenador_id, "senha": SENHA_COORD})
    return {"Authorization": f"Bearer {r.json()['passe']}"}


def passe_professor(cliente, professor_id="P001") -> dict:
    r = cliente.post("/v1/professores/login", json={"professor_id": professor_id, "senha": SENHA_DEMO})
    return {"Authorization": f"Bearer {r.json()['passe']}"}


def enviar(cliente, aluno_id, nome, texto, professor_id="P001"):
    """O professor entra com a senha e assina o relato com o nome completo."""
    return cliente.post("/v1/registros", headers=passe_professor(cliente, professor_id),
                        json={"aluno_id": aluno_id, "nome_completo": nome, "acompanhamento": texto})


def test_professores_sem_hash_de_senha(cliente):
    r = cliente.get("/v1/professores")
    assert r.status_code == 200
    assert r.json() and all(set(p) == {"id", "nome"} for p in r.json())


def test_senha_errada_401_e_nada_registrado(cliente):
    r = cliente.post("/v1/professores/login", json={"professor_id": "P001", "senha": "errada"})
    assert r.status_code == 401
    r = cliente.post("/v1/registros", json={"aluno_id": "A0008", "nome_completo": "Helena Costa",
                                           "acompanhamento": "Tentativa sem ter entrado."})
    assert r.status_code == 401
    assert cliente.get("/v1/registros", headers=passe(cliente)).json() == []


def test_alunos_so_com_login(cliente):
    assert cliente.get("/v1/alunos").status_code == 401
    assert cliente.get("/v1/alunos", headers=passe_professor(cliente)).status_code == 200
    assert cliente.get("/v1/alunos", headers=passe(cliente)).status_code == 200


def test_professor_ve_so_as_turmas_dele(cliente):
    turmas = lambda h: {a["turma"] for a in cliente.get("/v1/alunos", headers=h).json()}
    assert turmas(passe_professor(cliente, "P001")) == {"Turma A"}
    assert turmas(passe_professor(cliente, "P002")) == {"Turma B"}
    assert turmas(passe_professor(cliente, "P003")) == {"Turma A", "Turma B"}
    assert turmas(passe(cliente)) == {"Turma A", "Turma B"}  # a coordenação vê a escola toda


def test_aluno_de_outra_turma_403_e_nada_registrado(cliente):
    # Helena é da Turma A; o A0003 é da Turma B.
    r = enviar(cliente, "A0003", "Helena Costa", "Relato sobre aluno que não é dela.")
    assert r.status_code == 403
    assert cliente.get("/v1/registros", headers=passe(cliente)).json() == []
    assert cliente.get("/v1/alunos/A0003/acessos", headers=passe(cliente)).json() == []


def test_passe_do_professor_nao_abre_a_coordenacao(cliente):
    h = passe_professor(cliente)
    for rota in ["/v1/registros", "/v1/registros/1", "/v1/registros/1/documento", "/v1/alunos/A0001/acessos"]:
        assert cliente.get(rota, headers=h).status_code == 403
    # E o passe da coordenação não envia relato no lugar do professor.
    r = cliente.post("/v1/registros", headers=passe(cliente),
                     json={"aluno_id": "A0008", "nome_completo": "Lúcia Ramos", "acompanhamento": "Não deveria sair."})
    assert r.status_code == 401


def test_nome_que_nao_confere_403_e_nada_registrado(cliente):
    r = enviar(cliente, "A0008", "Marcos Vieira", "Assinou com o nome de outro professor.")
    assert r.status_code == 403
    assert cliente.get("/v1/registros", headers=passe(cliente)).json() == []
    # Maiúscula, espaço sobrando e o título não barram.
    assert enviar(cliente, "A0008", "  helena   COSTA ", "Assinou do jeito dela.").status_code == 201


def test_aluno_inexistente_404(cliente):
    r = enviar(cliente, "A9999", "Helena Costa", "Teste de aluno inexistente.")
    assert r.status_code == 404


def test_fluxo_professor_coordenacao(cliente):
    r = enviar(cliente, "A0008", "Prof.ª Helena Costa", "Faltou às duas últimas provas.")
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
    r = enviar(cliente, "A0003", "Marcos Vieira", "Chegou atrasado três vezes na semana.", professor_id="P002")
    rid = r.json()["id"]
    h = passe(cliente)
    assert cliente.get(f"/v1/registros/{rid}", headers=h).status_code == 200
    cliente.post(f"/v1/registros/{rid}/aprovar", headers=h)
    cliente.get(f"/v1/registros/{rid}/documento", headers=h)
    trilha = cliente.get("/v1/alunos/A0003/acessos", headers=h).json()
    assert [a["acao"] for a in trilha] == ["relatorio_enviado", "ficha_aberta", "aprovado", "documento_gerado"]
    # O "quem" vem do login, não de um nome digitado.
    assert [a["quem"] for a in trilha] == ["Prof. Marcos Vieira"] + ["Coord.ª Lúcia Ramos"] * 3


def test_trilha_grava_fila_historico_e_saidas_de_quem_fez(cliente):
    rid = enviar(cliente, "A0003", "Marcos Vieira", "Chegou atrasado três vezes na semana.", professor_id="P002").json()["id"]
    lucia, paulo = passe(cliente), passe(cliente, "C002")
    cliente.get("/v1/registros", headers=lucia)
    cliente.post(f"/v1/registros/{rid}/aprovar", headers=lucia)
    # Quem gera e imprime é o Paulo: a trilha grava ele, não quem aprovou.
    cliente.get(f"/v1/registros/{rid}/documento", headers=paulo)
    for tipo in ["documento_impresso", "envio_aberto"]:
        assert cliente.post(f"/v1/registros/{rid}/saida", headers=paulo, json={"tipo": tipo}).status_code == 201
    cliente.get("/v1/alunos/A0003/acessos", headers=lucia)
    trilha = cliente.get("/v1/alunos/A0003/acessos", headers=lucia).json()
    assert [(a["acao"], a["quem"]) for a in trilha] == [
        ("relatorio_enviado", "Prof. Marcos Vieira"), ("fila_vista", "Coord.ª Lúcia Ramos"),
        ("aprovado", "Coord.ª Lúcia Ramos"), ("documento_gerado", "Coord. Paulo Teixeira"),
        ("documento_impresso", "Coord. Paulo Teixeira"), ("envio_aberto", "Coord. Paulo Teixeira"),
        ("historico_aberto", "Coord.ª Lúcia Ramos")]
    assert trilha[-1]["registro_id"] is None


def test_saida_so_da_coordenacao_e_depois_da_aprovacao(cliente):
    rid = enviar(cliente, "A0008", "Helena Costa", "Faltou às duas últimas provas.").json()["id"]
    corpo = {"tipo": "documento_impresso"}
    assert cliente.post(f"/v1/registros/{rid}/saida", json=corpo).status_code == 401
    assert cliente.post(f"/v1/registros/{rid}/saida", headers=passe_professor(cliente), json=corpo).status_code == 403
    assert cliente.post(f"/v1/registros/{rid}/saida", headers=passe(cliente), json=corpo).status_code == 400
    assert cliente.post("/v1/registros/999/saida", headers=passe(cliente), json=corpo).status_code == 404
    assert cliente.post(f"/v1/registros/{rid}/saida", headers=passe(cliente), json={"tipo": "apagou"}).status_code == 422


def test_trilha_nao_se_altera_nem_se_apaga(cliente, tmp_path):
    enviar(cliente, "A0008", "Helena Costa", "Faltou às duas últimas provas.")
    con = sqlite3.connect(tmp_path / "data" / "escola.db")
    try:
        for sql in ["update acessos set quem = 'outra pessoa'", "delete from acessos"]:
            with pytest.raises(sqlite3.IntegrityError, match="só aceita inclusão"):
                con.execute(sql)
    finally:
        con.close()
