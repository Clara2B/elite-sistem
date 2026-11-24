from __future__ import annotations

from datetime import date
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api._shared import remover_temp, salvar_temp
from app.auth import PAPEIS_GLOBAIS
from app.db import get_db
from app.models import Usuario
from app.services import laudos as laudos_service
from app.services.auditoria import registrar
from app.services.empresas import listar_empresas
from app.web.auth import admin_logado_web, require_modulo_web
from app.web.menu import itens_menu
from app.web.templates import templates

router = APIRouter(prefix="/app/laudos")

_acesso_elite = require_modulo_web("LAUDOS")


@router.get("")
def tela(
    request: Request,
    empresa: str | None = None,
    ano: int | None = None,
    mes: int | None = None,
    status: str | None = None,
    mensagem: str | None = None,
    erro: str | None = None,
    usuario: Usuario = Depends(_acesso_elite),
    db: Session = Depends(get_db),
):
    # Período/status usados pra filtrar o menu de empresas (só quem tem
    # laudo aparece — a pedido da Clara, 2026-11-24) seguem o mesmo padrão
    # já pré-selecionado no template quando a tela abre sem filtro nenhum:
    # mês/ano de hoje e a primeira opção de status.
    periodo_ini_menu, periodo_fim_menu = laudos_service.periodo_20_a_20(
        ano or date.today().year, mes or date.today().month
    )
    status_menu = status or laudos_service.OPCOES_STATUS[0]
    ids_com_laudo = laudos_service.ids_empresas_com_laudo(db, periodo_ini_menu, periodo_fim_menu, status_menu)

    eh_admin = usuario.papel_global in PAPEIS_GLOBAIS
    contexto = {
        "usuario": usuario,
        "menu": itens_menu(db, usuario),
        "empresas": [e for e in listar_empresas(db, apenas_ativas=False) if e.id in ids_com_laudo],
        "opcoes_status": laudos_service.OPCOES_STATUS,
        "hoje": date.today(),
        "filtro": {"empresa": empresa, "ano": ano, "mes": mes, "status": status},
        "mensagem": mensagem,
        "resultado": None,
        "resumo": None,
        "resumo_texto": None,
        "erro": erro,
        "eh_admin": eh_admin,
        # Só calcula pra admin — mesma varredura da tabela inteira que
        # `detectar_duplicatas` faz não interessa pra quem não vê a seção.
        "duplicatas": laudos_service.detectar_duplicatas(db) if eh_admin else [],
    }
    # O resumo é sempre GERAL — cobre todas as empresas, ignorando o filtro
    # de "Empresa" do relatório detalhado (que continua servindo só pra
    # filtrar a tabela de laudo por laudo abaixo). Pedido explícito da
    # Clara (Bloco 4, 2026-09-25, ver DECISIONS.md): um único resumo
    # consolidado, nunca isolado por empresa/relatório.
    if ano and mes and status:
        periodo_ini, periodo_fim = laudos_service.periodo_20_a_20(ano, mes)
        try:
            resumo = laudos_service.gerar_resumo_por_assessoria(db, periodo_ini, periodo_fim, status)
        except ValueError as e:
            contexto["erro"] = str(e)
        else:
            contexto["resumo"] = resumo
            contexto["resumo_texto"] = laudos_service.formatar_texto_resumo_assessorias(resumo)

        if empresa and not contexto["erro"]:
            try:
                resultado = laudos_service.gerar_relatorio(db, empresa, periodo_ini, periodo_fim, status)
            except ValueError as e:
                contexto["erro"] = str(e)
            else:
                registrar(db, usuario, "GEROU_RELATORIO_LAUDOS", entidade="empresa_cliente", entidade_id=empresa)
                contexto["resultado"] = resultado
    return templates.TemplateResponse(request, "laudos.html", contexto)


@router.post("/import")
async def importar(
    request: Request,
    arquivo: UploadFile,
    usuario: Usuario = Depends(_acesso_elite),
    db: Session = Depends(get_db),
):
    path = salvar_temp(arquivo)
    # Lista cheia aqui (sem o filtro "só quem tem resultado" do período
    # atual) de propósito: a planilha recém-importada pode trazer laudo de
    # um período diferente de hoje, ou empresa nova — filtrar pelo período
    # de hoje faria a empresa que acabou de ser importada desaparecer do
    # menu bem na hora que a Clara mais precisa vê-la pra confirmar que o
    # import funcionou.
    eh_admin = usuario.papel_global in PAPEIS_GLOBAIS
    contexto = {
        "usuario": usuario,
        "menu": itens_menu(db, usuario),
        "empresas": listar_empresas(db, apenas_ativas=False),
        "opcoes_status": laudos_service.OPCOES_STATUS,
        "hoje": date.today(),
        "filtro": {},
        "resultado": None,
        "resumo": None,
        "resumo_texto": None,
        "mensagem": None,
        "erro": None,
        "eh_admin": eh_admin,
    }
    try:
        resumo = laudos_service.importar_planilha(db, path)
    except ValueError as e:
        contexto["erro"] = str(e)
    else:
        registrar(db, usuario, "IMPORTOU_LAUDOS", entidade="laudo", detalhes=str(resumo))
        contexto["mensagem"] = (
            f"{resumo.linhas_novas} linha(s) nova(s) importada(s), "
            f"{resumo.linhas_atualizadas} atualizada(s) "
            f"({resumo.linhas_ja_existentes} já existiam sem mudança)."
        )
    finally:
        remover_temp(path)
    contexto["duplicatas"] = laudos_service.detectar_duplicatas(db) if eh_admin else []
    return templates.TemplateResponse(request, "laudos.html", contexto)


@router.post("/{laudo_id}/excluir")
def excluir(
    laudo_id: int,
    usuario: Usuario = Depends(admin_logado_web),
    db: Session = Depends(get_db),
):
    """Exclui UM laudo específico — usado pra resolver uma duplicata
    apontada na seção "Possíveis duplicatas" da tela, depois da Clara
    decidir qual dos dois manter (ver laudos_service.detectar_duplicatas).
    Só Admin Superior/T.I."""
    excluido = laudos_service.excluir_laudo(db, laudo_id)
    if excluido:
        registrar(db, usuario, "EXCLUIU_LAUDO", entidade="laudo", entidade_id=str(laudo_id))
        mensagem = quote("Laudo excluído.")
    else:
        mensagem = quote("Esse laudo já não existe mais (pode já ter sido excluído).")
    return RedirectResponse(f"/app/laudos?mensagem={mensagem}", status_code=303)


@router.post("/apagar-tudo")
def apagar_tudo(
    usuario: Usuario = Depends(admin_logado_web),
    db: Session = Depends(get_db),
):
    """Apaga todo o histórico de laudos — a pedido explícito da Clara
    (2026-09-24), pra corrigir de vez os laudos com data errada gravados
    antes do bug da coluna de data ser corrigido (ver DECISIONS.md). Só
    Admin Superior/T.I.; a confirmação (obrigatória, com o nome digitado)
    acontece no navegador antes desse POST — ver laudos.html/static/app.js."""
    total = laudos_service.apagar_todos_laudos(db)
    registrar(db, usuario, "APAGOU_TODOS_LAUDOS", entidade="laudo", detalhes=f"{total} laudo(s) apagado(s)")
    mensagem = quote(f"{total} laudo(s) apagado(s). Pode importar a planilha do zero agora.")
    return RedirectResponse(f"/app/laudos?mensagem={mensagem}", status_code=303)
