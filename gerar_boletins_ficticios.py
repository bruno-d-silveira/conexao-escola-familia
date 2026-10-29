"""Cria data/boletins_ficticios.json: o boletim de demonstração de cada aluno, no padrão brasileiro.

A base UCI só tem médias e disciplinas aprovadas por SEMESTRE, numa escala de 0 a 20. O boletim
que os pais acompanham é outro: disciplina por disciplina, mês a mês, notas de 0 a 10 e faltas,
em dois blocos de semestre. Este script DERIVA o boletim a partir dos números da base: o 1º semestre
vira fevereiro a junho e o 2º semestre vira agosto até o mês atual. A média de cada semestre e a
proporção de disciplinas acima da média seguem as da base; as notas de cada mês e as faltas são
INVENTADAS em volta delas. Por isso cada boletim leva "fonte": "demo". Numa escola, vem do diário de classe.

O ano letivo de 2026 ainda não fechou: o boletim mostra até ATUALIZADO_EM, com o mês corrente em
andamento e os meses seguintes vazios.

Como rodar:  python gerar_boletins_ficticios.py   (depois de python gerar_alunos_ficticios.py)
"""
import json
import random
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
ANO_LETIVO = 2026
ATUALIZADO_EM = date(2026, 10, 29)
MEDIA_APROVACAO = 6.0
AULAS_POR_MES = 8  # duas aulas por semana, em cada disciplina
# Dez meses letivos, julho de férias: 1º semestre de fevereiro a junho, 2º de agosto a dezembro.
MESES = [(2, "fev"), (3, "mar"), (4, "abr"), (5, "mai"), (6, "jun"),
         (8, "ago"), (9, "set"), (10, "out"), (11, "nov"), (12, "dez")]
DISCIPLINAS = ["Língua Portuguesa", "Matemática", "Inglês", "Arte", "Educação Física", "História",
               "Geografia", "Filosofia", "Sociologia", "Física", "Química", "Biologia"]


def notas_do_semestre(rng, media, aprovadas, inscritas):
    """Uma nota de semestre por disciplina, em volta da média, com a mesma proporção acima da média."""
    if inscritas == 0 or media == 0:
        # Média 0 na base = sem nota registrada no semestre.
        return [None] * len(DISCIPLINAS)
    alvo = media / 2  # escala de 0 a 20 para 0 a 10
    notas = sorted((alvo + rng.uniform(-1.5, 1.5) for _ in DISCIPLINAS), reverse=True)
    quantas = round(aprovadas / inscritas * len(DISCIPLINAS))
    notas = [max(n, MEDIA_APROVACAO) if i < quantas else min(n, MEDIA_APROVACAO - 0.5)
             for i, n in enumerate(notas)]
    rng.shuffle(notas)
    return [min(max(n, 0.0), 10.0) for n in notas]


def meses_do_semestre(rng, nota_semestre, quantos):
    """Notas mensais que oscilam em volta da nota do semestre, sem mudar a média."""
    if nota_semestre is None:
        return [None] * quantos
    desvios = [rng.uniform(-0.8, 0.8) for _ in range(quantos)]
    media_desvios = sum(desvios) / quantos
    return [round(min(max(nota_semestre + d - media_desvios, 0.0), 10.0), 1) for d in desvios]


def faltas_do_mes(rng, frequencia):
    """Faltas no mês que batem com a frequência (%) do semestre."""
    return max(0, round(AULAS_POR_MES * (100 - frequencia) / 100 + rng.uniform(-0.6, 0.6)))


def main():
    alunos = json.loads((RAIZ / "data" / "alunos_ficticios.json").read_text(encoding="utf-8"))
    dados_ate = [m for m, _ in MESES if m <= ATUALIZADO_EM.month]  # do mês corrente em diante, nada
    sem1 = [m for m, _ in MESES if m <= 6]
    sem2 = [m for m in dados_ate if m >= 8]
    boletins = []
    for a in alunos:
        rng = random.Random(a["id"])  # mesma semente, mesmo boletim a cada execução
        d, f = a["dados"], a["frequencia"]
        n1 = notas_do_semestre(rng, d["media_1sem"], d["disciplinas_1sem_aprovadas"], d["disciplinas_1sem_inscritas"])
        n2 = notas_do_semestre(rng, d["media_2sem"], d["disciplinas_2sem_aprovadas"], d["disciplinas_2sem_inscritas"])
        disciplinas = []
        for nome, s1, s2 in zip(DISCIPLINAS, n1, n2):
            notas = meses_do_semestre(rng, s1, len(sem1)) + meses_do_semestre(rng, s2, len(sem2))
            faltas = ([faltas_do_mes(rng, f["sem1"]) for _ in sem1] + [faltas_do_mes(rng, f["sem2"]) for _ in sem2])
            vazios = len(MESES) - len(notas)
            disciplinas.append({"disciplina": nome, "notas": notas + [None] * vazios,
                                "faltas": faltas + [None] * vazios})
        boletins.append({"aluno_id": a["id"], "ano_letivo": ANO_LETIVO, "atualizado_em": ATUALIZADO_EM.isoformat(),
                         "meses": [nome for _, nome in MESES], "media_aprovacao": MEDIA_APROVACAO,
                         "aulas_por_mes": AULAS_POR_MES, "fechado": False, "fonte": "demo", "disciplinas": disciplinas})
    destino = RAIZ / "data" / "boletins_ficticios.json"
    destino.write_text(json.dumps(boletins, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{len(boletins)} boletins fictícios em {destino}")


if __name__ == "__main__":
    main()
