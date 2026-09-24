from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.models import (
    Base,
    FaixaAudiencia,
    Operadora,
    Setor,
    TipoEvento,
    TipoLaudo,
    Usuario,
)

DEFAULT_TIPOS_LAUDO = {
    "AUTO": 40.0,
    "AUTO-BALÃO": 60.0,
    "CONSÓRCIO": 200.0,
    "EMPRÉSTIMO": 40.0,
    "LOTEAMENTO": 400.0,
    "IMÓVEL": 70.0,
}

DEFAULT_FAIXAS_AUDIENCIA = (
    (1, 20, 400.0),
    (21, 39, 350.0),
    (40, 60, 300.0),
    (61, 79, 250.0),
    (80, 100, 200.0),
)

# Ver ARCHITECTURE.md seção 2.6 e o chat da Fase 4: setores reais informados
# pela Clara. "Financeiro" existe uma vez por operadora (times distintos);
# os outros três são exclusivos da ELITE. T.I. tem papel_global próprio
# (ADMIN_TI, ver app/auth.py) — não é um setor, por isso não está aqui.
DEFAULT_SETORES = {
    "ELITE": ["Líder - Gestão de Processos", "Doutores(as)", "Admin/dona", "Financeiro"],
    "EXIMIA": ["Financeiro"],
}

# Catálogo inicial de tipos de evento — os mais frequentes observados na
# planilha real "ELITE - GESTÃO DE PROCESSOS.xlsx" (Fase 5). Igual aos tipos
# de laudo: um evento com tipo fora dessa lista não é bloqueado no import,
# só fica sinalizado como "não catalogado" (mesmo tratamento que já existe
# para tipos de laudo desconhecidos).
DEFAULT_TIPOS_EVENTO = [
    "CUSTAS",
    "CUSTAS INICIAIS",
    "CUSTAS FINAIS",
    "DOCUMENTOS",
    "SOLICITAR DOCUMENTOS",
    "DADOS PARA MLE",
    "PREPARO DE APELAÇÃO",
    "CONTATO COM O CLIENTE",
    "SOLICITAR HONORÁRIOS SUCUMBENCIAIS",
    "PROCURAÇÃO",
    "SOLICITAR CUSTAS",
    "EMITIR PARCELA INCONTROVERSA",
    "TAXA DE CANCELAMENTO",
]

_engine = None
_SessionLocal: sessionmaker | None = None


def _normalizar_url(url: str) -> str:
    """Garante que a URL do Postgres use o driver `psycopg` (v3), que é o
    instalado em requirements.txt. Sem isso, uma URL comum
    (`postgresql://...`, como a que o Supabase fornece) faz o SQLAlchemy
    tentar o driver antigo `psycopg2` por padrão — que não instalamos —
    e o servidor não sobe (`ModuleNotFoundError: No module named 'psycopg2'`).

    Também remove o parâmetro `pgbouncer=true`, que algumas telas do
    Supabase (a de "ORM"/Prisma) incluem na connection string do pooler —
    é uma flag de aplicação (avisa o Prisma pra não usar prepared
    statements), não uma opção real de conexão do Postgres; o psycopg
    recusa a conexão se ela vier na URL
    (`invalid connection option "pgbouncer"`).

    Importante: a remoção do `pgbouncer` é feita com manipulação de texto
    simples (partir a string em "?"/"&"), **sem** usar `urllib.parse.urlsplit`
    para reanalisar a URL inteira — o parser da stdlib (a partir do Python
    3.14, usado no Render) passou a validar mais rigorosamente o "host" da
    URL e derruba o app (`ValueError: ... does not appear to be an IPv4 or
    IPv6 address`) quando a senha do banco tem certos caracteres especiais
    (comuns em senhas geradas pelo Supabase). Texto puro evita reanalisar
    (e potencialmente rejeitar) a parte de usuário/senha/host da URL.

    URLs de SQLite (usadas nos testes) passam direto, sem alteração."""
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    if url.startswith("postgresql+psycopg://") and "?" in url:
        base, _, query = url.partition("?")
        params = [p for p in query.split("&") if p and p.split("=", 1)[0].lower() != "pgbouncer"]
        url = base + ("?" + "&".join(params) if params else "")
    return url


def get_engine():
    global _engine
    if _engine is None:
        if not settings.database_url:
            raise RuntimeError(
                "DATABASE_URL não configurado. Defina a variável de ambiente antes de usar o banco."
            )
        url = _normalizar_url(settings.database_url)
        _engine = create_engine(
            url,
            pool_pre_ping=True,
            # O pooler do Supabase (PgBouncer/Supavisor) em modo transação
            # não sustenta prepared statements entre conexões — desliga o
            # cache de prepared statements do psycopg pra evitar erros
            # ("prepared statement already exists") sob esse tipo de pooler.
            # Inofensivo numa conexão direta; SQLite (testes) não usa isso.
            connect_args={"prepare_threshold": None} if url.startswith("postgresql+psycopg://") else {},
        )
    return _engine


def get_session_factory() -> sessionmaker:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), expire_on_commit=False)
    return _SessionLocal


def get_db() -> Generator[Session, None, None]:
    session_factory = get_session_factory()
    db = session_factory()
    try:
        yield db
    finally:
        db.close()


def _garantir_coluna(engine, tabela: str, coluna: str, tipo_sql: str) -> None:
    """Adiciona uma coluna nova a uma tabela que já existe em produção — o
    projeto não usa uma ferramenta de migração (Alembic); `create_all` só
    cria tabelas que ainda não existem, não altera as existentes. Sem isso,
    um campo novo (ex.: `mes_referencia`) some silenciosamente num banco já
    provisionado (Render/Supabase), mesmo depois do deploy do código novo."""
    inspector = inspect(engine)
    if not inspector.has_table(tabela):
        return  # create_all acima já criou a tabela com a coluna certa
    colunas = {c["name"] for c in inspector.get_columns(tabela)}
    if coluna not in colunas:
        with engine.begin() as conn:
            conn.execute(text(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo_sql}"))


def _garantir_texto_ilimitado(engine, tabela: str, *colunas: str) -> None:
    """Alarga colunas que já existem em produção como VARCHAR(N) para TEXT
    (sem limite) — dados reais da planilha de Gestão de Processos mostraram
    valores mais longos do que o esperado nesses campos (ex.: `advogada`
    com texto composto tipo "HUNTING - Fulana (CONTR. Beltrano)", 84+
    caracteres), causando `StringDataRightTruncation` em produção. Só roda
    no Postgres — SQLite (testes) não aplica limite de VARCHAR de verdade,
    e as tabelas de teste são recriadas do zero a cada execução."""
    if engine.dialect.name != "postgresql" or not inspect(engine).has_table(tabela):
        return
    with engine.begin() as conn:
        for coluna in colunas:
            conn.execute(text(f"ALTER TABLE {tabela} ALTER COLUMN {coluna} TYPE TEXT"))


def _garantir_indice_prazos_fatais(engine) -> None:
    """Índice parcial pra `prazos_proximos()` (`app/services/processos.py`)
    — sem índice, essa consulta varre `eventos_processo` inteira toda vez
    que a tela de Gestão de Processos carrega (log real do Render: ~13-15s
    numa tabela com ~50 mil linhas), mesmo quando o resultado é vazio — que
    hoje é sempre o caso, já que `data_prazo` só é preenchido por
    lançamento manual futuro, nunca pelo import. Índice parcial (só as
    linhas que a consulta realmente filtra) fica minúsculo mesmo com a
    tabela toda crescendo. Só roda no Postgres — SQLite (testes) tem tabela
    pequena o bastante pra não precisar."""
    if engine.dialect.name != "postgresql" or not inspect(engine).has_table("eventos_processo"):
        return
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_eventos_processo_prazo_fatal_pendente "
                "ON eventos_processo (data_prazo) "
                "WHERE prazo_fatal = true AND resolvido = false AND data_prazo IS NOT NULL"
            )
        )


def init_db() -> None:
    """Cria as tabelas (se não existirem) e semeia valores padrão, igual ao
    comportamento do core/db.py do sistema atual na primeira execução."""
    engine = get_engine()
    Base.metadata.create_all(engine)
    _garantir_coluna(engine, "eventos_processo", "mes_referencia", "VARCHAR(20)")
    _garantir_coluna(engine, "processos", "assessoria", "TEXT")
    _garantir_texto_ilimitado(engine, "processos", "nome_cliente", "advogada", "assistente")
    _garantir_texto_ilimitado(engine, "eventos_processo", "tipo_evento_nome")
    _garantir_texto_ilimitado(
        engine, "audiencias", "nome_cliente", "cpf", "data_agendamento", "conciliadora", "advogada"
    )
    _garantir_indice_prazos_fatais(engine)
    session_factory = get_session_factory()
    with session_factory() as db:
        if db.scalar(select(TipoLaudo.id).limit(1)) is None:
            for nome, valor in DEFAULT_TIPOS_LAUDO.items():
                db.add(TipoLaudo(nome=nome, valor_padrao=valor))
        if db.scalar(select(FaixaAudiencia.id).limit(1)) is None:
            for inicio, fim, valor in DEFAULT_FAIXAS_AUDIENCIA:
                db.add(FaixaAudiencia(inicio=inicio, fim=fim, valor=valor))
        if db.scalar(select(TipoEvento.id).limit(1)) is None:
            for nome in DEFAULT_TIPOS_EVENTO:
                db.add(TipoEvento(nome=nome))

        operadoras = {o.nome: o for o in db.scalars(select(Operadora))}
        for nome in ("EXIMIA", "ELITE"):
            if nome not in operadoras:
                operadora = Operadora(nome=nome)
                db.add(operadora)
                db.flush()
                operadoras[nome] = operadora

        setores_existentes = {(s.operadora_id, s.nome) for s in db.scalars(select(Setor))}
        for operadora_nome, nomes_setor in DEFAULT_SETORES.items():
            operadora = operadoras[operadora_nome]
            for nome_setor in nomes_setor:
                if (operadora.id, nome_setor) not in setores_existentes:
                    db.add(Setor(operadora_id=operadora.id, nome=nome_setor))

        db.commit()
        _bootstrap_admin(db)


def _bootstrap_admin(db: Session) -> None:
    """Cria o primeiro Admin Superior a partir de variáveis de ambiente, só
    se ainda não existir nenhum usuário com papel_global no banco. Depois
    do primeiro login, novos usuários são criados por `POST /usuarios` —
    ver README.md."""
    from app.auth import (
        hash_senha,  # import tardio: evita ciclo com app.auth (que importa app.db)
    )

    if not settings.admin_bootstrap_email or not settings.admin_bootstrap_senha:
        return
    if db.scalar(select(Usuario.id).where(Usuario.papel_global.isnot(None)).limit(1)) is not None:
        return
    db.add(
        Usuario(
            nome="Admin Superior",
            email=settings.admin_bootstrap_email.strip().lower(),
            senha_hash=hash_senha(settings.admin_bootstrap_senha),
            papel_global="ADMIN_SUPERIOR",
        )
    )
    db.commit()
