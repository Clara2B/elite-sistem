"""Tela /app/solicitacoes-audiencia — Nova Solicitação de Audiência (Fase 1,
2026-10-16, a pedido da Clara). Fluxo em duas etapas, pelo mesmo
formulário: "Buscar horário" mostra a prévia (sem gravar nada ainda);
"Confirmar" grava de verdade, com o travamento otimista de
app/services/solicitacoes_audiencia.py. Se a vaga prevista for perdida
nesse meio tempo (`HorarioJaOcupado`), busca a próxima automaticamente e
mostra a prévia de novo, com os mesmos dados do formulário preenchidos."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import SolicitacaoAudiencia, Usuario
from app.services.auditoria import registrar
from app.services.bancos import listar_bancos
from app.services.empresas import listar_empresas
from app.services.envio_cartas import enviar_emails, montar_previas
from app.services.solicitacoes_audiencia import (
    HorarioJaOcupado,
    HorarioVago,
    agora_brasil,
    confirmar_na_planilha,
    encontrar_proximo_horario_vago,
    reservar_horario,
)
from app.web.auth import require_modulo_web
from app.web.menu import itens_menu
from app.web.templates import templates

router = APIRouter(prefix="/app/solicitacoes-audiencia")

# Mesmo acesso de Audiências/Cartas/Bancos (2026-10-16, a pedido da Clara).
_acesso_eximia = require_modulo_web("AUDIENCIAS")


def _contexto_base(db: Session, usuario: Usuario) -> dict:
    return {
        "usuario": usuario,
        "menu": itens_menu(db, usuario),
        "empresas": listar_empresas(db, apenas_ativas=True),
        "bancos": listar_bancos(db, apenas_ativos=True),
        "hoje": date.today(),
        "valores": {},
        "previa": None,
        "previas_email": None,
        "solicitacao_id": None,
        "mensagem": None,
        "erro": None,
    }


@router.get("")
def tela(request: Request, usuario: Usuario = Depends(_acesso_eximia), db: Session = Depends(get_db)):
    return templates.TemplateResponse(request, "solicitacao_audiencia.html", _contexto_base(db, usuario))


def _ler_valores_do_form(form) -> dict:
    return {
        "empresa_cliente_id": str(form.get("empresa_cliente_id", "")),
        "nome_cliente": str(form.get("nome_cliente", "")).strip(),
        "cpf_cliente": str(form.get("cpf_cliente", "")).strip(),
        "email_cliente": str(form.get("email_cliente", "")).strip(),
        "telefone_cliente": str(form.get("telefone_cliente", "")).strip(),
        "data_recebimento": str(form.get("data_recebimento", "")),
        "numero_contrato": str(form.get("numero_contrato", "")).strip(),
        "banco_id": str(form.get("banco_id", "")),
        "link_audiencia": str(form.get("link_audiencia", "")).strip(),
    }


def _validar_campos_obrigatorios(valores: dict) -> str | None:
    obrigatorios = [
        "empresa_cliente_id", "nome_cliente", "cpf_cliente", "email_cliente", "telefone_cliente",
        "data_recebimento", "numero_contrato", "banco_id", "link_audiencia",
    ]
    if any(not valores[campo] for campo in obrigatorios):
        return "Todos os campos são obrigatórios."
    return None


def _buscar_proximo_horario_ou_erro(contexto: dict) -> HorarioVago | None:
    """Usada depois de perder a corrida pra uma vaga (`HorarioJaOcupado`) —
    busca a próxima e já marca `contexto["erro"]` em qualquer caso (vaga
    nenhuma encontrada, ou falha de verdade pra consultar a planilha, ex.:
    credencial/rede), nunca deixa a página sem explicação."""
    try:
        proximo = encontrar_proximo_horario_vago(settings.google_sheets_id, agora_brasil())
    except Exception as e:  # noqa: BLE001 — qualquer falha da API do Google (credencial, rede, permissão) vira mensagem amigável, não 500
        contexto["erro"] = f"Não foi possível consultar a planilha de controle: {e}"
        return None
    if proximo is None:
        contexto["erro"] = "Não há nenhum outro horário vago na planilha de controle no momento."
    return proximo


@router.post("/buscar-horario")
async def buscar_horario(
    request: Request,
    usuario: Usuario = Depends(_acesso_eximia),
    db: Session = Depends(get_db),
):
    form = await request.form()
    contexto = _contexto_base(db, usuario)
    valores = _ler_valores_do_form(form)
    contexto["valores"] = valores

    erro = _validar_campos_obrigatorios(valores)
    if erro:
        contexto["erro"] = erro
        return templates.TemplateResponse(request, "solicitacao_audiencia.html", contexto, status_code=400)

    if not settings.google_sheets_id:
        contexto["erro"] = "GOOGLE_SHEETS_ID não está configurado."
        return templates.TemplateResponse(request, "solicitacao_audiencia.html", contexto, status_code=400)

    try:
        horario = encontrar_proximo_horario_vago(settings.google_sheets_id, agora_brasil())
    except Exception as e:  # noqa: BLE001 — mesmo motivo do helper acima
        contexto["erro"] = f"Não foi possível consultar a planilha de controle: {e}"
        return templates.TemplateResponse(request, "solicitacao_audiencia.html", contexto, status_code=502)
    if horario is None:
        contexto["erro"] = "Não há nenhum horário vago na planilha de controle no momento."
        return templates.TemplateResponse(request, "solicitacao_audiencia.html", contexto, status_code=400)

    contexto["previa"] = {
        "numero_linha": horario.numero_linha,
        "dia": horario.dia,
        "hora": horario.hora,
    }
    return templates.TemplateResponse(request, "solicitacao_audiencia.html", contexto)


@router.post("/confirmar")
async def confirmar(
    request: Request,
    usuario: Usuario = Depends(_acesso_eximia),
    db: Session = Depends(get_db),
):
    form = await request.form()
    contexto = _contexto_base(db, usuario)
    valores = _ler_valores_do_form(form)
    contexto["valores"] = valores

    erro = _validar_campos_obrigatorios(valores)
    if erro:
        contexto["erro"] = erro
        return templates.TemplateResponse(request, "solicitacao_audiencia.html", contexto, status_code=400)
    if not settings.google_sheets_id:
        contexto["erro"] = "GOOGLE_SHEETS_ID não está configurado."
        return templates.TemplateResponse(request, "solicitacao_audiencia.html", contexto, status_code=400)

    try:
        numero_linha = int(form.get("numero_linha", ""))
        dia = date.fromisoformat(str(form.get("dia", "")))
        hora = str(form.get("hora", ""))
    except (TypeError, ValueError):
        contexto["erro"] = "Prévia inválida — busque o horário de novo."
        return templates.TemplateResponse(request, "solicitacao_audiencia.html", contexto, status_code=400)
    horario = HorarioVago(numero_linha=numero_linha, dia=dia, hora=hora)

    try:
        solicitacao = reservar_horario(
            db, usuario,
            empresa_cliente_id=int(valores["empresa_cliente_id"]),
            nome_cliente=valores["nome_cliente"],
            cpf_cliente=valores["cpf_cliente"],
            email_cliente=valores["email_cliente"],
            telefone_cliente=valores["telefone_cliente"],
            data_recebimento=date.fromisoformat(valores["data_recebimento"]),
            numero_contrato=valores["numero_contrato"],
            banco_id=int(valores["banco_id"]),
            link_audiencia=valores["link_audiencia"],
            horario=horario,
        )
    except ValueError as e:
        # Inclui HorarioJaOcupado (subclasse de ValueError) perdido no
        # banco — busca o próximo horário disponível e mostra a prévia de
        # novo, sem o usuário precisar redigitar nada.
        if isinstance(e, HorarioJaOcupado):
            contexto["mensagem"] = str(e) + " Buscando o próximo horário disponível..."
            proximo = _buscar_proximo_horario_ou_erro(contexto)
            if proximo:
                contexto["previa"] = {"numero_linha": proximo.numero_linha, "dia": proximo.dia, "hora": proximo.hora}
        else:
            contexto["erro"] = str(e)
        return templates.TemplateResponse(request, "solicitacao_audiencia.html", contexto, status_code=409)

    try:
        confirmar_na_planilha(db, settings.google_sheets_id, solicitacao)
    except HorarioJaOcupado as e:
        contexto["mensagem"] = str(e) + " Buscando o próximo horário disponível..."
        proximo = _buscar_proximo_horario_ou_erro(contexto)
        if proximo:
            contexto["previa"] = {"numero_linha": proximo.numero_linha, "dia": proximo.dia, "hora": proximo.hora}
        return templates.TemplateResponse(request, "solicitacao_audiencia.html", contexto, status_code=409)
    except Exception as e:  # noqa: BLE001 — qualquer falha inesperada da API do Google na gravação vira mensagem amigável, não 500
        contexto["erro"] = f"Não foi possível gravar na planilha de controle: {e}"
        return templates.TemplateResponse(request, "solicitacao_audiencia.html", contexto, status_code=502)

    registrar(
        db, usuario, "CRIOU_SOLICITACAO_AUDIENCIA", entidade="solicitacao_audiencia",
        entidade_id=solicitacao.id, detalhes=f"{solicitacao.nome_cliente} — linha {solicitacao.linha_planilha}",
    )
    contexto = _contexto_base(db, usuario)
    contexto["mensagem"] = (
        f"Solicitação gravada na planilha — {solicitacao.data_agendamento.strftime('%d/%m/%Y')} "
        f"às {solicitacao.hora_agendamento}. Revise as cartas abaixo antes de enviar."
    )
    contexto["solicitacao_id"] = solicitacao.id
    contexto["previas_email"] = montar_previas(db, solicitacao)
    return templates.TemplateResponse(request, "solicitacao_audiencia.html", contexto)


@router.post("/{solicitacao_id}/enviar-emails")
def enviar_emails_rota(
    request: Request,
    solicitacao_id: int,
    usuario: Usuario = Depends(_acesso_eximia),
    db: Session = Depends(get_db),
):
    """Só dispara depois do clique explícito em "Enviar" — a prévia (ver
    `confirmar` acima) já foi mostrada antes disso, como pedido. Em caso de
    falha (de um dos dois e-mails ou dos dois), não marca como concluído:
    mostra o erro e a prévia de novo, pronta pra tentar enviar outra vez."""
    contexto = _contexto_base(db, usuario)
    solicitacao = db.get(SolicitacaoAudiencia, solicitacao_id)
    if solicitacao is None:
        contexto["erro"] = "Solicitação não encontrada."
        return templates.TemplateResponse(request, "solicitacao_audiencia.html", contexto, status_code=404)

    resultado = enviar_emails(db, usuario, solicitacao, spreadsheet_id=settings.google_sheets_id)
    if resultado.cliente_enviado and resultado.banco_enviado:
        registrar(
            db, usuario, "ENVIOU_CARTAS_AUDIENCIA", entidade="solicitacao_audiencia",
            entidade_id=solicitacao.id, detalhes=solicitacao.nome_cliente,
        )
        contexto["mensagem"] = f"Os dois e-mails (cliente e banco) de {solicitacao.nome_cliente} foram enviados."
        return templates.TemplateResponse(request, "solicitacao_audiencia.html", contexto)

    partes = []
    if not resultado.cliente_enviado:
        partes.append(f"Cliente: {resultado.cliente_erro}")
    if not resultado.banco_enviado:
        partes.append(f"Banco: {resultado.banco_erro}")
    contexto["erro"] = "Falha ao enviar — " + " | ".join(partes) + ". Pode tentar enviar de novo."
    contexto["solicitacao_id"] = solicitacao.id
    contexto["previas_email"] = montar_previas(db, solicitacao)
    return templates.TemplateResponse(request, "solicitacao_audiencia.html", contexto, status_code=502)
