"""O que o modelo não enxerga, e as perguntas que ajudam a enxergar.

Regras escritas à mão, sem IA: são transparentes e qualquer pessoa da escola pode lê-las.
"""

PONTOS_CEGOS = [
    "Sono: o modelo não sabe se o estudante dorme bem.",
    "Luz do sol e hábitos: não sabe se ele sai de casa de dia, se se alimenta, se se mexe.",
    "Casa e escola: não sabe o que acontece entre a família e a escola.",
    "Pertencimento: não sabe se ele tem com quem contar na turma.",
    "O texto do professor: o acompanhamento escrito não entra no cálculo, só no registro.",
]

PERGUNTAS_BASE = [
    "Como ele tem dormido?",
    "Com quem ele conversa aqui na escola?",
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
