import io
import os
import tempfile
import zipfile

# 20 MB — generoso pra qualquer planilha real já vista em produção (a maior,
# "Gestão de Processos", gira em torno de poucos MB), mas protege o processo
# do plano gratuito do Render (memória limitada) de um arquivo enorme enviado
# por engano (ex.: a pessoa errada o campo de upload).
TAMANHO_MAXIMO_UPLOAD_BYTES = 20 * 1024 * 1024


def salvar_temp(upload) -> str:
    """Salva o arquivo enviado num arquivo temporário .xlsx — valida ANTES
    de gravar ou processar qualquer coisa (achado na varredura completa,
    2026-11-24): sem isso, um arquivo que não é .xlsx de verdade (PDF, foto,
    arquivo errado) ou grande demais ia direto pro openpyxl/pandas, que
    estourava com um erro técnico sem tratamento — tela genérica "Algo deu
    errado" em vez de uma mensagem clara dizendo o que fazer. `ValueError`
    aqui é capturado pelo mesmo `try/except` que cada tela de import já usa
    pros erros de `importar_planilha`.

    Um .xlsx de verdade é um arquivo ZIP por dentro — `zipfile.is_zipfile`
    pega tanto um arquivo com extensão trocada só no nome (ex.: um PDF
    renomeado "planilha.xlsx") quanto um .xlsx genuinamente corrompido
    (ex.: download incompleto), casos que passariam pela checagem de nome
    acima e só estourariam depois, dentro do openpyxl (`zipfile.BadZipFile`,
    sem tratamento)."""
    nome = upload.filename or ""
    if not nome.lower().endswith(".xlsx"):
        raise ValueError(
            f'O arquivo "{nome}" não é uma planilha .xlsx. Verifique se escolheu o arquivo certo e tente de novo.'
        )
    if upload.size is not None and upload.size > TAMANHO_MAXIMO_UPLOAD_BYTES:
        tamanho_mb = upload.size / (1024 * 1024)
        limite_mb = TAMANHO_MAXIMO_UPLOAD_BYTES // (1024 * 1024)
        raise ValueError(
            f"O arquivo tem {tamanho_mb:.1f} MB — o limite é {limite_mb} MB. Envie um arquivo menor."
        )
    conteudo = upload.file.read()
    if not zipfile.is_zipfile(io.BytesIO(conteudo)):
        raise ValueError(
            f'O arquivo "{nome}" não é uma planilha .xlsx válida — parece corrompido ou não é '
            "realmente um arquivo Excel. Verifique o arquivo e tente de novo."
        )
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        tmp.write(conteudo)
        return tmp.name


def remover_temp(caminho: str) -> None:
    """Remove o arquivo temporário criado por `salvar_temp` (2026-10-13,
    auditoria M03) — sem isso, cada planilha enviada (com nome de cliente,
    CPF, número de processo) fica pra sempre num diretório temporário do
    servidor, fora do controle de acesso do banco. Chamar sempre depois de
    processar o upload, com sucesso ou erro (ex.: num `finally`)."""
    os.remove(caminho)
