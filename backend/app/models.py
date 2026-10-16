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


class Funcionario(Base):
    """Cadastro manual dos assistentes de Gestão de Processos (2026-09-24) —
    alimenta o seletor "Funcionário" do relatório de Processos, mesmo
    padrão de EmpresaCliente. Não é FK de `Processo.assistente` (que
    continua texto livre, vindo da planilha) — só uma lista de valores
    pré-definidos pra montar o formulário sem digitar. Ver ARCHITECTURE.md."""

    __tablename__ = "funcionarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    ativo: Mapped[bool] = mapped_column(default=True)


class Banco(Base):
    """Cadastro de bancos (Fase 1 — Solicitação de Audiência, 2026-10-16) —
    alimenta o seletor "Banco" da tela de Nova Solicitação de Audiência e
    resolve nome/CNPJ/e-mail pra Carta Convite Banco sem digitar de novo.
    Mesmo padrão de EmpresaCliente/Funcionario."""

    __tablename__ = "bancos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    cnpj: Mapped[str] = mapped_column(String(20))
    # Alguns bancos têm um segundo CNPJ válido (ex.: Itaú, na planilha real
    # de bancos) — quem monta a Carta Banco escolhe qual se aplica a cada
    # caso. `None` pra quem só tem um.
    cnpj_alternativo: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Text, não VARCHAR (mesmo motivo já conhecido no projeto — ver
    # DECISIONS.md M02): a planilha real tem bancos com vários e-mails
    # separados por ponto-e-vírgula, alguns bem longos.
    email: Mapped[str] = mapped_column(Text)
    ativo: Mapped[bool] = mapped_column(default=True)


class Laudo(Base):
    __tablename__ = "laudos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # index=True (2026-10-08): todo relatório filtra por empresa — sem
    # índice nessa coluna, em produção (Postgres) isso é uma varredura
    # completa da tabela a cada relatório gerado. Ver DECISIONS.md.
    empresa_cliente_id: Mapped[int] = mapped_column(ForeignKey("empresas_clientes.id"), index=True)
    # Text, não VARCHAR (2026-10-13, auditoria M02): mesma classe de bug já
    # corrigida em Processo/Audiencia/LogAuditoria — texto livre vindo da
    # planilha ("NOME DO CLIENTE"/"TIPO DE LAUDO") pode exceder um limite
    # fixo e derrubar a importação com StringDataRightTruncation. Ver
    # DECISIONS.md e `_garantir_texto_ilimitado` em app/db.py.
    tipo_laudo_nome: Mapped[str] = mapped_column(Text)
    data: Mapped[date] = mapped_column(Date, index=True)
    nome_cliente: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20))  # SOLICITACAO | CORRECAO | CANCELADO
    valor: Mapped[float] = mapped_column(Float, default=0.0)
    origem: Mapped[str] = mapped_column(String(20), default="IMPORT_PLANILHA")
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    empresa_cliente: Mapped[EmpresaCliente] = relationship(back_populates="laudos")


class Correspondencia(Base):
    """Correspondências (Fase 9, ELITE, 2026-10-05) — mesmo padrão de Laudos:
    upload de planilha acumula histórico aqui, o relatório filtra por mês +
    empresa já importados. Sem coluna de data/dia na planilha real (só o
    nome do mês, ex. "JANEIRO") — `mes` é literalmente esse texto,
    normalizado em maiúsculas; não há controle de ano (confirmado com a
    Clara: a planilha não distingue, um reimport do mesmo mês em outro ano
    mistura os dados, aceito assim por enquanto).

    `valor` fica `None` quando a célula de VALOR não é um número
    reconhecível (ex.: "a combinar") — nesse caso `valor_texto` guarda o
    texto original da planilha pra mostrar no relatório tal como está
    (decisão da Clara: não zerar nem travar o import por causa disso), e a
    linha fica de fora da soma do Total."""

    __tablename__ = "correspondencias"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_cliente_id: Mapped[int] = mapped_column(ForeignKey("empresas_clientes.id"), index=True)
    mes: Mapped[str] = mapped_column(String(20), index=True)
    advogado: Mapped[str] = mapped_column(Text)
    autor: Mapped[str] = mapped_column(Text)
    adv_preposto: Mapped[str] = mapped_column(Text)
    valor_texto: Mapped[str] = mapped_column(Text)
    valor: Mapped[float | None] = mapped_column(Float, nullable=True)
    tipo_acao: Mapped[str] = mapped_column(Text)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    empresa_cliente: Mapped[EmpresaCliente] = relationship()


class FaixaAudiencia(Base):
    __tablename__ = "faixas_audiencia"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    inicio: Mapped[int] = mapped_column(Integer)
    fim: Mapped[int] = mapped_column(Integer)
    valor: Mapped[float] = mapped_column(Float)


class Audiencia(Base):
    __tablename__ = "audiencias"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_cliente_id: Mapped[int] = mapped_column(ForeignKey("empresas_clientes.id"), index=True)
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
    empresa_cliente_id: Mapped[int] = mapped_column(ForeignKey("empresas_clientes.id"), index=True)
    data: Mapped[date] = mapped_column(Date, index=True)
    # Text, não VARCHAR (2026-10-13, auditoria M02) — mesmo motivo de
    # Laudo.tipo_laudo_nome/nome_cliente acima.
    tipo_cobranca: Mapped[str] = mapped_column(Text)
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


class SetorModulo(Base):
    """Módulos (abas) que um Setor pode acessar (2026-09-28, a pedido da
    Clara) — ausência de qualquer linha para um `setor_id` é o estado
    padrão/retrocompatível: significa "acesso total às abas válidas para a
    operadora do setor" (igual ao comportamento de antes desta feature),
    não "acesso a nada". Só passa a restringir quando o setor tem pelo
    menos uma linha aqui, gravada explicitamente na tela de Setores — ver
    app/auth.py::modulos_acessiveis."""

    __tablename__ = "setor_modulos"

    setor_id: Mapped[int] = mapped_column(ForeignKey("setores.id"), primary_key=True)
    modulo: Mapped[str] = mapped_column(String(20), primary_key=True)


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
    # index=True nos 3 (2026-10-08): essa tabela cresce mais rápido que
    # qualquer outra do sistema (toda ação registra uma linha aqui, inclusive
    # cada download de PDF/Excel) — sem índice, a tela de Auditoria
    # (web/routes_auditoria.py) filtrando/ordenando por qualquer um desses
    # campos viraria uma varredura completa da tabela toda conforme ela
    # cresce. Ver DECISIONS.md 2026-10-08.
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True, index=True)
    acao: Mapped[str] = mapped_column(String(60), index=True)
    entidade: Mapped[str | None] = mapped_column(String(40), nullable=True)
    # Text, não VARCHAR(40): Cartas passa nome de autor/réu/titular em texto
    # livre (não raro nomes empresariais compridos) como entidade_id — mesmo
    # motivo do Processo.advogada/assistente (StringDataRightTruncation em
    # produção, 2026-09-30, a Clara reportou a tela de erro ao gerar o PDF).
    entidade_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    detalhes: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    usuario: Mapped[Usuario | None] = relationship()


class Chamado(Base):
    """Chamados de suporte abertos pelo pop-up flutuante (ver templates/
    base.html). Guardados direto aqui (2026-10-01, a pedido da Clara) —
    depois de três tentativas sem sucesso de enviar por e-mail (SMTP
    bloqueado, depois Cloudflare bloqueando a Resend, depois o domínio não
    verificar na Resend mesmo em duas tentativas — ver DECISIONS.md),
    trocamos pra guardar o chamado no próprio sistema: nunca depende de
    provedor externo. A tela de Configuração > Chamados lista todos; o
    Discord (opcional, ver services/suporte.py) só avisa na hora — não é o
    registro em si."""

    __tablename__ = "chamados"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    assunto: Mapped[str] = mapped_column(Text)
    descricao: Mapped[str] = mapped_column(Text)
    resolvido: Mapped[bool] = mapped_column(default=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    resolvido_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    usuario: Mapped[Usuario] = relationship()


class Processo(Base):
    """Gestão de Processos (Fase 5, ELITE) — ver DATABASE.md seção 6.1."""

    __tablename__ = "processos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    numero_processo: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    empresa_cliente_id: Mapped[int] = mapped_column(ForeignKey("empresas_clientes.id"), index=True)
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
    # True quando `data` na verdade veio da coluna "DATA DE LIBERAÇÃO..."
    # (data em que a Dra inseriu o cliente na planilha — abas "coringa" como
    # fatais/Dra Galzo/DOCS E CUSTAS não têm data de andamento real), não de
    # uma data de andamento de verdade. `gerar_relatorio` exclui esses
    # eventos do filtro por período (a Clara confirmou: não deve contar como
    # se fosse o mês do andamento) — ver DECISIONS.md 2026-09-24 e
    # app/excel_reader.py::_TEXTO_DATA_DE_LIBERACAO.
    data_e_liberacao: Mapped[bool] = mapped_column(default=False)
    prazo_fatal: Mapped[bool] = mapped_column(default=False)
    data_prazo: Mapped[date | None] = mapped_column(Date, nullable=True)
    resolvido: Mapped[bool] = mapped_column(default=False)
    resolvido_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    observacao: Mapped[str | None] = mapped_column(Text, nullable=True)
    origem: Mapped[str] = mapped_column(String(20), default="IMPORT_PLANILHA")
    criado_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    processo: Mapped[Processo] = relationship(back_populates="eventos")


class SolicitacaoAudiencia(Base):
    """Fase 1 — Solicitação de Audiência (2026-10-16, a pedido da Clara): o
    mesmo dado hoje é digitado 3x (planilha de controle, aba Cartas, corpo
    dos 2 e-mails) — esta tabela guarda a solicitação em si, pra digitar
    uma vez só.

    `linha_planilha` (o número da linha na aba AGENDAMENTO da planilha de
    controle) tem `unique=True` de propósito: é o travamento otimista que
    impede duas solicitações simultâneas de ocuparem o mesmo horário — a
    linha só é escrita na planilha de verdade depois que o INSERT aqui
    (com a constraint UNIQUE) é confirmado pelo banco; se duas requisições
    concorrentes acharem a mesma "próxima vaga" ao mesmo tempo, só uma
    consegue inserir, a outra recebe erro de integridade e busca a vaga
    seguinte. Ver app/services/solicitacoes_audiencia.py.

    Clientes podem solicitar 2ª, 3ª... audiências (confirmado pela Clara —
    não é duplicidade): não há nenhuma constraint de unicidade por CPF ou
    número de contrato aqui."""

    __tablename__ = "solicitacoes_audiencia"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_cliente_id: Mapped[int] = mapped_column(ForeignKey("empresas_clientes.id"), index=True)
    nome_cliente: Mapped[str] = mapped_column(Text)
    cpf_cliente: Mapped[str] = mapped_column(String(20))
    email_cliente: Mapped[str] = mapped_column(Text)
    telefone_cliente: Mapped[str] = mapped_column(String(30))
    data_recebimento: Mapped[date] = mapped_column(Date)
    numero_contrato: Mapped[str] = mapped_column(Text)
    banco_id: Mapped[int] = mapped_column(ForeignKey("bancos.id"), index=True)
    link_audiencia: Mapped[str] = mapped_column(Text)
    linha_planilha: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    data_agendamento: Mapped[date] = mapped_column(Date)
    hora_agendamento: Mapped[str] = mapped_column(String(10))
    # RESERVADA (ganhou a linha no banco, ainda não escreveu na planilha) ->
    # GRAVADA (escreveu na planilha de controle com sucesso) ->
    # CARTAS_GERADAS -> EMAILS_ENVIADOS. FALHOU em qualquer etapa que não
    # dê pra concluir (ex.: a linha não estava mais vaga na planilha de
    # verdade no momento de escrever).
    status: Mapped[str] = mapped_column(String(20), default="RESERVADA")
    criado_por: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    empresa_cliente: Mapped[EmpresaCliente] = relationship()
    banco: Mapped[Banco] = relationship()
    usuario: Mapped[Usuario] = relationship()
