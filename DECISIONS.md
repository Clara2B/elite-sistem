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

## 2026-09-24 — Sincronização com a lista oficial de empresas (PDF da Clara)

**Contexto:** a Clara mandou um PDF ("INFOS ASSESSORIAS") com nome + CNPJ oficial de cada
empresa-cliente, pedindo pra apagar o que está cadastrado e adicionar as novas. 48 empresas — 8 a
mais do que a lista de 40 que ela tinha digitado de memória num pedido anterior.
**Perguntei antes de implementar (4 pontos, todos aceitos com a opção recomendada):** (1) manter o
nome curto no cadastro (não a razão social do PDF), pra não quebrar o reconhecimento de empresa nos
imports futuros — sem adicionar campo de razão social; (2) incluir as 48 do PDF, não só as 40
digitadas antes; (3) usar "WNFAST" (sem espaço, como a planilha real de processos já grava) em vez
de "WN FAST" (como está escrito no PDF); (4) cadastrar "OPÇÃO1" sem CNPJ (o PDF não trouxe um).
**Decisão:** `sincronizar_lista_oficial()` (`app/services/empresas.py`) cria/atualiza CNPJ das 48
empresas oficiais e exclui de verdade qualquer empresa cadastrada fora dessa lista — reaproveitando
a proteção que `excluir_empresa` já tinha antes (recusa excluir se houver laudo/audiência/cobrança/
processo vinculado). Não force-apaguei histórico de nenhum outro módulo pra viabilizar a exclusão:
quem não pôde ser excluída aparece detalhado na mensagem de resultado, pra Clara decidir o que
fazer com cada uma.
**Bug pego pelo teste antes do commit:** a rota web `POST /app/empresas/sincronizar-lista-oficial`
precisou ser registrada antes de `POST /{empresa_id}` no arquivo de rotas — na ordem original, o
Starlette casava com a rota de editar primeiro (`empresa_id="sincronizar-lista-oficial"`) e devolvia
422 em vez de rodar a sincronização.
**Validação:** 8 testes novos — 122 no total — + teste manual de ponta a ponta com Playwright
(3 cenários: empresa sem vínculo excluída, empresa com laudo vinculado preservada e reportada, CNPJ
de uma empresa já existente corrigido) batendo exatamente com o esperado.
**Reversível:** não — as exclusões são definitivas; criação/CNPJ são triviais de reverter.

## 2026-09-25 — Resumo por assessoria em texto simples, na aba Laudos

**Contexto:** a Clara pediu uma lista-resumo em texto puro (sem PDF, pra copiar e colar), gerada
junto com o relatório de Laudos, com total de laudos e quantidade por tipo (+ valor individual) por
assessoria — seguindo um modelo de texto exato que ela deu.
**Pergunta antes de implementar:** o relatório de Laudos sempre exigiu uma empresa específica, mas
o exemplo dela mostrava várias assessorias na mesma lista — perguntei se a lista deveria cobrir só
a assessoria selecionada (sempre 1 bloco) ou todas do período/status (vários blocos, como no
exemplo). Ela escolheu "todas as assessorias do período/status" — o campo "Empresa-cliente" virou
opcional: vazio cobre todas, preenchido filtra pra uma só (mesmo filtro do relatório detalhado).
**Pontos que ela pediu pra eu avisar em vez de decidir sozinho, resolvidos ao explorar o código:**
(1) variação de valor do mesmo tipo — não pode acontecer, o valor é sempre resolvido ao vivo da
tabela de preços atual, nunca gravado por laudo; (2) laudo sem assessoria/tipo — não existe no
banco, o import já descarta essas linhas antes de gravar; o único caso real de dado faltando é tipo
sem valor cadastrado, tratado com "(sem valor cadastrado)" em vez de R$ 0,00 ou descarte silencioso.
**Decisão/implementação:** `gerar_resumo_por_assessoria()` (`app/services/laudos.py`) reaproveita a
mesma lógica de filtro de status e de valor por tipo que `gerar_relatorio()` já usava (extraí
`_status_bate`/`_resolver_status` pra ficarem compartilhadas) — os números batem entre relatório e
resumo porque é a mesma regra, não uma reimplementação paralela.
**Validação:** 10 testes novos — 132 no total — incluindo um que confirma o formato exato de saída
batendo com o modelo que a Clara deu, e um teste de ponta a ponta com Playwright reproduzindo o
exemplo do plano apresentado antes de implementar.
**Reversível:** sim — funções novas e isoladas; o relatório detalhado existente não mudou.

## 2026-09-25 — Gestão de Processos: relatórios Geral/Por empresa, remoção de "Agrupar por" (Blocos 1 e 3)

**Contexto:** a Clara mandou um pedido de 4 blocos, dizendo que era tudo na aba "Laudos". Antes de
tocar em qualquer código, explorei o modelo de dados dela: "número de processo", "evento", "fatal"
e "observação" só existem em `Processo`/`EventoProcesso` (Gestão de Processos) — Laudos não tem
nada disso, nem nunca teve "Agrupar por". Perguntei e ela confirmou: Blocos 1-3 são de Gestão de
Processos; só o Bloco 4 é de Laudos mesmo.
**Bloco 2 (nomes de Dra) ficou pendente:** busquei nos dados reais de Processos que ela já tinha
mandado (colunas EMPRESA e CLIENTE) e não achei nenhum caso do padrão — ela confirmou que acontece
na planilha de Laudos, que ainda vai mandar.
**Decisões de interpretação:** "Evento"/"Fatal"/"Observação" nos três formatos de relatório novos
(Geral Parte 1, Geral Parte 2, Por empresa) são sempre do andamento mais recente do processo —
uma linha por processo, não por andamento, pra bater com o total no topo. "Mais recente" usa
`criado_em` (data/hora de registro, pedido explícito dela), considerando toda a história do
processo — não só o período filtrado — e excluindo eventos "data de liberação" (mesmo motivo da
entrada de 2026-09-24). Ordenação: empresas alfabética; dentro delas, Assistente e depois Nº do
processo (Cliente, na Parte 2 que não tem assistente).
**O que foi removido:** "Agrupar por" e todo o relatório-pivô antigo (Cumpridos/Perdidos/
Pendentes/Parados, conceito de "processo parado") — substituídos pelos dois tipos novos. Nenhum
outro lugar do sistema usava isso (confirmado antes de apagar).
**PDF do relatório de Processos:** reescrito pros dois formatos novos, a pedido da Clara (ela
confirmou que preferia isso a remover o botão de PDF).
**Renomeação "Funcionário" → "Assistente":** além dos filtros/rótulos da tela de Processos,
estendi pra tela de cadastro `/app/funcionarios` (título, mensagens) e pro menu lateral, pra não
ficar inconsistente com o dropdown que ela alimenta — mesma tabela/rota por baixo, só texto visível.
**Validação:** suíte de testes de Processos reescrita (36 testes) + testes web novos — 139 no
total — + verificação de ponta a ponta com Playwright (formatos Geral/Por empresa corretos,
"último evento"/observação batendo com o andamento certo num processo com histórico, filtro sem
resultado com mensagem amigável, rótulos corretos em toda parte incluindo a tela de assistentes).
**Reversível:** sim — mudança isolada ao módulo de Processos; schema do banco não mudou.

## 2026-09-25 — Resumo de Laudos: sempre geral e visual em cards (Bloco 4)

**Contexto:** Bloco 4 do pedido de 4 blocos — da aba Laudos de verdade (diferente dos Blocos 1-3,
que eram de Gestão de Processos, ver entrada acima). Dois pedidos: (1) o resumo deve ser sempre
geral, cobrindo todas as empresas, mesmo que o relatório detalhado esteja filtrado por uma só;
(2) visual limpo, com a identidade do sistema, em vez do campo de texto monoespaçado atual.
**Decisão:** `routes_laudos.py` parou de passar o filtro de empresa pra
`gerar_resumo_por_assessoria` — o resumo sempre cobre todas, só período/status valem pra ele.
Visual trocado de `<textarea readonly>` pra um `.card` por assessoria (mesmo componente usado em
todo o resto do sistema), com tabela Tipo/Quantidade/Valor alinhada à direita. A função de cópia
foi mantida (botão "Copiar resumo", mesmo texto simples de antes, via clipboard API), só mudou a
forma de guardar o texto na página (um `<script type="application/json">` escondido em vez do
campo visível) — sem regredir a funcionalidade que já existia.
**Posição:** movido pra baixo do relatório detalhado, como pedido — antes ficava acima dele.
**Validação:** 2 testes web (cards visíveis, sem mais textarea; resumo continua geral mesmo com
filtro de empresa aplicado no relatório) — 139 no total — + Playwright confirmando visualmente o
posicionamento, o botão de copiar funcionando de verdade (toast + conteúdo certo na área de
transferência) e uma captura de tela do resultado final.
**Reversível:** sim — mudança de template/rota; a lógica de geração dos dados não mudou.

## 2026-09-25 — Cartas: respostas da Clara às perguntas pendentes (Carta Convite Cliente e Banco)

**Contexto:** pedido novo de uma aba "Cartas" (Carta Convite Cliente + Carta Convite Banco, em
PDF), aberto pela Clara com uma regra explícita e recorrente pro resto dessa feature: qualquer
dúvida de texto/layout/comportamento/biblioteca é perguntada antes de decidir, nunca assumida.
Antes de implementar, levantei a lista completa de dúvidas (formato de data/hora, onde colocar o
telefone, dois problemas encontrados no próprio modelo oficial da carta do Banco — "GOGGLE MEET"
com erro de digitação e a pontuação "CNPJ : -" — e mais várias outras) e esperei a resposta.
**Decisões (registradas para as duas cartas; só a Cliente foi implementada nesta rodada — ver
ARCHITECTURE.md 4.18):**
- **Plataforma dinâmica nas duas cartas:** identificada a partir da estrutura do link (não mais
  texto fixo "GOOGLE MEET"), Google Meet ou Teams; Cliente usa "Google Meet"/"Teams" no texto.
- **Data:** Cliente passa a ter ano (antes só dia/mês); hora mantém o formato do modelo
  ("HHhMM", ex. "10H30"), sem o "m" final que aparecia num dos modelos ("17H00m" → "17H00").
- **Telefone "55 11 93234-6989":** só na Carta Cliente (não na do Banco), numa linha logo abaixo
  do e-mail de contato existente, mesmo estilo de fonte — exatamente como eu tinha proposto.
- **Carta Banco (registrado agora, implementação na próxima rodada):** corrigir o "GOGGLE MEET"
  pra "GOOGLE MEET" certo; corrigir a pontuação "CNPJ : -" pra um formato limpo; adicionar Nome
  do banco e CNPJ como 2 campos novos no formulário (não são um dos 6 campos originais); CNPJ e
  nome do banco em caixa alta e negrito no PDF; aceitar o link com ou sem prefixo "https://";
  manter fixos os trechos em negrito que eu tinha identificado (são os mesmos em todas as cartas).
- **CPF inválido bloqueia a geração**, com um aviso explicando o motivo (não é só warning).
- **Nomes sempre em caixa alta** no PDF (Autor/Réu na Cliente; Nome na Banco).
- **Nome do arquivo:** segue a estrutura proposta ("Carta Convite Cliente/Banco - [nome]") — na
  prática, o PDF sai com esse nome passado por `nome_arquivo_pdf()` (a mesma função usada em todo
  o resto do sistema pra nomes de arquivo seguros), que troca espaços por "_" e maiúsculiza —
  ex. `CARTA_CONVITE_CLIENTE_MARIA_DE_FATIMA_OLIVEIRA.pdf` — mesmo padrão de Laudos/Audiências/
  Processos, não um texto solto.
- **Sem persistência:** cartas geradas não ficam salvas/registradas no banco — só o download.
- **Acesso:** aba "Cartas" só visível para quem tem acesso à EXIMIA (mesma regra de Audiências).
**Reversível:** decisão de produto, não de código — não se aplica.

## 2026-09-25 — Cartas: Carta Convite Banco aprovada e implementada

**Contexto:** depois da aprovação visual da Carta Convite Cliente (ver entrada acima), a Clara
pediu a Carta Convite Banco, "com a estrutura do prompt" (os 6 campos originais + Nome do
banco/CNPJ já aprovados) e posicionada abaixo da Carta Cliente na mesma tela.
**Última dúvida pendente resolvida:** a Carta Banco também mostra a data com ano (ex.
"07/10/2026"), mesma decisão já tomada pra Carta Cliente — perguntei especificamente porque essa
carta tem sua própria seção de data no modelo original ("07/10", sem ano) que não tinha sido
coberta pelas perguntas anteriores (essas eram só sobre a Carta Cliente).
**Implementado:** `montar_convite_banco`/`ConviteBanco` (`app/services/cartas.py`) e
`gerar_pdf_carta_banco` (`app/pdf_export.py`) — ver ARCHITECTURE.md 4.18 para os detalhes
técnicos completos (detecção de plataforma, validação/formatação de CPF, correção dos dois erros
do modelo oficial, negrito/caixa-alta do banco). Formulário da Carta Banco adicionado à mesma
tela `/app/cartas`, abaixo do formulário da Carta Cliente.
**Validado:** suíte completa sem regressão (139 testes) + lint limpo + PDF de exemplo com dados
fictícios conferido manualmente (Meet e Teams testados, CPF válido formatado corretamente) +
bloqueio de CPF inválido e de link inválido testados e confirmados + Playwright end-to-end (login
real, os dois cards na ordem certa, download funcionando pelos dois formulários).
**Reversível:** sim — mesma observação da entrada de implementação da Carta Cliente.

## 2026-09-25 — Cartas: ajuste de espaçamento e texto de contato no fechamento

**Contexto:** depois de ver o PDF de exemplo da Carta Cliente, a Clara pediu ajustes no bloco de
fechamento (contato/despedida/assinatura), mostrando um recorte da própria Carta Cliente como
referência.
**Dúvida levantada e resolvida:** ela disse "em ambos os documentos" antes de duas coisas — o
ajuste de espaçamento E a troca da frase de contato — mas a frase de contato mostrada já incluía
telefone (só existe na Carta Cliente; a Banco nunca teve telefone, por decisão anterior). Perguntei
se isso reabria a decisão de telefone só na Cliente. Resposta: **não** — "em ambos os documentos"
vale só pro espaçamento; a Carta Banco continua sem telefone.
**Decisões:**
- **Espaçamento maior** (mais espaço entre linhas + um espaço extra entre "Atenciosamente," e a
  assinatura) no bloco de fechamento **das duas cartas** — estilos dedicados só pra essa parte
  (`fechamento`, `atenciosamente`, `contato_cliente`, `contato_destaque`, `fechamento_caps` em
  `app/pdf_export.py::_estilos_carta`), sem mudar o espaçamento do corpo principal do texto.
- **Texto de contato da Carta Cliente** trocado de "Colocamo-nos à disposição por meio do
  e-mail: conciliacao@camaraeximia.com. / Telefone: ..." para "Colocamo-nos à disposição por
  meio dos contatos: / E-mail: conciliacao@camaraeximia.com / Telefone: ..." (3 linhas com label,
  sem ponto final depois do e-mail) — só na Carta Cliente.
- **Carta Banco:** texto de contato não muda (continua só "Colocamo-nos à disposição por meio do
  e-mail: conciliacao@camaraeximia.com."), só ganha o mesmo espaçamento maior.
**Validado:** suíte completa sem regressão (139 testes) + lint limpo + PDFs de exemplo
regenerados e conferidos visualmente (espaçamento maior visível, gap extra antes da assinatura
nas duas cartas, novo texto de contato só na Cliente).
**Reversível:** sim — mudança isolada aos estilos/parágrafos de fechamento em `pdf_export.py`.

## 2026-09-25 — Cartas: mais espaço acima da linha vermelha nas duas cartas

**Contexto:** depois de ver os PDFs de exemplo atualizados, a Clara pediu mais espaço entre a
"linha em vermelho" e o texto de cima, nos dois documentos. A linha vermelha é diferente em cada
carta: na Cliente é "(Segue link abaixo, pela plataforma ...)" + o link (estilo `link`); na Banco
é a linha "Colocamo-nos à disposição por meio do e-mail: ..." (estilo `contato_destaque`).
**Decisão:** `spaceBefore=14` adicionado aos dois estilos (`link` na Cliente, `contato_destaque`
na Banco) — afeta só o espaço acima dessas duas linhas específicas, sem alterar o espaçamento do
resto do texto (o reportlab usa o maior entre o `spaceAfter` do parágrafo anterior e o
`spaceBefore` do parágrafo seguinte, então o espaço visível aumentou de ~8-10pt pra 14pt nos dois
casos).
**Validado:** suíte completa sem regressão (139 testes) + lint limpo + PDFs de exemplo
regenerados e conferidos visualmente (espaço maior visível acima da linha vermelha nas duas
cartas).
**Reversível:** sim — dois valores de estilo em `pdf_export.py::_estilos_carta`.

## 2026-09-25 — Cartas: espaço acima da linha de e-mail da Banco aumentado de novo

**Contexto:** depois do ajuste anterior (mais espaço acima da linha vermelha nas duas cartas), a
Clara pediu, especificamente pra linha "Colocamo-nos à disposição por meio do e-mail:
conciliacao@camaraeximia.com" (texto exato só existe na Carta Banco — a Cliente já tinha sido
reestruturada em 3 linhas com telefone), ainda mais espaço em relação a todo o texto acima.
**Decisão:** `spaceBefore` do estilo `contato_destaque` (só usado na Carta Banco) subiu de 14
pra 26 — não mexeu no `link`/Cliente, que já tinha ficado do jeito que ela queria.
**Validado:** suíte completa sem regressão (139 testes) + lint limpo + PDF de exemplo da Banco
regenerado e conferido visualmente (espaço bem mais largo acima dessa linha agora).
**Reversível:** sim — um valor de estilo em `pdf_export.py::_estilos_carta`.

## 2026-09-28 — Configuração/Processos: plano de 5 blocos apresentado, Bloco 1 adiantado por urgência

**Contexto:** pedido novo com a mesma regra de "pergunte antes de decidir" e processo exigido
(explorar → plano único com todas as perguntas → implementar bloco a bloco com aprovação). Os 5
blocos: Bloco 1 (editar usuário), Bloco 2 (separar Usuário/Empresa/Cliente como área
administrativa), Bloco 3 (`papel_global` vira só 4 valores: Administrador Geral/T.I./Gerente/
Líder), Bloco 4 (tirar Assistente do relatório de Processos) e Bloco 5 (coluna de Observação sem
corte/rolagem horizontal). Apresentei o plano com achados (nenhuma área admin tem brecha de
acesso hoje — já são bloqueadas nas duas camadas; não existe "exclusão" de usuário hoje, só
inativar; "Líder" já existe como papel por setor, colidindo de nome com o "Líder" global pedido
no Bloco 3; não encontrei uma área "Cliente" separada de "Empresa"; não tenho acesso ao banco de
produção pra contar usuários por papel) e a lista completa de perguntas dos 5 blocos.
**Decisão sobre o Bloco 1 (única resposta até agora):** a Clara pediu urgência só na edição de
usuário, sem responder às perguntas específicas do Bloco 1 ainda. Implementei usando as opções
que eu mesma já tinha proposto no plano (sem contestação da Clara): todos os campos editáveis
(nome/e-mail/papel global/senha opcional/setores), proteção contra remover o último admin do
sistema, e formato inline reaproveitando o layout do cadastro — ver ARCHITECTURE.md 4.19 para
os detalhes técnicos completos.
**Ainda pendente:** Blocos 2-5 continuam esperando as respostas da Clara — nenhum foi
implementado.
**Validado:** suíte completa sem regressão (145 testes, 6 novos) + lint limpo + Playwright real
(login, expandir edição, trocar nome/papel, salvar, confirmar toast e dados atualizados).
**Reversível:** sim — mudança isolada às rotas/template de usuários; nenhuma coluna de banco
mudou.

## 2026-09-28 — Configuração: Bloco 2 adiantado (setores, edição mais bonita, aba única)

**Contexto:** a Clara pediu 3 coisas juntas, sem ter respondido ainda às perguntas completas do
Bloco 2 do plano original: (1) poder alterar/adicionar setores e o papel de um usuário dentro de
cada setor; (2) deixar a edição de usuário mais bonita; (3) separar Usuário/Empresa/Assistentes
numa aba "Configuração". O pedido (3) resolveu sozinho a dúvida que eu tinha deixado em aberto no
plano — o que era "Cliente" como terceira área — a resposta é: era "Assistentes", não uma área
nova.
**Decisões:**
- **Setores ganharam CRUD** (antes só existiam pré-cadastrados no banco, sem tela nenhuma) —
  criar, editar nome/operadora, ativar/desativar (sem excluir, mesma regra do resto do sistema).
  O vínculo usuário-setor-papel em si (Líder/Colaborador dentro do setor) não mudou — já existia
  desde a edição de usuário implementada antes; só faltava poder criar/editar o Setor em si.
- **Edição de usuário redesenhada visualmente:** painel destacado (fundo diferenciado + borda de
  acento), duas seções com título, ícone no botão "Editar", linha do setor marcado destacada —
  tudo CSS, sem JS novo.
- **Área "Configuração":** um item só no menu (no lugar dos 3 separados), levando a uma tela com
  cards pras 4 áreas administrativas (Usuários, Empresas-clientes, Assistentes, Setores). As 4
  telas por baixo **não mudaram nada** — mesmas rotas, mesma lógica — só o menu e a navegação
  mudaram (item "Configuração" fica destacado em qualquer uma das 4, e cada uma ganhou um link
  "Voltar à Configuração").
**Validado:** suíte completa sem regressão (152 testes, 7 novos) + lint limpo + Playwright real
(dashboard só com o card "Configuração", os 4 cards na tela de Configuração, visual novo da
edição de usuário conferido por captura de tela, setor criado pela tela aparecendo na hora no
checklist do formulário de usuário).
**Reversível:** sim — mudança de navegação/visual; nenhuma rota antiga foi removida, nenhuma
coluna de banco mudou.
**Ainda pendente:** Blocos 3-5 do plano original continuam esperando as respostas da Clara.

## 2026-09-28 — Configuração/Processos: Blocos 4 e 5 implementados

**Contexto:** a Clara confirmou que não existe (nem deve existir) uma área "Cliente" separada —
era "Assistentes" mesmo — e deu sinal verde pra continuar o plano ("pode prosseguir com as
alterações"). Segui com os Blocos 4 e 5, que não tinham dúvida estrutural travando (diferente do
Bloco 3, que ainda depende de dados/decisões que só ela pode dar — contagem de usuários por
papel, mapeamento de conversão, o que fazer com o "Líder" que já existe por setor).
**Bloco 4 — decisão sobre a única dúvida que eu tinha levantado:** a "versão exportada" que
existia (o campo `texto` da API JSON) também perdeu a coluna Assistente, pela mesma regra da
tela e do PDF — decisão minha, dentro do espírito claro da instrução original ("não exibir o
nome do assistente no relatório gerado"), já que não fazia sentido a API devolver o assistente
enquanto a tela e o PDF não mostram mais.
**Bloco 5 — decisões sobre as duas dúvidas que eu tinha levantado:**
- Observação mostrada **inteira, com quebra de linha** (não resumida com "ver mais") — segui a
  recomendação que eu mesma tinha proposto, sem objeção da Clara.
- O ajuste (wrap + `.tabela-wrap`) foi aplicado a **todas** as tabelas de Gestão de Processos
  (Prazos próximos incluído), não só às que têm Observação — por consistência, também já
  proposto no plano original.
**Validado:** suíte completa sem regressão (154 testes, 4 novos) + lint limpo + Playwright em 3
larguras de tela (1440/768/390px) confirmando que a página nunca ganha rolagem horizontal, texto
longo sem espaços quebra dentro da célula, e em telas muito estreitas a tabela passa a rolar
dentro do próprio contêiner (não da página) — ver ARCHITECTURE.md pros detalhes técnicos.
**Reversível:** sim — mudanças de apresentação (services/processos.py, pdf_export.py,
templates/processos.html, style.css); nenhuma lógica de filtro/ordenação/dados mudou.
**Ainda pendente:** só o Bloco 3 (papel global) continua esperando as respostas da Clara — é o
único que envolve migração de dados irreversível e que eu não tenho como avançar sozinha (preciso
da contagem de usuários por papel do banco de produção, que não tenho acesso daqui).

## 2026-09-28 — Bug: botões esmagados em Empresas/Assistentes/Setores (regressão do Bloco 5)

**Contexto:** a Clara reportou, com captura de tela, que os botões "Salvar"/"Desativar"/lixeira
nas telas de Empresas-clientes, Assistentes e Setores apareceram esmagados (o texto quebrando
letra por letra numa coluna estreitíssima).
**Causa raiz:** a regra `overflow-wrap: anywhere` que eu tinha adicionado em `tbody td` no Bloco
5 (pra resolver o corte da coluna Observação de Processos) foi aplicada **globalmente** — ou
seja, em toda tabela do sistema, não só nas de Processos. Essa propriedade é herdada, então o
texto dos botões dentro de `.acoes-linha` (que fica dentro de um `<td>`) passou a ser considerado
"quebrável em qualquer lugar" também. Como esses botões ficam num container flex, o navegador
deixou o espaço mínimo deles encolher até quase nada, e o texto ("Salvar", "Desativar") quebrou
verticalmente pra caber.
**Correção:** em vez de reverter o Bloco 5 (a quebra de texto longo na Observação continua
necessária), protegi especificamente os elementos que não devem quebrar — `button`/`.botao`
ganharam `white-space: nowrap` + `overflow-wrap: normal` + `flex-shrink: 0` (nunca encolhem nem
quebram, independente do que o pai herdar), e `.badge` (Ativo/Inativo) ganhou `white-space:
nowrap` pela mesma razão preventiva.
**Validado:** suíte completa sem regressão (154 testes) + lint limpo + Playwright confirmando
visualmente as 4 telas afetadas (Empresas-clientes, Assistentes, Setores, Usuários) com os
botões normais de novo, e reconfirmando que a quebra de texto longo na Observação de Processos
(o motivo original do Bloco 5) continua funcionando.
**Reversível:** sim — só CSS, isolado a `button`/`.botao`/`.badge` em `style.css`.

## 2026-09-28 — Modo escuro

**Contexto:** pedido direto da Clara ("adicione a opção de modo escuro"). Sem ambiguidade
estrutural (não mexe em banco, não é parte dos 5 blocos pendentes) — implementei direto, com as
decisões de design de costume: segue a preferência do sistema operacional por padrão, com um
botão para escolher manualmente, salvo por navegador (sem precisar de conta/login pra lembrar).
**Decisões:**
- **Persistência:** `localStorage`, por navegador — não é um campo por usuário no banco (não
  precisa, é preferência de exibição, não dado de negócio).
- **Padrão:** ao entrar pela primeira vez, usa a preferência de tema do sistema operacional
  (`prefers-color-scheme`) — a pessoa só precisa clicar no botão se quiser um tema diferente do
  que o SO já usa.
- **Sem "flash" do tema errado:** um script pequeno no `<head>` (antes do CSS carregar) aplica o
  tema salvo, se houver, antes da primeira pintura da página — inclusive na tela de login/erro,
  que não usam o layout principal (`_tema_inline.html`, incluído nos 3 templates HTML completos
  do sistema: `base.html`, `login.html`, `erro.html`).
- **Cobertura:** toda a interface — reaproveitei as variáveis CSS que já existiam
  (`--bg`/`--card`/`--border`/`--text` etc.) e separei um `--heading` novo pra texto de destaque
  (títulos, cabeçalho de tabela) que precisava mudar de cor no escuro, sem afetar `--navy`
  (marca fixa da sidebar/hero/botão primário, que não muda de cor nas duas aparências — só o
  fundo muda ao redor dela). Cores de sucesso/erro/aviso, sombras e o fundo do modal de
  confirmação também ganharam variantes escuras.
**Testado:** suíte completa sem regressão (155 testes, 1 novo) + lint limpo + Playwright
cobrindo: alternância manual, persistência entre navegações e depois de sair/entrar de novo
(mesmo navegador), telas de Usuários (com o painel de edição), Empresas-clientes (com modal de
confirmação e toast), dashboard, e a tela de login — em desktop e num viewport de celular
(390px).
**Reversível:** sim — só CSS/HTML/JS (`style.css`, `app.js`, `_icones.html`, `base.html`,
`login.html`, `erro.html`, `_tema_inline.html` novo); nenhuma coluna de banco, nenhuma rota, nada
no backend mudou.

## 2026-09-28 — "Excluir todas as empresas inativas" (Empresas-clientes)

**Contexto:** a Clara desativou as empresas que não quer mais usar e pediu pra excluí-las do
banco. Ela pediu inicialmente pra eu apagar direto no banco de produção — recusei fazer isso por
dois motivos: (1) este ambiente não tem acesso direto ao banco de produção; (2) mesmo se tivesse,
um `DELETE` direto pularia a proteção que a própria tela já tem contra apagar empresa com
histórico vinculado (laudo/audiência/cobrança/processo). Perguntei se ela queria que eu excluísse
pela tela (uma por uma) ou construísse um botão de "excluir todas as inativas" — ela escolheu o
botão.
**Decisão:** novo botão na "Zona de perigo" de Empresas-clientes, mesmo padrão visual e de
confirmação (digitar uma palavra pra destravar o botão) que "Sincronizar com a lista oficial" já
usa. Reaproveita `excluir_empresa` (a mesma função com a proteção contra histórico vinculado) pra
cada empresa com `ativo=False` — não é um DELETE em massa sem checagem, é a mesma exclusão
individual seguro, só disparada pra todas de uma vez. Uma empresa com histórico vinculado fica de
fora da exclusão e aparece na mensagem de resultado, exatamente como já acontece na sincronização
com a lista oficial.
**Testado:** suíte completa sem regressão (160 testes, 5 novos: 3 de serviço + 2 web) + lint
limpo + Playwright end-to-end (modal de confirmação com contagem certa, botão travado até digitar
"EXCLUIR", empresa inativa sem vínculo excluída de verdade, empresa inativa COM vínculo mantida e
citada na mensagem, empresa ativa nunca tocada).
**Reversível:** sim — módulo novo e isolado (`excluir_empresas_inativas` em
`services/empresas.py` + rotas web/API espelhando o padrão de `sincronizar-lista-oficial`); não
mudou nenhuma rota/função existente.

## 2026-09-28 — Seleção de abas por setor + exclusão de empresa com reatribuição

**Contexto:** a Clara pediu duas coisas na mesma mensagem — (1) poder escolher, ao cadastrar/
editar um setor, quais abas do site aquele setor pode acessar; (2) poder apagar uma empresa
mesmo que tenha processos vinculados. As duas mexem em várias partes do sistema e tinham
ambiguidade estrutural real, então perguntei antes de codar (regra dela, restated várias vezes
nessa engajamento) em vez de assumir.

**Pergunta 1 (seleção de abas):** (a) a área de Configuração (Usuários/Empresas/Assistentes/
Setores) devia entrar na seleção por setor, ou continuar controlada só por `papel_global` como
hoje, com a seleção por setor valendo só pras abas operacionais (Laudos/Processos/Audiências/
Cartas/Pendências)? (b) um setor podia ganhar acesso a uma aba fora da sua própria operadora, ou
a seleção tinha que ficar restrita às abas válidas pra operadora do próprio setor?
**Resposta da Clara:** "1. Só liberadas pelo papel global e deve continuar restrita às abas da
operadora do próprio setor" — Configuração fica intocada (só `papel_global`), e a seleção de um
setor não pode sair da operadora dele.

**Pergunta 2 (exclusão com vínculo):** expliquei que laudo/audiência/cobrança/processo têm todos
FK NOT NULL pra empresa-cliente — "excluir mesmo com vínculo" só é possível reatribuindo esses
registros a outra empresa antes (não existe um jeito de simplesmente apagar a empresa e deixar o
histórico órfão), ou cascateando a exclusão do histórico junto (que eu não queria fazer sem
confirmação explícita, por ser destrutivo). Perguntei qual ela queria, se era só pra "processos"
(a palavra que ela usou) ou pros quatro tipos, e se era um caso único ou uma política geral.
**Resposta da Clara:** "2. Deve ser indicado a troca de empresa antes da remoção, pode fazer isso
como se fosse um pop-up, um por um, quando for apagar uma empresa que tem processos" — confirma
reatribuição (não cascata), com um pop-up por empresa no momento da exclusão.

**Decisão de implementação (não perguntada de novo, sinalizada depois de pronta):** a Clara citou
só "processos" na resposta, mas os quatro tipos de vínculo (laudo/audiência/cobrança/processo)
têm exatamente a mesma restrição técnica (FK NOT NULL) e o mesmo problema — generalizei a
reatribuição pros quatro em vez de deixar laudo/audiência/cobrança ainda bloqueando a exclusão
enquanto só processo seria resolvido. Continua sendo uma escolha reversível (é um parâmetro
opcional; sem ele, nada muda).

**Implementado:**
- Tabela nova `SetorModulo` (`setor_id` + `modulo`) — ausência de linha pra um setor = acesso a
  todas as abas da operadora dele (retrocompatível, sem precisar migrar dado nenhum); só setores
  editados explicitamente na tela ganham restrição.
- `app/auth.py::modulos_acessiveis`/`require_modulo` (+ par web) — mesmo padrão de
  `operadoras_acessiveis`/`require_operadora`, só que por módulo/aba em vez de por operadora
  inteira. Pendências (que não tinha gate de operadora, por misturar EXIMIA/ELITE na mesma tela)
  ganhou `require_modulo("PENDENCIAS")`, marcado como válido pras duas operadoras.
- Tela de Setores: checkbox "Restringir abas" + lista de módulos (só os válidos pra operadora
  escolhida, filtrados tanto no JS quanto no backend) em cada linha da tabela e no formulário de
  criação. Marcar "Restringir" sem escolher nenhuma aba é rejeitado, pra não criar sem querer um
  setor indistinguível de "sem restrição" no banco.
- `excluir_empresa` ganhou `empresa_destino_id` opcional — com vínculo e destino informado,
  reatribui os quatro tipos de registro antes de excluir; sem destino, continua bloqueando como
  sempre. O modal de exclusão por empresa (Empresas-clientes) passou a mostrar um seletor "Mover
  histórico vinculado para" só quando aquela empresa específica tem vínculo.

**Testado:** suíte completa sem regressão (17 testes novos: unidade de `modulos_acessiveis`, 403
por módulo, persistência de setor com módulos pela API e pela tela, serviço de reatribuição de
empresa, web de exclusão com destino) + lint limpo + Playwright end-to-end nas duas telas
(restringir um setor existente, criar setor já restrito, os checkboxes de módulo reagindo à
operadora escolhida, modal de exclusão de empresa com o seletor de destino, reatribuição
confirmada no banco depois).

**Reversível:** sim — os dois são aditivos (parâmetro opcional em `excluir_empresa`, tabela nova
`SetorModulo` cujo estado padrão preserva o comportamento de antes); nenhuma rota ou tela
existente muda de comportamento pra quem não usa as opções novas.

## 2026-09-28 — Layout de Setores, "marcar todas as abas", exclusão de setor e pop-up de suporte

**Contexto:** a Clara mandou um screenshot da tela de Setores marcando o card "Novo setor" e
pediu: (1) melhorar o layout daquela área; (2) uma opção de selecionar todas as abas, "e não só
estas 3" (ela tinha escolhido operadora ELITE, que só libera 3 dos 5 módulos — LAUDOS, PROCESSOS,
PENDENCIAS); (3) poder apagar setor. Na mesma mensagem, pediu um pop-up de suporte novo: circular,
no canto inferior da tela, que abre um pop-up maior com "Assunto do chamado" e "Descrição...", e
manda isso por e-mail pra claracosta@elitemediacoes.com.br.

**Pergunta 1 (selecionar todas as abas):** a frase "e não só estas 3" tinha duas leituras
possíveis — um atalho "marcar todas" pras abas que já apareciam (continuando restrito à operadora
do setor, como ela mesma decidiu na rodada anterior), ou abrir as 5 abas do sistema pra qualquer
setor, mesmo fora da operadora dele (o que reverteria essa decisão). Perguntei antes de assumir.
**Resposta da Clara:** "Atalho 'Marcar todas' (Recomendado)" — confirma que a restrição por
operadora continua valendo; só queria um jeito mais rápido de marcar tudo que já é permitido.

**Pergunta 2 (envio de e-mail do pop-up de suporte):** o sistema não tinha nenhuma configuração
de e-mail (nem SMTP, nem serviço tipo SendGrid) — perguntei qual caminho ela queria: SMTP comum
(Gmail/Outlook com senha de app), um serviço transacional (SendGrid/Mailgun/Resend), ou só abrir
o e-mail pronto no aplicativo de e-mail da pessoa (`mailto:`, sem precisar de credencial nenhuma,
mas dependente do usuário ter um cliente de e-mail configurado).
**Resposta da Clara:** "SMTP (Gmail/Outlook com senha de app)".

**Implementado:**
- Layout: o card "Novo setor" tinha um bug de raiz (não só estético) — o checkbox "Restringir
  abas" e o bloco de módulos estavam dentro do `<form class="formulario">` (flex-row), a mesma
  classe de bug já vista no painel de edição de usuário antes nesse projeto. Corrigido tirando os
  dois pra fora do form (que ganhou `id="novo-setor"`), com os campos apontando pro form via
  `form="novo-setor"` — mesmo padrão já usado nas linhas de tabela de Empresas/Setores. Grade de
  módulos trocada de lista vertical pra CSS grid, mais compacta.
- "Marcar todas"/"Limpar seleção": dois botões de texto que só mexem nas caixas **visíveis no
  momento** — as escondidas pela filtragem por operadora ficam de fora, então nunca marcam uma
  aba fora da operadora do setor.
- Exclusão de setor: `services/setores.py::excluir_setor` (novo), mesma proteção de
  `excluir_empresa` — bloqueia se o setor tiver usuário vinculado (`UsuarioSetor`), pedindo pra
  desativar ou desvincular primeiro. Botão de lixeira + modal de confirmação por linha, mesmo
  padrão visual de Empresas-clientes.
- Pop-up de suporte: botão circular fixo no canto inferior direito (`base.html`, visível em toda
  tela autenticada) que abre um `<dialog>` maior com "Assunto do chamado" + "Descrição". Envio via
  `fetch()` (não form/redirect, pra funcionar de qualquer página) pra `POST /app/suporte/chamado`,
  que usa `services/suporte.py::enviar_chamado` (SMTP direto via `smtplib`, STARTTLS + login,
  `Reply-To` = e-mail de quem abriu o chamado). Sem as variáveis de ambiente de SMTP configuradas,
  o botão continua aparecendo mas o envio recusa com uma mensagem amigável ("avise o
  administrador") em vez de estourar um erro genérico — verificado visualmente que esse fallback
  funciona corretamente.

**Pendência:** a Clara ainda precisa passar as credenciais reais de SMTP (host, porta, e-mail e
senha de app do Gmail/Outlook) como variáveis de ambiente no Render — sem isso, o pop-up de
suporte fica visível mas o envio não funciona de verdade em produção ainda.

**Testado:** suíte completa sem regressão (188 testes, 12 novos) + lint limpo + Playwright
cobrindo layout novo em claro/escuro e desktop/mobile, "Marcar todas"/"Limpar seleção", exclusão
de setor bloqueada por vínculo e permitida sem vínculo, e o pop-up de suporte abrindo/preenchendo/
enviando (com SMTP mockado nos testes automatizados, já que não há credencial real ainda).

**Reversível:** sim — tudo aditivo (rota nova, variáveis de ambiente novas e opcionais, nenhuma
coluna/tabela removida); nenhum comportamento existente de Setores/Empresas mudou.

## 2026-09-28 — Integração com planilhas: análise pedida sem implementação

**Contexto:** a Clara pediu explicitamente uma análise e recomendação — "NÃO implemente nada, não
altere código, banco de dados nem planilhas" — sobre integrar Laudos/Audiências/Pendências/Gestão
de Processos com as planilhas que a equipe usa hoje. O pedido veio com um modelo detalhado (Etapas
1-4 + formato de entrega), mas três campos ficaram com o texto `[PREENCHA...]` do modelo, sem
preenchimento: onde as planilhas ficam, onde estão as cópias de exemplo, quem as edita.

**O que eu verifiquei antes de escrever qualquer coisa:** procurei por qualquer arquivo `.xlsx`/
`.xls`/`.csv` ou pasta de exemplos no repositório inteiro — não existe nenhum. Isso significa que a
Etapa 2 do pedido (analisar a estrutura real das planilhas) não pode ser feita de verdade nesta
rodada — eu não tenho a planilha real pra olhar. Decidi **não inventar/presumir uma estrutura
plausível** só pra preencher a seção — isso violaria a própria regra que a Clara deu ("PERGUNTE
antes de concluir"). Em vez disso, documentei em `docs/integracao-planilhas.md` seção 2.1 essa
lacuna de forma explícita, e usei como melhor aproximação disponível tudo que o parser já existente
(`app/excel_reader.py` + os quatro `services/*.py`) já sabe sobre a estrutura esperada — cabeçalhos
exigidos, aliases conhecidos, chaves de duplicidade, e os problemas de dado real já documentados no
código (com números reais: 6.278 linhas de Processos descartadas por número de processo inválido,
484 por falha ao separar "EMPRESA - Cliente", no último import validado, ver `ARCHITECTURE.md`
3.5). Isso cobre boa parte do que a Etapa 2 pedia, mas do lado do sistema, não da planilha real —
deixei essa distinção clara no documento.

**Achado relevante:** uma resposta a "onde as planilhas ficam" já existe registrada neste mesmo
projeto, de 21/09 (`ARCHITECTURE.md` seção 1.9, item 1): Google Sheets, atualizado todo dia pela
equipe — inclusive já havia um sequenciamento proposto na época (seção 2.5, D4) prevendo upload
manual primeiro e integração com a API do Google Sheets depois, exatamente o que está sendo pedido
agora. Decidi **não simplesmente reaproveitar essa resposta antiga sem confirmar** — o campo veio
em branco nesta rodada, o que pode significar que mudou, ou só que o modelo não foi preenchido dessa
vez. Perguntei de novo, citando a resposta anterior, em vez de assumir silenciosamente que continua
valendo.

**Entregue:** `docs/integracao-planilhas.md` — diagnóstico do sistema atual (stack, como os dados
entram hoje nas 4 áreas, modelo de dados/campos/relacionamentos, autenticação/permissões,
dependências já instaladas), diagnóstico parcial das planilhas (com a lacuna acima documentada),
comparação de 5 abordagens de integração (API direta, agendada vs. sob demanda, upload — o que já
existe, automação do lado da planilha, bidirecional), recomendação (leitura via API, sob demanda,
começando por uma área piloto, mantendo o upload manual como alternativa), plano em 6 fases,
ajustes recomendados nas planilhas, riscos/LGPD, e 10 perguntas pendentes (as do modelo da Clara +
a confirmação da lacuna de exemplo + duas específicas: minha leitura de "digitação duplicada" pra
confirmar se entendi certo o problema, e como tratar as ~21 abas de Gestão de Processos).

**Nenhum código, dado ou planilha foi alterado** — só o documento de análise foi criado, e uma
entrada de registro em `ARCHITECTURE.md` (seção 4.24) apontando pra ele, seguindo o mesmo padrão já
usado pra outras fases de levantamento deste projeto (ex.: Fase 5/Gestão de Processos, seção 3, foi
documentada como levantamento antes de qualquer implementação).

**Reversível:** não se aplica — nada foi implementado.

## 2026-09-28 — Integração com planilhas: respostas da Clara e ajuste da recomendação

**Contexto:** a Clara respondeu às perguntas pendentes de `docs/integracao-planilhas.md` (mesmo dia
da análise inicial). Confirmado: Google Sheets no Google Drive; muitas pessoas editam cada
planilha; o sistema deve **só ler** ("não deve mexer em NADA nas planilhas"); mecanismo = API;
frequência = no mínimo 10x/mês; escopo/prioridade das áreas ficou a meu critério; o problema real é
"o trabalho que está dando ter que subir as atualizações toda vez" (confirmou minha leitura); Gestão
de Processos deve considerar automaticamente as 21 abas.

**Mudança de recomendação, com justificativa:** a análise original recomendava começar por
sincronização **sob demanda** (um botão), deixando o agendamento automático para uma fase posterior,
como forma de reduzir risco/esforço inicial. A resposta da Clara sobre frequência mínima (10x/mês) e,
principalmente, sua explicação do problema real ("o trabalho de subir toda vez") tornam essa
recomendação inadequada: um botão manual não resolve o incômodo dela, que é justamente depender de
alguém lembrar de agir. Revisei a recomendação para **sincronização automática agendada desde o
início** (ex. algumas vezes por dia — folga confortável acima do mínimo pedido), mantendo um botão
manual como complemento (útil para testar e para forçar uma atualização pontual), não como a solução
principal.

**Duas respostas que pareceram cruzar com outras perguntas — sinalizado à Clara, não assumido:**
- A pergunta sobre "fonte oficial em caso de conflito" ficou sem resposta direta — mas como a
  direção é só leitura (confirmada), a pergunta deixa de fazer sentido no desenho atual (não existe
  dado "do sistema" competindo com o da planilha) — resolvida por inferência, registrada como tal.
- A pergunta sobre se a **equipe** (os humanos que editam as planilhas) toparia padronizar
  cabeçalhos/usar menus suspensos veio respondida com "o sistema não deve mexer em NADA nas
  planilhas" — que responde a uma pergunta diferente (se o *sistema* escreve nelas, já coberta pela
  pergunta de direção). Não presumi que isso também respondia à pergunta sobre ajuste feito pelos
  *humanos* — re-perguntei de forma mais clara no documento, sem travar o restante do plano por
  causa disso.

**Escolhi a área piloto (Laudos), já que a Clara deixou a critério meu:** operadora única (ELITE),
menor conjunto de colunas entre as 4 áreas, sem CPF (diferente de Audiências), e um comportamento
já bem coberto por teste (preferência pela coluna A na leitura de data) — bom primeiro caso pra
validar o mecanismo ponta a ponta antes de Processos (a mais complexa).

**Único bloqueio real que continua em aberto:** exemplo real de planilha (Laudos, pelo menos) — sem
isso não dá pra confirmar se os cabeçalhos que o sistema já espera hoje ainda batem com o que existe
de verdade, nem detectar problemas de dado que só apareceriam numa planilha real. `docs/
integracao-planilhas.md` seção 8 explica três formas de me enviar isso (anexar no chat, exportar pro
repositório, ou compartilhar o link — com recomendação contra a terceira opção por expor dado real).

**Nenhum código, dado ou planilha foi alterado** — só o documento de análise foi atualizado, e a
entrada em `ARCHITECTURE.md` (seção 4.24) complementada com este resumo.

**Reversível:** não se aplica — nada foi implementado.

## 2026-09-29 — Configuração selecionável por setor: recusei reverter sem confirmar

**Contexto:** a Clara mandou um screenshot do menu lateral completo (incluindo "Configuração") e
pediu que a lista de abas selecionáveis por setor tivesse "literalmente todas as opções" da foto.
Isso incluiria Configuração — que eu tinha deixado de fora de propósito, por decisão explícita dela
do dia anterior ("só liberadas pelo papel global... deve continuar restrita às abas da operadora do
próprio setor" não se aplicava a Configuração, que ficou fora da seleção por setor inteiramente).

**Por que perguntei antes de mudar:** incluir Configuração como selecionável por setor deixaria um
colaborador comum (não-admin) de um setor com essa aba liberada capaz de criar/editar outros
usuários do sistema — não é só mais uma tela operacional, é acesso administrativo. Reverter uma
decisão de segurança que ela mesma tinha tomado, sem confirmar que era isso que ela queria (ela pode
só ter esquecido dessa decisão, ou pensado que a foto do menu = a lista completa disponível), seria
o tipo de assunção que a regra dela pede pra eu nunca fazer.

**Resposta da Clara:** "Não, manter como está (Recomendado)" — confirmou que Configuração continua
de fora, só por `papel_global`. **Nenhuma mudança de código foi feita.** Expliquei a ela, em vez
disso, que as 5 abas operacionais da foto já eram todas selecionáveis, e que a razão de às vezes
aparecerem menos de 5 é o filtro por operadora do setor (regra que ela também já tinha confirmado
manter).

**Reversível:** não se aplica — nada foi implementado.

## 2026-09-29 — Sub-navegação em Configuração, cards 3x3, pop-up de suporte redesenhado

**Contexto:** três pedidos visuais na mesma mensagem, sem ambiguidade estrutural (puramente
apresentação, nenhum dado/permissão envolvido) — implementados direto, sem pergunta prévia:
(1) ao entrar numa das 4 áreas de Configuração, mostrar as outras 3 "em cima" (sem precisar voltar);
(2) os 6 cards da tela inicial organizados 3-e-3, maiores; (3) deixar o pop-up de suporte (pequeno e
grande) mais bonito.

**Decisão de implementação (1):** criei `app/web/areas_configuracao.py` centralizando a lista das 4
áreas (antes só existia dentro de `routes_configuracao.py`, sem acesso das outras 4 rotas) e um
macro Jinja reaproveitado (`_config_subnav.html`) — evita repetir a lista/markup 5 vezes. A sub-nav
fica logo abaixo do "Voltar à Configuração" já existente (não o substitui).

**Decisão de implementação (2):** dei ao grid da tela inicial classes próprias
(`grid-modulos-inicio`/`modulo-grande`), em vez de mudar `.grid-modulos`/`.modulo` diretamente —
essas classes genéricas também são usadas pelos 4 cards de Configuração, que a Clara não pediu pra
mudar; mudar a classe genérica teria alterado as duas telas por engano.

**Decisão de implementação (3):** aproveitei o mesmo tom de gradiente do botão da marca (`--navy-
light`→`--navy`→`--navy-deep`) no cabeçalho do pop-up grande, com um ícone circular e texto branco,
e dei ao botão "Enviar chamado" a cor de destaque (`--accent`, azul) — distinto do "Cancelar" e dos
outros botões do sistema (que são todos navy), reforçando visualmente que é a ação principal.
Achado no caminho: a regra genérica `dialog.modal-confirmacao h3` tinha mais especificidade CSS que
o seletor de classe que eu tinha escrito pro texto branco do cabeçalho — corrigido prefixando com
`dialog.popup-suporte` pra vencer a regra genérica (sem isso, o texto ficaria escuro sobre o fundo
escuro do gradiente, quase ilegível).

**Testado:** suíte completa sem regressão (188 testes) + lint limpo + Playwright em claro/escuro/
mobile (sub-navegação nas 4 telas, grade 3x3 colapsando pra 1 coluna no mobile, pop-up pequeno e
grande).

**Reversível:** sim — só CSS/template/rotas passando um dado extra; nenhuma coluna de banco,
permissão ou lógica de negócio mudou.

## 2026-09-29 — Pop-up de suporte falhava com "Errno 101" ao enviar por Gmail

**Contexto:** a Clara configurou as variáveis de SMTP no Render (Gmail, senha de app) e testou o
pop-up de suporte — o envio falhou com `[Errno 101] Network is unreachable`. Ela não tinha acesso
aos logs internos do Render pra mais detalhe, só o texto do erro que já aparecia na tela (o próprio
sistema mostra a mensagem de exceção capturada).

**Diagnóstico, sem acesso ao ambiente de produção:** pedi o texto exato do erro antes de mexer em
qualquer coisa (poderia ser autenticação, DNS, firewall, várias causas diferentes por trás de um
"erro genérico"). Confirmado "Errno 101" = `ENETUNREACH` do sistema operacional (não um código do
Gmail) — sintoma característico e bem documentado de containers/ambientes em nuvem que resolvem um
hostname (`smtp.gmail.com`) para um endereço IPv6 primeiro, mas não têm rota de saída IPv6
configurada. Não era nada que a Clara tivesse configurado errado — o código (`smtplib.SMTP` puro)
deixava o sistema operacional escolher entre IPv4/IPv6 livremente.

**Correção:** `app/services/suporte.py` ganhou `_SMTPForcandoIPv4`, uma subclasse de `smtplib.SMTP`
que resolve e conecta só em endereços IPv4, evitando a tentativa de IPv6 que falhava. Cuidado
específico: manter `self._host` como o nome (`smtp.gmail.com`), não o IP resolvido — a verificação
de certificado TLS em `starttls()` depende disso pra não quebrar.

**Testado:** teste novo isolado confirma que a resolução só pede endereços `AF_INET` (sem rede de
verdade — mocka `socket.getaddrinfo`/`socket.socket`); os testes existentes que mockavam
`smtplib.SMTP` foram ajustados pra mockar a nova classe (a subclasse não herda dinamicamente do que
o teste substitui no módulo `smtplib`, então o mock antigo tinha parado de funcionar pra esse
caminho). Suíte completa sem regressão (189 testes, 1 novo) + lint limpo.

**Reversível:** sim — troca só a classe usada internamente pra abrir a conexão SMTP; nenhuma
variável de ambiente, rota ou comportamento visível mudou. A Clara não precisa reconfigurar nada no
Render — é só testar de novo depois do deploy.

## 2026-09-29 — Pop-up de suporte: migrado de SMTP pra API HTTP da Resend

**Contexto:** a correção de IPv4 (entrada anterior) não resolveu — a Clara testou de novo e o erro
mudou de `[Errno 101] Network is unreachable` pra `timed out`. Fui atrás do texto exato do erro
antes de mexer em qualquer coisa de novo (dessa vez precisei pedir três formas diferentes até
conseguir — console do navegador não mostra o corpo da resposta, só o status; a aba certa é
Network → clicar na requisição → Response/Preview, não Sources).

**Diagnóstico:** "timed out" é um sintoma diferente de "Network is unreachable" — a conexão fica
esperando resposta até estourar o limite, em vez de falhar na hora. É o padrão de um firewall de
saída **derrubando o pacote em silêncio**, não recusando — comum em plataformas de hospedagem que
bloqueiam SMTP de saída (mesmo na porta 587) pra evitar virar relay de spam. Não era mais um bug de
código corrigível ajustando o `smtplib` — o problema é a conexão TCP nunca completar.

**Por que perguntei antes de migrar, em vez de só trocar:** migrar de SMTP pra uma API HTTP (Resend)
significa a Clara criar uma conta nova e gerar uma credencial nova — não é uma correção pequena, é
uma troca de abordagem. Perguntei se ela queria migrar direto (minha recomendação, com um argumento
concreto: este mesmo projeto já usou a Resend com sucesso nesse mesmo Render antes, no alerta de
prazo de Gestão de Processos — removido por decisão de produto dela, não por falha técnica) ou
tentar mais uma porta de SMTP primeiro (mudança menor, mas alto risco de ser a mesma causa raiz e
não resolver, já que "timed out" sugere bloqueio de porta, não erro de configuração específico de
uma porta). Ela escolheu migrar pra Resend.

**Implementado:** `app/services/suporte.py` reescrito sem `smtplib`/`_SMTPForcandoIPv4` (removidos
por completo — nunca deixo um caminho morto quando sei que não vai ser usado de novo), usando
`urllib.request` (biblioteca padrão, sem dependência nova) pra um `POST` HTTPS simples na API da
Resend — mesma porta 443 de qualquer chamada normal do navegador, contornando de vez a classe de
problema de firewall/porta de SMTP. `app/config.py`: variáveis `smtp_*` substituídas por
`resend_api_key`/`resend_remetente` (padrão: endereço de teste da própria Resend, funciona sem
verificar domínio)/`destinatario_suporte`.

**Testado:** suíte reescrita mockando `urllib.request.urlopen` (mesma cobertura de antes) — 189
testes, lint limpo. Verificado com Playwright que o fallback "não configurado" continua amigável.

**Pendência da Clara:** criar conta grátis na Resend, gerar uma chave de API, e trocar as variáveis
`SMTP_*` no Render por `RESEND_API_KEY` (as `SMTP_*` antigas ficam inofensivas se não forem
removidas, mas não fazem mais nada).

**Reversível:** sim — troca isolada de mecanismo de envio; nenhuma rota, permissão ou comportamento
visível pra quem usa o pop-up mudou.

## 2026-09-29 — Pop-up de suporte: bloqueio do Cloudflare por assinatura de bot

**Contexto:** a Clara testou de novo depois do deploy da migração pra Resend (entrada anterior) e
recebeu um erro novo: `error code: 1010`. Terceiro erro diferente no mesmo dia, na mesma
funcionalidade — sinal de que cada camada resolvida revela a próxima (rede → SMTP bloqueado →
agora um detalhe da própria chamada HTTP).

**Diagnóstico:** reconheci o formato "error code: 1010" como um código padrão da Cloudflare
("acesso negado com base na assinatura do navegador" — bloqueio anti-bot), não um erro da Resend em
si — a API da Resend fica atrás de Cloudflare, e esse bloqueio acontece antes da requisição chegar
no backend deles. Não precisei pedir mais informação à Clara pra esse — o texto já era
autoexplicativo. Tentei confirmar batendo na API real a partir deste ambiente, mas o proxy de rede
sandboxed daqui bloqueia a chamada por um motivo totalmente diferente (nada a ver com Resend/
Cloudflare) — segui só com o diagnóstico teórico, que é bem documentado e específico o bastante pra
eu ter confiança nele.

**Causa provável:** `urllib.request` sem um `User-Agent` configurado se identifica como
`Python-urllib/3.x`, uma assinatura genérica que proteções anti-bot reconhecem e bloqueiam por
padrão — independente da chave de API estar certa ou não.

**Implementado:** `app/services/suporte.py` ganhou um `User-Agent` próprio
(`EliteSistem/1.0 (+https://elite-sistem.onrender.com)`) e `Accept: application/json` nos
cabeçalhos da chamada.

**Testado:** teste ajustado pra confirmar que o `User-Agent` enviado não é mais a assinatura padrão
do `urllib`. 189 testes, lint limpo. **Não validado contra a API real** — o ambiente sandboxed não
consegue alcançar a Resend pra confirmar de ponta a ponta; a Clara precisa testar de novo depois do
próximo deploy e me avisar se esse foi o bloqueio de verdade ou se ainda falta algo.

**Reversível:** sim — só um cabeçalho HTTP a mais; nada mais mudou.

## 2026-09-29 — Cartas: botão "Copiar texto" (nova rota em vez de reaproveitar "Copiar resumo" tal como está)

**Pedido da Clara:** "na parte de Cartas, preciso que exatamente o mesmo conteúdo que vem escrito no
PDF (e com a mesma formatação) venha escrito em formato de texto para copiar e colar".

**Decisão de design (sem ambiguidade de negócio, então implementei direto):** o padrão "Copiar
resumo" de Laudos depende do texto já estar pronto no HTML quando a página carrega — a tela de
Laudos é um GET com os filtros na querystring, redesenhada no servidor a cada busca. Cartas não
funciona assim: o `POST` de "Gerar PDF" devolve o arquivo direto pra download, sem re-renderizar a
página com dados novos — não haveria onde embutir o texto de antemão do jeito que Laudos faz.
Optei por uma rota nova por carta (`/app/cartas/convite-cliente/texto` e `.../convite-banco/texto`)
que devolve o texto em JSON sob demanda (mesma validação de link/CPF do PDF), chamada via fetch no
clique do botão "Copiar texto" — mesmo padrão de UX final (toast "Texto copiado.", igual ao de
Laudos), só a mecânica por trás é diferente por causa de como Cartas já funcionava.

**Conteúdo do texto:** reproduz cada parágrafo do PDF na mesma ordem, com a marcação de formatação
do PDF (negrito, cor, link clicável, sublinhado) simplesmente omitida — texto puro não carrega
negrito/cor/sublinhado. Não perguntei à Clara sobre esse detalhe porque é uma limitação inerente de
"formato de texto" (ela mesma pediu as duas coisas juntas: "mesmo conteúdo" e "formato de texto" —
o texto por definição não carrega a formatação visual do PDF, só a mesma ordem/estrutura de
parágrafos e o mesmo conteúdo). Se ela achar que falta alguma coisa depois de testar, ajusto.

**Testado:** `tests/test_cartas.py` novo (Cartas não tinha teste nenhum até então) — formatação e
as duas rotas novas. 196 testes, lint limpo. Verificado com Playwright: texto copiado bate
exatamente com o texto do PDF (conferido campo a campo), toast de sucesso/erro funcionando.

**Reversível:** sim — duas rotas e um botão novos, aditivos; nada do fluxo de PDF existente mudou.

## 2026-09-30 — Carta Banco: campo "CPF" aceita CNPJ (identificação automática)

**Pedido da Clara:** "o campo CPF do cliente seja possível inserir CNPJ e, para o texto da carta,
ela precisa identificar se é CPF ou CNPJ e colocar de forma correta no texto do pdf e para colar" —
o titular da unidade, na Carta Convite Banco, às vezes é pessoa jurídica.

**Decisão de design (sem ambiguidade de negócio):** o campo passou a aceitar CPF (11 dígitos) ou
CNPJ (14 dígitos), identificados automaticamente pela quantidade de dígitos — sem precisar de um
seletor "tipo de documento" separado, já que o próprio número já diz qual é. Cada um é validado com
seu próprio algoritmo de dígito verificador (CPF já existia; CNPJ novo, mesmo padrão da Receita). O
rótulo mostrado no PDF e no texto pra copiar ("CPF: ..." ou "CNPJ: ...") muda de acordo com o que foi
identificado — nunca mais fixo em "CPF:". Renomeei o rótulo do campo na tela de "CPF" pra "CPF/CNPJ"
pra deixar claro que os dois são aceitos, sem mexer no nome técnico do campo (`id`/`name="cpf"`
continuam iguais — só o texto visível mudou).

**Testado:** `tests/test_cartas.py` — validação de CPF/CNPJ certos e errados, texto/PDF com titular
pessoa jurídica mostrando "CNPJ" (não "CPF"), regressão com CPF continuando igual. 204 testes, lint
limpo. Verificado com Playwright: CNPJ válido funciona (copia o texto certo, rótulo "CNPJ:"), CNPJ
com dígito verificador errado mostra "CNPJ inválido" (mensagem específica, não a genérica de CPF).

**Reversível:** sim — extensão aditiva; CPF continua funcionando exatamente como antes.

## 2026-09-30 — Cartas: erro genérico ao gerar PDF (`entidade_id` VARCHAR(40) truncando em produção)

**Relato da Clara:** print da tela "Algo deu errado" ao clicar em "Gerar PDF" nas Cartas — sem mais
detalhes (a tela de erro genérica não mostra o motivo real de propósito, pra não vazar detalhe
técnico pro usuário final).

**Diagnóstico sem precisar pedir mais nada a ela:** reconheci o padrão porque já vi esse exato bug
neste projeto antes, em outras tabelas — `registrar()` grava `convite.autor`/`convite.nome`
(texto livre, já em maiúsculas, sem limite de tamanho no formulário) na coluna `entidade_id` de
`logs_auditoria`, que era `VARCHAR(40)`. Nome completo ou razão social passa de 40 caracteres fácil.
Postgres (produção) aplica esse limite de verdade e recusa o insert (`StringDataRightTruncation`) —
SQLite (testes) não aplica limite de `VARCHAR` nenhum, por isso os 204 testes anteriores não
pegaram. Essa exceção não é `ValueError`, então não cai no tratamento de erro de validação das
rotas de Cartas — vira erro não tratado, tela genérica.

**Correção:** `entidade_id` virou `Text` (sem limite) — mesmo ajuste já aplicado antes em
`Processo.advogada`/`assistente` e `Audiencia.nome_cliente` (mesma causa raiz, tabela diferente).
`app/db.py::init_db()` ganhou o `ALTER TABLE` correspondente pra alargar a coluna já existente em
produção (esse projeto não usa Alembic) — roda sozinho no próximo deploy, sem passo manual da
Clara.

**Testado:** novo teste em `tests/test_cartas.py` gera uma carta com autor de 73 caracteres e
confirma que o log de auditoria guarda o valor inteiro (não reproduz o crash de Postgres em si —
SQLite não aplica limite de `VARCHAR` — mas protege contra a coluna voltar a ser `String(N)` por
engano). 205 testes, lint limpo.

**Reversível:** sim — só alarga uma coluna existente; nenhum dado perdido, nenhum comportamento
visível muda além do bug corrigido.

## 2026-10-01 — Pop-up de suporte: abandonado e-mail, chamado guardado no sistema + aviso no Discord

**Pergunta da Clara:** depois de três tentativas sem sucesso de enviar o chamado por e-mail em
produção (rede bloqueada → Cloudflare → verificação de domínio da Resend não completando mesmo em
duas tentativas dela), ela perguntou se havia outra forma, e o que empresas costumam fazer pra
receber esse tipo de chamado.

**Minha resposta (antes de implementar):** a maioria guarda o chamado no próprio sistema — nunca
depende de provedor externo, sempre funciona — e usa um canal mais simples de configurar que e-mail
corporativo pra avisar na hora (Discord/Slack/Telegram, sem verificação de domínio nenhuma).
Recomendei migrar pra essa abordagem em vez de insistir num quarto provedor de e-mail. A Clara
confirmou e escolheu Discord como canal de aviso.

**Implementado:** chamado vira uma tabela nova (`Chamado`) — salva sempre, sem depender de nada
externo. Uma tela de Configuração (`/app/chamados`, só Admin) lista todos e permite marcar/reabrir
resolvido. O aviso no Discord é opcional e best-effort: configurado via `DISCORD_WEBHOOK_SUPORTE`,
e uma falha nele (webhook errado, Discord fora do ar, não configurado) nunca impede o chamado de
ser salvo — diferente da versão por e-mail de antes, onde falha no provedor recusava o chamado
inteiro. Removi `smtplib`/Resend por completo do código (sem deixar caminho morto).

**Testado:** `tests/test_suporte.py` reescrito (banco + aviso Discord mockado, incluindo teste de
que falha no Discord não impede salvar); `tests/test_chamados.py` novo (lista, gate de Admin,
marcar/reabrir). 208 testes, lint limpo. Verificado com Playwright: chamado aberto pelo pop-up sem
nenhum Discord configurado — sucesso imediato, sem erro nenhum (diferente de antes, quando faltar
configuração recusava o chamado); aparece na lista; resolver/reabrir funcionando.

**Pendência da Clara:** criar um webhook num canal do Discord (opcional — Configurações do canal →
Integrações → Webhooks) e configurar `DISCORD_WEBHOOK_SUPORTE` no Render, se quiser ser avisada na
hora. Sem isso, os chamados continuam aparecendo normalmente na tela de Chamados.

**Reversível:** sim — tabela nova, nada existente foi alterado.

## 2026-10-02 — Gestão de Processos: fatal só na aba FATAIS agora entra no relatório

**Pergunta da Clara:** se o relatório pega os fatais das abas FATAIS (com os meses ao lado).

**Investigação:** sim, pra abas FATAIS que têm uma coluna de data real ("DIA") — mas abas/linhas
que só têm a data de quando a cliente foi inserida na planilha (sem data de andamento real) são
excluídas do relatório inteiro desde a correção de 2026-09-24 (seção 4.12 do ARCHITECTURE.md,
decisão já confirmada pela Clara na época — fazia o processo "ganhar" um mês errado). Isso incluía
excluir a determinação do "Fatal" também: um processo só marcado fatal numa dessas abas, sem
nenhum outro andamento datado, nunca aparecia em relatório nenhum.

**Pergunta de volta à Clara (ambiguidade real — como tratar o "mês" de algo sem data real):** usar
a data de liberação como se fosse a data do andamento (processo entra no relatório do mês em que
foi inserido na aba FATAIS), ou criar uma lista separada "fatais sem data" sempre visível,
independente do período escolhido. **Ela escolheu a primeira opção** (recomendada — mantém a
mesma lógica de período que o resto do sistema já usa).

**Implementado:** `_processos_em_escopo`/`_ultimo_evento_por_processo`
(`app/services/processos.py`) passam a incluir um evento `data_e_liberacao=True` quando
`prazo_fatal` for "SIM" — antes excluíam sempre. Um evento sem fatal continua excluído
normalmente (comportamento de 2026-09-24 preservado pro caso comum). Dados já importados não
precisam de reimportação — o `data_e_liberacao`/`prazo_fatal` já eram gravados certos, só o
filtro de leitura do relatório mudou.

**Testado:** novo teste confirma o processo-só-fatal-na-FATAIS aparecendo no relatório Geral e
Por Empresa com `fatal=True`; o teste antigo (caso sem fatal, continua excluído) segue passando
sem mudança. 209 testes, lint limpo.

**Efeito esperado:** contagem de processos por mês pode subir um pouco onde houver fatal só na
aba FATAIS dentro do período — é o comportamento pedido, avisar a Clara se ela notar a diferença
num relatório já conhecido.

**Reversível:** sim — reverter a condição `or_(...)` nas duas funções desfaz, sem mexer em dado
nenhum já importado.

## 2026-10-05 — Relatórios em Excel (Cartas e Pendências ficam de fora)

**Pedido da Clara:** "preciso que todos os relatórios do sistema tenham a opção de serem baixados
em formato de excel".

**Decisão de escopo (sem ambiguidade de negócio — segui a própria definição do sistema do que é
"relatório"):** Laudos, Audiências e Gestão de Processos (Geral e Por Empresa) ganharam Excel —
são os 4 que já tinham PDF, isto é, os relatórios tabulares de verdade. Cartas (carta-convite, já
tem "Copiar texto" desde 2026-09-29) e Pendências (mensagem de cobrança em texto corrido) ficam de
fora — nenhum dos dois é uma tabela/lista, nenhum dos dois tinha PDF antes por esse mesmo motivo.
Se a Clara quiser Excel pra algum desses dois mesmo assim, é um pedido novo (teria que definir o
que viraria linha de planilha, já que hoje nenhum dos dois é tabular).

**Implementado:** `app/excel_export.py` novo, uma função por relatório, reaproveitando o mesmo
dataclass de resultado que o PDF já usa (sem repetir consulta ao banco). Rotas `GET /<módulo>/
relatorio.xlsx`, mesmos parâmetros do `.pdf`, mesma autenticação por cookie. Botão "Baixar Excel"
ao lado de "Baixar PDF" nas 3 telas.

**Testado:** `tests/test_excel_export.py` novo (conteúdo/formatação das 4 planilhas) + testes de
rota em `test_api_laudos.py`/`test_web.py`. 218 testes, lint limpo. Verificado com Playwright: os
4 downloads completam, conteúdo bate com a tela.

**Reversível:** sim — módulo e rotas novos, aditivos.

## 2026-10-05 — Novo módulo "Correspondências": perguntas respondidas e decisões

**Pedido da Clara:** ambiente novo, mesmo padrão de Laudos (upload, filtro mês+empresa, PDF/Excel),
com uma regra explícita no topo da mensagem: "qualquer dúvida, pergunte antes de decidir — não
assuma nem escolha uma solução por conta própria". A mensagem original tinha o nome do ambiente
como placeholder ("[NOME DO AMBIENTE]") não preenchido, e cortava no meio de uma frase.

**Primeira rodada de perguntas (antes de qualquer código):**
1. Nome do ambiente → **"Correspondências"**.
2. Completar a frase cortada → regra de linha em branco (ignorar), regra de coluna faltando
   (mensagem clara) e cinco perguntas que a própria Clara já tinha identificado como precisando da
   minha pergunta antes de implementar (itens 3-4 abaixo).

**Segunda rodada, depois de explorar o código de Laudos e ler a planilha de exemplo anexada (achei
a aba real: "ADV. CONTRATOS", dentro de `PLANILHA_2026.xlsx`, que tem mais 7 abas sem relação):**
3. **Operadora** → ELITE (mesma de Laudos/Processos).
4. **Controle de ano** → a planilha real só tem o nome do mês ("JANEIRO"), sem ano — a Clara
   confirmou que não precisa controlar ano por enquanto (aceitou o risco de reimportar o mesmo mês
   de anos diferentes misturar os dados).
5. **Persistência** → a planilha enviada fica salva (acumula histórico), mesmo padrão exato de
   Laudos — não é "gerar e esquecer".
6. **Fonte da lista de empresas no filtro** → tabela oficial Empresas-clientes (não só as que
   aparecem na planilha), mesmo padrão de Laudos.
7. **VALOR vazio/inválido** → a Clara pediu pra manter escrito o que estiver na planilha (não
   zerar, não travar o import) — diferente da minha sugestão original (ignorar a linha). Isso
   significa que a coluna VALOR no banco guarda tanto o número interpretado (quando dá) quanto o
   texto original (`Correspondencia.valor`/`valor_texto`) — o relatório mostra o número formatado
   quando existe, ou o texto cru quando não.
8. **Linha de Total** → sim, soma de VALOR, mesmo padrão de Laudos (só soma as linhas com número
   reconhecido, por consequência direta da decisão 7).

**Discrepância encontrada e esclarecida sem precisar perguntar de novo:** a mensagem da Clara
mencionava "aplique a mesma regra já usada em Laudos" pra separar nome de Dra. do nome da empresa
— mas essa regra (`_separar_empresa_cliente`) existe em Gestão de Processos, não em Laudos. A
planilha real não tem esse problema (coluna EMPRESA já vem limpa: EROS, REVISION, NEXUS, etc.) —
decidi não aplicar nenhuma separação, já que os dados reais não precisam.

**Achado técnico durante a implementação, não uma decisão de negócio:** valores como "R$ 280,00."
(ponto final sobrando) apareciam na planilha real e não batiam o parser original — ajustado pra
tolerar esse típo de digitação (ponto final solto no fim), recuperando 6 de 9 linhas que teriam
ficado "sem valor reconhecido" por um erro de digitação, não por serem genuinamente não numéricas
(tipo "a combinar", que continua corretamente como texto).

**Testado:** 36 testes novos (serviço, API, web, PDF/Excel) — ver ARCHITECTURE.md 4.35 pros
detalhes. 254 testes no total, lint limpo. Verificado com Playwright usando a planilha real que a
Clara anexou (155 linhas novas importadas) e com uma amostra fictícia de textos bem longos (pra
testar quebra de linha e paginação com cabeçalho repetido) — ambas as amostras (PDF e Excel) foram
enviadas pra aprovação visual da Clara antes de considerar a tarefa concluída.

**Reversível:** sim — módulo, tabela e rotas 100% novos; nada em Laudos foi alterado.

## 2026-10-06 — Excel dos 5 relatórios com o mesmo visual do PDF

**Feedback da Clara:** "Os PDFs estão ok, mantenha a mesma formatação, porém, para as planilhas,
quero que elas sejam geradas na mesma configuração dos PDFs, mas com o formato de planilha para
editar nomes e valores se necessários" — reação às amostras de Correspondências.

**Pergunta antes de implementar:** só Correspondências, ou todos os 5 relatórios em Excel? **Ela
confirmou: todos.**

**Implementado:** faixa azul no topo (mesmo texto do PDF), cabeçalho da tabela com fundo navy/
texto branco, linhas intercaladas claro/branco, Total numa barra navy — aplicado aos 5 relatórios
(Laudos, Audiências, Processos Geral, Processos Por Empresa, Correspondências). A estrutura de
dados continua uma linha por item (não recriei a paginação/múltiplas tabelas por seção que alguns
PDFs têm) — isso é o que mantém a planilha editável/somável, que é o que ela pediu explicitamente.

**Achado ao comparar com o PDF:** a faixa do Excel de "Processos — Geral" estava incompleta (só
"Período", faltava "Empresa: ELITE MEDIAÇÕES" e "Relatório geral de processos" que o PDF mostra) —
corrigido.

**Testado:** 254 testes (os já existentes, ajustados pra nova estrutura de linha — nenhum teste
novo precisou ser escrito). Lint limpo. Verificado inspecionando as propriedades de cada célula
(cor, negrito, mesclagem) nos 5 relatórios, já que o conversor de planilha pra imagem deste
ambiente (LibreOffice) não funcionou por um problema de ambiente (nem um arquivo em branco
converteu) — não é um problema dos arquivos gerados.

**Reversível:** sim — só o visual da função de export mudou.

## 2026-10-06 — Bug: excluir empresa com correspondência vinculada dava erro genérico

**Relato da Clara:** "Quando apago uma empresa o sistema da erro e aparece a página dizendo para
chamar o suporte, e ai eu recarrego a página e tudo se repete".

**Causa:** quando o módulo Correspondências foi criado (seção 4.35), o modelo `Correspondencia`
não foi adicionado em `_ENTIDADES_VINCULADAS` (`app/services/empresas.py`) — o registro central que
diz o que precisa ser verificado/reatribuído antes de apagar uma empresa. Sem isso, excluir uma
empresa com correspondência vinculada não caía no aviso amigável de "não é possível excluir" —
seguia direto pro banco, e em produção (Postgres, que aplica a FK) virava erro de integridade não
tratado, daí a tela genérica. Nenhum dado foi perdido (a transação é desfeita a cada tentativa com
erro), só não dava pra apagar aquela empresa.

**Correção:** adicionada a entrada que faltava. Comportamento agora igual ao de laudos/audiências/
cobranças/processos: bloqueia com mensagem clara se não houver empresa de destino informada,
reatribui as correspondências pra ela se houver.

**Testado:** teste existente de reatribuição estendido pra cobrir Correspondencia + teste novo
reproduzindo o bug relatado e confirmando o bloqueio amigável. 255 testes, lint limpo.

**Reversível:** sim — mudança de uma linha num dicionário de registro em código, sem migração.

## 2026-10-06 — Exclusão e realocação de empresas em massa

**Pedido da Clara:** "preciso de alguma forma de selecionar e apagar empresas em massa, além de
realocá-las em massa se necessário".

**Perguntas antes de implementar e respostas:**
1. Exclusão em massa com vínculo misto (algumas com histórico vinculado, outras sem) → **uma
   única empresa de destino pra todas** (sem vínculo exclui direto; com vínculo move pro destino
   antes de excluir).
2. Realocação em massa é ação separada da exclusão, ou só parte dela? → **ação separada** (mover
   histórico de várias empresas pra uma, sem apagar as de origem).
3. Depois de realocar, o que fazer com as empresas de origem (ficam sem vínculo)? → **ficam como
   estão, ativas** — ela decide depois, manualmente.

**Implementado:** duas funções novas em `app/services/empresas.py`
(`excluir_empresas_em_massa`/`realocar_empresas_em_massa`), reaproveitando `excluir_empresa` e
`contar_vinculos_empresa`/`_ENTIDADES_VINCULADAS` já existentes — nenhuma lógica de vínculo foi
duplicada. Tela de Empresas-clientes ganhou checkboxes por linha + "selecionar todas", uma barra
de ações que aparece com a seleção, e dois modais (excluir/realocar) que reaproveitam o padrão de
modal de confirmação já usado na tela. Duas rotas novas, admin-only, com auditoria.

**Testado:** 15 testes novos (8 de serviço, 7 de tela). 270 testes no total, lint limpo. Verificado
com Playwright de ponta a ponta (seleção, modal com campo de destino condicional, exclusão em
massa movendo histórico, realocação em massa mantendo as empresas de origem cadastradas e ativas).

**Reversível:** sim — tudo aditivo; exclusão individual e zona de perigo continuam intactas.

## 2026-10-06 — Bug: exclusão em massa não apagava todas as selecionadas

**Relato da Clara:** "Eu clico em apagar em massa e ele continua apagando um só" e, depois de eu
perguntar se o campo de destino aparecia e se ela escolhia algo ali: "Eu seleciono o campo para
mover o histórico, e mesmo assim n apaga todos os selecionados."

**Causa:** o jeito mais natural de "excluir várias e manter uma" é clicar em "Selecionar todas"
(que marca literalmente todas as linhas, inclusive a que ela queria manter) e escolher essa mesma
empresa como destino. O backend recusa — de propósito — uma empresa de destino que esteja entre as
próprias selecionadas pra exclusão, então a operação inteira falhava (0 excluídas), sem deixar
claro por quê. Reproduzi localmente com Playwright e confirmei: sem a candidata a destino na
seleção, a exclusão em massa sempre funcionou certo (testado com 5 empresas com todos os 5 tipos
de vínculo); o problema era só esse caso específico de seleção.

**Correção:** `static/app.js` agora desmarca automaticamente a caixa da empresa assim que ela é
escolhida como destino no modal (se estiver marcada), com um aviso explicando. O fluxo "selecionar
tudo, escolher quem sobrevive" passa a funcionar sem exigir nenhum passo manual extra. Nenhuma
mudança no backend — a proteção contra destino-entre-selecionadas continua lá como última linha de
defesa.

**Testado:** suíte completa (270 testes) sem alteração — os testes de backend que já cobriam essa
proteção continuam passando. Verificado manualmente com Playwright reproduzindo o cenário exato
da Clara (selecionar todas, escolher a própria candidata a destino): a caixa dela desmarca
sozinha, o contador do modal atualiza, e a exclusão conclui com sucesso.

**Reversível:** sim — mudança isolada em JavaScript do navegador, sem tocar banco ou rotas.

## 2026-10-06 — Bug (continuação): exclusão em massa ainda só apagava uma

A correção anterior não resolveu — mesmo sintoma reportado de novo: "Seleciono mais de dois,
escolho a empresa que deve ser passada os processos e ele apaga apenas um dos selecionados."
Perguntei detalhes (erro? demora? histórico? quantas?) — resposta: sem erro (mensagem verde normal
com contagem "1"), demora bastante, pouco histórico, reproduzível com empresas diferentes, sempre
exatamente 1 de N.

**Investigação:** reproduzi exaustivamente (serviço direto, HTTP cru, navegador automatizado) —
inclusive contra um **Postgres real** local (não só o SQLite dos testes) com FK aplicada de
verdade e empresas com todos os 5 tipos de vínculo. Em todos os casos a exclusão em massa
funcionou perfeitamente. "Sem erro + sempre exatamente 1, não importa quais empresas" não bate com
um bug de banco/backend — bate com a seleção em si nunca chegando a marcar mais de uma caixinha de
fato.

**Hipótese mais provável:** a caixinha de seleção é pequena — fácil clicar ao lado dela (no nome,
no status) sem perceber que não marcou. A pessoa sente que selecionou várias, mas só a que acertou
o clique realmente ficou marcada.

**Correção:** `static/app.js` agora deixa a linha inteira clicável pra alternar a seleção (não só
a caixinha), sem interferir nos campos de nome/CNPJ nem nos botões da linha.

**Testado:** 270 testes (backend inalterado). Verificado com Playwright simulando clique
"impreciso" (na célula de status, não na caixinha) em 4 linhas — todas marcam corretamente, e o
fluxo completo de exclusão em massa funciona.

**Em aberto (na época):** a causa real foi encontrada depois pela própria Clara — ver a entrada
seguinte.

**Reversível:** sim — mudança isolada em JavaScript do navegador.

## 2026-10-06 — Bug (causa raiz real): hábito do ícone de lixeira por linha

Depois de 3 rodadas de investigação sem achar nada de errado no backend (incluindo teste contra
Postgres real), a Clara encontrou a causa ela mesma: "Quando apago elas eu clico em um único
símbolo de lixo em uma única empresa, mesmo depois de selecionar todos os que quero apagar."

Ela marcava as caixinhas de várias empresas mas clicava no ícone de lixeira de UMA linha
específica pra excluir — o controle que já existia antes da seleção em massa, hábito de uso
anterior. Esse ícone sempre excluiu só aquela empresa (nunca leu a seleção em massa), então
sempre "funcionava" — só que excluindo exatamente 1, por design. Explica tudo: sem erro (exclusão
individual é normal), sempre exatamente 1, independente de quais empresas (hábito de clique, não
dado).

**Sugestão da Clara:** adicionar um botão pra excluir todas as selecionadas — que já existe
("Excluir selecionadas" na barra azul). O problema era discoverability, não ausência da função.

**Correção:** os ícones de lixeira de cada linha agora ficam desativados (com aviso explicando)
sempre que houver qualquer seleção em massa ativa — torna fisicamente impossível repetir o
engano, em vez de só confiar que a pessoa vai notar a barra de seleção.

**Testado:** 270 testes (backend intocado). Verificado com Playwright: lixeira desativada em
todas as linhas assim que qualquer seleção fica ativa, reabilitada ao desmarcar tudo.

**Reversível:** sim — mudança isolada em JS + uma classe no HTML existente.

## 2026-10-08 — Varredura de otimização/produtividade

**Pedido da Clara:** "quero elevar o nível do sistema com foco em otimização e produtividade, pode
fazer uma varredura e me passar o que podemos melhorar?"

**Achados (sem mexer em nada, só levantamento):**
1. Tela de Empresas roda ~5 consultas por empresa cadastrada a cada carga de página (até 240
   consultas) só pra calcular vínculos.
2. Nenhuma das 5 tabelas com `empresa_cliente_id` tem índice nessa coluna.
3. O log de auditoria é gravado desde o início do projeto, mas não existe tela pra consultar.
4. Nenhuma tela do sistema tem busca/filtro de texto.

**Decisão da Clara:** primeiro perguntei por onde começar — ela escolheu a tela de Auditoria (item
3). Depois, no meio dessa implementação, pediu pra fazer as 4 em ordem de dificuldade (mais fácil
primeiro), parando uma a uma pra confirmar antes de seguir.

**Implementado nesta entrada:** tela de Auditoria (admin, em Configuração) com filtro por usuário/
ação/período e paginação — ver ARCHITECTURE.md 4.42 pros detalhes técnicos, incluindo um bug real
de validação (campos de filtro vazios) encontrado e corrigido antes da entrega, e os índices
adicionados em `logs_auditoria` (a tabela que mais cresce no sistema).

**Testado:** 283 testes, lint limpo, verificado com Playwright.

**Reversível:** sim — tudo aditivo.

## 2026-10-08 — Índices em empresa_cliente_id (item 2 da varredura)

Segundo item, seguindo a ordem "mais fácil primeiro" que a Clara pediu: índice em
`empresa_cliente_id` nas 5 tabelas que têm essa coluna (laudos, correspondencias, audiencias,
cobrancas, processos) — é a consulta mais comum do sistema e nenhuma tinha índice nela.

**Implementado:** `index=True` nos 5 modelos + migração manual em `db.py` (mesmo padrão já usado
pros índices anteriores do projeto — `CREATE INDEX IF NOT EXISTS`, só roda no Postgres).

**Testado:** 283 testes (não observável em SQLite). Verificado contra Postgres real local: criação
do zero, re-execução idempotente, e o cenário real de produção — tabelas já populadas sem o
índice, migração sozinha recriando corretamente.

**Reversível:** sim — índice não muda dado nem comportamento, só acelera consulta.

## 2026-10-08 — Fim das consultas repetidas na tela de Empresas (item 1 da varredura)

Terceiro item, seguindo a ordem "mais fácil primeiro": a tela de Empresas-clientes rodava 5
consultas por empresa cadastrada a cada carga de página (até 240 consultas com as 48 da lista
oficial), só pra calcular quantas têm laudo/audiência/cobrança/processo/correspondência vinculado.

**Implementado:** `contar_vinculos_todas_empresas` (nova, em `services/empresas.py`) — 5 consultas
agregadas no total, cobrindo todas as empresas de uma vez, em vez de uma consulta por empresa. A
versão antiga (`contar_vinculos_empresa`, de uma empresa só) continua intacta, ainda é a certa
pros outros usos (excluir/realocar uma empresa específica).

**Testado:** 286 testes, incluindo um teste novo que conta de verdade quantas consultas SQL rodam
numa carga da tela (trava contra o padrão N+1 voltar sem que ninguém perceba, já que o resultado
na tela fica idêntico, só mais lento). Lint limpo. Verificado com Playwright.

**Reversível:** sim — nenhum dado, template ou comportamento visível mudou.
