"""docxtpl + conversão pra PDF (Fase 7).

Gera a partir de `templates/relatorio.docx` (cópia do modelo atual,
Relatório_EWS_8.docx, com marcadores Jinja via docxtpl) — cabeçalho,
rodapé, logo, fontes e cores iguais ao modelo; textos e notas editáveis no
Word sem mexer em código.

Padronização da saída: números com dois dígitos e zero à esquerda ("03",
"14"), num único filtro; seção com lista vazia mostra a tabela só com
cabeçalho e total "0"; nome do arquivo
`Relatório_<ASSESSORIA>_<MM>-<AAAA>.docx`; erros de digitação do modelo
("REFRÊNCIA", "ASSESSSORIA", "QUATIDADE", "distribuidos") corrigidos no
template.

Conversão pra PDF: PENDENTE — não existe hoje nenhum conversor docx→pdf no
sistema (o `pdf_export.py` atual desenha PDF do zero com reportlab, não
converte um documento existente). Recomendação dada à Clara, 2026-10-08:
LibreOffice headless — precisa dela confirmar disponibilidade no servidor
(Render) antes desta fase.
"""
