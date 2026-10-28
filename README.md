# Conexão Escola-Família

![testes](https://github.com/bruno-d-silveira/conexao-escola-familia/actions/workflows/testes.yml/badge.svg)

Sistema para a escola registrar o que o professor observa, priorizar os casos na coordenação e gerar o documento para a conversa com a família. Uma API FastAPI estima o risco de evasão de cada estudante com um modelo scikit-learn.

## Contexto

Não existe perfil de estudante em risco: existe comportamento observável, e quase sempre alguém percebe antes. O sistema transforma essa percepção em registro: o professor escreve, a coordenação vê o caso com dados e decide o encaminhamento.

Referências de estratégia e formação que inspiraram o fluxo (sem vínculo institucional):

- [U.S. Secret Service – NTAC](https://www.secretservice.gov/protection/ntac): *Averting Targeted School Violence* (2021).
- [MEC – Escola que Protege](https://www.gov.br/mec/pt-br/escola-que-protege) (SNAVE, Lei 14.643/2023).
- [Polícia Militar de Santa Catarina](https://www.pm.sc.gov.br): Rede de Segurança Escolar.

## Fluxo

| Quem | Faz | Vê |
|---|---|---|
| Professor (senha) | escolhe turma e aluno, escreve o relatório | ficha do aluno, aprovação e frequência por semestre |
| Coordenação (senha) | abre a fila, aprova, gera o documento | prioridade, % de evasão, o que mais pesou, dispersão das médias, histórico de acesso |
| Família | recebe o convite para conversar | documento impresso ou e-mail, sem a lista de fatores |

## Modelo

| | |
|---|---|
| Base | [UCI 697 – Predict Students' Dropout and Academic Success](https://archive.ics.uci.edu/dataset/697) (4.424 estudantes, CC BY 4.0) |
| Alvo | 1 = evadiu; 0 = matriculado ou formado |
| Divisão | 60/20/20 estratificada (2654 / 885 / 885), semente 42 |
| Candidatos | Regressão logística × HistGradientBoosting, ambos com `class_weight="balanced"` |
| Escolhido | Regressão logística (diferença de ROC-AUC < 0,02; pesos explicáveis) |
| Teste | acurácia 0,872 · F1 (evasão) 0,804 · ROC-AUC 0,924 |
| Médias 1º × 2º semestre | r de Pearson = 0,837 |

Colunas fora por governança: gênero, nacionalidade, estado civil, necessidades especiais, profissão e escolaridade dos pais, indicadores macroeconômicos.

Treino offline: `python treinar.py` → `models/modelo_evasao.joblib` e `models/metricas.json`.

### Limitações

- A base é de ensino superior em Portugal, não de educação básica no Brasil. As notas vão de 0 a 20; a tela converte para 0 a 10.
- Média 0 na base significa sem nota registrada no semestre, não nota zero.
- Frequência e situação da matrícula não existem na base: na demonstração são inventadas (`"fonte": "demo"`); numa escola, vêm do diário de classe e da secretaria.
- Os alunos da demonstração são linhas anônimas da base, filtradas para 17 a 20 anos (os mais velhos são outliers para o público do projeto). O modelo é treinado com a base inteira.
- O relatório do professor não entra no cálculo. O risco mostra associação, não causa.

## Proteção de dados

- Senhas de professor e coordenação guardadas só como hash PBKDF2-SHA256 com sal (`hashlib`, sem dependência extra).
- O professor não recebe a previsão; ela fica com a coordenação.
- Coordenação entra com login e recebe um passe temporário (2 h, só em memória); sem passe, as rotas respondem 401.
- Trilha de auditoria: cada envio, abertura de ficha, aprovação e documento fica gravado com quem e quando (LGPD, art. 37).
- O modelo recebe só números acadêmicos, nunca nome ou texto.
- Todos os nomes, e-mails e senhas são fictícios. O banco `data/escola.db` não vai para o repositório.

## Estrutura

```
app/
  main.py               lifespan: modelo, banco, indicadores e passes, carregados uma vez
  services.py           inferência e fatores (peso × valor da regressão logística)
  schemas.py            contratos Pydantic com Field (faixas → 422)
  regras.py             limitações, níveis e perguntas, escritos à mão
  escola.py             SQLite: alunos, professores, coordenação, registros, acessos
  seguranca.py          hash de senha PBKDF2
  sessoes.py            passes temporários da coordenação
  indicadores.py        médias por semestre e r de Pearson
  routers/
    predicao.py         /health e /v1/predict
    escola.py           professor, coordenação, registros, documento, acessos
    indicadores.py      /v1/indicadores/medias
web/index.html          telas do professor e da coordenação (HTML, CSS e JS, sem dependências)
tests/                  API, fluxo da escola e indicadores
gerar_*_ficticios.py    dados de demonstração
treinar.py              pipeline offline
```

## Rodar

```bash
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

- Telas: http://127.0.0.1:8000
- Documentação interativa: http://127.0.0.1:8000/docs
- Senha de demonstração do professor: `escola2026`; da coordenação: `coord2026`.

## Endpoints

| Método | Rota | Acesso | Resposta |
|---|---|---|---|
| GET | `/health` | livre | status e se o modelo está carregado |
| POST | `/v1/predict` | livre | risco, nível, fatores, limitações, perguntas |
| GET | `/v1/alunos`, `/v1/professores`, `/v1/coordenacao` | livre | cadastros (sem hash) |
| POST | `/v1/registros` | senha do professor | só a confirmação do envio |
| POST | `/v1/coordenacao/login` | senha da coordenação | passe temporário |
| GET | `/v1/registros`, `/v1/registros/{id}` | passe | fila e ficha (abrir a ficha grava o acesso) |
| POST | `/v1/registros/{id}/aprovar` | passe | registro aprovado |
| GET | `/v1/registros/{id}/documento` | passe | texto para a família |
| GET | `/v1/alunos/{id}/acessos` | passe | histórico de acesso |
| GET | `/v1/indicadores/medias` | livre | pontos das médias e r de Pearson |

| Código | Quando |
|---|---|
| 200 / 201 | sucesso |
| 400 | regra de negócio (aprovadas > inscritas, registro já aprovado, documento antes da aprovação) |
| 401 | senha errada ou sem passe |
| 404 | aluno ou registro inexistente |
| 422 | tipo ou faixa inválidos (Pydantic) |
| 500 | modelo não carregado ou falha não prevista |

## Testes

```bash
python -m pytest -q
```

O GitHub Actions roda os testes em cada PR e em cada push na `main` e na `develop`.

## Fluxo de trabalho

GitFlow: `main` ← `develop` ← `feature/*`, branches mantidas após o merge.
