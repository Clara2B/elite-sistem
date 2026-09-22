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

## 2026-09-22 — Supabase usado só como Postgres gerenciado, não como Auth/SDK do lado do backend

**Contexto:** ao criar o projeto Supabase, a Clara recebeu da própria Supabase um passo a passo de
integração para **Next.js** (pacotes `@supabase/supabase-js`/`@supabase/ssr`, cookies de sessão,
`middleware.ts`). Isso não se aplica ao nosso backend, que é Python/FastAPI (decisão D2).
**Decisão:** usar o Supabase só pelo que já foi decidido em D3 — Postgres gerenciado (connection
string) — e manter a autenticação implementada no próprio backend FastAPI (login individual, hash
de senha, papéis por setor/operadora), como já definido em D1/D2. Isso não muda nenhuma decisão já
aprovada, só esclarece a implementação: não vamos usar o SDK/Auth do Supabase do lado do backend.
**Reversível:** sim, é só uma escolha de biblioteca/integração, não afeta o schema.
**Nota de segurança relacionada:** ver `SECURITY.md` seção 4 sobre o que é seguro compartilhar do
Supabase (URL/publishable key) vs. o que nunca deve ir para o chat (connection string com senha,
service_role key).

## 2026-09-22 — Fase 2 concluída: backend em produção (hello world)

**Contexto:** a Clara criou o Web Service no Render (branch
`claude/relatorios-arquitetura-auditoria-pewhu8`, root `backend/`) e o projeto no Supabase. O
esqueleto FastAPI ficou no ar em https://elite-sistem.onrender.com, `/health` confirmado
funcionando pela própria Clara (o ambiente de execução deste agente não tem acesso de saída a
domínios externos como `onrender.com`, então a verificação final foi feita por ela).
**Decisão:** considerar a Fase 2 concluída — critério de conclusão do prompt mestre atingido. O
Supabase fica provisionado mas sem conexão ativa até a Fase 3 precisar de fato gravar dados.
**Reversível:** sim, é infraestrutura, não dado nem schema.

## 2026-09-22 — Fase 3: laudos/audiências/pendências portados e validados

**Contexto:** implementação da Fase 3 (ver plano apresentado no chat): backend conectado ao
Supabase, lógica de `core/laudos.py`, `core/audiencias.py`, `core/pendencias.py` (leitor-relatorio)
portada para `backend/app/services/`, agora persistindo em banco em vez de recalcular a cada
upload. Endpoints de import (`.xlsx`) e de geração de relatório (texto + PDF) criados para os três
fluxos.
**Validação de paridade** (critério de conclusão da Fase 3) rodada contra os dados reais que a
Clara enviou: **272/272 combinações empresa×período de audiências** e **18/18 empresas com
pendência** batendo exatamente com a saída do `leitor-relatorio` para as mesmas planilhas. Laudos
validado com dados sintéticos (nenhuma das duas planilhas de exemplo tem `TIPO DE LAUDO`).
**Bug real encontrado durante a validação:** células vazias (`PAGO`, `DATA`) viravam o texto `"nan"`
em vez de `None` ao serem importadas (pandas representa célula vazia como `NaN`/`NaT`, não `None`) —
isso fazia uma pendência já paga (`PAGO` em branco) ser contada como pendente por engano.
Corrigido com `cell_text()` em `app/utils.py`, com teste de regressão. Esse mesmo padrão de bug foi
corrigido nos três serviços (laudos, audiências, pendências) antes de fechar a Fase 3 — nenhum dos
três tinha esse tratamento até a validação com dados reais expor o problema em pendências.
**Decisão de modelagem:** `laudos.tipo_laudo_nome` ficou como texto livre (não FK para
`tipos_laudo`) e o valor é resolvido por nome normalizado no momento da geração do relatório, não
congelado no lançamento — mantém o mesmo comportamento do sistema atual (avisar tipo sem valor
cadastrado, mas não travar o relatório). Documentado em `DATABASE.md` seção 3.
**Reversível:** os ajustes de modelagem são simplificações registradas, não perdas de dado — dá para
migrar para FK/valor congelado depois se necessário.

## 2026-09-22 — Fase 3 validada em produção

**Contexto:** primeiro deploy real após conectar o `DATABASE_URL` do Supabase falhou no startup
(`ModuleNotFoundError: No module named 'psycopg2'`) — a connection string do Supabase vem no
formato genérico `postgresql://`, e o SQLAlchemy tenta o driver `psycopg2` por padrão nesse caso,
mas só `psycopg` (v3) estava instalado.
**Decisão:** normalizar a URL em `app/db.py` para sempre usar `postgresql+psycopg://`
independente do formato recebido, com testes cobrindo os formatos possíveis. Corrigido, deploy
confirmado funcionando (`/health` respondendo em produção, conectado ao Supabase real).
**Fase 3 encerrada.**

## 2026-09-22 — Fase 4: setores reais, papéis globais e segregação implementada

**Contexto:** a Clara respondeu as perguntas pendentes da Fase 4 (lista real de setores, se
empresa-cliente pertence às duas operadoras, o que "acesso especial" do T.I. significa).
**Decisões resultantes:**
- Setores reais confirmados: ELITE tem *Líder - Gestão de Processos*, *Doutores(as)*, *Admin/dona*
  e *Financeiro*; EXIMIA tem só *Financeiro*. Seeds em `app/db.py DEFAULT_SETORES`.
- `empresa_cliente` **não** tem `operadora_id`: confirmado que a mesma empresa-cliente é atendida
  pelas duas operadoras — pendência 2 (abaixo) resolvida, sem mudança de schema necessária.
- T.I. ganhou um segundo papel de alcance global, `ADMIN_TI` (mesmo alcance de dados do Admin
  Superior) — o modelo trocou o booleano `is_admin_superior` do rascunho da Fase 1 por
  `papel_global: NULL | 'ADMIN_SUPERIOR' | 'ADMIN_TI'`.
- Doutores(as)/Admin/dona confirmados como **só ELITE**, apesar de aparecerem como "ADVOGADA" nas
  planilhas de audiência (EXIMIA) — é só um registro histórico da planilha, não implica acesso.
**Implementação:** login por token opaco (não JWT, ver `SECURITY.md` seção 5), segregação aplicada
via dependency do FastAPI em toda rota de negócio, auditoria de ações-chave, bootstrap do primeiro
Admin Superior via variáveis de ambiente. 37 testes automatizados (unitários + API + permissões).
**Reversível:** o schema pode evoluir (ex.: adicionar `operadora_id` depois, se algum dia deixar de
ser verdade que toda empresa-cliente atende as duas operadoras) sem perda de dado.

## Pendências abertas

1. Política de retenção de dados pessoais (LGPD) — `SECURITY.md` seção 6, levar à Clara antes da
   Fase 5 (Gestão de Processos).
2. Rate limiting / bloqueio de tentativas de login — sem risco relevante no volume atual, mas fica
   registrado para um refinamento futuro.
3. `criado_por` em `laudos`/`audiencias`/`cobrancas` (rastreabilidade linha a linha, hoje só o
   import/geração fica no log de auditoria, não cada registro) — `DATABASE.md` seção 9.
