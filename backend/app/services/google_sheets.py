"""Acesso à planilha de controle (Google Sheets) via conta de serviço do
Google (Fase 1 — Solicitação de Audiência, 2026-10-16, a pedido da Clara).
Primeira integração do sistema com uma API do Google — não existia nada
antes disso (ver DECISIONS.md).

Lê `settings.google_service_account_json` (conteúdo do .json da conta de
serviço, não um caminho de arquivo) pra autenticar. A conta de serviço
precisa ter permissão de Editor na planilha configurada em
`settings.google_sheets_id`."""
from __future__ import annotations

import json

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from app.config import settings
from app.utils import cell_text

_ESCOPOS = ["https://www.googleapis.com/auth/spreadsheets"]


def _credenciais() -> Credentials:
    if not settings.google_service_account_json:
        raise ValueError(
            "GOOGLE_SERVICE_ACCOUNT_JSON não está configurado — sem credencial, "
            "o sistema não consegue acessar a planilha de controle."
        )
    info = json.loads(settings.google_service_account_json)
    return Credentials.from_service_account_info(info, scopes=_ESCOPOS)


def _servico():
    return build("sheets", "v4", credentials=_credenciais(), cache_discovery=False)


def ler_aba(spreadsheet_id: str, aba: str) -> list[dict[str, str]]:
    """Lê uma aba inteira e devolve como lista de dicts (chave = cabeçalho
    da primeira linha, já sem espaços nas pontas; valor = texto da célula,
    "" se vazia). Ignora linhas totalmente vazias. Linhas mais curtas que o
    cabeçalho têm as colunas faltantes como ""."""
    servico = _servico()
    resposta = (
        servico.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=f"'{aba}'")
        .execute()
    )
    valores = resposta.get("values", [])
    if not valores:
        return []

    cabecalho = [cell_text(c).strip() for c in valores[0]]
    linhas = []
    for linha_bruta in valores[1:]:
        if not any(cell_text(v).strip() for v in linha_bruta):
            continue
        linha = {
            cabecalho[i]: cell_text(linha_bruta[i]) if i < len(linha_bruta) else ""
            for i in range(len(cabecalho))
        }
        linhas.append(linha)
    return linhas
