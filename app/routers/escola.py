"""Rotas do fluxo da escola: professor registra, coordenação aprova e gera o documento."""
from fastapi import APIRouter, Depends, Header, HTTPException, Request

from app.routers.predicao import checar_coerencia
from app.schemas import (Acesso, Aluno, DadosEstudante, Documento, LoginCoordenacao, NovoRegistro,
                         PasseCoordenacao, Professor, Registro, RegistroEnviado)

router = APIRouter(prefix="/v1", tags=["escola"])


def coordenacao_logada(request: Request, authorization: str | None = Header(None)) -> dict:
    """Só a coordenação logada passa. O passe vem no cabeçalho: Authorization: Bearer <passe>."""
    passe = (authorization or "").removeprefix("Bearer ").strip()
    pessoa = request.app.state.sessoes.quem(passe) if passe else None
    if pessoa is None:
        raise HTTPException(401, "Faça o login da coordenação.")
    return pessoa


@router.get("/alunos", response_model=list[Aluno])
def listar_alunos(request: Request):
    return request.app.state.escola.alunos()


@router.get("/professores", response_model=list[Professor])
def listar_professores(request: Request):
    return request.app.state.escola.professores()


@router.get("/coordenacao", response_model=list[Professor])
def listar_coordenacao(request: Request):
    return request.app.state.escola.coordenacao()


@router.post("/coordenacao/login", response_model=PasseCoordenacao)
def login_coordenacao(login: LoginCoordenacao, request: Request):
    pessoa = request.app.state.escola.autenticar_coordenacao(login.coordenador_id, login.senha)
    if pessoa is None:
        raise HTTPException(401, "Coordenação ou senha incorretas.")
    passe, expira = request.app.state.sessoes.abrir(pessoa)
    return PasseCoordenacao(passe=passe, nome=pessoa["nome"], expira_em=expira)


@router.post("/registros", response_model=RegistroEnviado, status_code=201)
def registrar(novo: NovoRegistro, request: Request):
    """O professor confirma a senha e escreve o acompanhamento; a previsão é feita e tudo vai para o log."""
    professor = request.app.state.escola.autenticar(novo.professor_id, novo.senha)
    if professor is None:
        # Mesma resposta para professor inexistente e senha errada: não revela quem existe.
        raise HTTPException(401, "Professor ou senha incorretos.")
    aluno = request.app.state.escola.aluno(novo.aluno_id)
    if aluno is None:
        raise HTTPException(404, f"Aluno {novo.aluno_id} não encontrado.")
    # O modelo recebe só os dados acadêmicos: nunca o nome, nunca o texto do professor.
    dados = DadosEstudante(**aluno["dados"])
    checar_coerencia(dados)
    predicao = request.app.state.modelo.prever(dados)
    registro = request.app.state.escola.novo_registro(
        novo.aluno_id, professor["nome"], novo.acompanhamento, predicao.model_dump())
    request.app.state.escola.registrar_acesso(novo.aluno_id, registro["id"], "relatorio_enviado", professor["nome"])
    return RegistroEnviado(id=registro["id"], status=registro["status"],
                           mensagem="Relatório enviado à coordenação.")


@router.get("/registros", response_model=list[Registro])
def listar_registros(request: Request, status: str | None = None, quem: dict = Depends(coordenacao_logada)):
    if status not in (None, "aguardando_coordenacao", "aprovado"):
        raise HTTPException(400, "status deve ser 'aguardando_coordenacao' ou 'aprovado'.")
    return request.app.state.escola.registros(status)


@router.get("/registros/{registro_id}", response_model=Registro)
def abrir_ficha(registro_id: int, request: Request, quem: dict = Depends(coordenacao_logada)):
    """Abre a ficha completa de um registro. Cada abertura fica na trilha de auditoria."""
    escola = request.app.state.escola
    reg = escola.registro(registro_id)
    if reg is None:
        raise HTTPException(404, f"Registro {registro_id} não encontrado.")
    escola.registrar_acesso(reg["aluno_id"], registro_id, "ficha_aberta", quem["nome"])
    return reg


@router.get("/alunos/{aluno_id}/acessos", response_model=list[Acesso])
def listar_acessos(aluno_id: str, request: Request, quem: dict = Depends(coordenacao_logada)):
    """Trilha de auditoria do aluno: quem enviou, abriu, aprovou ou gerou documento, e quando."""
    if request.app.state.escola.aluno(aluno_id) is None:
        raise HTTPException(404, f"Aluno {aluno_id} não encontrado.")
    return request.app.state.escola.acessos(aluno_id)


@router.post("/registros/{registro_id}/aprovar", response_model=Registro)
def aprovar(registro_id: int, request: Request, quem: dict = Depends(coordenacao_logada)):
    escola = request.app.state.escola
    reg = escola.registro(registro_id)
    if reg is None:
        raise HTTPException(404, f"Registro {registro_id} não encontrado.")
    if reg["status"] == "aprovado":
        raise HTTPException(400, f"Registro {registro_id} já foi aprovado.")
    escola.registrar_acesso(reg["aluno_id"], registro_id, "aprovado", quem["nome"])
    return escola.aprovar(registro_id, quem["nome"])


@router.get("/registros/{registro_id}/documento", response_model=Documento)
def documento(registro_id: int, request: Request, quem: dict = Depends(coordenacao_logada)):
    """Rascunho para a conversa com o responsável: só sai depois da aprovação."""
    escola = request.app.state.escola
    reg = escola.registro(registro_id)
    if reg is None:
        raise HTTPException(404, f"Registro {registro_id} não encontrado.")
    if reg["status"] != "aprovado":
        raise HTTPException(400, "O documento só sai depois da aprovação da coordenação.")
    aluno = escola.aluno(reg["aluno_id"])
    escola.registrar_acesso(reg["aluno_id"], registro_id, "documento_gerado", reg["aprovado_por"])
    p = reg["predicao"]
    perguntas = "\n".join(f"  - {q}" for q in p["perguntas_para_conversa"])
    texto = (
        f"Prezada família de {aluno['nome']} ({aluno['turma']}),\n\n"
        f"A escola gostaria de conversar sobre o acompanhamento de {aluno['nome']}.\n\n"
        f"O que {reg['professor']} observou:\n  {reg['acompanhamento']}\n\n"
        f"Algumas perguntas que podem ajudar na conversa:\n{perguntas}\n\n"
        f"Este documento não é um diagnóstico. É um convite para conversar.\n\n"
        f"Coordenação ({reg['aprovado_por']}), {reg['aprovado_em'][:10]}"
    )
    return Documento(registro_id=registro_id, para=aluno["email_responsavel"],
                     assunto=f"Acompanhamento de {aluno['nome']}", texto=texto)
