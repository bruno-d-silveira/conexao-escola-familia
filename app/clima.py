"""Mar e chuva para as escolas de Florianópolis: previsão de 7 dias e os avisos oficiais.

Fontes públicas, sem chave de acesso:
- Open-Meteo Marine: onda no mar aberto e na praia, swell (altura, direção, período) e o nível do mar.
- Open-Meteo Forecast: chuva, temperatura e o tempo de cada dia.
- INMET: avisos meteorológicos ativos para Florianópolis (geocódigo IBGE 4205407).

O nível do painel vem só dos avisos do INMET. A regra do swell de sul (que enche a maré nos mangues e
trava a mobilidade da cidade) ainda precisa de ajuste fino: não é qualquer ondulação de sul que pede
chamada. Até lá, os dados do mar aparecem no painel, mas não acendem alerta.
"""
import json
import urllib.request
from datetime import date, datetime

FLORIANOPOLIS = "4205407"
MAR_ABERTO = (-27.70, -48.20)
PRAIA = (-27.70, -48.46)  # Campeche, voltada para o sul
CENTRO = (-27.59, -48.55)
FUSO = "America%2FSao_Paulo"
DIAS = 7
JANELA = 2  # o nível do painel olha hoje e os 2 dias seguintes

# Severidade do aviso do INMET -> nível do painel
NIVEL_DO_INMET = {"Perigo Potencial": "atencao", "Perigo": "alerta", "Grande Perigo": "alerta"}

SEMANA = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]

MARINE = ("https://marine-api.open-meteo.com/v1/marine?latitude={}&longitude={}&timezone=" + FUSO +
          f"&forecast_days={DIAS}&hourly=wave_height,sea_level_height_msl"
          "&daily=swell_wave_height_max,swell_wave_direction_dominant,swell_wave_period_max,wave_height_max")
TEMPO = ("https://api.open-meteo.com/v1/forecast?latitude={}&longitude={}&timezone=" + FUSO +
         f"&forecast_days={DIAS}&daily=weather_code,temperature_2m_max,temperature_2m_min,"
         "precipitation_sum,precipitation_probability_max")
INMET = "https://apiprevmet3.inmet.gov.br/avisos/ativos"


def buscar_json(url: str) -> dict:
    pedido = urllib.request.Request(url, headers={"User-Agent": "conexao-escola-familia"})
    with urllib.request.urlopen(pedido, timeout=20) as r:
        return json.loads(r.read())


def _rumo(graus: float | None) -> str:
    if graus is None:
        return "—"
    return ["norte", "nordeste", "leste", "sudeste", "sul", "sudoeste", "oeste", "noroeste"][round(graus / 45) % 8]


def _tempo(codigo: int | None, chance: int | None = None) -> str:
    """Código do tempo (padrão WMO) -> o ícone do dia. O código diário marca chuva se chover em qualquer
    hora; com chance abaixo de 40%, o dia aparece nublado, como no app de clima do celular."""
    if codigo is not None and (51 <= codigo <= 67 or 80 <= codigo <= 82) and (chance or 0) < 40:
        return "nublado"
    if codigo is None:
        return "nublado"
    if codigo == 0:
        return "sol"
    if codigo in (1, 2):
        return "parcial"
    if codigo in (45, 48):
        return "neblina"
    if 51 <= codigo <= 67 or 80 <= codigo <= 82:
        return "chuva"
    if codigo >= 95:
        return "tempestade"
    return "nublado"


def rotulo(dia: str, hoje: date) -> str:
    """Hoje, amanhã ou o dia da semana, como no celular."""
    d = date.fromisoformat(dia)
    return {0: "Hoje", 1: "Amanhã"}.get((d - hoje).days, SEMANA[d.weekday()])


def _avisos_de_florianopolis(bruto: dict) -> list[dict]:
    avisos = []
    for quando in ("hoje", "futuro"):
        for a in bruto.get(quando, []):
            if FLORIANOPOLIS in str(a.get("geocodes", "")).split(","):
                avisos.append({"descricao": a["descricao"], "severidade": a["severidade"],
                               "inicio": a["inicio"], "fim": a["fim"], "riscos": a.get("riscos", []),
                               "instrucoes": [i.strip() for i in a.get("instrucoes", [])]})
    return avisos


def _resumo(proximos: list[dict]) -> str:
    """Uma frase curta no topo: o aviso dos próximos dias ou a chance de chuva de hoje."""
    por_aviso: dict[str, list[str]] = {}
    for d in proximos:
        for a in d["avisos"]:
            por_aviso.setdefault(a["descricao"], []).append(d["rotulo"].lower())
    if por_aviso:
        partes = [f"{desc} {' e '.join(dias) if len(dias) < 3 else ', '.join(dias[:-1]) + ' e ' + dias[-1]}"
                  for desc, dias in por_aviso.items()]
        return "; ".join(partes).capitalize() + "."
    if proximos and (proximos[0]["chuva_prob"] or 0) >= 60:
        return "Chuva provável hoje."
    return "Sem avisos do INMET para os próximos dias."


def previsao(hoje: date | None = None) -> dict:
    """Junta as três fontes num quadro de 7 dias; o nível vem dos avisos do INMET."""
    hoje = hoje or date.today()
    buscar = buscar_json  # lido na hora: os testes trocam por dados montados, sem internet
    mar = buscar(MARINE.format(*MAR_ABERTO))
    praia = buscar(MARINE.format(*PRAIA))
    tempo = buscar(TEMPO.format(*CENTRO))["daily"]
    avisos = _avisos_de_florianopolis(buscar(INMET))
    dias = []
    for i, dia in enumerate(mar["daily"]["time"]):
        mares = [v for t, v in zip(praia["hourly"]["time"], praia["hourly"]["sea_level_height_msl"])
                 if t.startswith(dia) and v is not None]
        do_dia = [a for a in avisos if a["inicio"][:10] <= dia <= a["fim"][:10]]
        niveis = [NIVEL_DO_INMET.get(a["severidade"], "atencao") for a in do_dia]
        dias.append({
            "data": dia, "rotulo": rotulo(dia, hoje),
            "tempo": _tempo(tempo["weather_code"][i], tempo["precipitation_probability_max"][i]),
            "temp_max": tempo["temperature_2m_max"][i], "temp_min": tempo["temperature_2m_min"][i],
            "chuva_mm": tempo["precipitation_sum"][i], "chuva_prob": tempo["precipitation_probability_max"][i],
            "swell_altura": mar["daily"]["swell_wave_height_max"][i],
            "swell_direcao": mar["daily"]["swell_wave_direction_dominant"][i],
            "swell_rumo": _rumo(mar["daily"]["swell_wave_direction_dominant"][i]),
            "swell_periodo": mar["daily"]["swell_wave_period_max"][i],
            "onda_praia": praia["daily"]["wave_height_max"][i],
            "mare_max": max(mares) if mares else None,
            "avisos": do_dia,
            "nivel": "alerta" if "alerta" in niveis else "atencao" if niveis else "normal"})
    proximos = [d for d in dias if 0 <= (date.fromisoformat(d["data"]) - hoje).days <= JANELA]
    nivel = "alerta" if any(d["nivel"] == "alerta" for d in proximos) else \
        "atencao" if any(d["nivel"] == "atencao" for d in proximos) else "normal"
    return {"atualizado_em": datetime.now().isoformat(timespec="minutes"), "nivel": nivel,
            "resumo": _resumo(proximos), "dias": dias,
            "horas": {"tempo": mar["hourly"]["time"], "onda_mar_aberto": mar["hourly"]["wave_height"],
                      "onda_praia": praia["hourly"]["wave_height"]},
            "avisos": avisos, "fontes": ["INMET (avisos)", "Open-Meteo (mar, chuva e temperatura)"]}


def aviso_da_semana(p: dict) -> dict:
    """A versão para e-mail do quadro da semana: só os dias com aviso, com o dia da semana na frente."""
    curto = lambda d: f"{SEMANA[date.fromisoformat(d['data']).weekday()][:3].upper()} {d['data'][8:10]}/{d['data'][5:7]}"
    marca = {"alerta": "alerta", "atencao": "atenção"}
    linhas = [f"  {curto(d)} · {marca[d['nivel']]} · {', '.join(a['descricao'].lower() for a in d['avisos'])}"
              for d in p["dias"] if d["avisos"]]
    corpo = ("Previsão dos próximos dias em Florianópolis:\n" + "\n".join(linhas)) if linhas \
        else "Semana sem avisos do INMET para Florianópolis."
    texto = (f"Prezados professores e famílias,\n\n{corpo}\n\n"
             "Em emergência: Defesa Civil 199 · Bombeiros 193.\nFonte: INMET\n\nCoordenação")
    return {"assunto": f"Previsão da semana: {curto(p['dias'][0])} a {curto(p['dias'][-1])}", "texto": texto}
