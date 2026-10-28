"""Registro da escola em SQLite: alunos e professores (fictícios) e o log de acompanhamentos."""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from app.seguranca import senha_confere

ALUNOS_SEMENTE = Path(__file__).resolve().parents[1] / "data" / "alunos_ficticios.json"
PROFESSORES_SEMENTE = Path(__file__).resolve().parents[1] / "data" / "professores_ficticios.json"
COORDENACAO_SEMENTE = Path(__file__).resolve().parents[1] / "data" / "coordenacao_ficticia.json"


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
            con.execute("""create table if not exists professores (
                id text primary key, nome text, sal text, senha_hash text)""")
            if con.execute("select count(*) from professores").fetchone()[0] == 0:
                for p in json.loads(PROFESSORES_SEMENTE.read_text(encoding="utf-8")):
                    con.execute("insert into professores values (?,?,?,?)",
                                (p["id"], p["nome"], p["sal"], p["senha_hash"]))
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

    def alunos(self) -> list[dict]:
        with self._con() as con:
            return [self._aluno(r) for r in con.execute("select * from alunos order by id")]

    def aluno(self, aluno_id: str) -> dict | None:
        with self._con() as con:
            r = con.execute("select * from alunos where id = ?", (aluno_id,)).fetchone()
        return self._aluno(r) if r else None

    def novo_registro(self, aluno_id: str, professor: str, acompanhamento: str, predicao: dict) -> dict:
        agora = datetime.now().isoformat(timespec="seconds")
        with self._con() as con:
            cur = con.execute(
                "insert into registros (aluno_id, professor, acompanhamento, predicao, status, criado_em) "
                "values (?,?,?,?,?,?)",
                (aluno_id, professor, acompanhamento, json.dumps(predicao, ensure_ascii=False),
                 "aguardando_coordenacao", agora))
            novo_id = cur.lastrowid
        return self.registro(novo_id)

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

    def registrar_acesso(self, aluno_id: str, registro_id: int, acao: str, quem: str) -> None:
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
    def _registro(r) -> dict:
        return {**dict(r), "predicao": json.loads(r["predicao"])}
