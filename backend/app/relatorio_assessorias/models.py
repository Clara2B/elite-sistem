"""Tabela nova (Fase 8) — só aditiva, nenhuma tabela existente é alterada
(regra da Clara: mudança de banco só aditiva, sem aprovação prévia de uma
tabela nova e isolada como esta). Fica num arquivo próprio do módulo, não
em `app/models.py`, pra manter a área nova isolada do resto do schema —
`app.db.init_db` importa este módulo (uma linha) só pra garantir que a
classe se registre em `Base.metadata` antes do `create_all`.

Um registro por (assessoria, mês, ano): o resultado calculado das 6
planilhas + os campos manuais, serializados em `dados_json` (ver
`armazenamento.py` pras funções de (de)serialização); `sobrescritas_json`
guarda só os números que alguém editou manualmente na tela de revisão
(especificação: "Qualquer número pode ser sobrescrito; o valor
sobrescrito fica marcado e registrado" — o registro em si, quem/quando/
de-quanto-pra-quanto, usa o `LogAuditoria` que já existe, em vez de um
mecanismo de histórico duplicado)."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class RelatorioAssessoriaResultado(Base):
    __tablename__ = "relatorio_assessorias_resultados"
    __table_args__ = (UniqueConstraint("assessoria", "mes", "ano", name="uq_rel_assessoria_mes_ano"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    assessoria: Mapped[str] = mapped_column(String(120), index=True)
    mes: Mapped[int] = mapped_column(Integer)
    ano: Mapped[int] = mapped_column(Integer, index=True)
    data_corte: Mapped[date] = mapped_column(Date)

    dados_json: Mapped[str] = mapped_column(Text)
    sobrescritas_json: Mapped[str] = mapped_column(Text, default="{}")

    gerado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    atualizado_por_usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
