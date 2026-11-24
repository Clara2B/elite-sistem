import io
import os
import zipfile

import pytest

from app.api._shared import TAMANHO_MAXIMO_UPLOAD_BYTES, remover_temp, salvar_temp


def _bytes_zip_valido() -> bytes:
    """Bytes de um ZIP válido mínimo — o suficiente pra passar a checagem
    de `zipfile.is_zipfile` (não precisa ser um .xlsx de verdade por
    dentro; o parsing do conteúdo em si é responsabilidade do openpyxl,
    testado em outro lugar)."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("conteudo.txt", "qualquer coisa")
    return buffer.getvalue()


class _FalsoUpload:
    """Dublê mínimo de `fastapi.UploadFile` — só o que `salvar_temp` usa
    (`filename`, `size`, `file.read()`), sem precisar montar um upload de
    verdade via TestClient pra testar a validação isolada."""

    def __init__(self, filename: str, conteudo: bytes, size: int | None = None):
        self.filename = filename
        self.size = size if size is not None else len(conteudo)
        self.file = io.BytesIO(conteudo)


def test_salvar_temp_aceita_xlsx_dentro_do_limite():
    conteudo = _bytes_zip_valido()
    path = salvar_temp(_FalsoUpload("planilha.xlsx", conteudo))
    try:
        assert os.path.exists(path)
        with open(path, "rb") as f:
            assert f.read() == conteudo
    finally:
        remover_temp(path)


@pytest.mark.parametrize("nome", ["planilha.pdf", "planilha.xls", "planilha", "foto.jpg.xlsx.exe"])
def test_salvar_temp_rejeita_arquivo_que_nao_e_xlsx(nome):
    """Bug real identificado na varredura (2026-11-24): antes, qualquer
    arquivo ia direto pro openpyxl/pandas, que estourava com um erro
    técnico em vez de uma mensagem clara."""
    with pytest.raises(ValueError, match="não é uma planilha .xlsx"):
        salvar_temp(_FalsoUpload(nome, b"qualquer coisa"))


def test_salvar_temp_rejeita_arquivo_maior_que_o_limite():
    with pytest.raises(ValueError, match="limite"):
        salvar_temp(_FalsoUpload("planilha.xlsx", b"x", size=TAMANHO_MAXIMO_UPLOAD_BYTES + 1))


def test_salvar_temp_aceita_arquivo_exatamente_no_limite():
    path = salvar_temp(_FalsoUpload("planilha.xlsx", _bytes_zip_valido(), size=TAMANHO_MAXIMO_UPLOAD_BYTES))
    remover_temp(path)


def test_salvar_temp_rejeita_arquivo_renomeado_pra_xlsx_sem_ser_de_verdade():
    """Bug real encontrado testando esta mudança num navegador de verdade:
    um arquivo com extensão .xlsx mas conteúdo que não é um ZIP (PDF
    renomeado, download corrompido) passava pela checagem de nome e
    estourava sem tratamento (`zipfile.BadZipFile`) só depois, dentro do
    openpyxl — 500 em vez de uma mensagem clara."""
    with pytest.raises(ValueError, match="não é uma planilha .xlsx válida"):
        salvar_temp(_FalsoUpload("planilha.xlsx", b"nao sou um zip de verdade"))
