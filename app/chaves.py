"""Motor de chaves: lê o relato do professor e devolve só o TEMA da situação.

Regras escritas à mão, sem agente de IA, código manual, como em regras.py: cada chave tem as expressões que a disparam,
e cada chave sai junto com o trecho do relato que a disparou, para qualquer pessoa ver o porquê.

A chave descreve a situação, nunca a pessoa: "ameaça", não gera classificação de pessoa, exemplo: "agressivo". Estudos de comportamento
fica a cargo do profissional de saúde mental, que decide e assina. O modelo de evasão não lê essas chaves geradas. Essas chaves ficam como banco de dados de históricos de situações reais, para estudo de caso.

Limitação conhecida: o motor não entende negação ("não bateu em ninguém" ainda dispara
"conflito físico"). Por isso a coordenação pode descartar uma chave que o motor errou.
"""
import re

# chave -> (nome legível, gravidade, expressões). As expressões são comparadas sem maiúscula, a partir
# do começo de uma palavra ("amea[cç]" pega ameaça, ameaçou, ameaçando), com e sem acento.
CHAVES = {
    "ameaca": ("ameaça", "imediata",
               [r"amea[cç]", r"vou te matar", r"vou matar", r"vai se arrepender", r"vou pegar (ele|ela|voc[eê])"]),
    "arma": ("arma", "imediata", [r"armas?\b", r"facas?\b", r"canivetes?\b", r"rev[oó]lver", r"pistola",
                                  r"atirar", r"tiros?\b"]),
    "autolesao": ("fala em se machucar", "imediata",
                  [r"se matar", r"suic[ií]d", r"se cortar", r"cortes no", r"automutil", r"n[aã]o quer mais viver"]),
    "conflito_fisico": ("conflito físico", "atencao",
                        [r"bat(eu|endo|er)\b", r"agred", r"socos?\b", r"chut(ou|ando)\b", r"empurr",
                         r"brig(a|as|ou|ando|ar)\b"]),
    "discurso_de_odio": ("discurso de ódio", "atencao", [r"[óo]dio", r"racis", r"homof[óo]b", r"nazis", r"xenof[óo]b"]),
    "discurso_sombrio": ("discurso sombrio", "atencao", [r"dark", r"sombri", r"morte", r"morrer", r"sumir"]),
    "bullying": ("bullying", "atencao", [r"bullying", r"humilh", r"zoa[cç]", r"apelid", r"exclu[ií]d"]),
    "isolamento": ("isolamento", "atencao", [r"isolad", r"sozinh", r"calad", r"n[aã]o fala com ningu[eé]m"]),
    "faltas": ("faltas", "atencao", [r"falt(ou|as|ando)\b", r"ausen", r"n[aã]o veio", r"atras(o|os|ad)"]),
    "substancias": ("substâncias", "atencao", [r"drogas?\b", r"maconha", r"[áa]lcool", r"bebida", r"cigarr", r"vape"]),
    "companhias": ("companhias", "atencao", [r"m[áa]s companhias", r"companhias? (estranh|de fora|ruins?)",
                                             r"aliciad", r"gente de fora", r"turma de fora"]),
}


def extrair(relato: str) -> list[dict]:
    """Cada chave encontrada no relato, uma vez só, com o trecho (a frase) que a disparou."""
    frases = [f.strip() for f in re.split(r"(?<=[.!?;])\s+|\n+", relato) if f.strip()]
    achadas = []
    for chave, (_, gravidade, expressoes) in CHAVES.items():
        padrao = re.compile(r"\b(" + "|".join(expressoes) + ")")
        frase = next((f for f in frases if padrao.search(f.casefold())), None)
        if frase:
            achadas.append({"chave": chave, "gravidade": gravidade, "trecho": frase[:200]})
    return achadas
