"""Resolução de empresa-cliente por nome (usada por todos os importadores).

Não confundir com `operadoras` (EXÍMIA/ELITE) — ver ARCHITECTURE.md seção 1.3.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Audiencia, Cobranca, EmpresaCliente, Laudo, Processo
from app.utils import normalize

# Lista oficial de empresas-clientes (nome curto usado em todo o sistema —
# não a razão social) + CNPJ, a partir do PDF "INFOS ASSESSORIAS" que a
# Clara mandou (2026-09-24). Usada só por `sincronizar_lista_oficial`, uma
# ação administrativa que ela dispara manualmente em /app/empresas — ver
# DECISIONS.md. "WNFAST" (sem espaço) e não "WN FAST" (como está no PDF):
# é o nome que a planilha real de processos já usa nos registros existentes
# (confirmado pela Clara). "OPÇÃO1" não tem CNPJ no PDF (célula em branco).
LISTA_OFICIAL_EMPRESAS: list[tuple[str, str | None]] = [
    ("ABSOLUTA", "33.420.655/0001-78"),
    ("ALLURE", "62.568.871/0001-63"),
    ("ALPHA", "52.144.384/0001-10"),
    ("ALTHERA", "25.216.743/0001-24"),
    ("ANGITU", "55.616.477/0001-98"),
    ("ANDRADE", "13.286.210/0001-30"),
    ("APEX", "47.133.521/0001-80"),
    ("ATITUDE", "55.259.389/0001-86"),
    ("ATIVA", "58.260.174/0001-73"),
    ("ATLAS", "60.754.486/0001-85"),
    ("AXIS", "65.149.579/0001-60"),
    ("DAKAL", "51.382.664/0001-01"),
    ("EROS", "51.117.907/0001-76"),
    ("EWS", "59.246.072/0001-66"),
    ("FLY", "57.089.510/0001-02"),
    ("FOX", "55.993.434/0001-21"),
    ("HEIT", "26.569.085/0001-17"),
    ("GUARDIÃ", "65.268.586/0001-15"),
    ("HUNTING", "48.647.719/0001-45"),
    ("JUROS JUSTOS", "53.089.716/0001-73"),
    ("MARTAN", "58.970.728/0001-26"),
    ("NEXUS", "45.125.081/0001-94"),
    ("NOVA GLOBAL", "48.373.106/0001-67"),
    ("NOVARE", "63.811.122/0001-88"),
    ("OPÇÃO1", None),
    ("PLATINO", "52.807.405/0001-30"),
    ("PERES", "48.031.350/0001-41"),
    ("PROMISS", "65.096.680/0001-34"),
    ("PRÓSPERA", "65.305.011/0001-25"),
    ("REAL", "53.936.950/0001-99"),
    ("ROYAL", "39.732.554/0001-19"),
    ("REALLY", "59.125.763/0001-01"),
    ("REGULARIZE", "46.668.859/0001-74"),
    ("REVISALPHA", "65.991.525/0001-81"),
    ("RENOVA", "65.012.274/0001-46"),
    ("RETRIX", "58.077.999/0001-57"),
    ("REVISION", "48.819.369/0001-57"),
    ("ROCKET", "61.198.351/0001-43"),
    ("SIMPLIFICA", "44.573.912/0001-28"),
    ("SW", "56.659.902/0001-99"),
    ("TEG", "53.032.919/0001-23"),
    ("TIMER", "59.009.116/0001-34"),
    ("TITÃ", "44.496.809/0001-21"),
    ("TORRES", "62.954.634/0001-30"),
    ("WALLTRIX", "58.346.810/0001-84"),
    ("WNFAST", "44.934.726/0001-77"),
    ("WNR CONSULTORIA", "59.455.552/0001-37"),
    ("ZENITH", "58.172.302/0001-27"),
]


def get_or_create_empresa(
    db: Session, nome: str, cache: dict[str, EmpresaCliente] | None = None
) -> EmpresaCliente:
    """`cache`: opcional, para imports com muitas linhas (ex.: Gestão de
    Processos, Fase 5) — sem ele, cada chamada faz uma consulta ao banco
    percorrendo todas as empresas-clientes, o que é aceitável para poucas
    linhas mas caro repetido milhares de vezes num único import. Quem chama
    em loop deve passar um dict vazio compartilhado entre as chamadas
    (ver `app/services/processos.py`)."""
    nome = nome.strip()
    alvo = normalize(nome)
    if cache is not None and alvo in cache:
        return cache[alvo]
    for empresa in db.scalars(select(EmpresaCliente)):
        if normalize(empresa.nome) == alvo:
            if cache is not None:
                cache[normalize(empresa.nome)] = empresa
            return empresa
    empresa = EmpresaCliente(nome=nome)
    db.add(empresa)
    db.flush()
    if cache is not None:
        cache[alvo] = empresa
    return empresa


def listar_empresas(db: Session, apenas_ativas: bool = True) -> list[EmpresaCliente]:
    """Usada pelas telas (Fase 6) para montar o seletor de empresa-cliente
    nos módulos de relatório."""
    query = select(EmpresaCliente).order_by(EmpresaCliente.nome)
    if apenas_ativas:
        query = query.where(EmpresaCliente.ativo.is_(True))
    return list(db.scalars(query))


def criar_empresa(db: Session, nome: str, cnpj: str | None = None) -> EmpresaCliente:
    """Cadastro manual (Fase 6, tela de Administração) — os imports usam
    `get_or_create_empresa`; aqui é o caminho explícito, com checagem de
    nome duplicado (a coluna `nome` é `unique`, mas checar antes dá um erro
    claro em vez de deixar o banco recusar sem contexto)."""
    nome = nome.strip()
    alvo = normalize(nome)
    for existente in db.scalars(select(EmpresaCliente)):
        if normalize(existente.nome) == alvo:
            raise ValueError(f"Já existe uma empresa-cliente chamada '{existente.nome}'.")
    empresa = EmpresaCliente(nome=nome, cnpj=(cnpj or "").strip() or None)
    db.add(empresa)
    db.commit()
    return empresa


def atualizar_empresa(db: Session, empresa_id: int, nome: str, cnpj: str | None) -> EmpresaCliente:
    empresa = db.get(EmpresaCliente, empresa_id)
    if empresa is None:
        raise ValueError(f"Empresa-cliente {empresa_id} não encontrada.")
    nome = nome.strip()
    alvo = normalize(nome)
    for existente in db.scalars(select(EmpresaCliente)):
        if existente.id != empresa_id and normalize(existente.nome) == alvo:
            raise ValueError(f"Já existe uma empresa-cliente chamada '{existente.nome}'.")
    empresa.nome = nome
    empresa.cnpj = (cnpj or "").strip() or None
    db.commit()
    return empresa


def alterar_ativo_empresa(db: Session, empresa_id: int, ativo: bool) -> EmpresaCliente:
    empresa = db.get(EmpresaCliente, empresa_id)
    if empresa is None:
        raise ValueError(f"Empresa-cliente {empresa_id} não encontrada.")
    empresa.ativo = ativo
    db.commit()
    return empresa


def excluir_empresa(db: Session, empresa_id: int) -> None:
    """Exclusão definitiva (a pedido da Clara — a tela pede confirmação
    antes de chamar isso). Bloqueada se a empresa tiver laudo/audiência/
    cobrança/processo vinculado: apagar apagaria esse histórico junto
    (violaria "nunca modificar/apagar sem autorização explícita" do
    prompt mestre para dado que não foi o alvo direto do pedido) — nesses
    casos, desativar (`alterar_ativo_empresa`) é o caminho seguro."""
    empresa = db.get(EmpresaCliente, empresa_id)
    if empresa is None:
        raise ValueError(f"Empresa-cliente {empresa_id} não encontrada.")

    vinculos = {
        "laudos": db.scalar(select(func.count()).select_from(Laudo).where(Laudo.empresa_cliente_id == empresa_id)),
        "audiências": db.scalar(select(func.count()).select_from(Audiencia).where(Audiencia.empresa_cliente_id == empresa_id)),
        "cobranças": db.scalar(select(func.count()).select_from(Cobranca).where(Cobranca.empresa_cliente_id == empresa_id)),
        "processos": db.scalar(select(func.count()).select_from(Processo).where(Processo.empresa_cliente_id == empresa_id)),
    }
    presentes = [f"{qtd} {nome}" for nome, qtd in vinculos.items() if qtd]
    if presentes:
        raise ValueError(
            f"Não é possível excluir '{empresa.nome}': existe {', '.join(presentes)} vinculado(s) a ela. "
            "Desative em vez de excluir, se quiser tirá-la das telas de relatório."
        )

    db.delete(empresa)
    db.commit()


@dataclass
class ResumoSincronizacao:
    criadas: list[str] = field(default_factory=list)
    atualizadas_cnpj: list[str] = field(default_factory=list)
    sem_mudanca: list[str] = field(default_factory=list)
    excluidas: list[str] = field(default_factory=list)
    nao_excluidas_por_vinculo: list[str] = field(default_factory=list)


def sincronizar_lista_oficial(
    db: Session, lista: list[tuple[str, str | None]] = LISTA_OFICIAL_EMPRESAS
) -> ResumoSincronizacao:
    """Ação administrativa (2026-09-24, a pedido explícito da Clara): cria as
    empresas da lista oficial que ainda não existem, atualiza o CNPJ das que
    já existem (por nome), e exclui de verdade qualquer empresa cadastrada
    que NÃO esteja na lista — usando `excluir_empresa` (mesma proteção contra
    apagar histórico vinculado: se tiver laudo/audiência/cobrança/processo,
    a exclusão dessa empresa é recusada e ela entra em
    `nao_excluidas_por_vinculo`, sem forçar o apagamento do histórico dela).
    Irreversível para quem for excluído; a tela que chama isso exige
    confirmação explícita antes."""
    resumo = ResumoSincronizacao()
    alvo_nomes = {normalize(nome) for nome, _ in lista}
    existentes = {normalize(e.nome): e for e in db.scalars(select(EmpresaCliente))}

    for nome, cnpj in lista:
        alvo = normalize(nome)
        empresa = existentes.get(alvo)
        if empresa is None:
            db.add(EmpresaCliente(nome=nome, cnpj=cnpj))
            resumo.criadas.append(nome)
        elif cnpj and empresa.cnpj != cnpj:
            empresa.cnpj = cnpj
            resumo.atualizadas_cnpj.append(nome)
        else:
            resumo.sem_mudanca.append(nome)
    db.commit()

    for alvo, empresa in existentes.items():
        if alvo in alvo_nomes:
            continue
        try:
            excluir_empresa(db, empresa.id)
            resumo.excluidas.append(empresa.nome)
        except ValueError:
            resumo.nao_excluidas_por_vinculo.append(empresa.nome)

    return resumo
