"""Cria data/professores_ficticios.json: os professores de demonstração da escola.

Os nomes são INVENTADOS. A senha nunca é guardada: só o sal e o hash (PBKDF2-SHA256).
Todos usam a mesma senha de demonstração, para o vídeo e para os testes.

Como rodar:  python gerar_professores_ficticios.py
"""
import json
import secrets
from pathlib import Path

from app.seguranca import gerar_hash

RAIZ = Path(__file__).resolve().parent
SENHA_DEMO = "escola2026"
PROFESSORES = [("P001", "Prof.ª Helena Costa"), ("P002", "Prof. Marcos Vieira"),
               ("P003", "Prof.ª Renata Alves")]


def main():
    professores = []
    for pid, nome in PROFESSORES:
        sal = secrets.token_hex(16)
        professores.append({"id": pid, "nome": nome, "sal": sal, "senha_hash": gerar_hash(SENHA_DEMO, sal)})
    destino = RAIZ / "data" / "professores_ficticios.json"
    destino.write_text(json.dumps(professores, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{len(professores)} professores fictícios em {destino}")


if __name__ == "__main__":
    main()
