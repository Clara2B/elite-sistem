import tempfile


def salvar_temp(upload) -> str:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        tmp.write(upload.file.read())
        return tmp.name
