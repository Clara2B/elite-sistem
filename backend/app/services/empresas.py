"""Resolução de empresa-cliente por nome (usada por todos os importadores).

Não confundir com `operadoras` (EXÍMIA/ELITE) — ver ARCHITECTURE.md seção 1.3.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models import (
    Audiencia,
    Cobranca,
    Correspondencia,
    EmpresaCliente,
    Laudo,
    Processo,
)
from app.utils import normalize

# Entidades com FK NOT NULL pra empresa-cliente — todo laudo/audiência/
# cobrança/processo/correspondência tem que pertencer a alguma empresa (ver
# models.py), por isso "excluir mesmo com vínculo" só é possível
# reatribuindo esses registros a outra empresa antes de apagar (nunca
# deixando-os orfãos). "correspondências" faltou aqui quando o módulo foi
# criado (2026-10-05) — bug real reportado pela Clara: excluir uma empresa
# com correspondência vinculada não caía no aviso amigável de baixo (porque
# `contar_vinculos_empresa` não sabia contar), ia direto pro `db.delete`, e
# o Postgres de produção recusava o DELETE por violação de FK (SQLite, usado
# nos testes, não aplica FK por padrão — por isso não pegou antes) — vira
# erro não tratado, tela genérica "Algo deu errado", sempre que tentasse de
# novo (ver DECISIONS.md 2026-10-06).
_ENTIDADES_VINCULADAS = {
    "laudos": Laudo,
    "audiências": Audiencia,
    "cobranças": Cobranca,
    "processos": Processo,
    "correspondências": Correspondencia,
}


def contar_vinculos_empresa(db: Session, empresa_id: int) -> dict[str, int]:
    return {
        nome: db.scalar(select(func.count()).select_from(modelo).where(modelo.empresa_cliente_id == empresa_id))
        for nome, modelo in _ENTIDADES_VINCULADAS.items()
    }


def contar_vinculos_todas_empresas(db: Session) -> dict[int, int]:
    """Versão em lote de `contar_vinculos_empresa` pra telas que precisam do
    total de TODAS as empresas de uma vez (2026-10-08, varredura de
    otimização — a tela de Empresas-clientes rodava `contar_vinculos_
    empresa` uma vez por empresa cadastrada, ou seja 5 consultas × N
    empresas a cada carga de página: com as 48 da lista oficial, até 240
    consultas só pra montar a coluna de "quantas são excluídas direto").
    Aqui é uma consulta agregada por tipo de vínculo — 5 no total, sempre,
    não importa quantas empresas existam. Resultado: {empresa_id: total de
    vínculos somando os 5 tipos}; empresa sem nenhum vínculo simplesmente
    não aparece no dict (quem usa trata ausência como 0, ex.: `.get(id, 0)`
    em empresas.html — nenhuma mudança de template foi necessária)."""
    totais: dict[int, int] = {}
    for modelo in _ENTIDADES_VINCULADAS.values():
        linhas = db.execute(select(modelo.empresa_cliente_id, func.count()).group_by(modelo.empresa_cliente_id))
        for empresa_id, quantidade in linhas:
            totais[empresa_id] = totais.get(empresa_id, 0) + quantidade
    return totais

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


def excluir_empresa(db: Session, empresa_id: int, empresa_destino_id: int | None = None) -> None:
    """Exclusão definitiva (a pedido da Clara — a tela pede confirmação
    antes de chamar isso). Bloqueada se a empresa tiver laudo/audiência/
    cobrança/processo vinculado, A MENOS que `empresa_destino_id` seja
    informado — nesse caso (2026-09-28, a pedido da Clara: "deve ser
    indicado a troca de empresa antes da remoção") todo esse histórico é
    reatribuído pra `empresa_destino_id` antes de excluir, em vez de
    deixá-lo orfão ou apagado junto (continua respeitando "nunca apagar
    sem autorização explícita" do prompt mestre — o histórico em si nunca é
    destruído, só passa a apontar pra outra empresa-cliente). Sem
    `empresa_destino_id`, o comportamento é o de sempre: desativar
    (`alterar_ativo_empresa`) é o caminho seguro pra quem tem vínculo."""
    empresa = db.get(EmpresaCliente, empresa_id)
    if empresa is None:
        raise ValueError(f"Empresa-cliente {empresa_id} não encontrada.")

    vinculos = contar_vinculos_empresa(db, empresa_id)
    presentes = [f"{qtd} {nome}" for nome, qtd in vinculos.items() if qtd]

    if presentes and empresa_destino_id is None:
        raise ValueError(
            f"Não é possível excluir '{empresa.nome}': existe {', '.join(presentes)} vinculado(s) a ela. "
            "Desative em vez de excluir, ou informe uma empresa de destino pra mover o histórico antes de excluir."
        )

    if presentes and empresa_destino_id is not None:
        if empresa_destino_id == empresa_id:
            raise ValueError("A empresa de destino precisa ser diferente da empresa que está sendo excluída.")
        destino = db.get(EmpresaCliente, empresa_destino_id)
        if destino is None:
            raise ValueError(f"Empresa-cliente de destino {empresa_destino_id} não encontrada.")
        for modelo in _ENTIDADES_VINCULADAS.values():
            db.execute(
                update(modelo).where(modelo.empresa_cliente_id == empresa_id).values(empresa_cliente_id=empresa_destino_id)
            )

    db.delete(empresa)
    db.commit()


@dataclass
class ResumoExclusaoEmMassa:
    excluidas: list[str] = field(default_factory=list)
    nao_excluidas_por_vinculo: list[str] = field(default_factory=list)


def excluir_empresas_em_massa(
    db: Session, empresa_ids: list[int], empresa_destino_id: int | None = None
) -> ResumoExclusaoEmMassa:
    """Exclusão em massa (a pedido da Clara, 2026-10-06 — "preciso de alguma
    forma de selecionar e apagar empresas em massa"): aplica `excluir_empresa`
    a cada id selecionado, com uma ÚNICA empresa de destino pra todas (opção
    que ela escolheu): quem não tiver vínculo é excluída direto; quem tiver
    vínculo e um destino foi informado tem o histórico movido pra lá antes de
    excluir; quem tiver vínculo e NENHUM destino foi informado fica de fora
    (não bloqueia as demais) e entra em `nao_excluidas_por_vinculo` — mesma
    mensagem amigável de sempre, só que por lote em vez de travar tudo."""
    if empresa_destino_id is not None:
        if empresa_destino_id in empresa_ids:
            raise ValueError("A empresa de destino não pode estar entre as selecionadas para exclusão.")
        if db.get(EmpresaCliente, empresa_destino_id) is None:
            raise ValueError(f"Empresa-cliente de destino {empresa_destino_id} não encontrada.")

    resumo = ResumoExclusaoEmMassa()
    for empresa_id in dict.fromkeys(empresa_ids):
        empresa = db.get(EmpresaCliente, empresa_id)
        if empresa is None:
            continue
        nome = empresa.nome
        try:
            excluir_empresa(db, empresa_id, empresa_destino_id)
            resumo.excluidas.append(nome)
        except ValueError:
            resumo.nao_excluidas_por_vinculo.append(nome)
    return resumo


@dataclass
class ResumoRealocacaoEmMassa:
    realocadas: list[tuple[str, int]] = field(default_factory=list)
    sem_vinculo: list[str] = field(default_factory=list)


def realocar_empresas_em_massa(
    db: Session, empresa_ids: list[int], empresa_destino_id: int
) -> ResumoRealocacaoEmMassa:
    """Realocação em massa (a pedido da Clara, 2026-10-06 — "além de
    realocá-las em massa se necessário"): ação SEPARADA da exclusão — move
    todo o histórico vinculado (laudos, audiências, cobranças, processos,
    correspondências) das empresas selecionadas pra uma única empresa de
    destino, sem excluir nem desativar as empresas de origem (ela escolheu
    deixá-las como estão — decide depois, manualmente, o que fazer com cada
    uma). Quem não tiver nada vinculado entra em `sem_vinculo` (nada a
    mover, não é erro)."""
    if empresa_destino_id in empresa_ids:
        raise ValueError("A empresa de destino não pode estar entre as selecionadas para realocação.")
    if db.get(EmpresaCliente, empresa_destino_id) is None:
        raise ValueError(f"Empresa-cliente de destino {empresa_destino_id} não encontrada.")

    resumo = ResumoRealocacaoEmMassa()
    for empresa_id in dict.fromkeys(empresa_ids):
        empresa = db.get(EmpresaCliente, empresa_id)
        if empresa is None:
            continue
        vinculos = contar_vinculos_empresa(db, empresa_id)
        total = sum(vinculos.values())
        if total == 0:
            resumo.sem_vinculo.append(empresa.nome)
            continue
        for modelo in _ENTIDADES_VINCULADAS.values():
            db.execute(
                update(modelo).where(modelo.empresa_cliente_id == empresa_id).values(empresa_cliente_id=empresa_destino_id)
            )
        resumo.realocadas.append((empresa.nome, total))
    db.commit()
    return resumo


@dataclass
class ResumoExclusaoInativas:
    excluidas: list[str] = field(default_factory=list)
    nao_excluidas_por_vinculo: list[str] = field(default_factory=list)


def excluir_empresas_inativas(db: Session) -> ResumoExclusaoInativas:
    """Ação administrativa (2026-09-28, a pedido explícito da Clara — ela
    desativou as empresas que não quer mais usar e pediu pra excluir todas
    de uma vez): exclui de verdade toda empresa-cliente com `ativo=False`,
    usando `excluir_empresa` — mesma proteção contra apagar histórico
    vinculado (laudo/audiência/cobrança/processo): quem tiver, fica de fora
    da exclusão e entra em `nao_excluidas_por_vinculo`, sem forçar o
    apagamento do histórico dela. Irreversível para quem for excluída; a
    tela que chama isso exige confirmação explícita antes."""
    resumo = ResumoExclusaoInativas()
    inativas = list(db.scalars(select(EmpresaCliente).where(EmpresaCliente.ativo.is_(False))))
    for empresa in inativas:
        try:
            excluir_empresa(db, empresa.id)
            resumo.excluidas.append(empresa.nome)
        except ValueError:
            resumo.nao_excluidas_por_vinculo.append(empresa.nome)
    return resumo


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
