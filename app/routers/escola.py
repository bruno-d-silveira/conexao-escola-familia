"""Rotas do fluxo da escola: professor registra, coordenação aprova e gera o documento."""
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from app.routers.predicao import checar_coerencia
from app.schemas import (Acesso, Aluno, DadosEstudante, Documento, LoginCoordenacao, LoginProfessor,
                         NovoRegistro, PasseCoordenacao, PasseProfessor, Professor, Registro, RegistroEnviado)

router = APIRouter(prefix="/v1", tags=["escola"])


def _dono_do_passe(request: Request, authorization: str | None) -> dict | None:
    """O passe vem no cabeçalho: Authorization: Bearer <passe>. Devolve a pessoa e o papel dela."""
    passe = (authorization or "").removeprefix("Bearer ").strip()
    return request.app.state.sessoes.quem(passe) if passe else None


def coordenacao_logada(request: Request, authorization: str | None = Header(None)) -> dict:
    """Só a coordenação logada passa. Passe de professor não abre estas rotas."""
    pessoa = _dono_do_passe(request, authorization)
    if pessoa is None:
        raise HTTPException(401, "Faça o login da coordenação.")
    if pessoa["papel"] != "coordenacao":
        raise HTTPException(403, "Só a coordenação tem acesso a esta parte.")
    return pessoa


def professor_logado(request: Request, authorization: str | None = Header(None)) -> dict:
    pessoa = _dono_do_passe(request, authorization)
    if pessoa is None or pessoa["papel"] != "professor":
        raise HTTPException(401, "Faça o login do professor.")
    return pessoa


def alguem_logado(request: Request, authorization: str | None = Header(None)) -> dict:
    """Professor ou coordenação: o cadastro dos alunos não fica aberto para quem não entrou."""
    pessoa = _dono_do_passe(request, authorization)
    if pessoa is None:
        raise HTTPException(401, "Faça o login para ver os alunos.")
    return pessoa


def _nome_sem_titulo(nome: str) -> str:
    """Compara nomes sem ligar para maiúscula, espaço sobrando ou o título (Prof., Prof.ª)."""
    partes = nome.casefold().split()
    if partes and partes[0].startswith("prof"):
        partes = partes[1:]
    return " ".join(partes)


@router.get("/alunos", response_model=list[Aluno])
def listar_alunos(request: Request, quem: dict = Depends(alguem_logado)):
    """A coordenação vê a escola toda; o professor, só os alunos das turmas dele."""
    escola = request.app.state.escola
    if quem["papel"] == "professor":
        return escola.alunos(turmas=escola.turmas_do_professor(quem["id"]))
    return escola.alunos()


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
    passe, expira = request.app.state.sessoes.abrir({**pessoa, "papel": "coordenacao"})
    return PasseCoordenacao(passe=passe, nome=pessoa["nome"], expira_em=expira)


@router.post("/professores/login", response_model=PasseProfessor)
def login_professor(login: LoginProfessor, request: Request):
    pessoa = request.app.state.escola.autenticar(login.professor_id, login.senha)
    if pessoa is None:
        # Mesma resposta para professor inexistente e senha errada: não revela quem existe.
        raise HTTPException(401, "Professor ou senha incorretos.")
    passe, expira = request.app.state.sessoes.abrir({**pessoa, "papel": "professor"})
    return PasseProfessor(passe=passe, nome=pessoa["nome"], expira_em=expira)


@router.post("/registros", response_model=RegistroEnviado, status_code=201)
def registrar(novo: NovoRegistro, request: Request, professor: dict = Depends(professor_logado)):
    """O professor entrou com a senha, escreve o acompanhamento e assina com o nome completo."""
    if _nome_sem_titulo(novo.nome_completo) != _nome_sem_titulo(professor["nome"]):
        raise HTTPException(403, "O nome digitado não confere com o professor que entrou. Nada foi enviado.")
    aluno = request.app.state.escola.aluno(novo.aluno_id)
    if aluno is None:
        raise HTTPException(404, f"Aluno {novo.aluno_id} não encontrado.")
    if aluno["turma"] not in request.app.state.escola.turmas_do_professor(professor["id"]):
        raise HTTPException(403, "Este aluno não é de uma turma sua. Nada foi enviado.")
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
def documento(registro_id: int, request: Request, modelo: Literal["convite", "convite_boletim"] = "convite",
              quem: dict = Depends(coordenacao_logada)):
    """Convite para a conversa com o responsável: só sai depois da aprovação.

    O relato do professor e a previsão ficam no banco, na ficha do aluno; não vão para a família.
    """
    escola = request.app.state.escola
    reg = escola.registro(registro_id)
    if reg is None:
        raise HTTPException(404, f"Registro {registro_id} não encontrado.")
    if reg["status"] != "aprovado":
        raise HTTPException(400, "O documento só sai depois da aprovação da coordenação.")
    aluno = escola.aluno(reg["aluno_id"])
    escola.registrar_acesso(reg["aluno_id"], registro_id, "documento_gerado", reg["aprovado_por"])
    boletim = ""
    if modelo == "convite_boletim":
        d, f = aluno["dados"], aluno["frequencia"]
        # A base UCI usa notas de 0 a 20; o boletim mostra na escala brasileira, de 0 a 10.
        nota = lambda v: f"{v / 2:.1f}".replace(".", ",")
        boletim = (
            f"Boletim de {aluno['nome']}:\n"
            f"  1º semestre: {d['disciplinas_1sem_aprovadas']} de {d['disciplinas_1sem_inscritas']} disciplinas "
            f"aprovadas, média {nota(d['media_1sem'])} de 10, frequência {f['sem1']}%\n"
            f"  2º semestre: {d['disciplinas_2sem_aprovadas']} de {d['disciplinas_2sem_inscritas']} disciplinas "
            f"aprovadas, média {nota(d['media_2sem'])} de 10, frequência {f['sem2']}%\n\n"
        )
    ano, mes, dia = reg["aprovado_em"][:10].split("-")
    texto = (
        f"Prezada família de {aluno['nome']} ({aluno['turma']}),\n\n"
        f"Queremos marcar uma conversa com vocês sobre o ano de {aluno['nome']} na escola.\n\n"
        f"{boletim}"
        f"É um encontro para trocar impressões e combinar juntos como apoiar {aluno['nome']} daqui para frente. "
        f"Fiquem à vontade para sugerir o dia e o horário que forem melhores.\n\n"
        f"Até breve,\n"
        f"Coordenação ({reg['aprovado_por']}), {dia}/{mes}/{ano}"
    )
    return Documento(registro_id=registro_id, para=aluno["email_responsavel"],
                     assunto=f"Acompanhamento de {aluno['nome']}", texto=texto)
