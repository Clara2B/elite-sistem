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
        itens.append({"url": "/app/laudos", "rotulo": "Laudos", "descricao": "Importar planilha e gerar relatório por empresa-cliente."})
        itens.append({"url": "/app/processos", "rotulo": "Gestão de Processos", "descricao": "Andamentos, prazos fatais e relatórios da equipe."})
    if "EXIMIA" in acessiveis:
        itens.append({"url": "/app/audiencias", "rotulo": "Audiências", "descricao": "Importar planilha e gerar relatório quinzenal."})
    if acessiveis:
        itens.append({"url": "/app/pendencias", "rotulo": "Pendências", "descricao": "Cobranças em aberto por empresa-cliente."})
    if usuario.papel_global in PAPEIS_GLOBAIS:
        itens.append({"url": "/app/usuarios", "rotulo": "Usuários", "descricao": "Cadastrar e gerenciar acessos da equipe."})
    return itens
