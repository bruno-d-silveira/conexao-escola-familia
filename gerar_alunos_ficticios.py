"""Cria data/alunos_ficticios.json: o cadastro de demonstração da escola.

Os dados acadêmicos vêm de linhas reais e anônimas da base UCI (que não tem nomes).
Os nomes, turmas e e-mails são INVENTADOS. Nenhum dado pessoal real entra no projeto.

Matrícula e frequência também são inventadas: a base UCI não tem esses campos.
Numa escola, os dois vêm do sistema de secretaria: a situação da matrícula do cadastro
e a frequência do diário de classe (a chamada). Por isso cada aluno leva "fonte": "demo".

Faixa etária: a base é de ensino superior e vai de 17 a 70 anos. A demonstração usa só
estudantes de 17 a 20 anos, a idade típica de quem acaba de sair da escola; os mais velhos
são outliers para o público do projeto e deixariam a demo implausível.

Como rodar:  python gerar_alunos_ficticios.py   (depois de python treinar.py)
"""
import json
from pathlib import Path

import joblib
import pandas as pd

from treinar import BINARIAS, COLUNAS, DADOS

RAIZ = Path(__file__).resolve().parent
IDADE_MIN, IDADE_MAX = 17, 20
NOMES = ["Ana Beatriz Rocha", "Caio Henrique Lima", "Débora Martins", "Felipe Duarte",
         "Gabriela Nunes", "Igor Santana", "Júlia Ferraz", "Lucas Pereira"]
# Frequência (%) por semestre, do menor para o maior risco: quem falta mais, arrisca mais.
FREQUENCIA = [(97, 96), (95, 93), (94, 90), (92, 88), (90, 84), (86, 78), (80, 66), (74, 52)]


def main():
    bruto = pd.read_csv(DADOS, sep=";")
    x = bruto[list(COLUNAS)].rename(columns=COLUNAS)
    x = x[x["idade"].between(IDADE_MIN, IDADE_MAX)]
    risco = joblib.load(RAIZ / "models" / "modelo_evasao.joblib").predict_proba(x)[:, 1]
    # Oito estudantes espalhados do risco mais baixo ao mais alto, para a demonstração.
    ordem = pd.Series(risco, index=x.index).sort_values().index
    escolhidos = [ordem[int(i * (len(ordem) - 1) / 7)] for i in range(8)]
    alunos = []
    for n, idx in enumerate(escolhidos, start=1):
        dados = x.loc[idx].to_dict()
        for coluna in BINARIAS.values():
            dados[coluna] = bool(dados[coluna])
        for coluna in ("idade", "disciplinas_1sem_inscritas", "disciplinas_1sem_aprovadas",
                       "disciplinas_2sem_inscritas", "disciplinas_2sem_aprovadas",
                       "disciplinas_2sem_sem_avaliacao"):
            dados[coluna] = int(dados[coluna])
        for coluna in ("nota_admissao", "media_1sem", "media_2sem"):
            dados[coluna] = round(float(dados[coluna]), 2)
        alunos.append({
            "id": f"A{n:04d}",
            "nome": NOMES[n - 1],
            "turma": f"Turma {'AB'[n % 2]}",
            "email_responsavel": f"responsavel.a{n:04d}@example.com",
            "matricula": ({"situacao": "inativa", "motivo": "Pendência de documentação na secretaria."}
                          if n == 8 else {"situacao": "ativa", "motivo": None}),
            "frequencia": {"sem1": FREQUENCIA[n - 1][0], "sem2": FREQUENCIA[n - 1][1], "fonte": "demo"},
            "dados": dados,
        })
    destino = RAIZ / "data" / "alunos_ficticios.json"
    destino.write_text(json.dumps(alunos, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{len(alunos)} alunos fictícios em {destino}")


if __name__ == "__main__":
    main()
