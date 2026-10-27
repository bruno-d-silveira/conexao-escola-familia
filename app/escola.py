"""Registro da escola em SQLite: alunos e professores (fictícios) e o log de acompanhamentos."""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from app.seguranca import senha_confere

ALUNOS_SEMENTE = Path(__file__).resolve().parents[1] / "data" / "alunos_ficticios.json"
PROFESSORES_SEMENTE = Path(__file__).resolve().parents[1] / "data" / "professores_ficticios.json"


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
                id text primary key, nome text, turma text, email_responsavel text, dados text)""")
            con.execute("""create table if not exists registros (
                id integer primary key autoincrement, aluno_id text, professor text,
                acompanhamento text, predicao text, status text,
                criado_em text, aprovado_em text, aprovado_por text)""")
            if con.execute("select count(*) from alunos").fetchone()[0] == 0:
                for a in json.loads(ALUNOS_SEMENTE.read_text(encoding="utf-8")):
                    con.execute("insert into alunos values (?,?,?,?,?)",
                                (a["id"], a["nome"], a["turma"], a["email_responsavel"],
                                 json.dumps(a["dados"])))
            con.execute("""create table if not exists professores (
                id text primary key, nome text, sal text, senha_hash text)""")
            if con.execute("select count(*) from professores").fetchone()[0] == 0:
                for p in json.loads(PROFESSORES_SEMENTE.read_text(encoding="utf-8")):
                    con.execute("insert into professores values (?,?,?,?)",
                                (p["id"], p["nome"], p["sal"], p["senha_hash"]))

    def professores(self) -> list[dict]:
        """Só id e nome: o hash da senha nunca sai do banco."""
        with self._con() as con:
            return [dict(r) for r in con.execute("select id, nome from professores order by nome")]

    def autenticar(self, professor_id: str, senha: str) -> dict | None:
        """Devolve o professor se a senha confere; senão, None."""
        with self._con() as con:
            r = con.execute("select * from professores where id = ?", (professor_id,)).fetchone()
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

    @staticmethod
    def _aluno(r) -> dict:
        return {**dict(r), "dados": json.loads(r["dados"])}

    @staticmethod
    def _registro(r) -> dict:
        return {**dict(r), "predicao": json.loads(r["predicao"])}
