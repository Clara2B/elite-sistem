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

## 2026-09-22 — Fase 4 validada em produção; início da Fase 5

**Contexto:** depois de alguns problemas reais de infraestrutura no caminho (driver Postgres, URL do
pooler do Supabase quebrando o parser do Python 3.14, senha do banco com caractere reservado `@`,
connection string de "Direct connection" — IPv6, incompatível com o Render — em vez de "Session
pooler"), o deploy ficou estável e a Clara confirmou ter conseguido cadastrar os usuários principais
direto pela API em produção. Fase 4 encerrada.
**Decisão:** seguir para a Fase 5 (Gestão de Processos), começando pelo levantamento de requisitos
exigido pelo prompt mestre antes de qualquer código — não existe hoje nenhuma regra de negócio
documentada sobre esse domínio (ao contrário de laudos/audiências/pendências, que vieram de um
sistema existente auditável).

## 2026-09-22 — Fase 5: levantamento de requisitos da Gestão de Processos

**Contexto:** módulo sem precedente no sistema atual — nenhum código para auditar. Levantamento
feito em duas partes: perguntas diretas à Clara (tipo de processo, prioridades, quem usa) e análise
da planilha real `ELITE - GESTÃO DE PROCESSOS.xlsx` (21 abas, milhares de linhas de andamentos).
**Decisões resultantes:** ver `ARCHITECTURE.md` seção 3 e `DATABASE.md` seção 6.1 — resumo: data de
prazo fatal estruturada e obrigatória (para permitir alertas automáticos, que hoje não existem —
a equipe copia manualmente os itens urgentes para abas "fatais" à parte), `status_prazo` calculado
(não gravado), "processo parado" proposto como 15 dias sem novo evento (número inicial, ajustável),
`advogada`/`assistente` como texto livre por ora (não existe setor "Assistente" no modelo de
permissões da Fase 4), alerta de prazo dentro do sistema + e-mail (WhatsApp fica para depois).
**Reversível:** é uma proposta ainda não implementada — aguardando aprovação da Clara antes de
escrever qualquer código (ver plano em `ARCHITECTURE.md` seção 3.4).

## 2026-09-22 — Fase 5: `advogada`/`assistente` confirmados como texto livre; implementação concluída

**Contexto:** última pendência aberta da proposta da Fase 5 — se `advogada`/`assistente` deveriam
virar FK de `usuarios` (exigindo login) ou continuar texto livre. A Clara respondeu: "Os assistentes
não acessam o sistema, só seus líderes, mas pode manter apenas como texto pois eles aparecerão no
relatório".
**Decisão:** mantido como texto livre em `Processo.advogada`/`Processo.assistente` (pendência 4 da
lista abaixo, agora fechada). Com isso, a proposta inteira da Fase 5 foi implementada: modelos
`Processo`/`TipoEvento`/`EventoProcesso`, import da planilha real, relatório individual+geral
(texto e PDF com identidade ELITE), "prazos próximos" e alerta por e-mail (Resend, no-op sem
configurar `RESEND_API_KEY`/`RESEND_EMAIL_REMETENTE`).
**Achado durante a validação:** o mesmo defeito de desalinhamento de cabeçalho que já exigia uma
checagem de sanidade no número do processo (formato CNJ) também pôde jogar uma data de outra coluna
dentro de `ADVOGADA`/`ASSISTENTE` — um teste com a planilha real mostrou uma "pessoa" aparecendo
como `2025-12-03 00:00:00` no relatório. Mitigado com um guard (`_pessoa_valida`) que descarta
valores parecidos com data nesses dois campos, em vez de gravá-los como se fossem nome de pessoa.
**Validado com a planilha real** (`ELITE - GESTÃO DE PROCESSOS.xlsx`, 21 abas, 51.116 linhas
brutas): 44.333 eventos importados, 5.636 processos, 6.303 prazos fatais. 49 testes automatizados,
`ruff check .` limpo. `data_prazo` fica `None` em todo o histórico importado — só existe para
lançamentos feitos daqui pra frente, com data informada explicitamente (não há extração de data por
regex de texto livre, decisão já registrada na entrada anterior).
**Reversível:** sim — trocar `advogada`/`assistente` por FK de `usuarios` mais tarde é uma migração
de baixo risco, se/quando as assistentes também tiverem login próprio.

## 2026-09-22 — Fase 5: regra de `prazo_fatal` corrigida (bug real encontrado antes de produção)

**Contexto:** a implementação original marcava `prazo_fatal = true` sempre que a célula da coluna
`PRAZO FATAL` não estivesse vazia (`bool(texto)`) — o que faria qualquer texto, inclusive um
eventual `"NÃO"` escrito na célula, contar como fatal. Perguntei à Clara antes de assumir a regra.
**Resposta da Clara:** "se a coluna FATAL estiver como qualquer coisa que não seja SIM, então não é
fatal. Obs: o status fatal é sempre referente ao evento" — confirmando também que o campo pertence
ao evento (`eventos_processo.prazo_fatal`), não ao processo, que já era como o schema estava
modelado.
**Correção:** só o valor `SIM` (normalizado — ignora acento/caixa/espaço) marca o evento como fatal;
qualquer outro valor vira `false`. Coberto por teste com planilha real gerada em memória
(`test_import_prazo_fatal_so_quando_coluna_e_sim`, `openpyxl`), incluindo o caso `"NÃO"`. Ver
`DATABASE.md` seção 6.1 e `app/services/processos.py::importar_planilha`.
**Reversível:** sim, é lógica de import; não afeta dado já gravado (o dado real ainda não foi
importado em produção — pendência 4 abaixo).

## 2026-09-22 — Fase 5: alerta por e-mail removido; só dentro do sistema

**Contexto:** ao tentar validar a Fase 5 em produção pelo `/docs`, a Clara pediu pra tirar o alerta
por e-mail do escopo e deixar só o alerta dentro do sistema.
**Decisão:** removidos `app/email_alertas.py`, a rota `POST /processos/prazos-proximos/notificar`,
as funções `destinatarios_alerta`/`formatar_email_alerta` e as variáveis de configuração
`RESEND_API_KEY`/`RESEND_EMAIL_REMETENTE`. O painel `GET /processos/prazos-proximos` (alerta dentro
do sistema) continua como estava — não dependia do e-mail.
**Reversível:** sim, é uma extensão futura de baixo esforço reintroduzir o envio por e-mail (a
lógica de "quem recebe" e "como formatar" pode ser recriada do zero ou recuperada do histórico do
git) se a prioridade mudar.

## 2026-09-22 — Corrige botão "Authorize" ausente no `/docs`

**Contexto:** a Clara não estava achando o botão "Authorize" no Swagger (`/docs`) pra colar o token
de login, travando a validação manual da Fase 5 em produção. Causa raiz: `get_current_user`
(`app/auth.py`) lia o cabeçalho `Authorization` via `Header()` genérico — o FastAPI só desenha o
botão "Authorize" para dependências que declaram um esquema de segurança reconhecido (OAuth2,
API key, HTTP Bearer/Basic), então esse botão nunca existiu em nenhuma fase, mesmo com o `README.md`
descrevendo como se existisse.
**Correção:** trocado por `fastapi.security.HTTPBearer`, que registra o esquema no OpenAPI. Sem
mudança de comportamento pra quem já chama a API via `curl`/Postman com o cabeçalho manual — só
muda a experiência dentro do `/docs`, que agora tem o cadeado de verdade. `README.md` atualizado com
o passo a passo (colar só o token, sem o prefixo "Bearer").
**Reversível:** sim, mudança de infraestrutura de auth, sem impacto em dado.

## 2026-09-22 — Import de processos em produção deu 502; corrigido N+1 de empresa-cliente, causa raiz não confirmada

**Contexto:** ao testar `POST /processos/import` em produção com a planilha real, a Clara recebeu
`502 Bad Gateway` (erro do proxy do Render, não da nossa aplicação — sinal de processo travado ou
sem resposta a tempo, não uma exceção tratada). Investigando o código antes de arriscar um palpite:
encontrei que `get_or_create_empresa` (usada por todo import, `app/services/empresas.py`) faz uma
consulta ao banco percorrendo **todas** as empresas-clientes **a cada linha** — no import de
processos, isso significa uma ida-e-volta à rede (Supabase, via pooler) repetida para cada evento
processado, quando existem só ~43 empresas fixas no total. Em laudos/audiências/pendências isso
nunca doeu (poucas centenas/milhares de linhas por import); em processos, com um volume bem maior,
pode ser o suficiente pra estourar o tempo de resposta.
**Correção aplicada:** `get_or_create_empresa` ganhou um parâmetro `cache` opcional (dict
compartilhado durante o loop); `importar_planilha` (Fase 5) monta esse cache uma vez e reaproveita
em todas as linhas — elimina a consulta repetida para empresas já vistas. Também troquei o
`openpyxl.load_workbook` de `excel_reader.py` para `read_only=True` (bem mais leve em memória para
planilhas grandes) e passei a commitar a cada 2.000 linhas novas no import de processos, em vez de
uma única transação gigante no final.
**Importante — ainda não confirmado:** a Clara questionou o número "44.333 linhas" que eu tinha
reportado (validação local rodada antes da compactação do contexto desta sessão) — ela está vendo
uma aba com só ~2.500 linhas. Preciso confirmar com ela se o arquivo testado em produção é o mesmo
de 21 abas (44.333 é a soma de todas, não de uma aba só) ou um arquivo menor/diferente, porque isso
muda se o N+1 acima é de fato a causa do 502 ou só uma melhoria correta encontrada no caminho.
**Reversível:** sim, mudanças de performance sem alteração de comportamento/dado.

## 2026-09-22 — Fase 5: `mes_referencia` extraído do nome da aba da planilha

**Contexto:** a Clara pediu que o sistema identifique o mês de referência (ex. "SETEMBRO 2026") da
planilha subida. Perguntei onde essa informação mora e o que fazer com ela antes de implementar.
**Resposta da Clara:** o mês de referência é o **nome da aba** (ex. "SETEMBRO26"), não uma coluna
nem o nome do arquivo; o sistema deve só **guardar e mostrar** — sem travar o import nem filtrar
relatório por enquanto.
**Implementação:** novo campo `eventos_processo.mes_referencia` (string, ex. `"SETEMBRO/2026"`),
preenchido no import a partir do nome da aba (`_mes_referencia_da_aba` em
`app/services/processos.py`, ver `DATABASE.md` seção 6.1). Abas que não são nomeadas por mês (ex.
"DOCS E CUSTAS", abas "fatais") ficam com `mes_referencia = None` — não bloqueia o import, mesmo
tratamento das outras checagens de sanidade do módulo. Aparece no painel `prazos-proximos` e na
resposta de `POST /processos/eventos/{id}/resolver`.
**Migração de schema:** como o projeto não usa Alembic e a tabela `eventos_processo` já existe em
produção (mesmo vazia — nenhum import real teve sucesso até agora), adicionei um guard em
`app/db.py::_garantir_coluna` que roda um `ALTER TABLE ... ADD COLUMN` idempotente dentro de
`init_db()`, no próximo start do servidor — sem apagar nem alterar dado nenhum.
**Reversível:** sim, campo novo e nullable; não afeta o resto do schema.

## Nota sobre o número "44.333 linhas" (pendente de confirmação da Clara)

Reportei anteriormente que o import local processou 44.333 eventos a partir de "51.116 linhas
brutas" numa planilha de 21 abas. A Clara mostrou uma captura de tela de uma aba única com ~2.500
linhas e perguntou de onde veio esse número. Esclarecimento: **51.116 é a soma de todas as 21 abas**
(cada aba mensal/por advogada real tem algo em torno de 2 a 2,5 mil linhas — 21 × ~2.400 ≈ 51 mil),
não o tamanho de uma aba isolada. Essa validação foi rodada localmente, numa parte anterior desta
sessão, contra o arquivo `ELITE - GESTÃO DE PROCESSOS.xlsx` que a Clara enviou na época — o arquivo
não está mais disponível neste ambiente pra reconferir. **Ainda não confirmado** se o arquivo que
ela está testando agora em produção é o mesmo (21 abas) ou um arquivo diferente/menor — relevante
porque muda se a correção de N+1 da entrada acima é de fato a causa do 502 relatado.
**Atualização:** a Clara confirmou que é o mesmo arquivo de 21 abas, e testou de novo depois do
deploy — o 502 sumiu (a correção de N+1 resolveu). Apareceu um erro novo, tratado na entrada abaixo.

## 2026-09-22 — Corrige linhas de tamanho desigual no modo `read_only` do openpyxl

**Contexto:** depois da correção do N+1 (entrada acima), o import real não deu mais 502, mas passou
a dar `400` com `"X columns passed, passed data had Y columns"` — um erro do pandas ao montar o
DataFrame. Causa: o modo `read_only=True` do openpyxl (ligado na correção anterior pra economizar
memória) não garante que toda linha de uma aba tenha o mesmo número de células — uma linha sem
célula preenchida no fim vem "cortada" (tupla mais curta), refletindo só o que está escrito naquele
trecho do XML da planilha real, diferente do modo padrão do openpyxl (que sempre preenche até a
última coluna usada na aba inteira, reconstruindo a grade inteira em memória). Isso é conhecido do
openpyxl em modo somente leitura e mais comum em arquivos gerados por outra ferramenta que não o
próprio openpyxl (ex. Excel, exportação do Google Sheets — a planilha real da Clara parece vir de
um desses).
**Correção:** nova função `_normalizar_larguras` (`app/excel_reader.py`) — completa toda linha até o
tamanho da mais larga da aba com `None` antes de montar o DataFrame. Coberta por teste unitário
direto (não depende de conseguir gerar um arquivo .xlsx com linhas desiguais via openpyxl, que
sempre escreve larguras uniformes — por isso testei a função isolada com tuplas de tamanhos
diferentes construídas à mão).
**Reversível:** sim, correção pura de parsing, sem mudança de dado.

## 2026-09-23 — `advogada`/`assistente`/`nome_cliente`/`tipo_evento_nome` viram Text (sem limite)

**Contexto:** depois da correção anterior, o import real deu um erro novo — 500 com
`sqlalchemy.exc.DataError`. A Clara colou o log completo do Render, que mostrou a causa exata:
`psycopg.errors.StringDataRightTruncation: value too long for type character varying(80)` ao
inserir em `processos`, coluna `advogada`, com o valor `'HUNTING - MARIA DULCE CARDOSO DOS SANTOS
(CONTR. LUIZ FERNANDO PAULINO DOS SANTOS)'` (84 caracteres) — bem mais longo do que os nomes simples
("DRA KELLY", "DANILO") que eu previ ao desenhar o campo como `VARCHAR(80)`.
**Correção:** `Processo.nome_cliente`, `Processo.advogada`, `Processo.assistente` e
`EventoProcesso.tipo_evento_nome` trocados de `String(N)` para `Text` (sem limite) — todos texto
livre vindo da mesma planilha real, que já se mostrou consistentemente mais "rica" em conteúdo do
que o desenho original previu (mesmo padrão do problema do `mes_referencia`/aba desalinhada
encontrado antes). Migração idempotente `_garantir_texto_ilimitado` (`app/db.py`) roda
`ALTER TABLE ... ALTER COLUMN ... TYPE TEXT` no próximo start do servidor, só no Postgres (SQLite
dos testes não aplica limite de VARCHAR de verdade, sem impacto ali).
**Por que não também limitei o texto em vez de alargar:** truncar silenciosamente um nome de
cliente ou de advogada geraria dado errado (um nome cortado no meio) sem avisar ninguém — pior do
que simplesmente guardar o texto inteiro. `Text` no Postgres não tem custo de performance relevante
nesse volume comparado a `VARCHAR(N)`.
**Reversível:** sim, campo mais permissivo, não descarta nem altera dado nenhum já gravado.

## Pendências abertas

1. Política de retenção de dados pessoais (LGPD) — `SECURITY.md` seção 6. Ainda mais relevante
   agora: processos judiciais carregam nome completo + número de processo (pode revelar o tipo de
   ação). Não foi perguntado explicitamente na Fase 5 — levar à Clara antes de ir para produção
   com dados reais de processos.
2. Rate limiting / bloqueio de tentativas de login — sem risco relevante no volume atual, mas fica
   registrado para um refinamento futuro.
3. `criado_por` em `laudos`/`audiencias`/`cobrancas` (rastreabilidade linha a linha, hoje só o
   import/geração fica no log de auditoria, não cada registro) — `DATABASE.md` seção 9.
4. Validar o import de Gestão de Processos (Fase 5) via API já em produção, com a planilha real da
   Clara — a validação até aqui foi só local.
