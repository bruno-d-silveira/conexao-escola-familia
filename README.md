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
| Professor (senha) | entra com a senha, escolhe turma e aluno, escreve o relatório e assina com o nome completo | ficha do aluno, aprovação e frequência por semestre |
| Coordenação (senha) | abre a fila e a caixa de casos, marca cada chave como solucionada ou descarta, aprova, gera o documento | prioridade (perigo iminente primeiro), % de evasão, o que mais pesou, chaves dos relatos, chaves na escola sem nome, dispersão das médias, linha do tempo das chamadas, boletim do ano, histórico de acesso |
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
- O boletim mensal por disciplina também é de demonstração: a base só tem médias por semestre, então `gerar_boletins_ficticios.py` deriva as notas e as faltas de cada mês em volta da média, da proporção de aprovadas e da frequência de cada aluno (`"fonte": "demo"`). O ano letivo de 2026 aparece em andamento, atualizado em 29/10/2026.
- O relatório do professor não entra no cálculo. O risco mostra associação, não causa.

## Motor de chaves

O relato do professor é livre ("saiu batendo cadeiras", "falou em discurso de ódio"). Quando ele chega, o motor (`app/chaves.py`) lê o texto e devolve só o tema da situação, junto com a frase que o disparou. São regras escritas à mão, sem IA, que qualquer pessoa pode ler.

| Gravidade | Chaves |
|---|---|
| perigo iminente: o caso vai para o topo da fila | ameaça, arma, fala em se machucar |
| atenção | conflito físico, discurso de ódio, discurso sombrio, bullying, isolamento, faltas, substâncias, companhias |

- A chave descreve a situação, nunca a pessoa. Dar nome a comportamento é do profissional de saúde mental, que decide e assina.
- Cada chave fica num banco de chaves, separado do relato, e a coordenação marca como solucionada, reabre ou descarta quando o motor errou. Cada mudança vai para a trilha.
- O motor não entende negação: "não bateu em ninguém" ainda dispara "conflito físico". Por isso existe o descarte.
- A vista da escola mostra quantas vezes cada chave apareceu em cada mês, sem nome de aluno e sem relato.
- O modelo de evasão não lê o relato nem as chaves.

## Proteção de dados

- Senhas de professor e coordenação guardadas só como hash PBKDF2-SHA256 com sal (`hashlib`, sem dependência extra).
- O professor não recebe a previsão; ela fica com a coordenação.
- Professor e coordenação entram com login e recebem um passe temporário (2 h, só em memória) que carrega o papel de quem entrou; sem passe, as rotas respondem 401, e passe de professor nas rotas da coordenação responde 403.
- O cadastro dos alunos só abre com login. O professor vê e envia relato só dos alunos das turmas dele; a coordenação vê a escola toda.
- O relato só sai assinado: o nome completo digitado precisa conferir com o professor que entrou (sem diferenciar maiúscula, espaço ou título); se não conferir, nada é gravado.
- Trilha de auditoria (LGPD, art. 37): fica gravado, com quem e quando, cada envio, cada aluno que aparece na fila, cada abertura de ficha, de histórico e de boletim, cada aprovação, cada documento gerado e cada vez que a coordenação imprime o documento ou abre o e-mail para o responsável. O "quem" vem sempre do login.
- A trilha só aceita inclusão: gatilhos no SQLite barram alterar ou apagar uma linha, mesmo fora da API.
- O modelo recebe só números acadêmicos, nunca nome ou texto.
- Todos os nomes, e-mails e senhas são fictícios. O banco `data/escola.db` não vai para o repositório.

## Estrutura

```
app/
  main.py               lifespan: modelo, banco, indicadores e passes, carregados uma vez
  services.py           inferência e fatores (peso × valor da regressão logística)
  schemas.py            contratos Pydantic com Field (faixas → 422)
  regras.py             limitações, níveis e perguntas, escritos à mão
  chaves.py             motor de chaves: o tema da situação em cada relato, escrito à mão
  escola.py             SQLite: alunos, boletins, professores e suas turmas, coordenação, registros, chaves, acessos
  seguranca.py          hash de senha PBKDF2
  sessoes.py            passes temporários do professor e da coordenação
  indicadores.py        médias por semestre e r de Pearson
  routers/
    predicao.py         /health e /v1/predict
    escola.py           professor, coordenação, registros, documento, acessos
    indicadores.py      /v1/indicadores/medias
web/index.html          telas do professor e da coordenação (HTML, CSS e JS, sem dependências)
tests/                  API, fluxo da escola, motor de chaves e indicadores
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
| GET | `/v1/professores`, `/v1/coordenacao` | livre | nomes para o login (sem hash) |
| POST | `/v1/professores/login` | senha do professor | passe temporário do professor |
| POST | `/v1/coordenacao/login` | senha da coordenação | passe temporário da coordenação |
| GET | `/v1/alunos` | passe (professor ou coordenação) | cadastro dos alunos (o professor recebe só as turmas dele) |
| POST | `/v1/registros` | passe do professor + nome completo | só a confirmação do envio |
| GET | `/v1/registros`, `/v1/registros/{id}` | passe da coordenação | fila e ficha (as duas gravam o acesso) |
| POST | `/v1/registros/{id}/aprovar` | passe da coordenação | registro aprovado |
| GET | `/v1/registros/{id}/documento?modelo=` | passe da coordenação | convite para a família (`convite` ou `convite_boletim`) |
| POST | `/v1/registros/{id}/saida` | passe da coordenação | grava que o documento foi impresso ou que o e-mail foi aberto |
| GET | `/v1/alunos/{id}/boletim` | passe da coordenação | boletim do ano: notas por mês em dois semestres (fevereiro a junho, agosto a dezembro), médias, faltas e situação (grava o acesso) |
| GET | `/v1/alunos/{id}/chaves` | passe da coordenação | chaves do aluno com o trecho do relato e a situação (grava o acesso) |
| POST | `/v1/chaves/{id}/situacao` | passe da coordenação | marca a chave como aberta, solucionada ou descartada (grava na trilha) |
| GET | `/v1/indicadores/chaves` | passe da coordenação | ocorrências de cada chave por mês letivo, sem nome de aluno |
| GET | `/v1/alunos/{id}/acessos` | passe da coordenação | histórico de acesso (ver o histórico também grava o acesso) |
| GET | `/v1/indicadores/medias` | livre | pontos das médias e r de Pearson |

| Código | Quando |
|---|---|
| 200 / 201 | sucesso |
| 400 | regra de negócio (aprovadas > inscritas, registro já aprovado, documento antes da aprovação) |
| 401 | senha errada ou sem passe |
| 403 | passe de outro papel, nome da assinatura que não confere, ou aluno fora das turmas do professor |
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
