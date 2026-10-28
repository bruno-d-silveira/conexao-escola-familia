"""Passes temporários da coordenação: ficam só na memória da API e valem 2 horas."""
import secrets
from datetime import datetime, timedelta

VALIDADE = timedelta(hours=2)


class Sessoes:
    def __init__(self):
        self._passes: dict[str, tuple[dict, datetime]] = {}

    def abrir(self, pessoa: dict) -> tuple[str, datetime]:
        """Gera um passe aleatório para quem acabou de fazer o login."""
        passe = secrets.token_urlsafe(32)
        expira = datetime.now() + VALIDADE
        self._passes[passe] = (pessoa, expira)
        return passe, expira

    def quem(self, passe: str) -> dict | None:
        """Devolve a pessoa dona do passe, ou None se o passe não existe ou já venceu."""
        item = self._passes.get(passe)
        if item is None:
            return None
        pessoa, expira = item
        if datetime.now() > expira:
            del self._passes[passe]
            return None
        return pessoa
