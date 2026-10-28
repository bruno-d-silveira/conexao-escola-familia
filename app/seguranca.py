"""Senha do professor: só o hash vai para o banco, nunca o texto."""
import hashlib
import hmac

ITERACOES = 200_000


def gerar_hash(senha: str, sal: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), bytes.fromhex(sal), ITERACOES).hex()


def senha_confere(senha: str, sal: str, senha_hash: str) -> bool:
    # compare_digest leva o mesmo tempo acerte ou erre: não entrega pistas a quem tenta adivinhar.
    return hmac.compare_digest(gerar_hash(senha, sal), senha_hash)
