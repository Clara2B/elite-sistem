import hashlib
from pathlib import Path

from fastapi.templating import Jinja2Templates

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


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
