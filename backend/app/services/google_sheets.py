"""Acesso à planilha de controle (Google Sheets) via conta de serviço do
Google (Fase 1 — Solicitação de Audiência, 2026-10-16, a pedido da Clara).
Primeira integração do sistema com uma API do Google — não existia nada
antes disso (ver DECISIONS.md).

Lê `settings.google_service_account_json` (conteúdo do .json da conta de
serviço, não um caminho de arquivo) pra autenticar. A conta de serviço
precisa ter permissão de Editor na planilha configurada em
`settings.google_sheets_id`.

Todo valor lido já passa por `cell_text` (nunca None) e por
`eh_valor_real` descartada quando é a fórmula de sugestão de IA do Google
Sheets não resolvida (ex.: a coluna "2° OPÇÃO CNPJ" da planilha real de
bancos vem assim em quase toda linha) — isso não é feito aqui pra manter
`ler_aba`/`ler_linha` fiéis ao conteúdo bruto da célula; quem usa decide
via `valor_coluna`."""
from __future__ import annotations

import json

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from app.config import settings
from app.utils import cell_text, normalize

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


def eh_valor_real(texto: str) -> bool:
    """False pra fórmula do Google Sheets não resolvida (ex.: a "sugestão
    de IA" da célula, tipo `=AI("Preencha com...")`) — não é dado de
    verdade digitado por alguém."""
    return bool(texto) and not texto.startswith("=")


def valor_coluna(linha: dict[str, str], nome_coluna: str) -> str:
    """Busca o valor de `linha` (dict devolvido por `ler_aba`/`ler_linha`)
    pelo nome da coluna, tolerante a espaço extra/acento/caixa no
    cabeçalho de verdade (ex.: "BANCOS " com espaço, na planilha real) —
    "" se a coluna não existir ou o valor não for real (ver
    `eh_valor_real`)."""
    alvo = normalize(nome_coluna)
    for chave, valor in linha.items():
        if normalize(chave) == alvo:
            return valor if eh_valor_real(valor) else ""
    return ""


def _linhas_a_partir_do_cabecalho(valores: list[list]) -> tuple[list[str], list[tuple[int, dict[str, str]]]]:
    if not valores:
        return [], []
    cabecalho = [cell_text(c).strip() for c in valores[0]]
    linhas = []
    for indice, linha_bruta in enumerate(valores[1:], start=2):  # linha 1 é o cabeçalho
        if not any(cell_text(v).strip() for v in linha_bruta):
            continue
        linha = {
            cabecalho[i]: cell_text(linha_bruta[i]) if i < len(linha_bruta) else ""
            for i in range(len(cabecalho))
        }
        linhas.append((indice, linha))
    return cabecalho, linhas


def ler_aba_com_numero_linha(spreadsheet_id: str, aba: str) -> list[tuple[int, dict[str, str]]]:
    """Mesmo que `ler_aba`, mas cada linha vem acompanhada do seu número
    real na planilha (1 = cabeçalho, então a primeira linha de dado é 2) —
    necessário pra escrever de volta na linha certa (ver
    `escrever_valores`)."""
    servico = _servico()
    resposta = servico.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range=f"'{aba}'").execute()
    _, linhas = _linhas_a_partir_do_cabecalho(resposta.get("values", []))
    return linhas


def ler_aba(spreadsheet_id: str, aba: str) -> list[dict[str, str]]:
    """Lê uma aba inteira e devolve como lista de dicts (chave = cabeçalho
    da primeira linha, já sem espaços nas pontas; valor = texto da célula,
    "" se vazia). Ignora linhas totalmente vazias. Linhas mais curtas que o
    cabeçalho têm as colunas faltantes como ""."""
    return [linha for _, linha in ler_aba_com_numero_linha(spreadsheet_id, aba)]


def _ler_cabecalho(spreadsheet_id: str, aba: str) -> list[str]:
    servico = _servico()
    resposta = servico.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range=f"'{aba}'!1:1").execute()
    valores = resposta.get("values", [])
    return [cell_text(c).strip() for c in valores[0]] if valores else []


def _letra_coluna(indice_zero_based: int) -> str:
    letra = ""
    indice = indice_zero_based + 1
    while indice > 0:
        indice, resto = divmod(indice - 1, 26)
        letra = chr(65 + resto) + letra
    return letra


def ler_linha(spreadsheet_id: str, aba: str, numero_linha: int) -> dict[str, str]:
    """Lê só UMA linha (pelo número real na planilha) — usada pra
    reconfirmar que uma vaga ainda está vaga no momento exato de gravar,
    sem reler a aba inteira de novo."""
    cabecalho = _ler_cabecalho(spreadsheet_id, aba)
    if not cabecalho:
        return {}
    servico = _servico()
    resposta = (
        servico.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=f"'{aba}'!{numero_linha}:{numero_linha}")
        .execute()
    )
    valores = resposta.get("values", [])
    linha_bruta = valores[0] if valores else []
    return {
        cabecalho[i]: cell_text(linha_bruta[i]) if i < len(linha_bruta) else ""
        for i in range(len(cabecalho))
    }


def escrever_valores(spreadsheet_id: str, aba: str, numero_linha: int, valores_por_coluna: dict[str, str]) -> None:
    """Escreve valores em colunas específicas de UMA linha, resolvidas pelo
    nome real da coluna no cabeçalho — nunca toca em nenhuma outra coluna
    da mesma linha (ex.: CONCILIADORA/ADVOGADA já pré-atribuídas), nem em
    nenhuma outra linha, nem na estrutura da planilha (restrição explícita
    da Clara). `numero_linha` é o número real da linha (1 = cabeçalho)."""
    if not valores_por_coluna:
        return
    cabecalho = _ler_cabecalho(spreadsheet_id, aba)
    indices_normalizados = {normalize(nome): i for i, nome in enumerate(cabecalho)}

    dados = []
    for nome_coluna, valor in valores_por_coluna.items():
        indice = indices_normalizados.get(normalize(nome_coluna))
        if indice is None:
            raise ValueError(f"Coluna '{nome_coluna}' não encontrada na aba '{aba}'.")
        letra = _letra_coluna(indice)
        dados.append({"range": f"'{aba}'!{letra}{numero_linha}", "values": [[valor]]})

    servico = _servico()
    servico.spreadsheets().values().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"valueInputOption": "RAW", "data": dados},
    ).execute()
