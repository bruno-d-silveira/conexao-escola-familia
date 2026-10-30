"""Testes do painel de mar e chuva. Sem internet: as fontes públicas são trocadas por dados montados aqui."""
import urllib.error
from datetime import date, timedelta

import pytest

import app.clima as clima
from tests.test_escola import cliente, passe, passe_professor  # noqa: F401  (fixture e ajudantes)

HOJE = date.today()
DIAS = [(HOJE + timedelta(days=i)).isoformat() for i in range(7)]


def fontes(inmet=None, swell=None, chuva_prob=None):
    """Monta as respostas das três fontes. swell: {dia: (altura, direção, período)}; chuva_prob: {dia: %}."""
    swell, chuva_prob = swell or {}, chuva_prob or {}
    horas = [f"{d}T{h:02d}:00" for d in DIAS for h in range(24)]

    def marine(praia):
        s = [swell.get(i, (1.0, 90, 7)) for i in range(7)]
        return {"daily": {"time": DIAS, "swell_wave_height_max": [x[0] for x in s],
                          "swell_wave_direction_dominant": [x[1] for x in s],
                          "swell_wave_period_max": [x[2] for x in s],
                          "wave_height_max": [round(x[0] * (0.7 if praia else 1.2), 2) for x in s]},
                "hourly": {"time": horas, "wave_height": [0.8] * len(horas), "sea_level_height_msl": [0.3] * len(horas)}}

    def buscar(url):
        if "marine" in url:
            return marine(praia="-48.46" in url)
        if "forecast" in url:
            return {"daily": {"time": DIAS, "weather_code": [61, 3, 0, 2, 45, 95, 80],
                              "temperature_2m_max": [24.0] * 7, "temperature_2m_min": [17.0] * 7,
                              "precipitation_sum": [2.0] * 7,
                              "precipitation_probability_max": [chuva_prob.get(i, 20) for i in range(7)]}}
        return inmet or {"hoje": [], "futuro": []}
    return buscar


def aviso_inmet(dia, geocodes="4205407,4202305,", severidade="Perigo Potencial"):
    return {"descricao": "Chuvas Intensas", "severidade": severidade, "inicio": f"{DIAS[dia]} 00:00",
            "fim": f"{DIAS[dia]} 23:59", "geocodes": geocodes, "riscos": ["Chuva de 20 a 30 mm/h."],
            "instrucoes": ["Obtenha mais informações junto à Defesa Civil (telefone 199)."]}


def test_nivel_vem_so_do_inmet(monkeypatch):
    inmet = {"hoje": [aviso_inmet(0)], "futuro": [aviso_inmet(1, severidade="Perigo")]}
    monkeypatch.setattr(clima, "buscar_json", fontes(inmet=inmet))
    p = clima.previsao()
    assert [d["nivel"] for d in p["dias"][:3]] == ["atencao", "alerta", "normal"]
    assert p["nivel"] == "alerta"


def test_swell_de_sul_nao_acende_nada_enquanto_a_regra_nao_for_ajustada(monkeypatch):
    monkeypatch.setattr(clima, "buscar_json", fontes(swell={0: (3.0, 180, 14)}))
    p = clima.previsao()
    assert p["nivel"] == "normal" and p["dias"][0]["swell_rumo"] == "sul"


def test_aviso_fora_da_janela_nao_muda_o_nivel_do_painel(monkeypatch):
    monkeypatch.setattr(clima, "buscar_json", fontes(inmet={"hoje": [], "futuro": [aviso_inmet(5, severidade="Perigo")]}))
    p = clima.previsao()
    assert p["dias"][5]["nivel"] == "alerta" and p["nivel"] == "normal"


def test_so_avisos_de_florianopolis(monkeypatch):
    inmet = {"hoje": [aviso_inmet(0), aviso_inmet(0, geocodes="2900603,")], "futuro": []}
    monkeypatch.setattr(clima, "buscar_json", fontes(inmet=inmet))
    assert len(clima.previsao()["avisos"]) == 1


def test_dias_como_no_celular(monkeypatch):
    inmet = {"hoje": [aviso_inmet(0)], "futuro": [aviso_inmet(1)]}
    monkeypatch.setattr(clima, "buscar_json", fontes(inmet=inmet))
    p = clima.previsao()
    assert [d["rotulo"] for d in p["dias"][:2]] == ["Hoje", "Amanhã"]
    assert p["dias"][2]["rotulo"] == clima.SEMANA[date.fromisoformat(DIAS[2]).weekday()]
    # chance de 20%: o código marca chuva, mas o dia aparece nublado
    assert [d["tempo"] for d in p["dias"]] == ["nublado", "nublado", "sol", "parcial", "neblina", "tempestade", "nublado"]
    assert p["resumo"] == "Chuvas intensas hoje e amanhã."


def test_resumo_sem_aviso(monkeypatch):
    monkeypatch.setattr(clima, "buscar_json", fontes(chuva_prob={0: 85}))
    p = clima.previsao()
    assert p["resumo"] == "Chuva provável hoje." and p["dias"][0]["tempo"] == "chuva"
    monkeypatch.setattr(clima, "buscar_json", fontes())
    assert clima.previsao()["resumo"] == "Sem avisos do INMET para os próximos dias."


def test_rota_so_da_coordenacao_e_guarda_por_tres_horas(cliente, monkeypatch):
    chamadas = []
    buscar = fontes(inmet={"hoje": [aviso_inmet(0)], "futuro": []})
    monkeypatch.setattr(clima, "buscar_json", lambda url: chamadas.append(url) or buscar(url))
    assert cliente.get("/v1/clima").status_code == 401
    assert cliente.get("/v1/clima", headers=passe_professor(cliente)).status_code == 403
    h = passe(cliente)
    r = cliente.get("/v1/clima", headers=h)
    assert r.status_code == 200 and r.json()["nivel"] == "atencao" and len(r.json()["dias"]) == 7
    cliente.get("/v1/clima", headers=h)
    assert len(chamadas) == 4  # 4 fontes, buscadas uma vez só
    cliente.get("/v1/clima?atualizar=true", headers=h)
    assert len(chamadas) == 8


def test_aviso_da_semana_curto_com_o_dia_da_semana(cliente, monkeypatch):
    monkeypatch.setattr(clima, "buscar_json", fontes(inmet={"hoje": [], "futuro": [aviso_inmet(1)]}))
    texto = cliente.get("/v1/clima/aviso", headers=passe(cliente)).json()["texto"]
    amanha = date.fromisoformat(DIAS[1])
    linha = f"{clima.SEMANA[amanha.weekday()][:3].upper()} {amanha:%d/%m} · atenção · chuvas intensas"
    assert linha in texto and "Fonte: INMET" in texto and "199" in texto
    assert texto.count(" · atenção · ") == 1  # só os dias com aviso


def test_semana_sem_aviso(cliente, monkeypatch):
    monkeypatch.setattr(clima, "buscar_json", fontes())
    assert "Semana sem avisos do INMET" in cliente.get("/v1/clima/aviso", headers=passe(cliente)).json()["texto"]


@pytest.mark.parametrize("erro", [urllib.error.URLError("sem rede"), TimeoutError(), KeyError("daily")])
def test_fonte_fora_do_ar_vira_503(cliente, monkeypatch, erro):
    def falha(url):
        raise erro
    monkeypatch.setattr(clima, "buscar_json", falha)
    r = cliente.get("/v1/clima", headers=passe(cliente))
    assert r.status_code == 503 and "indisponível" in r.json()["detail"]
