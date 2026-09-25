import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.audiencias import router as audiencias_router
from app.api.auth import router as auth_router
from app.api.cartas import router as cartas_router
from app.api.empresas import router as empresas_router
from app.api.funcionarios import router as funcionarios_router
from app.api.health import router as health_router
from app.api.laudos import router as laudos_router
from app.api.pendencias import router as pendencias_router
from app.api.processos import router as processos_router
from app.api.usuarios import router as usuarios_router
from app.config import settings
from app.db import init_db
from app.web.auth import PrecisaLogin, SemPermissao
from app.web.routes_audiencias import router as web_audiencias_router
from app.web.routes_auth import router as web_auth_router
from app.web.routes_cartas import router as web_cartas_router
from app.web.routes_dashboard import router as web_dashboard_router
from app.web.routes_empresas import router as web_empresas_router
from app.web.routes_funcionarios import router as web_funcionarios_router
from app.web.routes_laudos import router as web_laudos_router
from app.web.routes_pendencias import router as web_pendencias_router
from app.web.routes_processos import router as web_processos_router
from app.web.routes_usuarios import router as web_usuarios_router
from app.web.templates import templates


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Sem DATABASE_URL configurado, o app ainda sobe (útil para dev local
    # sem banco e para o healthcheck) — só as rotas de negócio exigem banco.
    if settings.database_url:
        init_db()
    yield


app = FastAPI(title="Elite Sistem API", lifespan=lifespan)

STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Sem isso, uma mensagem de nível INFO sem handler configurado não aparece
# em lugar nenhum (o "last resort" padrão do Python só mostra WARNING+) —
# ou seja, os logs de tempo de requisição abaixo ficariam mudos nos logs do
# Render sem essa linha.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
_logger_requisicoes = logging.getLogger("elite_sistem.requisicoes")


@app.middleware("http")
async def _medir_tempo_de_requisicao(request: Request, call_next):
    """Só para diagnóstico ("sistema todo devagar", relatado pela Clara sem
    detalhes suficientes pra reproduzir) — sem isso, a próxima vez que algo
    estiver lento só dá pra adivinhar onde. Fica nos logs do Render
    (stdout), sem persistir em banco nem expor nada pra fora."""
    inicio = time.perf_counter()
    resposta = await call_next(request)
    duracao_ms = (time.perf_counter() - inicio) * 1000
    _logger_requisicoes.info(
        "%s %s -> %s em %.0fms", request.method, request.url.path, resposta.status_code, duracao_ms
    )
    return resposta


@app.exception_handler(PrecisaLogin)
async def _precisa_login(request: Request, exc: PrecisaLogin):
    return RedirectResponse("/login", status_code=303)


@app.exception_handler(SemPermissao)
async def _sem_permissao(request: Request, exc: SemPermissao):
    return templates.TemplateResponse(
        request, "erro.html",
        {"titulo": "Acesso restrito", "mensagem": "Você não tem permissão para acessar esta página."},
        status_code=403,
    )


def _e_rota_html(path: str) -> bool:
    return path == "/" or path.startswith(("/app", "/login", "/logout"))


_logger_erros = logging.getLogger("elite_sistem.erros")


@app.exception_handler(Exception)
async def _erro_nao_tratado(request: Request, exc: Exception):
    """Sem isso, qualquer erro inesperado (ex.: o `StringDataRightTruncation`
    que já pegou `processos` uma vez — ver DECISIONS.md) derruba a página
    inteira numa "Internal Server Error" em branco, sem estilo nenhum e sem
    dizer nada pra Clara — a mesma queixa dela sobre avisos feios de sistema
    velho, só que pior (nem um aviso é). Loga o traceback completo (aparece
    nos logs do Render, com o middleware de tempo de requisição já em uso
    pra diagnóstico) e devolve uma página de erro estilizada pras rotas de
    tela; pras rotas de API/JSON, devolve um JSON genérico em vez de uma
    página HTML, que quebraria qualquer cliente esperando JSON."""
    _logger_erros.error("Erro não tratado em %s %s", request.method, request.url.path, exc_info=exc)
    if _e_rota_html(request.url.path):
        return templates.TemplateResponse(
            request, "erro.html",
            {
                "titulo": "Algo deu errado",
                "mensagem": "Não conseguimos concluir essa ação. Tente de novo — se continuar "
                "acontecendo, chame o suporte técnico.",
            },
            status_code=500,
        )
    return JSONResponse({"detail": "Internal Server Error"}, status_code=500)


app.include_router(health_router)
app.include_router(auth_router)
app.include_router(usuarios_router)
app.include_router(laudos_router)
app.include_router(audiencias_router)
app.include_router(pendencias_router)
app.include_router(processos_router)
app.include_router(empresas_router)
app.include_router(funcionarios_router)
app.include_router(cartas_router)

# Páginas HTML (Fase 6) — autenticação por cookie, ver app/web/auth.py.
app.include_router(web_auth_router)
app.include_router(web_dashboard_router)
app.include_router(web_laudos_router)
app.include_router(web_audiencias_router)
app.include_router(web_pendencias_router)
app.include_router(web_processos_router)
app.include_router(web_usuarios_router)
app.include_router(web_empresas_router)
app.include_router(web_funcionarios_router)
app.include_router(web_cartas_router)
