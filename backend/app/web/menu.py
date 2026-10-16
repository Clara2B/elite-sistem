"""Monta os itens de navegação visíveis para o usuário logado, reaproveitando
as mesmas regras de acesso por operadora já usadas pela API (app/auth.py)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.auth import PAPEIS_GLOBAIS, modulos_acessiveis
from app.models import Usuario


def itens_menu(db: Session, usuario: Usuario) -> list[dict]:
    acessiveis = modulos_acessiveis(db, usuario)
    itens = []
    if "LAUDOS" in acessiveis:
        itens.append({"url": "/app/laudos", "rotulo": "Laudos", "icone": "laudos", "descricao": "Importar planilha e gerar relatório por empresa-cliente."})
    if "PROCESSOS" in acessiveis:
        itens.append({"url": "/app/processos", "rotulo": "Gestão de Processos", "icone": "processos", "descricao": "Andamentos, prazos fatais e relatórios da equipe."})
    if "AUDIENCIAS" in acessiveis:
        itens.append({"url": "/app/audiencias", "rotulo": "Audiências", "icone": "audiencias", "descricao": "Importar planilha e gerar relatório quinzenal."})
        # Mesmo acesso de Audiências (2026-10-16, Fase 1 — Solicitação de
        # Audiência, a pedido da Clara: "reaproveita o acesso").
        itens.append({
            "url": "/app/solicitacoes-audiencia", "rotulo": "Nova Solicitação", "icone": "solicitacao",
            "descricao": "Encontra o próximo horário vago e grava na planilha de controle.",
        })
    if "CARTAS" in acessiveis:
        itens.append({"url": "/app/cartas", "rotulo": "Cartas", "icone": "cartas", "descricao": "Cartas-convite em PDF para clientes e bancos."})
    if "AUDIENCIAS" in acessiveis:
        # Mesmo acesso de Audiências (2026-10-16, Fase 1 — Solicitação de
        # Audiência, a pedido da Clara: "reaproveita o acesso").
        itens.append({"url": "/app/bancos", "rotulo": "Bancos", "icone": "bancos", "descricao": "Cadastro de bancos para a Carta Convite Banco."})
    if "PENDENCIAS" in acessiveis:
        itens.append({"url": "/app/pendencias", "rotulo": "Pendências", "icone": "pendencias", "descricao": "Cobranças em aberto por empresa-cliente."})
    if "CORRESPONDENCIAS" in acessiveis:
        itens.append({"url": "/app/correspondencias", "rotulo": "Correspondências", "icone": "correspondencias", "descricao": "Importar planilha e gerar relatório por mês e empresa."})
    if usuario.papel_global in PAPEIS_GLOBAIS:
        # Relatórios das Assessorias e Chamados saíram de dentro de
        # Configuração (2026-10-14, a pedido da Clara) — ganham item
        # próprio no menu, em vez de ficar escondidos dentro de outra área.
        itens.append({
            "url": "/app/relatorios-assessorias", "rotulo": "Relatórios das Assessorias", "icone": "relatorios",
            "descricao": "Gerador de relatórios mensais por assessoria (EWS, WNR...).",
        })
        itens.append({
            "url": "/app/chamados", "rotulo": "Chamados", "icone": "suporte",
            "descricao": "Chamados de suporte abertos pelo pop-up, em qualquer tela.",
        })
        # Área administrativa separada (2026-09-28, a pedido da Clara) — um item só no
        # menu, mas continua "ativo" (destacado) em qualquer uma das telas por baixo
        # dela, que mantiveram suas rotas próprias (`/app/usuarios` etc.) sem mudança.
        itens.append({
            "url": "/app/configuracao", "rotulo": "Configuração", "icone": "configuracao",
            "descricao": "Usuários, empresas-clientes, assistentes e setores.",
            "tambem_ativo_em": [
                "/app/usuarios", "/app/empresas", "/app/funcionarios", "/app/setores", "/app/auditoria",
            ],
        })
    return itens
