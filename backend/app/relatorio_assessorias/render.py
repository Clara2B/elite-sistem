"""docxtpl + conversão pra PDF (Fase 7).

Gera a partir de `templates/relatorio.docx` (cópia do modelo atual,
Relatório_EWS_8.docx, com marcadores Jinja via docxtpl — ver
`scripts/preparar_template_relatorio.py`) — cabeçalho, rodapé, logo,
fontes e cores iguais ao modelo; textos e notas editáveis no Word sem
mexer em código.

Padronização da saída: números com dois dígitos e zero à esquerda ("03",
"14"), num único filtro Jinja (`dois_digitos`); seção com lista vazia
mostra a tabela só com cabeçalho e total "0" (comportamento natural do
loop `{%tr for/endfor %}` com lista vazia, sem código extra); nome do
arquivo `Relatório_<ASSESSORIA>_<MM>-<AAAA>.docx`; erros de digitação do
modelo ("REFRÊNCIA", "ASSESSSORIA", "QUATIDADE", "distribuidos")
corrigidos no template.

Conversão pra PDF: ADIADA (decisão da Clara, 2026-10-09) — não existe hoje
nenhum conversor docx→pdf no sistema (o `pdf_export.py` atual desenha PDF
do zero com reportlab, não converte um documento existente); minha
recomendação foi LibreOffice headless, mas Clara optou por gerar só o
`.docx` por enquanto, deixando a conversão pra uma versão futura."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from io import BytesIO
from pathlib import Path

from docx.shared import Mm
from docxtpl import DocxTemplate, InlineImage
from jinja2 import Environment

from app.relatorio_assessorias import mapas
from app.relatorio_assessorias.avisos import Aviso
from app.relatorio_assessorias.config import carregar
from app.relatorio_assessorias.secoes.contrarias import ResultadoContrarias
from app.relatorio_assessorias.secoes.extrajudiciais import ResultadoExtrajudiciais
from app.relatorio_assessorias.secoes.iniciais import ResultadoIniciais
from app.relatorio_assessorias.secoes.judiciais import ResultadoAudiencias
from app.relatorio_assessorias.secoes.laudos import ResultadoLaudos
from app.relatorio_assessorias.secoes.manuais import CamposManuais
from app.relatorio_assessorias.secoes.procons import ResultadoProcons
from app.utils import format_brl

_CAMINHO_TEMPLATE = Path(__file__).resolve().parent / "templates" / "relatorio.docx"

_MESES_EXTENSO = {
    1: "JANEIRO", 2: "FEVEREIRO", 3: "MARÇO", 4: "ABRIL", 5: "MAIO", 6: "JUNHO",
    7: "JULHO", 8: "AGOSTO", 9: "SETEMBRO", 10: "OUTUBRO", 11: "NOVEMBRO", 12: "DEZEMBRO",
}


@dataclass
class DadosRelatorio:
    """Tudo que o template precisa — resultado das Fases 4 (seções) e 5
    (avisos, não usados no corpo do relatório, só na tela de revisão,
    mas carregados aqui pra `renderizar_docx` ficar com uma assinatura só)
    + os campos digitados manualmente (Fase 8)."""
    assessoria: str
    mes: int
    ano: int
    data_corte: date
    laudos: ResultadoLaudos
    iniciais: ResultadoIniciais
    extrajudiciais: ResultadoExtrajudiciais
    audiencias_judiciais: ResultadoAudiencias
    audiencias_contrarias: ResultadoAudiencias
    contrarias: ResultadoContrarias
    procons: ResultadoProcons
    manuais: CamposManuais
    avisos: list[Aviso]


def _dois_digitos(numero: int) -> str:
    return f"{numero:02d}"


def _valor_brl(valor: float | None) -> str:
    return "Não informado" if valor is None else format_brl(valor)


def _jinja_env() -> Environment:
    ambiente = Environment()
    ambiente.filters["dois_digitos"] = _dois_digitos
    ambiente.filters["valor_brl"] = _valor_brl
    return ambiente


def nome_arquivo_docx(assessoria: str, mes: int, ano: int) -> str:
    return f"Relatório_{assessoria}_{mes:02d}-{ano}.docx"


def renderizar_docx(dados: DadosRelatorio) -> bytes:
    """Gera o .docx do relatório a partir de `templates/relatorio.docx` +
    os dados já calculados. Devolve os bytes do arquivo — nada salvo em
    disco (mesmo padrão do resto do sistema: PDFs/Excels gerados na hora,
    nunca persistidos; só o resultado numérico fica no banco, Fase 8)."""
    template = DocxTemplate(str(_CAMINHO_TEMPLATE))
    mapa_rotulos = carregar("mapa_rotulos")

    tabela_revisional_uf = mapas.tabela_por_uf(dados.manuais.processos_ativos_revisionais_por_uf)
    tabela_processos_ganhos_uf = mapas.tabela_por_uf(dados.manuais.processos_ganhos_por_uf)
    tabela_contrarias_uf = mapas.tabela_por_uf(dados.contrarias.ativos_por_uf)

    mapa_revisional_png = mapas.desenhar(tabela_revisional_uf, mapa_rotulos["paletas"]["revisional"], mapa_rotulos)
    mapa_contrarias_png = mapas.desenhar(tabela_contrarias_uf, mapa_rotulos["paletas"]["contrarias"], mapa_rotulos)

    contexto = {
        "assessoria": dados.assessoria,
        "mes_extenso": _MESES_EXTENSO[dados.mes],
        "ano": dados.ano,
        "data_corte": dados.data_corte.strftime("%d/%m/%Y"),
        "laudos": dados.laudos,
        "iniciais": dados.iniciais,
        "extrajudiciais": dados.extrajudiciais,
        "audiencias_judiciais": dados.audiencias_judiciais,
        "audiencias_contrarias": dados.audiencias_contrarias,
        "contrarias": dados.contrarias,
        "procons": dados.procons,
        "manuais": dados.manuais,
        "tabela_revisional_uf": tabela_revisional_uf,
        "tabela_processos_ganhos_uf": tabela_processos_ganhos_uf,
        "tabela_contrarias_uf": tabela_contrarias_uf,
        "mapa_revisional": InlineImage(template, BytesIO(mapa_revisional_png), width=Mm(140)),
        "mapa_contrarias": InlineImage(template, BytesIO(mapa_contrarias_png), width=Mm(140)),
    }

    template.render(contexto, _jinja_env())
    buffer = BytesIO()
    template.save(buffer)
    return buffer.getvalue()
