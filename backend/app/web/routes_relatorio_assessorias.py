"""Telas do Gerador de Relatórios Mensais das Assessorias (Fase 8) — área
nova e isolada, só admin (mesmo padrão de Configuração/Auditoria: sem item
próprio no menu lateral, só dentro de Configuração — decisão da Clara,
2026-10-08, "Quem pode acessar a nova área: só admin por enquanto", que
também cobre o pedido dela de manter a área fora de vista até o
lançamento, sem precisar de uma flag separada).

Fluxo (especificação, "Fluxo do usuário e telas"): parâmetros + upload →
processamento (todas as assessorias do cadastro de uma vez) → painel →
revisão (por assessoria) → geração (.docx individual ou .zip em lote). A
conversão pra PDF foi adiada (decisão da Clara, 2026-10-09, Fase 7) — só
.docx por enquanto."""
from __future__ import annotations

import base64
import io
import json
import unicodedata
import zipfile
from datetime import date
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Request, UploadFile
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session

from app.api._shared import salvar_temp
from app.db import get_db
from app.models import Usuario
from app.relatorio_assessorias import armazenamento, mapas, processamento
from app.relatorio_assessorias.config import carregar
from app.relatorio_assessorias.leitores.base import ErroDeLeituraBloqueante
from app.relatorio_assessorias.render import nome_arquivo_docx, renderizar_docx
from app.relatorio_assessorias.secoes.manuais import CamposManuais, PastasRevisionais
from app.web.areas_configuracao import AREAS_CONFIGURACAO
from app.web.auth import admin_logado_web
from app.web.menu import itens_menu
from app.web.templates import templates

router = APIRouter(prefix="/app/relatorios-assessorias")


def _cabecalho_download(nome_arquivo: str) -> dict[str, str]:
    """Content-Disposition com nome de arquivo acentuado (a especificação
    pede literalmente "Relatório_...") — filename (ASCII, fallback) +
    filename* (UTF-8, RFC 5987) pros navegadores que suportam, em vez de
    só tirar o acento como o resto do sistema faz hoje (`app.utils.
    nome_arquivo_pdf`) — aqui o nome acentuado é parte do que a Clara
    pediu, não só um detalhe incidental."""
    ascii_nome = unicodedata.normalize("NFKD", nome_arquivo).encode("ascii", "ignore").decode("ascii")
    return {"Content-Disposition": f"attachment; filename=\"{ascii_nome}\"; filename*=UTF-8''{quote(nome_arquivo)}"}


def _contexto_base(request: Request, usuario: Usuario, db: Session) -> dict:
    return {
        "request": request, "usuario": usuario, "menu": itens_menu(db, usuario),
        "areas_configuracao": AREAS_CONFIGURACAO,
    }


def _tem_movimento(dados) -> bool:
    return bool(
        dados.laudos.elaborados or dados.iniciais.distribuidos_no_mes or dados.extrajudiciais.enviadas
        or dados.audiencias_judiciais.quantidade or dados.audiencias_contrarias.quantidade
        or dados.contrarias.incluidos_no_mes or dados.procons.lista
    )


@router.get("")
def tela_upload(request: Request, usuario: Usuario = Depends(admin_logado_web), db: Session = Depends(get_db)):
    hoje = date.today()
    contexto = _contexto_base(request, usuario, db)
    contexto.update({"mes": hoje.month, "ano": hoje.year, "data_corte": hoje.isoformat(), "erro": None})
    return templates.TemplateResponse(request, "relatorio_assessorias_upload.html", contexto)


@router.post("/processar")
async def processar(
    request: Request,
    mes: int = Form(...),
    ano: int = Form(...),
    data_corte: date = Form(...),
    laudo: UploadFile = None,
    iniciais: UploadFile = None,
    agendamento: UploadFile = None,
    extrajudicial: UploadFile = None,
    contrarias: UploadFile = None,
    procon: UploadFile = None,
    usuario: Usuario = Depends(admin_logado_web),
    db: Session = Depends(get_db),
):
    arquivos = {
        "laudo": laudo, "iniciais": iniciais, "agendamento": agendamento,
        "extrajudicial": extrajudicial, "contrarias": contrarias, "procon": procon,
    }
    faltando = [campo for campo, arquivo in arquivos.items() if arquivo is None or not arquivo.filename]
    if faltando:
        contexto = _contexto_base(request, usuario, db)
        contexto.update({
            "mes": mes, "ano": ano, "data_corte": data_corte.isoformat(),
            "erro": f"Falta anexar: {', '.join(faltando)}.",
        })
        return templates.TemplateResponse(request, "relatorio_assessorias_upload.html", contexto)

    caminhos = {campo: salvar_temp(arquivo) for campo, arquivo in arquivos.items()}

    try:
        resultados, desconhecidas = processamento.processar_upload(db, caminhos, mes, ano, data_corte, usuario)
    except ErroDeLeituraBloqueante as e:
        contexto = _contexto_base(request, usuario, db)
        contexto.update({
            "mes": mes, "ano": ano, "data_corte": data_corte.isoformat(),
            "erro": f"Não consegui ler uma das planilhas: {e}",
        })
        return templates.TemplateResponse(request, "relatorio_assessorias_upload.html", contexto)

    mensagem = quote(
        f"{len(resultados)} assessoria(s) processada(s)."
        + (f" {len(desconhecidas)} nome(s) de empresa não reconhecido(s) nas planilhas." if desconhecidas else "")
    )
    return RedirectResponse(f"/app/relatorios-assessorias/painel?mes={mes}&ano={ano}&mensagem={mensagem}", status_code=303)


@router.get("/painel")
def painel(
    request: Request,
    mes: int | None = None,
    ano: int | None = None,
    mensagem: str | None = None,
    usuario: Usuario = Depends(admin_logado_web),
    db: Session = Depends(get_db),
):
    hoje = date.today()
    mes = mes or hoje.month
    ano = ano or hoje.year
    registros = armazenamento.listar_resultados(db, mes, ano)
    linhas = []
    for registro in registros:
        dados = armazenamento.dados_efetivos(registro)
        linhas.append({
            "assessoria": registro.assessoria,
            "tem_movimento": _tem_movimento(dados),
            "qtd_avisos": len(dados.avisos),
        })

    contexto = _contexto_base(request, usuario, db)
    contexto.update({"mes": mes, "ano": ano, "linhas": linhas, "mensagem": mensagem})
    return templates.TemplateResponse(request, "relatorio_assessorias_painel.html", contexto)


@router.get("/revisao/{assessoria}")
def revisao(
    request: Request,
    assessoria: str,
    mes: int,
    ano: int,
    usuario: Usuario = Depends(admin_logado_web),
    db: Session = Depends(get_db),
):
    registro = armazenamento.carregar_resultado(db, assessoria, mes, ano)
    if registro is None:
        return RedirectResponse(f"/app/relatorios-assessorias/painel?mes={mes}&ano={ano}", status_code=303)

    dados = armazenamento.dados_efetivos(registro)
    numeros_calculados = armazenamento.numeros_calculados_do_registro(registro)
    sobrescritas = json.loads(registro.sobrescritas_json)

    mapa_rotulos = carregar("mapa_rotulos")
    tabela_revisional_uf = mapas.tabela_por_uf(dados.manuais.processos_ativos_revisionais_por_uf)
    tabela_contrarias_uf = mapas.tabela_por_uf(dados.contrarias.ativos_por_uf)
    mapa_revisional_b64 = base64.b64encode(
        mapas.desenhar(tabela_revisional_uf, mapa_rotulos["paletas"]["revisional"], mapa_rotulos)
    ).decode("ascii")
    mapa_contrarias_b64 = base64.b64encode(
        mapas.desenhar(tabela_contrarias_uf, mapa_rotulos["paletas"]["contrarias"], mapa_rotulos)
    ).decode("ascii")

    contexto = _contexto_base(request, usuario, db)
    contexto.update({
        "assessoria": assessoria, "mes": mes, "ano": ano,
        "dados": dados, "registro": registro,
        "numeros_calculados": numeros_calculados, "sobrescritas": sobrescritas,
        "campos_sobrescreviveis": armazenamento.CAMPOS_NUMERICOS_SOBRESCREVIVEIS,
        "mapa_revisional_b64": mapa_revisional_b64, "mapa_contrarias_b64": mapa_contrarias_b64,
    })
    return templates.TemplateResponse(request, "relatorio_assessorias_revisao.html", contexto)


@router.post("/revisao/{assessoria}/sobrescrever")
def sobrescrever(
    assessoria: str,
    mes: int = Form(...),
    ano: int = Form(...),
    campo: str = Form(...),
    valor: int = Form(...),
    usuario: Usuario = Depends(admin_logado_web),
    db: Session = Depends(get_db),
):
    registro = armazenamento.carregar_resultado(db, assessoria, mes, ano)
    if registro is not None and campo in armazenamento.CAMPOS_NUMERICOS_SOBRESCREVIVEIS:
        armazenamento.sobrescrever_numero(db, registro, usuario, campo, valor)
    return RedirectResponse(
        f"/app/relatorios-assessorias/revisao/{quote(assessoria)}?mes={mes}&ano={ano}", status_code=303
    )


@router.post("/revisao/{assessoria}/manuais")
def salvar_manuais(
    assessoria: str,
    mes: int = Form(...),
    ano: int = Form(...),
    pastas_recebidas: int = Form(0),
    pastas_aprovadas: int = Form(0),
    pastas_aguardando_analise: int = Form(0),
    pastas_aguardando_correcao: int = Form(0),
    pastas_acumulado_crm: int = Form(0),
    processos_ativos_revisionais_total: int = Form(0),
    extrajudiciais_pendentes_correcao: int = Form(0),
    usuario: Usuario = Depends(admin_logado_web),
    db: Session = Depends(get_db),
):
    registro = armazenamento.carregar_resultado(db, assessoria, mes, ano)
    if registro is not None:
        dados_atuais = armazenamento.dados_efetivos(registro)
        manuais = CamposManuais(
            pastas_revisionais=PastasRevisionais(
                recebidas_no_mes=pastas_recebidas, aprovadas=pastas_aprovadas,
                aguardando_analise=pastas_aguardando_analise,
                aguardando_correcao_no_mes=pastas_aguardando_correcao, acumulado_crm=pastas_acumulado_crm,
            ),
            processos_ativos_revisionais_total=processos_ativos_revisionais_total,
            # Mapa por UF, sentenças e processos ganhos ainda não têm campo
            # na tela (v1 cobre os totais — ver resumo pra Clara, listado
            # como pendência de uma versão futura); preserva o que já
            # estava salvo em vez de zerar.
            processos_ativos_revisionais_por_uf=dados_atuais.manuais.processos_ativos_revisionais_por_uf,
            sentencas_procedentes=dados_atuais.manuais.sentencas_procedentes,
            processos_ganhos_por_uf=dados_atuais.manuais.processos_ganhos_por_uf,
            sentencas_favoraveis_contrarias=dados_atuais.manuais.sentencas_favoraveis_contrarias,
            extrajudiciais_solicitacoes_pendentes_correcao=extrajudiciais_pendentes_correcao,
        )
        armazenamento.salvar_campos_manuais(db, registro, manuais, usuario)
    return RedirectResponse(
        f"/app/relatorios-assessorias/revisao/{quote(assessoria)}?mes={mes}&ano={ano}", status_code=303
    )


@router.get("/docx/{assessoria}")
def baixar_docx(
    assessoria: str, mes: int, ano: int,
    usuario: Usuario = Depends(admin_logado_web), db: Session = Depends(get_db),
):
    registro = armazenamento.carregar_resultado(db, assessoria, mes, ano)
    if registro is None:
        return RedirectResponse(f"/app/relatorios-assessorias/painel?mes={mes}&ano={ano}", status_code=303)
    conteudo = renderizar_docx(armazenamento.dados_efetivos(registro))
    nome = nome_arquivo_docx(assessoria, mes, ano)
    return Response(
        content=conteudo,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers=_cabecalho_download(nome),
    )


@router.post("/lote")
def baixar_lote(
    mes: int = Form(...),
    ano: int = Form(...),
    assessorias: list[str] = Form(default=[]),
    usuario: Usuario = Depends(admin_logado_web),
    db: Session = Depends(get_db),
):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as arquivo_zip:
        for assessoria in assessorias:
            registro = armazenamento.carregar_resultado(db, assessoria, mes, ano)
            if registro is None:
                continue
            conteudo = renderizar_docx(armazenamento.dados_efetivos(registro))
            arquivo_zip.writestr(nome_arquivo_docx(assessoria, mes, ano), conteudo)

    nome_zip = f"Relatórios_{mes:02d}-{ano}.zip"
    return Response(
        content=buffer.getvalue(), media_type="application/zip", headers=_cabecalho_download(nome_zip)
    )
