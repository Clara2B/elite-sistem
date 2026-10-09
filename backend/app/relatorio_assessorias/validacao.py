"""Avisos e conferências cruzadas (Fase 5).

Nada é corrigido em silêncio: o que o sistema consegue converter, converte;
o resto vira aviso na tela de revisão, com planilha, aba e linha (origem
que cada leitor devolve junto com os dados — ver leitores/base.py).

Conferências cruzadas (avisos, não bloqueiam) — cada uma, uma função pura
testável isoladamente:
- `detectar_empresas_desconhecidas`: nome que não bate com nenhum apelido
  cadastrado (especificação, "Cadastro de assessorias e apelidos").
- `conferir_soma_uf`: soma da tabela por UF diferente do total de ativos
  (acontece quando há UF inválida, que entra no total mas não no mapa).
- `conferir_cronologia_laudos` / `conferir_cronologia_iniciais`: laudo
  pronto com data de pronto anterior à data de entrada; distribuição
  anterior ao recebimento.
- `conferir_campos_essenciais`: linha da assessoria com campo essencial
  vazio (data, processo, UF) — genérica, pros módulos de `secoes/` que
  ainda não checam isso sozinhos ao calcular (Iniciais, Audiências
  judiciais/contrárias). Laudos e Extrajudiciais não têm coluna de
  processo/UF, então não se aplica a eles. Contrárias e Procons já
  verificam processo/UF/data dentro do próprio `calcular` (precisam disso
  pra decidir o que entra na lista), então rodar esta função de novo lá
  só duplicaria o aviso — não é chamada nesses dois.
- Duplicata de processo dentro da mesma lista (ex.: Dirceu de Oliveira
  Pires nas abas SW e EWS): já resolvida dentro de `secoes/contrarias.py`
  e `secoes/procons.py` (ver os dois), porque afeta a CONTAGEM da seção,
  não só um aviso solto — não repetida aqui.

Erros bloqueantes (impedem gerar a seção): arquivo errado no campo de
upload, aba obrigatória ausente, coluna obrigatória não encontrada — já
implementados desde a Fase 2 (`leitores/base.py::AbaNaoEncontrada`,
`CabecalhoNaoEncontrado`), não repetidos aqui.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.relatorio_assessorias.avisos import Aviso
from app.relatorio_assessorias.leitores.base import LinhaBruta, Origem
from app.relatorio_assessorias.normalizacao import datas
from app.relatorio_assessorias.normalizacao.assessoria import resolver
from app.relatorio_assessorias.secoes.contrarias import ResultadoContrarias
from app.utils import cell_text


@dataclass
class EmpresaDesconhecida:
    nome: str
    quantidade: int
    origens: list[Origem] = field(default_factory=list)


def detectar_empresas_desconhecidas(
    linhas: list[LinhaBruta], campo: str, nomes_por_apelido: dict[str, str]
) -> list[EmpresaDesconhecida]:
    """Resolve o campo de empresa/assessoria de cada linha (mesma regra de
    `normalizacao.assessoria.resolver` — separa célula com mais de uma
    empresa) e agrupa os fragmentos não reconhecidos por nome, com a
    contagem e a origem de cada ocorrência."""
    agrupado: dict[str, EmpresaDesconhecida] = {}
    for linha in linhas:
        resolvida = resolver(linha.valores.get(campo), nomes_por_apelido)
        for nome in resolvida.nao_reconhecidos:
            entrada = agrupado.setdefault(nome, EmpresaDesconhecida(nome, 0))
            entrada.quantidade += 1
            entrada.origens.append(linha.origem)
    return list(agrupado.values())


def conferir_soma_uf(resultado: ResultadoContrarias) -> Aviso | None:
    soma = sum(resultado.ativos_por_uf.values())
    if soma != resultado.ativos_total:
        return Aviso(
            None,
            f"soma da tabela por UF ({soma}) diferente do total de ativos ({resultado.ativos_total}) "
            "— confira linhas com UF inválida",
        )
    return None


def conferir_cronologia_laudos(linhas: list[LinhaBruta]) -> list[Aviso]:
    avisos = []
    for linha in linhas:
        entrada = datas.normalizar(linha.valores.get("data")).valor
        pronto = datas.normalizar(linha.valores.get("data_pronto")).valor
        if entrada is not None and pronto is not None and pronto < entrada:
            avisos.append(
                Aviso(linha.origem, f"data de pronto ({pronto.isoformat()}) anterior à data de entrada ({entrada.isoformat()})")
            )
    return avisos


def conferir_cronologia_iniciais(linhas: list[LinhaBruta]) -> list[Aviso]:
    avisos = []
    for linha in linhas:
        recebimento = datas.normalizar(linha.valores.get("data_recebimento")).valor
        distribuicao = datas.normalizar(linha.valores.get("data_distribuicao")).valor
        if recebimento is not None and distribuicao is not None and distribuicao < recebimento:
            avisos.append(
                Aviso(
                    linha.origem,
                    f"data de distribuição ({distribuicao.isoformat()}) anterior à data de "
                    f"recebimento ({recebimento.isoformat()})",
                )
            )
    return avisos


def conferir_campos_essenciais(linhas: list[LinhaBruta], campos: list[str]) -> list[Aviso]:
    avisos = []
    for linha in linhas:
        vazios = [campo for campo in campos if not cell_text(linha.valores.get(campo))]
        if vazios:
            avisos.append(Aviso(linha.origem, f"campo(s) essencial(is) vazio(s): {', '.join(vazios)}"))
    return avisos
