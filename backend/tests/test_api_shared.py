import io
import os

import pytest

from app.api._shared import TAMANHO_MAXIMO_UPLOAD_BYTES, remover_temp, salvar_temp


class _FalsoUpload:
    """Dublê mínimo de `fastapi.UploadFile` — só o que `salvar_temp` usa
    (`filename`, `size`, `file.read()`), sem precisar montar um upload de
    verdade via TestClient pra testar a validação isolada."""

    def __init__(self, filename: str, conteudo: bytes, size: int | None = None):
        self.filename = filename
        self.size = size if size is not None else len(conteudo)
        self.file = io.BytesIO(conteudo)


def test_salvar_temp_aceita_xlsx_dentro_do_limite():
    path = salvar_temp(_FalsoUpload("planilha.xlsx", b"conteudo qualquer"))
    try:
        assert os.path.exists(path)
        with open(path, "rb") as f:
            assert f.read() == b"conteudo qualquer"
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
    path = salvar_temp(_FalsoUpload("planilha.xlsx", b"x", size=TAMANHO_MAXIMO_UPLOAD_BYTES))
    remover_temp(path)
