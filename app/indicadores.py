"""Indicadores da base: a relação entre a média do 1º e a do 2º semestre (r de Pearson)."""
from pathlib import Path

import pandas as pd

MEDIA_1SEM = "Curricular units 1st sem (grade)"
MEDIA_2SEM = "Curricular units 2nd sem (grade)"


def medias_por_semestre(caminho_csv: Path) -> dict:
    """Lê a base uma vez e devolve os pontos (escala 0 a 10) e o r de Pearson."""
    base = pd.read_csv(caminho_csv, sep=";")
    # A base usa notas de 0 a 20 (Portugal); dividimos por 2 para a escala brasileira.
    m1 = base[MEDIA_1SEM] / 2
    m2 = base[MEDIA_2SEM] / 2
    evadiu = base["Target"] == "Dropout"
    return {
        "r": round(float(m1.corr(m2)), 3),
        "n": len(base),
        "pontos": [{"m1": round(float(a), 1), "m2": round(float(b), 1), "evadiu": bool(e)}
                   for a, b, e in zip(m1, m2, evadiu)],
    }
