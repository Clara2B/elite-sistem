"""Localização de cabeçalho e leitura comum aos três padrões (Fase 2).

Responsabilidades (especificação, "Regras de leitura comuns"):
- Cabeçalho localizado, não fixo: procura, nas primeiras 10 linhas de uma
  aba, a linha que contém as colunas esperadas (comparação sem acento e
  com sinônimos de `config/fontes.yaml`).
- Colunas duplicadas (ex.: "DATA" duas vezes em Laudos) resolvidas por
  posição relativa: basta listar o mesmo sinônimo pras duas colunas
  canônicas em `fontes.yaml` (ex.: `data: ["DATA"]` e
  `data_pronto: ["DATA"]`) — a primeira ocorrência de "DATA" na linha fica
  pra a primeira delas, a segunda ocorrência pra segunda, sem precisar de
  código especial (ver `_achar_coluna`, que nunca reusa uma coluna já
  atribuída).
- Linhas vazias e linhas de título repetido no meio da aba são descartadas.
- Toda linha lida devolve, junto com o valor, a origem (planilha, aba,
  número da linha) — usada pelos avisos de validação (Fase 5) pra apontar
  onde corrigir.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.utils import normalize as normalizar_estrutural

# `normalizar_estrutural` é só pra comparar NOME de coluna/aba (estrutura
# da planilha) — reaproveita `app.utils.normalize` (já usado em todo o
# resto do sistema pra comparar nome de empresa/tipo/etc., mesma regra:
# sem acento, sem espaço extra, maiúsculas). Diferente de
# `normalizacao/texto.py` (Fase 3), que normaliza o VALOR dos dados (nomes
# de pessoa, UF) com regras próprias — propósitos diferentes.


class ErroDeLeituraBloqueante(Exception):
    """Base dos 3 erros bloqueantes da especificação ("Erros bloqueantes
    (impedem gerar a seção)"): arquivo errado, aba obrigatória ausente,
    coluna obrigatória não encontrada."""


class AbaNaoEncontrada(ErroDeLeituraBloqueante):
    def __init__(self, planilha: str, descricao_aba: str):
        self.planilha = planilha
        self.descricao_aba = descricao_aba
        super().__init__(f"'{planilha}': aba '{descricao_aba}' não encontrada.")


class CabecalhoNaoEncontrado(ErroDeLeituraBloqueante):
    def __init__(self, planilha: str, aba: str, colunas_faltando: list[str]):
        self.planilha = planilha
        self.aba = aba
        self.colunas_faltando = colunas_faltando
        super().__init__(
            f"'{planilha}', aba '{aba}': não encontrei a(s) coluna(s) {', '.join(colunas_faltando)} "
            "nas primeiras 10 linhas."
        )


@dataclass(frozen=True)
class Origem:
    """De onde uma linha lida veio — planilha (nome do campo de upload,
    ex. 'laudo'), aba e número da linha (1-indexed, como a pessoa vê no
    Excel). Usada pelos avisos de validação (Fase 5) pra apontar onde
    corrigir."""
    planilha: str
    aba: str
    linha: int


@dataclass
class LinhaBruta:
    """Uma linha lida de uma planilha, ainda sem normalização (Fase 3) —
    valores crus (string, número, datetime ou None, como o openpyxl
    devolve), indexados pelo nome canônico da coluna (a chave em
    `colunas:` de `config/fontes.yaml`, não o sinônimo literal da
    planilha)."""
    valores: dict[str, object]
    origem: Origem


@dataclass
class _ColunasLocalizadas:
    indice_linha: int  # 0-indexed, posição da linha de cabeçalho
    mapa_colunas: dict[str, int]  # nome canônico -> índice da coluna (0-indexed)
    sinonimos_normalizados: dict[str, list[str]]  # pra detectar título repetido em ler_linhas


def _celulas_normalizadas(linha: tuple) -> list[str]:
    return [normalizar_estrutural(celula) for celula in linha]


def _achar_coluna(celulas_normalizadas: list[str], sinonimos: list[str], ja_usadas: set[int]) -> int | None:
    for indice, celula in enumerate(celulas_normalizadas):
        if indice in ja_usadas:
            continue
        if celula in sinonimos:
            return indice
    return None


def localizar_cabecalho(
    linhas: list[tuple],
    colunas_config: dict[str, list[str]],
    colunas_fixas: dict[str, int] | None = None,
    linhas_de_busca: int = 10,
) -> _ColunasLocalizadas | None:
    """Procura, nas primeiras `linhas_de_busca` linhas de `linhas`, a que
    contém todas as colunas de `colunas_config` (comparação sem acento,
    maiúscula, espaço extra — por sinônimo). Colunas em `colunas_fixas`
    (ex.: `{"data": 0}`, coluna sem título) não entram nessa busca — a
    linha de cabeçalho só precisa ter as colunas "de verdade" (com
    título). Devolve `None` se nenhuma das primeiras linhas servir."""
    colunas_fixas = colunas_fixas or {}
    sinonimos_normalizados = {
        canonico: [normalizar_estrutural(s) for s in sinonimos] for canonico, sinonimos in colunas_config.items()
    }

    for indice_linha, linha in enumerate(linhas[:linhas_de_busca]):
        celulas = _celulas_normalizadas(linha)
        mapa: dict[str, int] = {}
        for canonico, sinonimos in sinonimos_normalizados.items():
            indice_coluna = _achar_coluna(celulas, sinonimos, ja_usadas=set(mapa.values()))
            if indice_coluna is None:
                mapa = None  # type: ignore[assignment]
                break
            mapa[canonico] = indice_coluna
        if mapa is not None:
            mapa.update(colunas_fixas)
            return _ColunasLocalizadas(indice_linha, mapa, sinonimos_normalizados)
    return None


def _valor_celula(linha: tuple, indice: int) -> object:
    if indice >= len(linha):
        return None
    return linha[indice]


def _linha_vazia(valores: dict[str, object]) -> bool:
    return all(v is None or (isinstance(v, str) and not v.strip()) for v in valores.values())


def _linha_e_titulo_repetido(valores: dict[str, object], sinonimos_normalizados: dict[str, list[str]]) -> bool:
    """Linha de título repetida no meio da aba: todas as colunas que têm
    sinônimo configurado batem de novo com algum sinônimo (ou seja, a
    linha só repete os nomes das colunas, não é um dado de verdade)."""
    comparaveis = [canonico for canonico in valores if sinonimos_normalizados.get(canonico)]
    if not comparaveis:
        return False
    return all(normalizar_estrutural(valores[c]) in sinonimos_normalizados[c] for c in comparaveis)


def ler_linhas(
    linhas: list[tuple],
    localizado: _ColunasLocalizadas,
    planilha: str,
    aba: str,
) -> list[LinhaBruta]:
    """Lê todas as linhas de dado depois da linha de cabeçalho
    (`localizado.indice_linha`), descartando linhas vazias e linhas de
    título repetido. Cada `LinhaBruta` carrega a origem (planilha, aba,
    número da linha 1-indexed) pros avisos da Fase 5."""
    resultado: list[LinhaBruta] = []
    for indice_linha, linha in enumerate(linhas):
        if indice_linha <= localizado.indice_linha:
            continue
        valores = {canonico: _valor_celula(linha, indice) for canonico, indice in localizado.mapa_colunas.items()}
        if _linha_vazia(valores):
            continue
        if _linha_e_titulo_repetido(valores, localizado.sinonimos_normalizados):
            continue
        resultado.append(LinhaBruta(valores=valores, origem=Origem(planilha, aba, indice_linha + 1)))
    return resultado


def ler_aba(linhas: list[tuple], config_fonte: dict, planilha: str, aba: str) -> list[LinhaBruta]:
    """Orquestra `localizar_cabecalho` + `ler_linhas` pra uma aba já
    carregada — usado pelos três padrões (aba_mensal, aba_unica,
    aba_por_assessoria) depois de cada um resolver QUAL aba ler."""
    localizado = localizar_cabecalho(
        linhas,
        config_fonte["colunas"],
        colunas_fixas=config_fonte.get("colunas_fixas"),
        linhas_de_busca=10,
    )
    if localizado is None:
        raise CabecalhoNaoEncontrado(planilha, aba, list(config_fonte["colunas"]))
    return ler_linhas(linhas, localizado, planilha, aba)
