"""Cria data/coordenacao_ficticia.json: quem pode abrir as fichas e aprovar os documentos.

Os nomes são INVENTADOS. A senha nunca é guardada: só o sal e o hash (PBKDF2-SHA256),
com o mesmo app/seguranca.py dos professores.

Como rodar:  python gerar_coordenacao_ficticia.py
"""
import json
import secrets
from pathlib import Path

from app.seguranca import gerar_hash

RAIZ = Path(__file__).resolve().parent
SENHA_DEMO = "coord2026"
COORDENACAO = [("C001", "Coord.ª Lúcia Ramos"), ("C002", "Coord. Paulo Teixeira")]


def main():
    pessoas = []
    for cid, nome in COORDENACAO:
        sal = secrets.token_hex(16)
        pessoas.append({"id": cid, "nome": nome, "sal": sal, "senha_hash": gerar_hash(SENHA_DEMO, sal)})
    destino = RAIZ / "data" / "coordenacao_ficticia.json"
    destino.write_text(json.dumps(pessoas, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{len(pessoas)} pessoas da coordenação em {destino}")


if __name__ == "__main__":
    main()
