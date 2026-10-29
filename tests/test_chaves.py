"""Testes do motor de chaves: o relato vira tema da situação, nunca rótulo da pessoa."""
from app.chaves import CHAVES, extrair
from tests.test_escola import cliente, enviar, passe, passe_professor  # noqa: F401  (fixture e ajudantes)


def temas(relato):
    return [c["chave"] for c in extrair(relato)]


def test_relato_organico_vira_tema():
    assert temas("Saiu batendo cadeiras na sala. Tem discurso de ódio forte sobre certos assuntos.") == [
        "conflito_fisico", "discurso_de_odio"]
    assert temas("Falou sobre coisas dark; disse que vai se arrepender quem mexer com ele.") == [
        "ameaca", "discurso_sombrio"]
    assert temas("Trouxe um canivete na mochila.") == ["arma"]


def test_palavra_parecida_nao_dispara():
    assert temas("Faça a lição, guardou no armário, tirou nota boa, comeu brigadeiro.") == []
    assert temas("Esta semana participou bem e ajudou os colegas.") == []


def test_cada_chave_traz_o_trecho_que_a_disparou():
    [c] = extrair("Chegou no horário. Trouxe um canivete na mochila. Depois ficou tranquilo.")
    assert c["trecho"] == "Trouxe um canivete na mochila." and c["gravidade"] == "imediata"


def test_chave_e_tema_nunca_rotulo_da_pessoa():
    rotulos = {"agressivo", "agressiva", "violento", "violenta", "perigoso", "perigosa", "problematico"}
    assert not rotulos & {nome.casefold() for nome, _, _ in CHAVES.values()}


def test_alerta_vai_para_o_topo_da_fila(cliente):
    enviar(cliente, "A0008", "Helena Costa", "Faltou às duas últimas provas.")
    enviar(cliente, "A0002", "Helena Costa", "Disse a um colega que vai se arrepender e mostrou um canivete.")
    fila = cliente.get("/v1/registros", headers=passe(cliente)).json()
    alerta = [r for r in fila if r["alerta"]]
    assert [r["aluno_id"] for r in alerta] == ["A0002"]
    assert set(alerta[0]["chaves"]) == {"ameaça", "arma"}


def test_coordenacao_soluciona_descarta_e_tudo_fica_na_trilha(cliente):
    enviar(cliente, "A0006", "Helena Costa", "Não bateu em ninguém hoje, mas ficou isolado no intervalo.")
    h = passe(cliente)
    chaves = cliente.get("/v1/alunos/A0006/chaves", headers=h).json()
    assert {c["chave"] for c in chaves} == {"conflito_fisico", "isolamento"}
    errada = next(c for c in chaves if c["chave"] == "conflito_fisico")  # a negação que o motor não entende
    certa = next(c for c in chaves if c["chave"] == "isolamento")
    r = cliente.post(f"/v1/chaves/{errada['id']}/situacao", headers=h, json={"situacao": "descartada"})
    assert r.status_code == 200 and r.json()["atualizado_por"] == "Coord.ª Lúcia Ramos"
    cliente.post(f"/v1/chaves/{certa['id']}/situacao", headers=h, json={"situacao": "solucionada"})
    # A descartada sai da fila e do painel da escola.
    assert cliente.get("/v1/registros", headers=h).json()[0]["chaves"] == ["isolamento"]
    acoes = [a["acao"] for a in cliente.get("/v1/alunos/A0006/acessos", headers=h).json()]
    assert {"chaves_vistas", "chave_descartada", "chave_solucionada"} <= set(acoes)
    assert cliente.post(f"/v1/chaves/{certa['id']}/situacao", headers=h, json={"situacao": "apagada"}).status_code == 422


def test_painel_da_escola_sem_nome_e_so_da_coordenacao(cliente):
    enviar(cliente, "A0006", "Helena Costa", "Ficou isolado no intervalo.")
    enviar(cliente, "A0008", "Helena Costa", "Ficou sozinho a semana toda.")
    assert cliente.get("/v1/indicadores/chaves").status_code == 401
    assert cliente.get("/v1/indicadores/chaves", headers=passe_professor(cliente)).status_code == 403
    painel = cliente.get("/v1/indicadores/chaves", headers=passe(cliente)).json()
    isolamento = next(c for c in painel["chaves"] if c["chave"] == "isolamento")
    assert isolamento["total"] == 2 and len(isolamento["por_mes"]) == len(painel["meses"]) == 10
    assert "A0006" not in str(painel) and "Helena" not in str(painel)


def test_chaves_do_aluno_so_da_coordenacao(cliente):
    assert cliente.get("/v1/alunos/A0006/chaves").status_code == 401
    assert cliente.get("/v1/alunos/A0006/chaves", headers=passe_professor(cliente)).status_code == 403
    assert cliente.get("/v1/alunos/A9999/chaves", headers=passe(cliente)).status_code == 404
    assert cliente.post("/v1/chaves/999/situacao", headers=passe(cliente), json={"situacao": "aberta"}).status_code == 404
