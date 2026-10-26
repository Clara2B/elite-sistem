import os
import tempfile


def salvar_temp(upload) -> str:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        tmp.write(upload.file.read())
        return tmp.name


def remover_temp(caminho: str) -> None:
    """Remove o arquivo temporário criado por `salvar_temp` (2026-10-13,
    auditoria M03) — sem isso, cada planilha enviada (com nome de cliente,
    CPF, número de processo) fica pra sempre num diretório temporário do
    servidor, fora do controle de acesso do banco. Chamar sempre depois de
    processar o upload, com sucesso ou erro (ex.: num `finally`)."""
    os.remove(caminho)
