"""Aviso de validação (Fase 4+): algo que o sistema não conseguiu
processar com segurança, mas que não impede gerar a seção — fica
marcado na tela de revisão com a origem (planilha, aba, linha), pra
quem revisa saber onde corrigir (especificação, "Normalização e
validação dos dados": "nada é corrigido em silêncio: o que o sistema
consegue converter, converte; o resto vira aviso")."""
from __future__ import annotations

from dataclasses import dataclass

from app.relatorio_assessorias.leitores.base import Origem


@dataclass(frozen=True)
class Aviso:
    origem: Origem | None
    mensagem: str
