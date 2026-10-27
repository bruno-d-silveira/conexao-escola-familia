"""Rotas do fluxo da escola: professor registra, coordenação aprova e gera o documento."""
from fastapi import APIRouter, HTTPException, Request

from app.routers.predicao import checar_coerencia
from app.schemas import Aluno, Aprovacao, DadosEstudante, Documento, NovoRegistro, Professor, Registro

router = APIRouter(prefix="/v1", tags=["escola"])


@router.get("/alunos", response_model=list[Aluno])
def listar_alunos(request: Request):
    return request.app.state.escola.alunos()


@router.get("/professores", response_model=list[Professor])
def listar_professores(request: Request):
    return request.app.state.escola.professores()


@router.post("/registros", response_model=Registro, status_code=201)
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
    return request.app.state.escola.novo_registro(
        novo.aluno_id, professor["nome"], novo.acompanhamento, predicao.model_dump())


@router.get("/registros", response_model=list[Registro])
def listar_registros(request: Request, status: str | None = None):
    if status not in (None, "aguardando_coordenacao", "aprovado"):
        raise HTTPException(400, "status deve ser 'aguardando_coordenacao' ou 'aprovado'.")
    return request.app.state.escola.registros(status)


@router.post("/registros/{registro_id}/aprovar", response_model=Registro)
def aprovar(registro_id: int, aprovacao: Aprovacao, request: Request):
    escola = request.app.state.escola
    reg = escola.registro(registro_id)
    if reg is None:
        raise HTTPException(404, f"Registro {registro_id} não encontrado.")
    if reg["status"] == "aprovado":
        raise HTTPException(400, f"Registro {registro_id} já foi aprovado.")
    return escola.aprovar(registro_id, aprovacao.coordenador)


@router.get("/registros/{registro_id}/documento", response_model=Documento)
def documento(registro_id: int, request: Request):
    """Rascunho para a conversa com o responsável: só sai depois da aprovação."""
    escola = request.app.state.escola
    reg = escola.registro(registro_id)
    if reg is None:
        raise HTTPException(404, f"Registro {registro_id} não encontrado.")
    if reg["status"] != "aprovado":
        raise HTTPException(400, "O documento só sai depois da aprovação da coordenação.")
    aluno = escola.aluno(reg["aluno_id"])
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
