"""Nome (de planilha) → empresa-cliente oficial, via apelidos (Fase 3).

Toda filtragem por assessoria passa por aqui, porque as planilhas usam
nomes diferentes pra mesma empresa. Fonte da lista oficial: `EmpresaCliente`
(não um YAML separado — ver decisão da Clara, 2026-10-08, "Cadastro
assessorias"); `config/assessorias.yaml` guarda só os apelidos.

Regras do tradutor (especificação):
- Comparação sem acento, sem espaços extras e em maiúsculas — reaproveita
  `app.utils.normalize`, a mesma usada por `leitores/base.py` pra nome de
  coluna/aba (propósito diferente, regra idêntica).
- Célula com mais de uma empresa (ex.: "RETRIX/ REVISION" na pauta) é
  separada por `/`, `,` ou ` E ` e conta pra cada uma.
- Nome que não está no cadastro (nem como oficial, nem como apelido) vira
  aviso global ("empresa desconhecida: ANGITU, 83 linhas") — ver
  secoes/*.py (Fase 4), que agrega `nao_reconhecidos` de todas as linhas;
  aqui só devolve a lista por célula."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import EmpresaCliente
from app.relatorio_assessorias.config import carregar
from app.utils import normalize as normalizar_estrutural

_SEPARADOR_MULTIPLAS_EMPRESAS = re.compile(r"\s*(?:/|,|\sE\s)\s*", re.IGNORECASE)


def construir_nomes_por_apelido(db: Session) -> dict[str, str]:
    """Monta {nome normalizado -> nome oficial} a partir de `EmpresaCliente`
    (nome oficial sempre mapeia pra si mesmo) + apelidos de
    `config/assessorias.yaml`. Uma chave do YAML que não bate com nenhum
    `EmpresaCliente.nome` cadastrado é ignorada silenciosamente — não
    deveria acontecer (a chave é o próprio nome oficial), mas não é motivo
    pra quebrar a geração do relatório por um apelido órfão."""
    nomes_oficiais = [empresa.nome for empresa in db.execute(select(EmpresaCliente)).scalars()]
    nomes_por_apelido = {normalizar_estrutural(nome): nome for nome in nomes_oficiais}

    apelidos_por_chave = carregar("assessorias")
    nomes_oficiais_por_chave = {normalizar_estrutural(nome): nome for nome in nomes_oficiais}
    for chave, dados in apelidos_por_chave.items():
        nome_oficial = nomes_oficiais_por_chave.get(normalizar_estrutural(chave))
        if nome_oficial is None:
            continue
        for apelido in dados.get("apelidos", []):
            nomes_por_apelido[normalizar_estrutural(apelido)] = nome_oficial
    return nomes_por_apelido


@dataclass
class AssessoriaResolvida:
    nomes: list[str] = field(default_factory=list)
    nao_reconhecidos: list[str] = field(default_factory=list)


def resolver(bruto: object, nomes_por_apelido: dict[str, str]) -> AssessoriaResolvida:
    """Resolve o conteúdo de uma célula de assessoria pro(s) nome(s)
    oficial(is) em `nomes_por_apelido` (ver `construir_nomes_por_apelido`).
    Célula com mais de uma empresa é separada por `/`, `,` ou ` E ` e cada
    parte resolvida independentemente; parte não reconhecida vai pra
    `nao_reconhecidos` em vez de gerar erro bloqueante."""
    resolvida = AssessoriaResolvida()
    if bruto is None:
        return resolvida
    texto = str(bruto).strip()
    if not texto:
        return resolvida

    partes = [parte.strip() for parte in _SEPARADOR_MULTIPLAS_EMPRESAS.split(texto) if parte.strip()]
    for parte in partes:
        nome_oficial = nomes_por_apelido.get(normalizar_estrutural(parte))
        if nome_oficial is None:
            resolvida.nao_reconhecidos.append(parte)
        else:
            resolvida.nomes.append(nome_oficial)
    return resolvida
