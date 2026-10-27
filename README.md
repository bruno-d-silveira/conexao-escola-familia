# Conexão Escola-Família

API FastAPI que estima o risco de evasão de um estudante e devolve, junto com o número, os fatores que mais pesaram, o que o modelo não enxerga e perguntas para a conversa com a família.

## Modelo

| | |
|---|---|
| Base | [UCI 697 – Predict Students' Dropout and Academic Success](https://archive.ics.uci.edu/dataset/697) (4.424 estudantes, CC BY 4.0) |
| Alvo | 1 = evadiu; 0 = matriculado ou formado |
| Divisão | 60/20/20 estratificada (2654 / 885 / 885), semente 42 |
| Candidatos | Regressão logística × HistGradientBoosting, ambos com `class_weight="balanced"` |
| Escolhido | Regressão logística (diferença de ROC-AUC < 0,02; pesos explicáveis) |
| Teste | acurácia 0,872 · F1 (evasão) 0,804 · ROC-AUC 0,924 |

Colunas fora por governança: gênero, nacionalidade, estado civil, necessidades especiais, profissão e escolaridade dos pais, indicadores macroeconômicos.

Treino offline: `python treinar.py` → `models/modelo_evasao.joblib` e `models/metricas.json`.

## Estrutura

```
app/
  main.py          lifespan (carrega o .joblib uma vez) e handler de 500
  services.py      inferência e fatores (peso × valor da regressão logística)
  schemas.py       contratos Pydantic com Field (faixas → 422)
  regras.py        limitações, níveis e perguntas, escritos à mão
  routers/
    predicao.py    /health e /v1/predict
tests/test_api.py  200, 400, 422 e 500
treinar.py         pipeline offline
```

## Rodar

```bash
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Documentação interativa: http://127.0.0.1:8000/docs

## Endpoints

| Método | Rota | Resposta |
|---|---|---|
| GET | `/health` | status e se o modelo está carregado |
| POST | `/v1/predict` | risco, nível, fatores, limitações, perguntas |

| Código | Quando |
|---|---|
| 200 | previsão feita |
| 400 | regra de negócio: aprovadas > inscritas |
| 422 | tipo ou faixa inválidos (Pydantic) |
| 500 | modelo não carregado ou falha não prevista |

## Testes

```bash
python -m pytest -q
```

## Fluxo de trabalho

GitFlow: `main` ← `develop` ← `feature/*`, branches mantidas após o merge.
