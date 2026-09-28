"""Monta os itens de navegação visíveis para o usuário logado, reaproveitando
as mesmas regras de acesso por operadora já usadas pela API (app/auth.py)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.auth import PAPEIS_GLOBAIS, operadoras_acessiveis
from app.models import Usuario


def itens_menu(db: Session, usuario: Usuario) -> list[dict]:
    acessiveis = operadoras_acessiveis(db, usuario)
    itens = []
    if "ELITE" in acessiveis:
        itens.append({"url": "/app/laudos", "rotulo": "Laudos", "icone": "laudos", "descricao": "Importar planilha e gerar relatório por empresa-cliente."})
        itens.append({"url": "/app/processos", "rotulo": "Gestão de Processos", "icone": "processos", "descricao": "Andamentos, prazos fatais e relatórios da equipe."})
    if "EXIMIA" in acessiveis:
        itens.append({"url": "/app/audiencias", "rotulo": "Audiências", "icone": "audiencias", "descricao": "Importar planilha e gerar relatório quinzenal."})
        itens.append({"url": "/app/cartas", "rotulo": "Cartas", "icone": "cartas", "descricao": "Cartas-convite em PDF para clientes e bancos."})
    if acessiveis:
        itens.append({"url": "/app/pendencias", "rotulo": "Pendências", "icone": "pendencias", "descricao": "Cobranças em aberto por empresa-cliente."})
    if usuario.papel_global in PAPEIS_GLOBAIS:
        # Área administrativa separada (2026-09-28, a pedido da Clara) — um item só no
        # menu, mas continua "ativo" (destacado) em qualquer uma das telas por baixo
        # dela, que mantiveram suas rotas próprias (`/app/usuarios` etc.) sem mudança.
        itens.append({
            "url": "/app/configuracao", "rotulo": "Configuração", "icone": "configuracao",
            "descricao": "Usuários, empresas-clientes, assistentes e setores.",
            "tambem_ativo_em": ["/app/usuarios", "/app/empresas", "/app/funcionarios", "/app/setores"],
        })
    return itens
