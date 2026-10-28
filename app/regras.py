"""Limitações do modelo, níveis de risco e perguntas para a conversa com a família.

Regras escritas à mão, sem IA: são transparentes e auditáveis.
"""

LIMITACOES = [
    "Base de treino: ensino superior em Portugal (UCI 697), não educação básica no Brasil.",
    "Não usa frequência: a presença vem do diário de classe e é mostrada à parte.",
    "Não lê o relatório do professor: o texto fica no registro, fora do cálculo.",
    "Média 0 na base significa sem nota registrada no semestre, não nota zero.",
    "Mostra associação, não causa: o risco é um ponto de partida para a conversa, não um diagnóstico.",
]

PERGUNTAS_BASE = [
    "Como tem sido a rotina de estudos em casa?",
    "Há algo na escola que esteja dificultando a presença dele?",
]

# fator do modelo -> pergunta humana
PERGUNTAS_POR_FATOR = {
    "mensalidade_em_dia": "Como está a situação em casa para manter os estudos? Há algum apoio possível?",
    "devedor": "Existe alguma dívida que esteja pesando? Ele sabe dos auxílios da instituição?",
    "disciplinas_1sem_aprovadas": "Em quais disciplinas ele se sente perdido? Sabe a quem pedir ajuda?",
    "disciplinas_2sem_aprovadas": "Em quais disciplinas ele se sente perdido? Sabe a quem pedir ajuda?",
    "media_1sem": "O que mudou entre o começo do curso e agora?",
    "media_2sem": "O que mudou entre o começo do curso e agora?",
    "disciplinas_2sem_sem_avaliacao": "Ele tem deixado de fazer provas? O que aconteceu nesses dias?",
    "mora_longe_de_casa": "Ele tem com quem contar perto de onde mora agora?",
    "idade": "Ele concilia o estudo com trabalho ou com a família?",
    "turno_diurno": "Como está o cansaço de quem estuda à noite?",
}

ROTULOS = {
    "idade": "idade na matrícula",
    "nota_admissao": "nota de admissão",
    "disciplinas_1sem_inscritas": "disciplinas inscritas no 1º semestre",
    "disciplinas_1sem_aprovadas": "poucas disciplinas aprovadas no 1º semestre",
    "media_1sem": "média do 1º semestre",
    "disciplinas_2sem_inscritas": "disciplinas inscritas no 2º semestre",
    "disciplinas_2sem_aprovadas": "poucas disciplinas aprovadas no 2º semestre",
    "media_2sem": "média do 2º semestre",
    "disciplinas_2sem_sem_avaliacao": "disciplinas sem avaliação no 2º semestre",
    "mensalidade_em_dia": "mensalidade atrasada",
    "devedor": "dívida com a instituição",
    "bolsista": "sem bolsa",
    "mora_longe_de_casa": "mora longe de casa",
    "turno_diurno": "turno",
}


def nivel(risco: float) -> str:
    if risco < 0.33:
        return "baixo"
    if risco < 0.66:
        return "medio"
    return "alto"


def perguntas(fatores: list[str]) -> list[str]:
    """Perguntas base + as ligadas aos fatores que mais pesaram, sem repetir."""
    saida = list(PERGUNTAS_BASE)
    for f in fatores:
        p = PERGUNTAS_POR_FATOR.get(f)
        if p and p not in saida:
            saida.append(p)
    return saida
