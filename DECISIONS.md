# DECISIONS.md — Elite Sistem

Histórico de decisões técnicas e pendências abertas. Formato por entrada: contexto, opções,
decisão/recomendação, reversibilidade.

---

## 2026-09-21 — Auditoria do sistema atual feita a partir do repositório `leitor-relatorio`, não do `elite-sistem`

**Contexto:** o repositório `elite-sistem` (onde este projeto roda) estava vazio. A Clara enviou
acesso ao código-fonte real em `Clara2B/leitor-relatorio`, ao app publicado no Streamlit Cloud e a
duas planilhas de exemplo. A Fase 0 (diagnóstico) foi feita clonando esse repositório
separadamente (leitura apenas, sem push).
**Decisão:** manter `elite-sistem` como o repositório do sistema **novo**; `leitor-relatorio`
continua sendo tratado como o sistema **atual**, somente para leitura/estudo, nunca modificado sem
autorização e acesso de escrita explícitos.
**Reversível:** sim, é só uma convenção de trabalho.

## 2026-09-21 — Achado de segurança: dados sensíveis expostos publicamente em `leitor-relatorio`

**Contexto:** o commit único do repositório (`27bde13`, "Add files via upload") inclui, apesar do
`.gitignore` bloquear os padrões, o arquivo `core/Lançamentos - Fluxo de Caixa (1).xlsx` (dados
financeiros reais) e `data/leitor_relatorio.sqlite3` (43 CNPJs de empresas-clientes) — rastreados
no Git de um repositório **público**.
**Decisão:** não tentar corrigir isso automaticamente. Reportado como risco crítico em
`ARCHITECTURE.md` seção 1.5, com recomendação de ação imediata (tornar o repo privado) e passos
seguintes (reescrever histórico), aguardando autorização e concessão de acesso de escrita da Clara
antes de qualquer ação destrutiva no histórico do Git.
**Reversível:** tornar o repo privado é reversível/imediato; reescrever histórico do Git é
irreversível sem backup — por isso não será feito sem aprovação explícita.

## 2026-09-21 — Ambiguidade de nomenclatura "empresa" identificada

**Contexto:** as planilhas usam a coluna `EMPRESA` para se referir a **empresas-clientes** da
EXIMIA/ELITE (dezenas de nomes, ex. ABSOLUTA, ALLURE, NEXUS), enquanto o requisito de
"multiempresa" da Clara se refere às **duas operadoras do sistema** (EXÍMIA e ELITE).
**Decisão (proposta, aguardando confirmação):** tratar como duas entidades distintas no modelo de
dados futuro: `operadoras` (EXÍMIA/ELITE, fixo, controla acesso/segregação) e `empresas_clientes`
(muitas, dado de negócio dos relatórios). Ver pendência 3 em `ARCHITECTURE.md` seção 1.9.
**Reversível:** sim, é uma decisão de modelagem ainda não implementada.

## 2026-09-21 — Respostas do Gate 0 recebidas; Fase 0 encerrada

**Contexto:** a Clara respondeu às 5 pendências de `ARCHITECTURE.md` seção 1.9.
**Decisões/registros resultantes:**
- Fonte de dados real = Google Sheets, atualizado todo dia (não Excel local). Ver D5 em
  `ARCHITECTURE.md` 2.5 — import manual/planilha na Fase 3, integração direta com a API do Google
  Sheets fica para uma Fase 7 (automação) futura, evitando overengineering agora.
- Módulo de fluxo de caixa/contas a pagar interno (`PAGAMENTOS`, `PAG.<mês>`) **fica fora do
  escopo** do novo sistema — confirmado explicitamente.
- Nomenclatura operadora (EXÍMIA/ELITE) vs. empresa-cliente confirmada; regra dura adicionada: só o
  Admin Superior vê as duas operadoras, qualquer outro usuário fica restrito à(s) sua(s).
- Hierarquia real tem 3 níveis: Admin Superior (hoje 3 pessoas) → Líder de setor → Colaborador de
  setor — atualizado em `DATABASE.md` seção 1 e `ARCHITECTURE.md` seção 2.6.
- Risco crítico de segurança (dados expostos publicamente) **mitigado**: repositório
  `leitor-relatorio` já está privado.
**Reversível:** os registros de nomenclatura/hierarquia são decisões de modelagem ainda não
implementadas em código — reversíveis até a Fase 4 começar de fato.

## 2026-09-21 — D1/D2/D3 aprovados; Fase 1 concluída

**Decisão:** a Clara aprovou as três recomendações do arquiteto: login individual (D1), migrar
frontend para stack própria com backend FastAPI (D2), Supabase como banco/hospedagem (D3). Detalhes
e justificativas em `ARCHITECTURE.md` seção 2.
**Reversível:** D1 e D3 são reversíveis com esforço baixo/médio; D2 (frontend) é a mais cara de
reverter depois — decidida com essa ressalva já exposta e aceita.

## Pendências abertas

1. Lista real dos setores (nomes) — não bloqueia o schema (`setores` é genérico), mas precisa ser
   confirmada antes da Fase 4.
2. Se uma `empresa_cliente` pode pertencer às duas operadoras ao mesmo tempo, ou é sempre separada
   por operadora (`DATABASE.md` seção 8).
3. Política de retenção de dados pessoais (LGPD) — `SECURITY.md` seção 4.
4. Contas de infraestrutura a serem criadas pela Clara antes da Fase 2 avançar para deploy real:
   projeto Supabase e provedor de hospedagem do backend — ver pedido no chat.
