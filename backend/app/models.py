"""Modelos SQLAlchemy — schema v1 (ver DATABASE.md).

Fase 3: só as tabelas necessárias para laudos/audiências/pendências.
`operadoras` existe como referência (EXIMIA/ELITE, sem controle de acesso
ainda — isso é Fase 4). `usuarios`/`setores`/`logs_auditoria` ficam para a
Fase 4, junto com a autenticação.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String
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
    nome_cliente: Mapped[str] = mapped_column(String(200))
    cpf: Mapped[str | None] = mapped_column(String(20), nullable=True)
    data_recebimento: Mapped[date] = mapped_column(Date, index=True)
    data_agendamento: Mapped[str | None] = mapped_column(String(60), nullable=True)
    conciliadora: Mapped[str | None] = mapped_column(String(80), nullable=True)
    advogada: Mapped[str | None] = mapped_column(String(80), nullable=True)
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
