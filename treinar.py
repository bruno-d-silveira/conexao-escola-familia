"""
Fase 1 — Preparação e serialização do modelo (pipeline offline)

Pergunta de negócio: este estudante corre risco de evadir?
Base: UCI "Predict Students' Dropout and Academic Success" (id 697, CC BY 4.0),
4.424 estudantes do Politécnico de Portalegre, Portugal. Arquivo: data/data.csv.

Como rodar:  python treinar.py
Saídas:      models/modelo_evasao.joblib  e  models/metricas.json
"""
import json
from pathlib import Path

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, f1_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

RAIZ = Path(__file__).resolve().parent
DADOS = RAIZ / "data" / "data.csv"
SAIDA = RAIZ / "models"
SEMENTE = 42

# ---------------------------------------------------------------------------
# 1. Escolha das colunas
# ---------------------------------------------------------------------------
# Só entra o que um professor ou a coordenação sabe sobre o estudante.
# Ficam FORA, por decisão de governança: gênero, nacionalidade, estado civil,
# necessidades educativas especiais, profissão e escolaridade dos pais.
# Também ficam fora os indicadores da economia do país (desemprego, inflação, PIB):
# a escola não os controla e eles não dizem nada sobre o estudante.
NUMERICAS = {
    "Age at enrollment": "idade",
    "Admission grade": "nota_admissao",
    "Curricular units 1st sem (enrolled)": "disciplinas_1sem_inscritas",
    "Curricular units 1st sem (approved)": "disciplinas_1sem_aprovadas",
    "Curricular units 1st sem (grade)": "media_1sem",
    "Curricular units 2nd sem (enrolled)": "disciplinas_2sem_inscritas",
    "Curricular units 2nd sem (approved)": "disciplinas_2sem_aprovadas",
    "Curricular units 2nd sem (grade)": "media_2sem",
    "Curricular units 2nd sem (without evaluations)": "disciplinas_2sem_sem_avaliacao",
}
BINARIAS = {
    "Tuition fees up to date": "mensalidade_em_dia",
    "Debtor": "devedor",
    "Scholarship holder": "bolsista",
    "Displaced": "mora_longe_de_casa",
    "Daytime/evening attendance\t": "turno_diurno",
}
COLUNAS = {**NUMERICAS, **BINARIAS}


def carregar():
    """Lê a base, renomeia para português e cria o alvo binário."""
    bruto = pd.read_csv(DADOS, sep=";")
    x = bruto[list(COLUNAS)].rename(columns=COLUNAS)
    # Alvo: 1 = evadiu (Dropout); 0 = continua matriculado ou formou-se.
    y = (bruto["Target"] == "Dropout").astype(int)
    return x, y


def montar_pipeline(modelo):
    """Pré-processamento dentro do pipeline: o mesmo tratamento no treino e na API."""
    numericas = Pipeline([
        # A base não tem nulos, mas o dado real da escola sempre vem com buraco.
        ("imputar", SimpleImputer(strategy="median")),
        ("escalar", StandardScaler()),
    ])
    binarias = Pipeline([
        ("imputar", SimpleImputer(strategy="most_frequent")),
        ("codificar", OneHotEncoder(drop="if_binary", handle_unknown="ignore")),
    ])
    preparo = ColumnTransformer([
        ("num", numericas, list(NUMERICAS.values())),
        ("bin", binarias, list(BINARIAS.values())),
    ])
    return Pipeline([("preparo", preparo), ("modelo", modelo)])


def avaliar(pipeline, x, y):
    prob = pipeline.predict_proba(x)[:, 1]
    pred = (prob >= 0.5).astype(int)
    return {
        "acuracia": round(accuracy_score(y, pred), 4),
        "f1_evasao": round(f1_score(y, pred), 4),
        "roc_auc": round(roc_auc_score(y, prob), 4),
    }


def main():
    x, y = carregar()

    # ---------------------------------------------------------------------
    # 2. Divisão treino / validação / teste (60 / 20 / 20), estratificada
    # ---------------------------------------------------------------------
    x_tmp, x_teste, y_tmp, y_teste = train_test_split(
        x, y, test_size=0.20, stratify=y, random_state=SEMENTE)
    x_treino, x_val, y_treino, y_val = train_test_split(
        x_tmp, y_tmp, test_size=0.25, stratify=y_tmp, random_state=SEMENTE)

    # ---------------------------------------------------------------------
    # 3. Dois candidatos, escolhidos pela validação
    # ---------------------------------------------------------------------
    # class_weight="balanced": evadir é a classe menor (32%); sem peso,
    # o modelo aprende a dizer "fica" para quase todos.
    candidatos = {
        "regressao_logistica": LogisticRegression(
            max_iter=2000, class_weight="balanced", random_state=SEMENTE),
        "gradient_boosting": HistGradientBoostingClassifier(
            class_weight="balanced", random_state=SEMENTE),
    }
    validacao = {}
    for nome, modelo in candidatos.items():
        pipe = montar_pipeline(modelo).fit(x_treino, y_treino)
        validacao[nome] = avaliar(pipe, x_val, y_val)
        print(f"validação  {nome:22} {validacao[nome]}")

    # Critério: a regressão logística ganha se ficar a menos de 0,02 de ROC-AUC
    # do melhor. Ela explica cada fator com um peso, e é isso que a API mostra
    # ao professor ("o que mais pesou").
    melhor = max(validacao, key=lambda n: validacao[n]["roc_auc"])
    escolhido = ("regressao_logistica"
                 if validacao[melhor]["roc_auc"] - validacao["regressao_logistica"]["roc_auc"] < 0.02
                 else melhor)
    print(f"escolhido: {escolhido}")

    # ---------------------------------------------------------------------
    # 4. Treino final (treino + validação) e teste, que só é visto uma vez
    # ---------------------------------------------------------------------
    final = montar_pipeline(candidatos[escolhido]).fit(x_tmp, y_tmp)
    teste = avaliar(final, x_teste, y_teste)
    print(f"teste      {escolhido:22} {teste}")
    print(classification_report(y_teste, final.predict(x_teste),
                                target_names=["não evadiu", "evadiu"]))

    # ---------------------------------------------------------------------
    # 5. Serialização do artefato e relatório de métricas
    # ---------------------------------------------------------------------
    SAIDA.mkdir(exist_ok=True)
    joblib.dump(final, SAIDA / "modelo_evasao.joblib")
    relatorio = {
        "base": "UCI 697 - Predict Students' Dropout and Academic Success (CC BY 4.0)",
        "alvo": "1 = evadiu (Dropout); 0 = matriculado ou formado",
        "divisao": {"treino": len(x_treino), "validacao": len(x_val), "teste": len(x_teste)},
        "colunas": list(COLUNAS.values()),
        "validacao": validacao,
        "modelo_escolhido": escolhido,
        "teste": teste,
    }
    (SAIDA / "metricas.json").write_text(json.dumps(relatorio, indent=2, ensure_ascii=False),
                                         encoding="utf-8")
    print(f"salvo em {SAIDA / 'modelo_evasao.joblib'}")


if __name__ == "__main__":
    main()
