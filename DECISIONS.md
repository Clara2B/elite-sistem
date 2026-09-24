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

## 2026-09-23 — Validação com a planilha "padronizada" da Clara + abreviação de mês nas abas antigas

**Contexto:** a Clara padronizou a planilha real e pediu pra eu checar se isso ajudava nos problemas
de leitura. Rodei o import completo (`importar_planilha`) localmente contra o arquivo novo.
**Resultado:** import completo sem erro — todas as correções anteriores (N+1, memória do openpyxl,
linhas desiguais, `Text` sem limite) seguram bem com o arquivo padronizado. Números: 44.344 eventos
novos, 5.636 processos, 2.147 prazos fatais (bem menor que os 6.303 de antes — esperado, é o efeito
combinado da correção da regra "só SIM é fatal" e da própria Clara ter passado a preencher "NÃO"
explicitamente em vez de deixar em branco).
**Achado durante a validação — corrigido:** várias abas mais antigas usam abreviação de 3 letras no
nome (`JUN-25`, `JUL-25`, `AGO-25`, `SET- 25`, `OUT- 25`) em vez do nome completo do mês — o
`_mes_referencia_da_aba` só reconhecia nome completo, então essas abas ficavam sem
`mes_referencia`. Estendido pra aceitar as 12 abreviações (JAN, FEV, MAR, ABR, MAI, JUN, JUL, AGO,
SET, OUT, NOV, DEZ). Cobertura de `mes_referencia` subiu de 61% para 76% dos eventos (o resto é
esperado — abas não nomeadas por mês, como "DOCS E CUSTAS" e as abas por advogada, continuam sem
esse campo por design).
**Achado durante a validação — não corrigido, é dado da planilha, não bug do parser:** nas abas
"JANEIRO26" e "Dra Galzo", a primeira célula do cabeçalho (que devia dizer "ASSISTENTE") tem um
número de processo escrito nela por engano — faz essas duas abas perderem a coluna de assistente
inteira (contribui para os 2.654/5.636 processos sem assistente). Não é algo que o parser deveria
"adivinhar" — é um erro de digitação na própria planilha; melhor avisar a Clara do que tentar
inferir automaticamente qual coluna era a pretendida.
**Reversível:** sim, extensão de regex sem mudança de comportamento pra abas já reconhecidas.

## 2026-09-23 — Fase 5 validada em produção; encerrada

**Contexto:** depois de corrigir JANEIRO26/Dra Galzo na própria planilha, a Clara testou
`POST /processos/import` em produção (Render) com o arquivo real completo, pelo `/docs`.
**Resultado:** `200 OK`, sem nenhum erro — 51.126 linhas lidas, ~44 mil eventos novos, 8 linhas já
existentes (do teste anterior local não afeta produção, mas confirma que a checagem de duplicidade
funciona), 6.278 sem número de processo válido, 484 sem empresa reconhecida (ambos os contadores de
sanidade já esperados e documentados). Números batendo com a validação local.
**Decisão:** Fase 5 (Gestão de Processos) encerrada — import, relatórios (individual/geral, texto e
PDF), painel de prazos próximos e todas as correções de robustez confirmadas de ponta a ponta, em
produção, com dado real. Modelo do relatório aprovado por ora (pendência 4 abaixo, revisar depois a
pedido da Clara).

## 2026-09-23 — D2 (frontend): Jinja2 + HTMX, todas as telas de uma vez

**Contexto:** o sistema só tinha API + `/docs` (Swagger) até aqui — a Clara pediu a parte visual de
verdade, dizendo que o sistema ainda não está "profissional e funcional" como pedido. A decisão D2
original (`ARCHITECTURE.md` seção 2.3/2.7) já tinha aprovado "backend API + frontend próprio", mas
deixou em aberto a escolha entre Jinja2+HTMX (tudo em Python) ou React/Next.js.
**Decisão da Clara:** Jinja2 + HTMX (recomendado — sem stack JS separada, permissão por rota
reaproveitada do backend, menos custo de manutenção); construir as telas de todos os módulos de uma
vez (Laudos, Audiências, Pendências, Gestão de Processos, Administração), não módulo a módulo;
reaproveitar a identidade visual já usada nos PDFs (azul-marinho `#152A40`, logos ELITE/EXIMIA).
**Plano:** layout base (navegação, cores) + login com sessão por cookie HttpOnly primeiro; depois
uma tela por módulo, reaproveitando os endpoints de API já prontos (nenhuma rota de negócio nova
necessária — a interface só consome o que já existe).
**Reversível:** sim, é a camada de apresentação; a API por trás fica intacta e continua funcionando
para automações futuras (Fase 7) independente do frontend.

## 2026-09-23 — Fase 6 (interface visual) implementada, validada localmente

**Construído:** login por cookie de sessão, menu dinâmico por permissão, e uma tela por módulo
(Laudos, Audiências, Pendências, Gestão de Processos, Usuários) — todas consumindo os endpoints de
API já existentes, sem duplicar regra de negócio. Ver `ARCHITECTURE.md` seção 4 pro detalhe completo
do que foi construído e dos três bugs achados e corrigidos no caminho (`PrazoProximo` sem
`evento_id`, cookie `expires` exigindo timezone, PDF não baixando de verdade).
**Validação:** `tests/test_web.py` (7 testes novos, 63 no total) + navegação ponta a ponta com
Playwright/Chromium local, usando a planilha real de Gestão de Processos como dado de teste —
login, as 5 telas, gerar relatório, baixar PDF pelo navegador (via cookie, não Bearer), criar
usuário com setor, ativar/desativar usuário. Capturas de tela conferidas visualmente antes de
reportar como pronto (instrução do projeto: nunca declarar uma mudança de UI pronta sem ver rodando
num navegador).
**Ainda não visto pela Clara:** a interface roda só localmente até aqui — falta ela ver rodando em
produção depois do deploy.
**Reversível:** sim, mudanças aditivas (rotas novas sob `/app/...`, um endpoint `GET /empresas`
novo); nada do que já existia foi alterado em comportamento.

## 2026-09-23 — Corrige N+1 real em `gerar_relatorio`/`prazos_proximos` (tela de processos "muito lenta")

**Contexto:** a Clara reportou que a tela de Gestão de Processos ficou muito lenta em produção.
Investigando `app/services/processos.py::gerar_relatorio` (chamada por padrão ao abrir
`/app/processos`, sem filtro): o código faz `for processo in db.scalars(select(Processo))` e acessa
`processo.eventos` duas vezes por processo — sem eager loading, cada acesso a uma relação ainda não
carregada dispara uma consulta nova ao banco (lazy load). Com ~5.636 processos, isso é até ~11 mil
consultas separadas numa única requisição, cada uma pagando a latência de rede até o Supabase (via
pooler) — exatamente o tipo de problema já visto antes (Fase 5, N+1 de empresa-cliente no import).
`prazos_proximos` tinha o mesmo padrão, acessando `evento.processo` por evento.
**Correção:** `selectinload(Processo.eventos)` e `selectinload(EventoProcesso.processo)` nas duas
consultas — troca N+1 consultas por 2 (uma pros processos/eventos, uma batched pra relação). Medido
localmente com a planilha real (5.636 processos, ~28 mil eventos no ano): **13 consultas no total**
pra gerar o relatório geral do ano inteiro, nenhuma delas cresce com o número de processos.
**Reversível:** sim, só otimização de consulta — mesmo resultado, muito mais rápido.

## 2026-09-23 — Mesmo N+1 encontrado (e corrigido) em Laudos, Audiências e Pendências

**Contexto:** logo depois da correção acima, a Clara reportou lentidão em "nível de preocupação
extrema" no sistema inteiro, não só em Gestão de Processos. Fui direto conferir se o mesmo padrão
de bug (N+1 de `get_or_create_empresa`) existia nos outros três importadores — existia, sem cache,
nos três: `laudos.py`, `audiencias.py`, `pendencias.py` chamavam
`get_or_create_empresa(db, empresa_nome)` dentro do loop de cada linha da planilha, sem o parâmetro
`cache` (só `processos.py` tinha sido corrigido na Fase 5, porque foi lá que o problema apareceu
primeiro). Isso explica provavelmente os dois sintomas reportados: lentidão geral (qualquer import
de planilha grande vira centenas/milhares de consultas separadas ao Supabase) e "Audiências não
está gerando" (o import provavelmente estava só muito lento, não quebrado — sem feedback visual de
progresso, uma espera de vários minutos parece uma tela travada).
**Correção:** mesmo cache compartilhado já usado em `processos.py`, agora nos quatro importadores.
**Reversível:** sim, só otimização — mesmo resultado, muito mais rápido.
**Pendente:** confirmar com a Clara que a lentidão melhorou depois desse deploy, e voltar em
Audiências especificamente para confirmar se "não estava gerando" era só isso ou se tem outro
problema por trás.

## 2026-09-23 — Tela de Empresas-clientes + redesign visual (sidebar, ícones, cards)

**Contexto:** a mesma mensagem que reportou a lentidão trouxe dois outros pedidos: faltava uma tela
pra gerenciar empresas-clientes (nome, CNPJ, ativar/desativar) e o visual estava "esteticamente
muito simples, nada moderno".
**Empresas-clientes:** só existia leitura (`GET /empresas`, usada pelos seletores das telas de
relatório). Adicionado `POST /empresas`, `PATCH /empresas/{id}` e `PATCH /empresas/{id}/ativo`
(`app/api/empresas.py`, `app/services/empresas.py`) — restrito a Admin Superior/T.I., mesma regra
já usada em `/usuarios`/`/setores` (dado compartilhado por todo o sistema, não específico de um
módulo). Tela em `/app/empresas` com edição inline por linha da tabela.
**Redesign visual:** troquei a navegação de barra no topo para uma sidebar fixa à esquerda (padrão
mais comum em ferramentas internas modernas — Linear, Stripe dashboard, etc.), com ícones SVG
inline por módulo (sem depender de fonte de ícone externa, que precisaria de CDN). Refinei sombras,
raio de borda, hierarquia tipográfica e paleta (mantendo o azul-marinho como cor primária, por
decisão já fechada). Como a mudança ficou concentrada em `style.css`/`base.html`, as páginas dos
módulos herdaram o visual novo automaticamente, sem precisar reescrever cada uma.
**Validação:** `tests/test_web.py` ganhou 3 testes novos (criar/editar/desativar empresa, nome
duplicado, página restrita a admin — 66 testes no total) + navegação visual conferida com
Playwright/Chromium local antes de reportar como pronto.
**Reversível:** sim, mudança de camada de apresentação e um recurso administrativo aditivo — nada
do que já existia foi alterado em comportamento.

## 2026-09-23 — Polimento de UI (upload, toasts, exclusão de empresa) + bug de validação nativa

**Contexto:** feedback pós-deploy do redesign: botão de voltar em toda tela, upload de planilha
"muito feio", pop-up de erro "antigo de sistema velho" (a bolha nativa do navegador), homepage mais
produzida no menu, e exclusão definitiva de empresa-cliente com confirmação de perigo.
**Toasts vs. aviso inline:** ao transformar `.mensagem` de banner fixo em toast flutuante,
identifiquei que um uso existente (tipo de laudo sem valor cadastrado, dentro do card de
resultado do relatório) precisa continuar fixo no lugar — não faz sentido ele flutuar e desaparecer
como um toast de sucesso/erro de ação. Criada a classe separada `.aviso-inline` pra esse caso, sem
virar toast.
**Bug real achado ao trocar a bolha nativa por toast:** a validação HTML5 nativa do navegador nunca
dispara o evento `submit` de um formulário quando um campo `required` está vazio — ela intercepta e
aborta antes disso. Um listener de `submit` que só mostrasse o toast nesse momento nunca seria
chamado. Corrigido com `form.noValidate = true` nos formulários de import (únicos com esse padrão;
não têm outro campo obrigatório além do arquivo) + validação manual em `app.js`, confirmado com
Playwright que o toast aparece de verdade agora (antes o teste visual mostrava a mesma tela, sem
toast, comprovando o bug).
**Exclusão definitiva de empresa-cliente:** a pedido explícito da Clara ("apagar por completo").
Ficou de fora da tela de "ativar/desativar" já existente porque apagar é irreversível — bloqueado
no backend se houver laudo/audiência/cobrança/processo vinculado (evita apagar histórico que não
era o alvo direto do pedido), com confirmação obrigatória num `<dialog>` estilizado (não
`window.confirm()`, que não é estilizável) antes do POST.
**Validação:** `tests/test_web.py` ganhou 2 testes novos (exclusão sem vínculos, exclusão bloqueada
com laudo vinculado — 68 testes no total) + verificação visual com Playwright/Chromium local,
incluindo a captura que comprovou o bug da validação nativa antes da correção.
**Reversível:** sim — mudança de camada de apresentação, mais um recurso administrativo aditivo e
irreversível apenas quando o próprio usuário confirma explicitamente no modal.

## 2026-09-23 — Cache-busting de estáticos + log de tempo de requisição

**Contexto:** a Clara testou o deploy anterior (exclusão de empresa) e mandou print do modal de
exclusão sem nenhum estilo — borda preta padrão do navegador, sem sombra, cantos arredondados nem
ícone colorido, só os botões com o CSS antigo (`.perigo`/`.secundario`, que já existiam antes desse
deploy). Isso é a marca registrada de CSS em cache — localmente, com Playwright, o mesmo arquivo
renderizava perfeito (mesma captura já mandada antes pra ela), então o problema nunca foi o CSS em
si, foi o navegador (ou algum proxy no caminho) continuar servindo a versão anterior de
`/static/style.css`, porque a URL nunca mudava entre deploys.
**Decisão:** hash do conteúdo de `style.css`/`app.js`, calculado uma vez na inicialização do
processo (`app/web/templates.py::_versao_estatico`) e usado como `?v=<hash>` nos links desses
arquivos em `base.html`/`login.html`. Cada deploy que muda o conteúdo gera uma URL nova
automaticamente — não depende de lembrar de bumpar uma versão manualmente, nem depende de
configurar headers de cache num CDN que eu não controlo diretamente.
**Log de tempo de requisição:** a mesma mensagem trouxe "o sistema todo está muito devagar, tudo
que clico demora muito pra carregar" — mais amplo que só o import, e sem conseguir reproduzir
localmente. Como não existia nenhum log de tempo, cada relato de lentidão até agora dependia de
pedir pra Clara copiar o log do Render manualmente e adivinhar onde olhar. Adicionado um middleware
simples (`app/main.py::_medir_tempo_de_requisicao`) que loga método, caminho, status e duração de
toda requisição — aparece direto nos logs do Render (stdout), sem precisar instrumentar nada extra
da próxima vez que isso for reportado.
**Hipótese não confirmada:** o padrão descrito ("tudo demora") é consistente com o plano gratuito
do Render "dormir" por inatividade (`ARCHITECTURE.md` seção 2.8) — a primeira requisição depois de
um tempo parado pode levar dezenas de segundos pra acordar o serviço. Não é uma correção de código;
se for confirmado, é uma decisão de custo (upgrade de plano) que cabe à Clara, não algo que eu
resolvo sozinho.
**Validação:** `ruff check`/`pytest -q` (68 testes, sem mudança de contagem — é infraestrutura, não
comportamento novo) + verificação visual local confirmando que a URL do CSS carrega `?v=<hash>` e o
modal volta a renderizar estilizado.
**Reversível:** sim, mudança de infraestrutura (cache-busting e logging), sem efeito em dado ou
comportamento de negócio.

## 2026-09-23 — Reimport de andamento vira "upsert" + filtro por assessoria

**Contexto:** a Clara reimportou a planilha de Gestão de Processos e viu "0 evento(s) novo(s), 44353
já existiam de antes" — apontou que mesmo um cliente já citado antes deve ter sua última
atualização puxada para o período em questão. Junto, pediu um filtro de relatório por assessoria
(primeira palavra antes do nome, na coluna `ADVOGADA`).
**Risco considerado antes de implementar:** essa é uma mudança em como o import lida com ~44 mil
registros de produção já gravados (prazos de processos judiciais reais) — errar a semântica poderia
sobrescrever silenciosamente um dado correto ou desfazer um `resolvido` marcado manualmente pela
equipe. Por isso a regra ficou deliberadamente conservadora: só atualiza um campo quando a linha
nova traz valor preenchido (célula vazia nunca apaga o que já estava lá) e nunca toca em
`resolvido`/`resolvido_em`/`data_prazo`, que são estado operacional controlado dentro do sistema,
não vindo da planilha.
**Import "upsert":** `eventos_existentes` (usado pra detectar duplicata) deixou de ser um set de
chaves e virou um dict pro objeto, permitindo atualizar `observacao`/`prazo_fatal`/`mes_referencia`
quando a chave (processo+data+tipo de evento) já existe, em vez de só contar e ignorar.
`Processo.nome_cliente` passou a ser atualizado com o lançamento mais recente, estendendo o mesmo
padrão que `advogada`/`assistente` já seguiam desde a Fase 5.
**Campo `assessoria`:** extraído da coluna `ADVOGADA` no import (`_separar_assessoria`,
`"HUNTING - Fulana de Tal"` → `"HUNTING"`) — `advogada` continua com o texto original, sem o prefixo
removido. Adicionado como terceiro valor de `agrupar_por` no relatório, reaproveitando o campo de
filtro "pessoa" já existente na tela em vez de criar um controle novo.
**Validação:** 7 testes novos em `tests/test_processos_service.py` (75 no total) cobrindo a extração
de assessoria, o agrupamento por assessoria no relatório, a atualização de evento existente com dado
novo, a proteção contra célula vazia apagando dado, `resolvido` nunca desfeito pelo import, e a
atualização de `nome_cliente` — + verificação visual local do filtro e da mensagem de import.
**Reversível:** sim — campo novo aditivo (migração idempotente, mesmo padrão já usado pra
`mes_referencia`) e o import fica mais permissivo (atualiza em vez de ignorar), nunca menos seguro:
nenhum dado é apagado, e o estado operacional (`resolvido`/prazo) segue imune ao import.

## 2026-09-23 — "Internal Server Error" em branco no import de audiências

**Contexto:** a Clara importou uma planilha de audiências e recebeu uma página em branco do
navegador com só "Internal Server Error" — sem estilo, sem mensagem, sem nada. Sem acesso ao log do
Render do momento exato, não dá pra confirmar 100% a causa, mas o padrão bate exatamente com um bug
já resolvido uma vez neste projeto.
**Hipótese forte (não 100% confirmada):** `Audiencia.nome_cliente`/`data_agendamento`/
`conciliadora`/`advogada` continuavam `VARCHAR(N)`, e a Fase 5 já mostrou que a coluna `ADVOGADA`
dessa mesma planilha/equipe carrega texto tipo `"HUNTING - Fulana de Tal (CONTR. Beltrano)"`
(84+ caracteres) — exatamente o que já causou `StringDataRightTruncation` em `processos` antes.
Ninguém tinha auditado se `audiencias` (planilha de origem diferente, mas provavelmente preenchida
pela mesma equipe) tinha o mesmo padrão de dado. Convertidos os quatro campos pra `Text`, mesmo
tratamento e mesma migração aditiva (`_garantir_texto_ilimitado`) já usada em `processos`.
**Corrigido também, independente de confirmar a causa raiz acima:** a rota só capturava
`ValueError` — qualquer outro erro (esse `DataError` incluído) derrubava a request sem handler
nenhum. Adicionado `@app.exception_handler(Exception)` global (`app/main.py`) que loga o traceback
completo nos logs do Render e devolve `erro.html` (a mesma página estilizada já usada pro 403) em
rotas de tela, e JSON genérico em rotas de API (pra não quebrar clientes que esperam JSON). Efeito:
qualquer bug futuro não tratado — não só esse — já aparece decente pra Clara e com traceback
completo pra mim, em vez de repetir esse susto.
**Achado ao testar:** um handler registrado pra `Exception` (a classe base) no Starlette vai pra
`ServerErrorMiddleware`, a camada mais externa — funciona certinho contra um navegador/uvicorn de
verdade, mas o `TestClient` dos testes, por padrão, relança a exceção mesmo assim (é um alarme
deliberado de "bug não tratado"). Os dois testes desse handler usam `TestClient(...,
raise_server_exceptions=False)` especificamente, pra testar o comportamento real (resposta pro
cliente), não o alarme de debug.
**Validação:** 2 testes novos em `tests/test_web.py` (erro genérico em rota de tela vs. rota de
API) + 2 testes novos em `tests/test_audiencias_service.py` (schema `Text` não `VARCHAR`; import
com `ADVOGADA` longa não quebra) — 79 testes no total. Verificação visual local: import de
audiências com `ADVOGADA` de 90+ caracteres funcionando ponta a ponta; `erro.html` (caso 403)
continua igual.
**Reversível:** sim — campo mais permissivo (nunca menos seguro) e handler de erro aditivo, que só
muda o que acontece quando já ia dar erro sem tratamento nenhum.

## 2026-09-23 — Causa raiz confirmada: era `cpf`, não `advogada`

**Contexto:** a Clara mandou o log real do Render pouco depois da entrada acima — o import de
audiências deu erro de novo, mesmo depois do deploy que converteu `nome_cliente`/
`data_agendamento`/`conciliadora`/`advogada` pra `Text`.
**O log mostrou a causa exata:** `StringDataRightTruncation: value too long for type character
varying(20)`. De todos os campos de `audiencias`, só `cpf` continuava `VARCHAR(20)` — os outros
quatro (já convertidos na entrada anterior) não bateriam com esse "(20)" no erro. A célula de CPF na
planilha real às vezes tem mais que um CPF formatado (14 caracteres) — provavelmente dois titulares
na mesma linha, ou uma anotação junto. Minha suposição inicial (que seria `advogada`, pelo padrão já
visto em `processos`) não estava de todo errada como raciocínio — só não era a coluna certa dessa
vez. `cpf` também virou `Text`.
**Lição:** quando a causa exata não está confirmada (sem acesso a log de produção), vale registrar
isso como hipótese explicitamente — o que a entrada anterior já fazia — e corrigir de novo, rápido,
assim que o dado real (o log) chegar, em vez de insistir na hipótese original.
**Validação:** teste novo em `tests/test_audiencias_service.py` (import com `CPF` de texto longo,
reproduzindo o caso real — 80 testes no total) + `cpf` incluído na checagem de schema já existente.
**Reversível:** sim — mesmo campo mais permissivo, mesma categoria de mudança da entrada anterior.

## 2026-09-23 — Import de planilha lento: dois achados medidos, não adivinhados

**Contexto:** a Clara pediu "o sistema precisa ler os arquivos em planilha mais rápido". Em vez de
tentar mais uma correção às cegas (já tinha corrigido a causa errada uma vez nessa mesma sessão, ver
entrada acima), gerei planilhas sintéticas do tamanho e formato da planilha real (ver ARCHITECTURE.md
seção 3.5 — ~45 mil linhas, ~5.600 processos; e uma versão de 21 abas, a maioria sem os cabeçalhos
exigidos, imitando a estrutura real descrita na seção 6 do DATABASE.md) e medi o import ponta a
ponta antes e depois de cada mudança, local, sem depender do log de produção dessa vez.
**Achado 1:** `importar_planilha` (processos) dava `db.flush()` a cada `Processo` novo criado, só
pra ter `.id` disponível na mesma linha. Num import de ~45 mil linhas/~5.600 processos novos, isso é
~5.600 idas e vindas ao banco em vez de umas poucas dúzias. Corrigido trocando a chave de
deduplicação de evento pra usar `numero_processo` (já vem na própria linha) em vez de `processo.id`,
e criando o evento novo via `EventoProcesso(processo=processo, ...)` (o relacionamento do
SQLAlchemy) em vez de `processo_id=processo.id` — o SQLAlchemy resolve a FK sozinho no próximo
flush, mesmo que o processo ainda não tenha ido pro banco. Medido: 17,7s → 14,3s localmente (SQLite,
sem rede — Supabase em produção deve ganhar proporcionalmente mais, cada flush ali sendo uma
ida-e-volta de rede de verdade).
**Achado 2:** `load_data_sheets` (`app/excel_reader.py`, usado pelos quatro importadores) lia cada
aba inteira antes de checar se ela tinha os cabeçalhos exigidos — numa planilha real de ~21 abas, a
maioria (dashboard, resumo, abas "fatais" sem o formato certo) era lida por inteiro só pra ser
descartada. Corrigido: só as 5 primeiras linhas de cada aba (o que a checagem de cabeçalho já
olhava) são lidas antes de decidir se vale ler o resto. Medido com arquivo de 21 abas (6
relevantes): `load_data_sheets` sozinho 4,96s → 3,29s; import completo 31,3s → 15,9s — quase metade.
**Log de diagnóstico:** `load_data_sheets` e os quatro `importar_planilha` agora logam sua própria
duração (mesmo canal do middleware de tempo de requisição já existente), separando parse do arquivo
vs. resto do import. Sem isso, "a planilha demora" só dava pra investigar adivinhando de novo.
**Validação:** 1 teste novo em `tests/test_processos_service.py` cobrindo o cenário exato que a
mudança do `db.flush()` afeta (dois eventos de um processo novo na mesma planilha, ainda sem `.id`,
precisam se ligar ao mesmo processo) — 81 testes no total, nenhum existente quebrou. Verificação
ponta a ponta local via navegador com arquivo de 21 abas/36 mil linhas — log confirmando a duração
de cada fase.
**Reversível:** sim — mesmo comportamento de import (mesmos dados gravados, mesmas regras), só
menos idas e vindas ao banco e menos leitura desperdiçada.

## 2026-09-24 — Log real revela a causa maior: tela de Processos recarregava tudo sempre

**Contexto:** a Clara mandou o log real do Render depois do deploy anterior. Ele mostrou dois números
que eu não esperava: `GET /app/processos` levando 13-15s **sem nenhum import acontecendo**, e o
import de verdade (51.129 linhas, 22 abas) levando 169,8s (48,9s parse + 120,9s resto). Montei um
Postgres local (já vinha instalado neste ambiente) com o mesmo volume de dado da planilha real
(~5.600 processos, ~45 mil eventos) pra medir contra algo mais parecido com produção que SQLite.
**Achado principal:** a rota `GET /app/processos` chama `gerar_relatorio()` com o período padrão
toda vez que a tela abre — não só quando alguém pede um relatório — e essa função carregava **todos**
os processos e **todos** os eventos de sempre (com `selectinload`, que ainda dividia isso em ~13
idas e vindas ao banco), filtrando por período só depois, em Python. Corrigido: a consulta agora
filtra por data direto no SQL, trazendo só os eventos do período pedido; a contagem de "processo
parado" (que precisa do último evento de *toda* a história, não só do período) virou uma consulta
agregada separada e leve, restrita aos processos já relevantes. Medido: 13 consultas/1,1-1,6s → 7
consultas/0,14-0,2s localmente contra Postgres de verdade — em produção, com latência de rede real
Render↔Supabase, a diferença deve ser bem maior.
**Achado secundário:** `prazos_proximos()` filtra por `data_prazo IS NOT NULL`, mas nada no sistema
preenche `data_prazo` hoje (só fica pronto pra lançamento manual futuro) — ou seja, sempre devolve
zero linhas, mas varria a tabela inteira sem índice pra chegar nisso. Testado: nem com nem sem
índice isso foi lento o bastante (<50ms com ~45 mil linhas) pra ser a causa principal dos 13-15s —
mas ganhou um índice parcial mesmo assim (`_garantir_indice_prazos_fatais`), seguro e barato, e que
pode importar mais com o banco sob carga real ou uma tabela maior.
**O que ainda não foi resolvido:** o import da planilha real em si continua pesado — carrega todos
os processos/eventos já existentes no banco (não só os do arquivo) pra decidir o que é novo. Medido
localmente contra Postgres, reproduzindo o cenário real (importar o mesmo arquivo duas vezes, "quase
tudo já existe"): ~8,65s sem nenhuma latência de rede. Os ~120s vistos em produção batem com latência
de rede real movendo dezenas de milhares de linhas, não com um bug — o trabalho já se mostrou rápido
localmente até contra Postgres de verdade. Uma correção mais profunda (upsert direto no SQL, sem
carregar tudo em objetos Python antes de comparar) reduziria isso ainda mais, mas mexe num caminho de
dado de produção real (prazos de processos judiciais) com mais risco — fica como pendência em aberto
(item novo abaixo), não implementada nesta rodada.
**Validação:** 2 testes novos em `tests/test_processos_service.py` (83 no total) — "processo parado"
considera a história inteira, não só o período do relatório; e um teste que trava a contagem de
consultas SQL, pra pegar de volta qualquer mudança futura que volte a carregar a tabela inteira.
Validado contra Postgres local de verdade (não só SQLite), com contagem real de consultas SQL antes/
depois de cada correção — não foi só medir tempo, foi confirmar a causa.
**Reversível:** sim — mesmo resultado de relatório (só a consulta mudou), índice é aditivo.

## 2026-09-24 — Datas erradas no relatório de Laudos: coluna errada lida no import

**Contexto:** a Clara comparou o relatório de Laudos da ABSOLUTA linha por linha com a planilha real
e achou datas erradas em 3 das 6 linhas — as datas erradas batiam exatamente com uma das outras
colunas de data mais à direita na planilha (prazo/entrega), não com a coluna A (entrada do laudo).
**Causa:** o import buscava a data pelo nome do cabeçalho (`_col(df, "DATA")`) no DataFrame já
unificado de todas as abas. Quando mais de uma coluna cai no mesmo nome canônico "DATA" (a ordem das
colunas varia de aba pra aba na planilha real — mesma classe de defeito já visto em Gestão de
Processos), a busca por nome pode resolver pra uma coluna diferente dependendo de qual aba a linha
veio, só nalgumas abas.
**Corrigido:** a Clara confirmou que a coluna A é sempre a data certa. `load_data_sheets` passou a
guardar o valor bruto da coluna A por posição (`_COL_A`), e o import de laudos usa esse valor quando
ele é uma data válida, caindo pro nome "DATA" só quando a coluna A não é uma data (protege layouts
onde a coluna A é outra coisa — um teste já existente com "EMPRESA" na coluna A provou isso ao
continuar passando sem mudança).
**Risco considerado:** cheguei a implementar uma versão que ignorava o nome completamente e sempre
lia a coluna A — quebrou um teste existente (`test_import_e_relatorio_via_api`, que tem "EMPRESA" na
coluna A, um layout plausível diferente do da Clara). Isso mostrou que a suposição "coluna A é
sempre data" não é universal o bastante pra virar regra fixa — daí o fallback condicional (só usa
coluna A quando ela mesma é uma data) em vez de substituir a lógica de nome por completo.
**Pendência importante:** esse conserto vale só pra importações novas — laudos já importados com
data errada continuam errados no banco. Simplesmente reimportar o mesmo arquivo hoje criaria um
registro novo (data certa) sem remover o antigo (data errada), já que a data faz parte da chave de
duplicidade do import — duplicaria em vez de corrigir. Não fiz nenhuma limpeza de dado existente
nesta rodada — é dado real de faturamento, e "quais registros corrigir/apagar" não é uma decisão
técnica pra tomar sozinho. Perguntar à Clara como ela quer corrigir o que já foi importado errado.
**Validação:** 2 testes novos (`tests/test_excel_reader.py`, `tests/test_laudos_service.py`) — 85 no
total, nenhum existente quebrou.
**Reversível:** sim — muda só qual coluna o import lê daqui pra frente, sem mexer em dado já gravado.

## 2026-09-24 — "Apagar todo o histórico de laudos", a pedido explícito da Clara

**Contexto:** continuação direta da entrada anterior. Perguntei quais empresas foram afetadas pela
data errada e como ela queria corrigir — respondeu que todas foram afetadas, e pediu explicitamente
pra apagar o histórico inteiro de laudos, confirmar que o sistema está corrigido, e reimportar a
planilha do zero.
**Decisão:** implementei `apagar_todos_laudos()` (DELETE em massa, só na tabela `laudos`, não mexe
em empresas-clientes nem em outro módulo) com rota web e de API, ambas restritas a Admin Superior/
T.I. — mais restrito que as outras rotas de laudos (que qualquer usuário ELITE usa).
**Confirmação reforçada:** o modal de "excluir empresa" já existente não pareceu proteção
suficiente pra uma exclusão em massa dessa escala (histórico inteiro, não um registro) — adicionei
um mecanismo novo (botão só destrava depois de digitar "APAGAR" no modal), pensado pra ser
reaproveitável em qualquer ação de risco parecido no futuro, não só essa.
**Por que não fiz sozinho sem perguntar:** é dado real de faturamento e uma exclusão em massa e
irreversível — mesmo tendo entendido a causa do bug, "apagar tudo" é uma decisão que só a dona dos
dados pode tomar, e ela tomou, explicitamente, depois de eu perguntar.
**Validação:** 4 testes novos (serviço, rota web com bloqueio pra não-admin, rota de API) — 90 no
total — + verificação visual local ponta a ponta (import, modal, botão travado até digitar certo,
exclusão de verdade confirmada).
**Reversível:** não — a ação em si é irreversível por natureza (é uma exclusão real). A decisão de
executá-la foi explícita e documentada.

## 2026-09-24 — Pendências: "Não" também vira pendência, a pedido da Clara

**Contexto:** a Clara pediu diretamente: "na aba pendências do sistema, eu preciso que o que
estiver com 'Não' na planilha também seja lido como pendência". A regra antiga tratava "NÃO" como
equivalente a "SIM" (resolvido); só valores como "EM ATRASO"/"PENDENTE" viravam pendência.
**Decisão:** reduzi `STATUS_PAGO_OK` (`app/services/pendencias.py`) de `{"SIM", "NÃO"}` para
`{"SIM"}` — agora só "SIM" conta como pago; qualquer outro valor não-vazio, incluindo "NÃO", conta
como pendência. Sem mudança de lógica em `_e_pendente()`, só no conjunto de valores considerados OK.
**Sem migração necessária:** a regra é aplicada ao vivo sobre o texto já gravado (não há
interpretação no momento do import), então todo o histórico já importado passa a ser lido
corretamente assim que o deploy sobe — diferente do bug de Laudos (entrada acima), não precisa
apagar nem reimportar nada.
**Validação:** novo teste (`test_pago_nao_conta_como_pendente`) + suíte completa (91 testes) +
verificação visual local com planilha sintética (Não/Sim/vazio), confirmando que só "Não" vira
pendência.
**Reversível:** sim — é uma única constante; fácil de reverter se a regra mudar de novo.

## 2026-09-24 — "Zona de perigo" (apagar todo o histórico) estendida para Audiências, Pendências e Gestão de Processos

**Contexto:** a Clara pediu pra adicionar o mesmo botão de "apagar todo o histórico" que já existia
em Laudos (entrada 2026-09-24 acima) também nas telas de Audiências, Pendências e Gestão de
Processos.
**Decisão:** implementei `apagar_todas_audiencias()`, `apagar_todas_pendencias()` e
`apagar_todos_processos()`, cada uma seguindo exatamente o mesmo formato de `apagar_todos_laudos()`
— rota web e de API, ambas restritas a Admin Superior/T.I., mesmo modal de confirmação por texto
digitado ("APAGAR") já usado em Laudos, reaproveitado sem escrever JS novo.
**Particularidade de Gestão de Processos:** não há `cascade` entre `eventos_processo` e `processos`
no banco — `apagar_todos_processos()` apaga os eventos antes dos processos, na mesma função/
transação, senão a segunda parte quebraria por chave estrangeira.
**Validação:** 12 testes novos (serviço + rota web, um par por módulo) — 103 no total — +
verificação visual local com Playwright nas três telas (botão só aparece pra admin, modal abre,
botão de confirmar destrava só depois de digitar "APAGAR", exclusão real confirmada em Audiências
ponta a ponta).
**Reversível:** não — mesma natureza irreversível da função já existente em Laudos.

## Pendências abertas

1. Política de retenção de dados pessoais (LGPD) — `SECURITY.md` seção 6. Ainda mais relevante
   agora: processos judiciais carregam nome completo + número de processo (pode revelar o tipo de
   ação). Não foi perguntado explicitamente na Fase 5 — levar à Clara antes de ir para produção
   com dados reais de processos.
2. Rate limiting / bloqueio de tentativas de login — sem risco relevante no volume atual, mas fica
   registrado para um refinamento futuro.
3. `criado_por` em `laudos`/`audiencias`/`cobrancas` (rastreabilidade linha a linha, hoje só o
   import/geração fica no log de auditoria, não cada registro) — `DATABASE.md` seção 9.
4. Modelo do relatório de Gestão de Processos (layout/colunas do PDF) — a Clara viu o exemplo
   gerado (Março/2026, geral + individual) e gostou, mas quer revisitar detalhes depois. Não é um
   pedido concreto ainda; retomar quando ela trouxer o que quer mudar.
5. ~~Lentidão geral relatada pela Clara~~ — resolvida (2026-09-24): ela mandou o log real do Render,
   que revelou a causa (`GET /app/processos` recarregando toda a tabela em toda geração de
   relatório, mesmo sem pedir um) — ver entrada 2026-09-24 acima. Falta ela confirmar, depois desse
   deploy, que a tela de Gestão de Processos abre rápido agora.
6. Confirmar com a Clara que o modal de exclusão de empresa aparece estilizado depois do deploy do
   cache-busting (ela viu sem estilo por causa de CSS em cache — ver entrada 2026-09-23 acima).
7. Tela de "acordando" do Render (2026-09-24) — confirmado: é o "sleep" por inatividade do plano
   gratuito (não um bug), aparece depois de ~15 minutos sem uso. Duas opções apresentadas: upgrade
   pago (~US$7/mês, instância "Starter", elimina o sleep de vez — não precisa de plano de workspace
   pago junto) ou um "ping" automático externo pra manter o serviço sempre ativo (grátis, mas não é
   garantido). A Clara decidiu deixar como está por enquanto — não é uma pendência técnica, é uma
   decisão de custo dela; só retomar se ela pedir.
8. Import da planilha real de Gestão de Processos ainda é pesado quando reimporta o histórico quase
   todo de uma vez (ver entrada 2026-09-24) — carrega todos os processos/eventos já existentes no
   banco pra decidir o que é novo/atualizado, não só os do arquivo. Um upsert direto no SQL (em vez
   de carregar tudo em objetos Python antes de comparar) reduziria isso mais, mas é uma mudança de
   maior risco num caminho de dado real (prazos de processos judiciais) — não implementada ainda.
   Também vale perguntar à Clara se o fluxo dela realmente precisa reimportar o histórico inteiro
   toda vez, ou se dava pra importar só a aba/mês novo — isso sozinho já reduziria bastante sem
   precisar de nenhuma mudança de código.
9. ~~Laudos com data errada já gravados no banco~~ — resolvida (2026-09-24): a Clara confirmou que
   todas as empresas foram afetadas e pediu pra apagar todo o histórico de laudos; construída a
   função/rota de "apagar tudo" (ver entrada 2026-09-24 acima). Falta ela de fato clicar em apagar
   e reimportar a planilha completa — só aí a Fase 5/6 de Laudos volta a ter dado confiável no ar.
10. Relatório de Gestão de Processos com contagem errada no mês corrente — corrigido (ver entrada
    2026-09-24 "Relatório de Gestão de Processos..." abaixo); falta a Clara apagar o histórico de
    processos (zona de perigo, mesma seção) e reimportar a planilha completa pra garantir que os
    dados de meses recentes (que estavam sendo descartados) entrem certinho no sistema.

## 2026-09-24 — Relatório de Gestão de Processos contando errado no mês corrente

**Contexto:** a Clara reportou (com print e a planilha real anexada): o relatório geral mostrou
3.552 eventos pro período 01/09–24/09/2026, mas a aba SETEMBRO26 da planilha só tem ~2.449 linhas.
Pediu pra explicar como o relatório está puxando os dados e o que está puxando.
**Investigação:** com a planilha real, encontrei dois bugs reais, um em cada direção. (1) Abas
recentes (AGOSTO26/SETEMBRO26) passaram a ter EMPRESA numa coluna própria, não mais embutida no
formato "EMPRESA - Cliente" da coluna CLIENTE — o import só sabia o formato antigo, então ~97% da
aba SETEMBRO26 (2.333 de 2.406 linhas) era descartada como "empresa não reconhecida", nunca virava
`Processo`/`EventoProcesso`. (2) Abas "coringa" (fatais, Dra Galzo, Dra Kelly, Dra Sleiman, DOCS E
CUSTAS, JUN-25 a OUT-25) não têm data de andamento real, só "DATA DE LIBERAÇÃO — QUANDO A DRA
INSERIU O CLIENTE NA PLANILHA" — o sistema tratava isso como se fosse a data do andamento, fazendo
uma linha contar no mês em que o cliente foi cadastrado naquela aba, não no mês do andamento de
verdade (ex.: FATAIS 08 sozinha contribuiu 333 "eventos de setembro" que eram só data de intake).
**Perguntei à Clara e ela decidiu:** (1) corrigir o import pra aceitar as duas formas de EMPRESA
(coluna própria ou hífen); (2) as abas sem data real de andamento não devem contar no filtro por
período do relatório — continuam existindo no sistema normalmente, só não entram nessa contagem
mensal.
**Decisão/implementação:** `importar_planilha` (`app/services/processos.py`) agora lê a coluna
EMPRESA diretamente quando ela existir e vier preenchida; `load_data_sheets`
(`app/excel_reader.py`) ganhou um marcador `_DATA_E_LIBERACAO` por aba, sinalizando quando a
"DATA" resolvida veio literalmente da coluna de liberação (não de "DATA"/"DIA" — essas continuam
tendo data real, ex. FATAIS 08); novo campo `EventoProcesso.data_e_liberacao` grava esse marcador
por evento, e `gerar_relatorio` exclui eventos marcados do filtro por período.
**Achado que não é bug:** parte da diferença entre 2.449 (contagem manual da Clara, só da aba
SETEMBRO26) e o total correto pós-correção (~2.693) é legítima — FATAIS 08 tem ~333 prazos fatais
reais de setembro (data real na coluna "DIA"), só que numa aba separada da mensal.
**Validação:** 4 testes novos (serviço + leitor de planilha) — 107 no total — + validação manual
rodando o import completo contra a planilha real da Clara (fora da suíte): "empresa não
reconhecida" caiu de 6.632 para 450 linhas; total do período foi de 3.552 para 2.693.
**Reversível:** sim — mudanças isoladas e pequenas (uma coluna nova, um booleano) se a regra mudar.

## 2026-09-24 — Dropdowns de Empresa e Funcionário no Relatório de Processos

**Contexto:** a Clara pediu pra trocar digitação livre por menus suspensos no Relatório de Gestão
de Processos, reaproveitando a mesma fonte de dados dos menus já existentes (sem duplicar lista).
Antes de implementar, ela avisou um plano futuro: apagar todas as empresas cadastradas e recadastrar
só as oficiais (com CNPJ), e parar o sistema de criar empresa nova sozinho a partir da planilha —
perguntou se isso mudava a forma de implementar.
**Minha recomendação (aceita):** sim, seguir a ideia de reaproveitar a mesma fonte
(`empresas_clientes`) pro dropdown de Empresa — assim, quando ela recadastrar as 40 oficiais, o
relatório já reflete automaticamente, sem eu mexer de novo. Mas tratar "parar de auto-criar
empresa no import" como etapa **separada**, futura — é uma mudança mais delicada (toca import de
Laudos/Audiências/Pendências/Processos) que merece sua própria decisão sobre o que fazer com uma
linha cuja empresa não está cadastrada.
**Achado ao investigar:** nem o dropdown de Empresa nem de Funcionário existiam de fato no
Relatório de Processos antes disso — Empresa não tinha filtro nenhum ali (só em Laudos/Audiências/
Pendências), e "Funcionário" não existia como lista cadastrada em lugar nenhum do sistema
(assistente/advogada sempre foram texto livre, vindo da planilha).
**Decisões da Clara:** (1) Funcionário = os assistentes de Gestão de Processos; (2) guardar numa
tabela editável (não fixo no código), mesmo padrão de Empresa.
**Implementação:** tabela nova `Funcionario` (nome, ativo — sem FK de `Processo.assistente`, que
continua texto livre), semeada com os 7 nomes que ela informou; tela `/app/funcionarios` (CRUD,
admin) espelhando `/app/empresas`; `gerar_relatorio` ganhou `filtro_empresa`; campo "Pessoa" agora
alterna entre dropdown de Funcionário (quando agrupa por Assistente) e texto livre (Advogada/
Assessoria, sem lista cadastrada ainda).
**Validação:** 7 testes novos — 114 no total — + verificação visual local com Playwright (dropdowns
populados, alternância funcionário/texto funcionando, filtro por empresa correto, CRUD de
funcionários funcionando).
**Reversível:** sim — tabela e filtro isolados, sem FK apontando pra `Funcionario`.
