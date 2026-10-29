"""Registro da escola em SQLite: alunos e professores (fictícios) e o log de acompanhamentos."""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from app.chaves import CHAVES, extrair
from app.seguranca import senha_confere

ALUNOS_SEMENTE = Path(__file__).resolve().parents[1] / "data" / "alunos_ficticios.json"
PROFESSORES_SEMENTE = Path(__file__).resolve().parents[1] / "data" / "professores_ficticios.json"
COORDENACAO_SEMENTE = Path(__file__).resolve().parents[1] / "data" / "coordenacao_ficticia.json"
BOLETINS_SEMENTE = Path(__file__).resolve().parents[1] / "data" / "boletins_ficticios.json"


class Escola:
    def __init__(self, caminho_db: Path):
        self.caminho_db = caminho_db

    @contextmanager
    def _con(self):
        """Abre, confirma e FECHA a conexão a cada operação."""
        con = sqlite3.connect(self.caminho_db)
        con.row_factory = sqlite3.Row
        try:
            yield con
            con.commit()
        finally:
            con.close()

    def preparar(self) -> None:
        with self._con() as con:
            con.execute("""create table if not exists alunos (
                id text primary key, nome text, turma text, email_responsavel text,
                matricula text, frequencia text, dados text)""")
            con.execute("""create table if not exists registros (
                id integer primary key autoincrement, aluno_id text, professor text,
                acompanhamento text, predicao text, status text,
                criado_em text, aprovado_em text, aprovado_por text)""")
            if con.execute("select count(*) from alunos").fetchone()[0] == 0:
                for a in json.loads(ALUNOS_SEMENTE.read_text(encoding="utf-8")):
                    con.execute("insert into alunos values (?,?,?,?,?,?,?)",
                                (a["id"], a["nome"], a["turma"], a["email_responsavel"],
                                 json.dumps(a["matricula"], ensure_ascii=False),
                                 json.dumps(a["frequencia"]), json.dumps(a["dados"])))
            # Trilha de auditoria (LGPD, art. 37): quem fez o quê com os dados de qual aluno, e quando.
            con.execute("""create table if not exists acessos (
                id integer primary key autoincrement, aluno_id text, registro_id integer,
                acao text, quem text, em text)""")
            # Só inclusão: nem a API nem quem abrir o banco consegue alterar ou apagar uma linha da trilha.
            for operacao in ("update", "delete"):
                con.execute(f"""create trigger if not exists acessos_sem_{operacao} before {operacao} on acessos
                    begin select raise(abort, 'A trilha de auditoria só aceita inclusão.'); end""")
            con.execute("""create table if not exists professores (
                id text primary key, nome text, sal text, senha_hash text)""")
            if con.execute("select count(*) from professores").fetchone()[0] == 0:
                for p in json.loads(PROFESSORES_SEMENTE.read_text(encoding="utf-8")):
                    con.execute("insert into professores values (?,?,?,?)",
                                (p["id"], p["nome"], p["sal"], p["senha_hash"]))
            # Turmas de cada professor: tabela à parte, para entrar também num banco que já existia.
            con.execute("""create table if not exists professor_turmas (
                professor_id text, turma text, primary key (professor_id, turma))""")
            if con.execute("select count(*) from professor_turmas").fetchone()[0] == 0:
                for p in json.loads(PROFESSORES_SEMENTE.read_text(encoding="utf-8")):
                    for turma in p.get("turmas", []):
                        con.execute("insert into professor_turmas values (?,?)", (p["id"], turma))
            # Banco de chaves: o tema de cada situação relatada, separado do texto do relato.
            con.execute("""create table if not exists chaves (
                id integer primary key autoincrement, registro_id integer, aluno_id text, chave text,
                gravidade text, trecho text, situacao text, em text, atualizado_por text, atualizado_em text)""")
            if con.execute("select count(*) from chaves").fetchone()[0] == 0:
                # Banco que já existia: os relatos antigos também passam pelo motor.
                for r in con.execute("select id, aluno_id, acompanhamento, criado_em from registros").fetchall():
                    self._gravar_chaves(con, r["id"], r["aluno_id"], r["acompanhamento"], r["criado_em"])
            con.execute("create table if not exists boletins (aluno_id text primary key, boletim text)")
            if con.execute("select count(*) from boletins").fetchone()[0] == 0:
                for b in json.loads(BOLETINS_SEMENTE.read_text(encoding="utf-8")):
                    con.execute("insert into boletins values (?,?)", (b["aluno_id"], json.dumps(b, ensure_ascii=False)))
            con.execute("""create table if not exists coordenacao (
                id text primary key, nome text, sal text, senha_hash text)""")
            if con.execute("select count(*) from coordenacao").fetchone()[0] == 0:
                for p in json.loads(COORDENACAO_SEMENTE.read_text(encoding="utf-8")):
                    con.execute("insert into coordenacao values (?,?,?,?)",
                                (p["id"], p["nome"], p["sal"], p["senha_hash"]))

    def professores(self) -> list[dict]:
        """Só id e nome: o hash da senha nunca sai do banco."""
        with self._con() as con:
            return [dict(r) for r in con.execute("select id, nome from professores order by nome")]

    def autenticar(self, professor_id: str, senha: str) -> dict | None:
        """Devolve o professor se a senha confere; senão, None."""
        return self._autenticar("professores", professor_id, senha)

    def coordenacao(self) -> list[dict]:
        """Só id e nome, como nos professores."""
        with self._con() as con:
            return [dict(r) for r in con.execute("select id, nome from coordenacao order by nome")]

    def autenticar_coordenacao(self, coordenador_id: str, senha: str) -> dict | None:
        return self._autenticar("coordenacao", coordenador_id, senha)

    def _autenticar(self, tabela: str, pessoa_id: str, senha: str) -> dict | None:
        with self._con() as con:
            r = con.execute(f"select * from {tabela} where id = ?", (pessoa_id,)).fetchone()
        if r is None or not senha_confere(senha, r["sal"], r["senha_hash"]):
            return None
        return {"id": r["id"], "nome": r["nome"]}

    def turmas_do_professor(self, professor_id: str) -> list[str]:
        with self._con() as con:
            return [r["turma"] for r in con.execute(
                "select turma from professor_turmas where professor_id = ? order by turma", (professor_id,))]

    def alunos(self, turmas: list[str] | None = None) -> list[dict]:
        """Todos os alunos, ou só os das turmas indicadas."""
        with self._con() as con:
            linhas = [self._aluno(r) for r in con.execute("select * from alunos order by id")]
        return linhas if turmas is None else [a for a in linhas if a["turma"] in turmas]

    def aluno(self, aluno_id: str) -> dict | None:
        with self._con() as con:
            r = con.execute("select * from alunos where id = ?", (aluno_id,)).fetchone()
        return self._aluno(r) if r else None

    def boletim(self, aluno_id: str) -> dict | None:
        with self._con() as con:
            r = con.execute("select boletim from boletins where aluno_id = ?", (aluno_id,)).fetchone()
        return json.loads(r["boletim"]) if r else None

    def novo_registro(self, aluno_id: str, professor: str, acompanhamento: str, predicao: dict) -> dict:
        agora = datetime.now().isoformat(timespec="seconds")
        with self._con() as con:
            cur = con.execute(
                "insert into registros (aluno_id, professor, acompanhamento, predicao, status, criado_em) "
                "values (?,?,?,?,?,?)",
                (aluno_id, professor, acompanhamento, json.dumps(predicao, ensure_ascii=False),
                 "aguardando_coordenacao", agora))
            novo_id = cur.lastrowid
            self._gravar_chaves(con, novo_id, aluno_id, acompanhamento, agora)
        return self.registro(novo_id)

    @staticmethod
    def _gravar_chaves(con, registro_id: int, aluno_id: str, relato: str, em: str) -> None:
        for c in extrair(relato):
            con.execute("insert into chaves (registro_id, aluno_id, chave, gravidade, trecho, situacao, em) "
                        "values (?,?,?,?,?,?,?)",
                        (registro_id, aluno_id, c["chave"], c["gravidade"], c["trecho"], "aberta", em))

    def chaves_do_aluno(self, aluno_id: str) -> list[dict]:
        with self._con() as con:
            return [self._chave(r) for r in con.execute(
                "select c.*, r.professor from chaves c join registros r on r.id = c.registro_id "
                "where c.aluno_id = ? order by c.em, c.id", (aluno_id,))]

    def chave(self, chave_id: int) -> dict | None:
        with self._con() as con:
            r = con.execute("select c.*, r.professor from chaves c join registros r on r.id = c.registro_id "
                            "where c.id = ?", (chave_id,)).fetchone()
        return self._chave(r) if r else None

    def mudar_situacao(self, chave_id: int, situacao: str, quem: str) -> dict:
        agora = datetime.now().isoformat(timespec="seconds")
        with self._con() as con:
            con.execute("update chaves set situacao = ?, atualizado_por = ?, atualizado_em = ? where id = ?",
                        (situacao, quem, agora, chave_id))
        return self.chave(chave_id)

    def chaves_por_registro(self) -> dict[int, list[dict]]:
        """As chaves de cada relato, menos as que a coordenação descartou."""
        saida: dict[int, list[dict]] = {}
        with self._con() as con:
            for r in con.execute("select registro_id, chave, gravidade from chaves where situacao != 'descartada'"):
                saida.setdefault(r["registro_id"], []).append(dict(r))
        return saida

    def contagem_de_chaves(self, ano: int) -> list[dict]:
        """Quantas vezes cada chave apareceu em cada mês do ano. Sem aluno, sem relato: só o número."""
        with self._con() as con:
            return [dict(r) for r in con.execute(
                "select chave, cast(substr(em, 6, 2) as integer) as mes, count(*) as n from chaves "
                "where situacao != 'descartada' and substr(em, 1, 4) = ? group by chave, mes", (str(ano),))]

    def registros(self, status: str | None = None) -> list[dict]:
        sql, args = "select * from registros", ()
        if status:
            sql, args = sql + " where status = ?", (status,)
        with self._con() as con:
            return [self._registro(r) for r in con.execute(sql + " order by id desc", args)]

    def registro(self, registro_id: int) -> dict | None:
        with self._con() as con:
            r = con.execute("select * from registros where id = ?", (registro_id,)).fetchone()
        return self._registro(r) if r else None

    def aprovar(self, registro_id: int, coordenador: str) -> dict:
        agora = datetime.now().isoformat(timespec="seconds")
        with self._con() as con:
            con.execute("update registros set status = 'aprovado', aprovado_em = ?, aprovado_por = ? "
                        "where id = ?", (agora, coordenador, registro_id))
        return self.registro(registro_id)

    def registrar_acesso(self, aluno_id: str, registro_id: int | None, acao: str, quem: str) -> None:
        agora = datetime.now().isoformat(timespec="seconds")
        with self._con() as con:
            con.execute("insert into acessos (aluno_id, registro_id, acao, quem, em) values (?,?,?,?,?)",
                        (aluno_id, registro_id, acao, quem, agora))

    def acessos(self, aluno_id: str) -> list[dict]:
        with self._con() as con:
            return [dict(r) for r in con.execute(
                "select registro_id, acao, quem, em from acessos where aluno_id = ? order by id", (aluno_id,))]

    @staticmethod
    def _aluno(r) -> dict:
        return {**dict(r), "matricula": json.loads(r["matricula"]),
                "frequencia": json.loads(r["frequencia"]), "dados": json.loads(r["dados"])}

    @staticmethod
    def _chave(r) -> dict:
        return {**dict(r), "nome": CHAVES[r["chave"]][0]}

    @staticmethod
    def _registro(r) -> dict:
        return {**dict(r), "predicao": json.loads(r["predicao"])}
