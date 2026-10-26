import hashlib
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi.templating import Jinja2Templates

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

_FUSO_BRASIL = ZoneInfo("America/Sao_Paulo")


def _horario_brasil(valor: datetime | None, formato: str = "%d/%m/%Y %H:%M") -> str:
    """Filtro `|horario_brasil` — todo `criado_em`/`enviado_em` etc. é
    gravado em UTC (`datetime.utcnow()`, ver app/models.py), mas a equipe
    inteira está no fuso de Brasília; exibir o valor cru fazia a tela
    mostrar um horário 2h ou 3h à frente do real (reportado pela Clara em
    2026-10-19, na tela de Auditoria). Este filtro só converte pra exibição
    — nada gravado no banco muda."""
    if valor is None:
        return ""
    com_fuso = valor.replace(tzinfo=timezone.utc) if valor.tzinfo is None else valor
    return com_fuso.astimezone(_FUSO_BRASIL).strftime(formato)


templates.env.filters["horario_brasil"] = _horario_brasil


def _versao_estatico() -> str:
    """Hash do conteúdo de style.css/app.js, usado como ?v= nos links pra
    esses arquivos (ver base.html/login.html). Sem isso, o navegador (ou um
    proxy no caminho) pode continuar servindo uma versão em cache do CSS/JS
    depois de um deploy — já aconteceu (modal de exclusão apareceu sem
    nenhum estilo pra Clara logo depois do deploy que o estilizou). Como o
    hash muda sempre que o conteúdo muda, a URL muda junto e o cache antigo
    nunca é reaproveitado por engano."""
    conteudo = b""
    for nome in ("style.css", "app.js"):
        caminho = STATIC_DIR / nome
        if caminho.exists():
            conteudo += caminho.read_bytes()
    return hashlib.sha256(conteudo).hexdigest()[:10]


templates.env.globals["versao_estatico"] = _versao_estatico()
