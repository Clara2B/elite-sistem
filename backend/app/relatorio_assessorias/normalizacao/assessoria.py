"""Nome (de planilha) → empresa-cliente oficial, via apelidos (Fase 3).

Toda filtragem por assessoria passa por aqui, porque as planilhas usam
nomes diferentes pra mesma empresa. Fonte da lista oficial: `EmpresaCliente`
(não um YAML separado — ver decisão da Clara, 2026-10-08, "Cadastro
assessorias"); `config/assessorias.yaml` guarda só os apelidos.

Regras do tradutor (especificação):
- Comparação sem acento, sem espaços extras e em maiúsculas.
- Célula com mais de uma empresa (ex.: "RETRIX/ REVISION" na pauta) é
  separada por `/`, `,` ou ` E ` e conta pra cada uma.
- Nome que não está no cadastro (nem como oficial, nem como apelido) vira
  aviso global ("empresa desconhecida: ANGITU, 83 linhas"), com botão pra
  adicionar como nova empresa-cliente ou como apelido de uma existente.
"""
