"""Modelos SQLAlchemy — schema v1 (ver DATABASE.md).

Fase 4: adiciona setores, usuários, vínculo usuário-setor, sessões de login
e log de auditoria — ver ARCHITECTURE.md seção 2.6 para o modelo de papéis.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Operadora(Base):
    __tablename__ = "operadoras"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(20), unique=True)
    ativo: Mapped[bool] = mapped_column(default=True)


class EmpresaCliente(Base):
    __tablename__ = "empresas_clientes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    cnpj: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ativo: Mapped[bool] = mapped_column(default=True)

    laudos: Mapped[list[Laudo]] = relationship(back_populates="empresa_cliente")
    audiencias: Mapped[list[Audiencia]] = relationship(back_populates="empresa_cliente")
    cobrancas: Mapped[list[Cobranca]] = relationship(back_populates="empresa_cliente")


class TipoLaudo(Base):
    __tablename__ = "tipos_laudo"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    valor_padrao: Mapped[float] = mapped_column(Float, default=0.0)
    ativo: Mapped[bool] = mapped_column(default=True)


class Laudo(Base):
    __tablename__ = "laudos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_cliente_id: Mapped[int] = mapped_column(ForeignKey("empresas_clientes.id"))
    tipo_laudo_nome: Mapped[str] = mapped_column(String(60))  # texto livre — igual à planilha hoje
    data: Mapped[date] = mapped_column(Date, index=True)
    nome_cliente: Mapped[str] = mapped_column(String(200), default="")
    status: Mapped[str] = mapped_column(String(20))  # SOLICITACAO | CORRECAO | CANCELADO
    valor: Mapped[float] = mapped_column(Float, default=0.0)
    origem: Mapped[str] = mapped_column(String(20), default="IMPORT_PLANILHA")
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    empresa_cliente: Mapped[EmpresaCliente] = relationship(back_populates="laudos")


class FaixaAudiencia(Base):
    __tablename__ = "faixas_audiencia"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    inicio: Mapped[int] = mapped_column(Integer)
    fim: Mapped[int] = mapped_column(Integer)
    valor: Mapped[float] = mapped_column(Float)


class Audiencia(Base):
    __tablename__ = "audiencias"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_cliente_id: Mapped[int] = mapped_column(ForeignKey("empresas_clientes.id"))
    # Text (sem limite), não VARCHAR(N): mesmo texto livre da mesma planilha
    # real que já causou StringDataRightTruncation em `processos` (ver
    # DECISIONS.md) — nome_cliente/cpf/data_agendamento/conciliadora/advogada
    # vêm sem validação de tamanho da planilha. `cpf` em VARCHAR(20) foi o
    # que realmente estourou em produção (a Clara mandou o log) — a célula
    # de CPF às vezes tem mais que um CPF formatado (14 caracteres); os
    # outros três (nome_cliente/data_agendamento/conciliadora/advogada)
    # foram convertidos preventivamente no mesmo commit, por precaução (não
    # foi confirmado que estouraram, mas são o mesmo tipo de texto livre da
    # mesma planilha/equipe que já mostrou o mesmo problema em `advogada`
    # de `processos`, "HUNTING - Fulana de Tal (CONTR. Beltrano)", 84+
    # caracteres).
    nome_cliente: Mapped[str] = mapped_column(Text)
    cpf: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_recebimento: Mapped[date] = mapped_column(Date, index=True)
    data_agendamento: Mapped[str | None] = mapped_column(Text, nullable=True)
    conciliadora: Mapped[str | None] = mapped_column(Text, nullable=True)
    advogada: Mapped[str | None] = mapped_column(Text, nullable=True)
    origem: Mapped[str] = mapped_column(String(20), default="IMPORT_PLANILHA")
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    empresa_cliente: Mapped[EmpresaCliente] = relationship(back_populates="audiencias")


class Cobranca(Base):
    __tablename__ = "cobrancas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_cliente_id: Mapped[int] = mapped_column(ForeignKey("empresas_clientes.id"))
    data: Mapped[date] = mapped_column(Date, index=True)
    tipo_cobranca: Mapped[str] = mapped_column(String(200))
    cobrador: Mapped[str] = mapped_column(String(10))  # EXIMIA | ELITE
    valor: Mapped[float] = mapped_column(Float)
    status_pagamento: Mapped[str | None] = mapped_column(String(30), nullable=True)
    origem: Mapped[str] = mapped_column(String(20), default="IMPORT_PLANILHA")
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    empresa_cliente: Mapped[EmpresaCliente] = relationship(back_populates="cobrancas")


class Setor(Base):
    __tablename__ = "setores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    operadora_id: Mapped[int] = mapped_column(ForeignKey("operadoras.id"))
    nome: Mapped[str] = mapped_column(String(80))
    ativo: Mapped[bool] = mapped_column(default=True)

    operadora: Mapped[Operadora] = relationship()


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    senha_hash: Mapped[str] = mapped_column(String(100))
    # Papel de alcance global (vê as duas operadoras, todos os setores).
    # None = usuário comum, escopo definido só pelos vínculos em usuario_setor.
    papel_global: Mapped[str | None] = mapped_column(String(20), nullable=True)  # 'ADMIN_SUPERIOR' | 'ADMIN_TI'
    ativo: Mapped[bool] = mapped_column(default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    setores: Mapped[list[UsuarioSetor]] = relationship(back_populates="usuario")


class UsuarioSetor(Base):
    __tablename__ = "usuario_setor"

    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), primary_key=True)
    setor_id: Mapped[int] = mapped_column(ForeignKey("setores.id"), primary_key=True)
    papel: Mapped[str] = mapped_column(String(20))  # 'LIDER' | 'COLABORADOR'

    usuario: Mapped[Usuario] = relationship(back_populates="setores")
    setor: Mapped[Setor] = relationship()


class Sessao(Base):
    """Token opaco de login — revogável (basta apagar a linha), consultado
    a cada requisição autenticada. Evita depender de segredo de assinatura
    (JWT) e permite "sair" de verdade, não só o token expirar sozinho."""

    __tablename__ = "sessoes"

    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expira_em: Mapped[datetime] = mapped_column(DateTime)

    usuario: Mapped[Usuario] = relationship()


class LogAuditoria(Base):
    __tablename__ = "logs_auditoria"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    acao: Mapped[str] = mapped_column(String(60))
    entidade: Mapped[str | None] = mapped_column(String(40), nullable=True)
    entidade_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    detalhes: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Processo(Base):
    """Gestão de Processos (Fase 5, ELITE) — ver DATABASE.md seção 6.1."""

    __tablename__ = "processos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    numero_processo: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    empresa_cliente_id: Mapped[int] = mapped_column(ForeignKey("empresas_clientes.id"))
    # Text (sem limite), não VARCHAR(N): a planilha real já mostrou texto
    # bem mais longo do que um nome simples nesses campos (ex.: ADVOGADA
    # com "HUNTING - Fulana de Tal (CONTR. Beltrano)", 84+ caracteres) —
    # causou StringDataRightTruncation em produção. Ver DECISIONS.md.
    nome_cliente: Mapped[str] = mapped_column(Text, default="")
    advogada: Mapped[str | None] = mapped_column(Text, nullable=True)
    assistente: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Extraído da coluna ADVOGADA (ex.: "HUNTING - Fulana de Tal" -> "HUNTING")
    # — a equipe/escritório terceirizado, distinto do nome da advogada em si.
    # `advogada` continua com o texto original da planilha, sem alteração —
    # ver services/processos.py::_separar_assessoria.
    assessoria: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    empresa_cliente: Mapped[EmpresaCliente] = relationship()
    eventos: Mapped[list[EventoProcesso]] = relationship(back_populates="processo")


class TipoEvento(Base):
    __tablename__ = "tipos_evento"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    ativo: Mapped[bool] = mapped_column(default=True)


class EventoProcesso(Base):
    __tablename__ = "eventos_processo"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    processo_id: Mapped[int] = mapped_column(ForeignKey("processos.id"), index=True)
    data: Mapped[date] = mapped_column(Date, index=True)
    # Text, não VARCHAR(80): mesmo motivo do Processo.advogada/assistente
    # acima — texto livre vindo da mesma planilha real, que já se mostrou
    # mais longa do que um nome de evento do catálogo.
    tipo_evento_nome: Mapped[str] = mapped_column(Text)
    # Mês/ano da aba de origem na planilha (ex.: "SETEMBRO/2026") — não é
    # extraído de `data`, é o que a própria planilha chama a aba. Só
    # informativo (mostrado em relatórios/painel), pode ficar None quando a
    # aba não é nomeada por mês (ex. abas "fatais", "DOCS E CUSTAS"). Ver
    # app/services/processos.py::_mes_referencia_da_aba.
    mes_referencia: Mapped[str | None] = mapped_column(String(20), nullable=True)
    prazo_fatal: Mapped[bool] = mapped_column(default=False)
    data_prazo: Mapped[date | None] = mapped_column(Date, nullable=True)
    resolvido: Mapped[bool] = mapped_column(default=False)
    resolvido_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    observacao: Mapped[str | None] = mapped_column(Text, nullable=True)
    origem: Mapped[str] = mapped_column(String(20), default="IMPORT_PLANILHA")
    criado_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    processo: Mapped[Processo] = relationship(back_populates="eventos")
