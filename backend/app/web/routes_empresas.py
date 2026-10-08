from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import EmpresaCliente, Usuario
from app.services.auditoria import registrar
from app.services.empresas import (
    alterar_ativo_empresa,
    atualizar_empresa,
    contar_vinculos_todas_empresas,
    criar_empresa,
    excluir_empresa,
    excluir_empresas_em_massa,
    excluir_empresas_inativas,
    listar_empresas,
    realocar_empresas_em_massa,
    sincronizar_lista_oficial,
)
from app.web.areas_configuracao import AREAS_CONFIGURACAO
from app.web.auth import admin_logado_web
from app.web.menu import itens_menu
from app.web.templates import templates

router = APIRouter(prefix="/app/empresas")


def _contexto_base(db: Session, usuario: Usuario) -> dict:
    empresas = listar_empresas(db, apenas_ativas=False)
    return {
        "usuario": usuario,
        "menu": itens_menu(db, usuario),
        "areas_configuracao": AREAS_CONFIGURACAO,
        "empresas": empresas,
        "vinculos_por_empresa": contar_vinculos_todas_empresas(db),
        "mensagem": None,
        "erro": None,
    }


@router.get("")
def tela(
    request: Request,
    erro: str | None = None,
    mensagem: str | None = None,
    usuario: Usuario = Depends(admin_logado_web),
    db: Session = Depends(get_db),
):
    contexto = _contexto_base(db, usuario)
    # erro/mensagem por query string: só usado depois de um redirect (ex.:
    # excluir, que precisa de POST + redirect, então não pode simplesmente
    # devolver a página com o erro no corpo da mesma resposta como os
    # outros formulários desta tela fazem).
    contexto["erro"] = erro
    contexto["mensagem"] = mensagem
    return templates.TemplateResponse(request, "empresas.html", contexto)


@router.post("")
async def criar(
    request: Request,
    usuario: Usuario = Depends(admin_logado_web),
    db: Session = Depends(get_db),
):
    form = await request.form()
    contexto = _contexto_base(db, usuario)
    nome = str(form.get("nome", "")).strip()
    cnpj = str(form.get("cnpj", "")).strip() or None
    if not nome:
        contexto["erro"] = "Nome é obrigatório."
        return templates.TemplateResponse(request, "empresas.html", contexto, status_code=400)
    try:
        empresa = criar_empresa(db, nome, cnpj)
    except ValueError as e:
        contexto["erro"] = str(e)
        return templates.TemplateResponse(request, "empresas.html", contexto, status_code=400)
    registrar(db, usuario, "CRIOU_EMPRESA", entidade="empresa_cliente", entidade_id=empresa.id)
    contexto = _contexto_base(db, usuario)
    contexto["mensagem"] = f"Empresa {empresa.nome} cadastrada."
    return templates.TemplateResponse(request, "empresas.html", contexto)


@router.post("/sincronizar-lista-oficial")
def sincronizar(
    usuario: Usuario = Depends(admin_logado_web),
    db: Session = Depends(get_db),
):
    """Sincroniza com a lista oficial de 48 empresas (nome + CNPJ) que a
    Clara mandou em PDF (2026-09-24) — a confirmação (obrigatória, com o
    nome digitado) acontece no navegador antes desse POST (ver empresas.html
    e static/app.js). Irreversível para quem for excluído. Precisa ficar
    ANTES de `POST /{empresa_id}` abaixo — senão o Starlette casa essa rota
    com `empresa_id="sincronizar-lista-oficial"` primeiro e devolve 422."""
    resumo = sincronizar_lista_oficial(db)
    registrar(
        db, usuario, "SINCRONIZOU_EMPRESAS_OFICIAIS", entidade="empresa_cliente",
        detalhes=(
            f"{len(resumo.criadas)} criada(s), {len(resumo.atualizadas_cnpj)} CNPJ atualizado(s), "
            f"{len(resumo.excluidas)} excluída(s), {len(resumo.nao_excluidas_por_vinculo)} não excluída(s) por vínculo"
        ),
    )
    mensagem = (
        f"{len(resumo.criadas)} criada(s), {len(resumo.atualizadas_cnpj)} com CNPJ atualizado, "
        f"{len(resumo.excluidas)} excluída(s)."
    )
    if resumo.nao_excluidas_por_vinculo:
        mensagem += (
            f" {len(resumo.nao_excluidas_por_vinculo)} não puderam ser excluídas por terem histórico "
            f"vinculado: {', '.join(resumo.nao_excluidas_por_vinculo)}."
        )
    return RedirectResponse(f"/app/empresas?mensagem={quote(mensagem)}", status_code=303)


@router.post("/excluir-inativas")
def excluir_inativas(
    usuario: Usuario = Depends(admin_logado_web),
    db: Session = Depends(get_db),
):
    """Exclui de verdade toda empresa-cliente desativada (a pedido da
    Clara, 2026-09-28) — a confirmação (obrigatória, com o texto digitado)
    acontece no navegador antes desse POST (ver empresas.html e
    static/app.js). O backend recusa excluir qualquer uma com histórico
    vinculado. Precisa ficar ANTES de `POST /{empresa_id}` abaixo — mesmo
    motivo de `sincronizar-lista-oficial`."""
    resumo = excluir_empresas_inativas(db)
    registrar(
        db, usuario, "EXCLUIU_EMPRESAS_INATIVAS", entidade="empresa_cliente",
        detalhes=(
            f"{len(resumo.excluidas)} excluída(s), "
            f"{len(resumo.nao_excluidas_por_vinculo)} não excluída(s) por vínculo"
        ),
    )
    if resumo.excluidas:
        mensagem = f"{len(resumo.excluidas)} empresa(s) inativa(s) excluída(s): {', '.join(resumo.excluidas)}."
    else:
        mensagem = "Nenhuma empresa inativa para excluir."
    if resumo.nao_excluidas_por_vinculo:
        mensagem += (
            f" {len(resumo.nao_excluidas_por_vinculo)} não puderam ser excluídas por terem histórico "
            f"vinculado: {', '.join(resumo.nao_excluidas_por_vinculo)}."
        )
    return RedirectResponse(f"/app/empresas?mensagem={quote(mensagem)}", status_code=303)


@router.post("/excluir-em-massa")
def excluir_em_massa(
    empresa_ids: list[int] = Form([]),
    empresa_destino_id: str | None = Form(None),
    usuario: Usuario = Depends(admin_logado_web),
    db: Session = Depends(get_db),
):
    """Exclusão em massa (a pedido da Clara, 2026-10-06) — a seleção
    (checkboxes) e a confirmação acontecem no navegador antes desse POST
    (ver empresas.html e static/app.js). Uma única `empresa_destino_id`
    (opcional) vale pra todas as selecionadas que tiverem vínculo; sem
    destino, essas ficam de fora da exclusão, sem travar as demais. Precisa
    ficar ANTES de `POST /{empresa_id}` abaixo — mesmo motivo de
    `sincronizar-lista-oficial`."""
    if not empresa_ids:
        return RedirectResponse(f"/app/empresas?erro={quote('Nenhuma empresa selecionada.')}", status_code=303)
    destino_id = int(empresa_destino_id) if empresa_destino_id else None
    try:
        resumo = excluir_empresas_em_massa(db, empresa_ids, destino_id)
    except ValueError as e:
        return RedirectResponse(f"/app/empresas?erro={quote(str(e))}", status_code=303)
    registrar(
        db, usuario, "EXCLUIU_EMPRESAS_EM_MASSA", entidade="empresa_cliente",
        detalhes=(
            f"{len(resumo.excluidas)} excluída(s), "
            f"{len(resumo.nao_excluidas_por_vinculo)} não excluída(s) por vínculo"
        ),
    )
    mensagem = f"{len(resumo.excluidas)} empresa(s) excluída(s) definitivamente."
    if resumo.nao_excluidas_por_vinculo:
        mensagem += (
            f" {len(resumo.nao_excluidas_por_vinculo)} não puderam ser excluídas por terem histórico "
            f"vinculado sem destino informado: {', '.join(resumo.nao_excluidas_por_vinculo)}."
        )
    return RedirectResponse(f"/app/empresas?mensagem={quote(mensagem)}", status_code=303)


@router.post("/realocar-em-massa")
def realocar_em_massa(
    empresa_ids: list[int] = Form([]),
    empresa_destino_id: str | None = Form(None),
    usuario: Usuario = Depends(admin_logado_web),
    db: Session = Depends(get_db),
):
    """Realocação em massa (a pedido da Clara, 2026-10-06) — ação separada
    da exclusão: move o histórico vinculado das empresas selecionadas pra
    uma empresa de destino, sem excluir nem desativar as empresas de
    origem. Precisa ficar ANTES de `POST /{empresa_id}` abaixo — mesmo
    motivo de `sincronizar-lista-oficial`."""
    if not empresa_ids:
        return RedirectResponse(f"/app/empresas?erro={quote('Nenhuma empresa selecionada.')}", status_code=303)
    if not empresa_destino_id:
        return RedirectResponse(f"/app/empresas?erro={quote('Escolha uma empresa de destino.')}", status_code=303)
    try:
        resumo = realocar_empresas_em_massa(db, empresa_ids, int(empresa_destino_id))
    except ValueError as e:
        return RedirectResponse(f"/app/empresas?erro={quote(str(e))}", status_code=303)
    registrar(
        db, usuario, "REALOCOU_EMPRESAS_EM_MASSA", entidade="empresa_cliente",
        detalhes=(
            f"{len(resumo.realocadas)} empresa(s) com histórico movido, "
            f"{len(resumo.sem_vinculo)} sem nada a mover"
        ),
    )
    destino = db.get(EmpresaCliente, int(empresa_destino_id))
    total_registros = sum(qtd for _, qtd in resumo.realocadas)
    mensagem = (
        f"{total_registros} registro(s) de {len(resumo.realocadas)} empresa(s) movido(s) "
        f"para {destino.nome if destino else empresa_destino_id}."
    )
    if resumo.sem_vinculo:
        mensagem += f" {len(resumo.sem_vinculo)} empresa(s) não tinham nada vinculado: {', '.join(resumo.sem_vinculo)}."
    return RedirectResponse(f"/app/empresas?mensagem={quote(mensagem)}", status_code=303)


@router.post("/{empresa_id}")
async def editar(
    request: Request,
    empresa_id: int,
    usuario: Usuario = Depends(admin_logado_web),
    db: Session = Depends(get_db),
):
    form = await request.form()
    contexto = _contexto_base(db, usuario)
    nome = str(form.get("nome", "")).strip()
    cnpj = str(form.get("cnpj", "")).strip() or None
    if not nome:
        contexto["erro"] = "Nome é obrigatório."
        return templates.TemplateResponse(request, "empresas.html", contexto, status_code=400)
    try:
        empresa = atualizar_empresa(db, empresa_id, nome, cnpj)
    except ValueError as e:
        contexto["erro"] = str(e)
        return templates.TemplateResponse(request, "empresas.html", contexto, status_code=400)
    registrar(db, usuario, "EDITOU_EMPRESA", entidade="empresa_cliente", entidade_id=empresa_id)
    contexto = _contexto_base(db, usuario)
    contexto["mensagem"] = f"Empresa {empresa.nome} atualizada."
    return templates.TemplateResponse(request, "empresas.html", contexto)


@router.post("/{empresa_id}/ativo")
def alterar_ativo(
    empresa_id: int,
    ativo: bool,
    usuario: Usuario = Depends(admin_logado_web),
    db: Session = Depends(get_db),
):
    try:
        alterar_ativo_empresa(db, empresa_id, ativo)
    except ValueError:
        pass
    else:
        registrar(
            db, usuario, "ATIVOU_EMPRESA" if ativo else "DESATIVOU_EMPRESA",
            entidade="empresa_cliente", entidade_id=empresa_id,
        )
    return RedirectResponse("/app/empresas", status_code=303)


@router.post("/{empresa_id}/excluir")
def excluir(
    empresa_id: int,
    empresa_destino_id: str | None = Form(None),
    usuario: Usuario = Depends(admin_logado_web),
    db: Session = Depends(get_db),
):
    """Exclusão definitiva — a confirmação (obrigatória) acontece no
    navegador, num modal, antes desse POST ser disparado (ver empresas.html
    e static/app.js). Se a empresa tiver laudo/audiência/cobrança/processo
    vinculado, `empresa_destino_id` (escolhido no mesmo modal, 2026-09-28, a
    pedido da Clara) reatribui esse histórico pra outra empresa antes de
    excluir; sem destino nesse caso, o backend recusa a exclusão como
    sempre."""
    empresa = db.get(EmpresaCliente, empresa_id)
    nome = empresa.nome if empresa else str(empresa_id)
    destino_id = int(empresa_destino_id) if empresa_destino_id else None
    try:
        excluir_empresa(db, empresa_id, destino_id)
    except ValueError as e:
        return RedirectResponse(f"/app/empresas?erro={quote(str(e))}", status_code=303)
    registrar(db, usuario, "EXCLUIU_EMPRESA", entidade="empresa_cliente", entidade_id=empresa_id)
    return RedirectResponse(f"/app/empresas?mensagem={quote(f'Empresa {nome} excluída definitivamente.')}", status_code=303)
