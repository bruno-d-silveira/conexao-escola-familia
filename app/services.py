"""Camada de serviço: carrega o modelo uma vez e faz a inferência. Não sabe nada de HTTP."""
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from app import regras
from app.schemas import DadosEstudante, Fator, Predicao


class ServicoModelo:
    def __init__(self, caminho: Path):
        self.caminho = caminho
        self.pipeline = None

    @property
    def carregado(self) -> bool:
        return self.pipeline is not None

    def carregar(self) -> None:
        """Chamado uma única vez, no lifespan da aplicação."""
        self.pipeline = joblib.load(self.caminho)

    def prever(self, dados: DadosEstudante) -> Predicao:
        if not self.carregado:
            raise RuntimeError("modelo não carregado")
        linha = pd.DataFrame([dados.model_dump()])
        linha[["mensalidade_em_dia", "devedor", "bolsista", "mora_longe_de_casa", "turno_diurno"]] = \
            linha[["mensalidade_em_dia", "devedor", "bolsista", "mora_longe_de_casa", "turno_diurno"]].astype(int)
        risco = float(self.pipeline.predict_proba(linha)[0, 1])
        fatores = self._fatores(linha)
        return Predicao(
            risco_evasao=round(risco, 4),
            nivel=regras.nivel(risco),
            fatores_do_dado=fatores,
            limitacoes_do_modelo=regras.LIMITACOES,
            perguntas_para_conversa=regras.perguntas([f.fator for f in fatores]),
        )

    def _fatores(self, linha: pd.DataFrame, top: int = 3) -> list[Fator]:
        """Na regressão logística, cada coluna contribui com peso x valor.
        Mostramos as que mais empurraram o risco para cima."""
        preparo = self.pipeline.named_steps["preparo"]
        modelo = self.pipeline.named_steps["modelo"]
        valores = np.asarray(preparo.transform(linha))[0]
        nomes = preparo.get_feature_names_out()
        contrib = modelo.coef_[0] * valores
        ordem = np.argsort(contrib)[::-1]
        saida = []
        for i in ordem[:top]:
            if contrib[i] <= 0:
                break
            coluna = nomes[i].split("__", 1)[1].removesuffix("_1").removesuffix("_0")
            saida.append(Fator(fator=coluna, descricao=regras.ROTULOS.get(coluna, coluna),
                               peso=round(float(contrib[i]), 3)))
        return saida
