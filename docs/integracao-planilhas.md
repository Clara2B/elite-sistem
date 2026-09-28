# Integração com planilhas — Laudos, Audiências, Pendências e Gestão de Processos

> **Documento de análise e recomendação — nenhum código foi alterado para produzi-lo.**
> Não inicio nenhuma implementação até a Clara aprovar o plano e responder às perguntas da seção 8.

---

## 0. Resumo executivo

Hoje o sistema **já lê planilhas `.xlsx`** para essas 4 áreas — é a única forma de entrada de dados
que existe (não há formulário de cadastro manual paralelo em nenhuma delas). O que falta não é
"aprender a ler planilha" — isso já existe, testado e validado com dados reais — é **trocar o
gatilho**: hoje alguém precisa lembrar de baixar/exportar a planilha e fazer o upload manual na
tela; a proposta é que o sistema busque os dados **direto na fonte**, sob demanda (um botão
"Atualizar agora") em vez de esperar um upload.

**Recomendação, em uma frase:** manter o parser atual (`app/excel_reader.py` + os quatro
`services/*.py`) exatamente como está, e trocar só a **origem dos bytes** — de "arquivo enviado pelo
navegador" para "arquivo baixado da API do Google Sheets" (ou Microsoft Graph, se as planilhas
estiverem no OneDrive/SharePoint — **isso ainda precisa ser confirmado, ver seção 8**) — começando
por **sincronização sob demanda** (um clique, não agendada) numa única área piloto, sem mexer em
agendamento automático nem em escrita de volta na planilha por enquanto.

Por quê essa é a rota de menor risco: reaproveita ~95% do código já testado (inclusive todas as
defesas contra dado sujo já descobertas em produção — cabeçalho que muda de nome entre abas, texto
data-de-liberação sendo confundido com data de andamento, número de processo fora do padrão,
"EMPRESA - Cliente" numa célula só etc.), não exige nenhuma peça de infraestrutura nova (agendador/
cron não existe no projeto hoje), e mantém uma pessoa no controle de quando os relatórios são
atualizados — importante enquanto a qualidade do dado na origem ainda não foi validada com exemplos
reais (ver lacuna na seção 2).

**A peça que falta pra eu fechar esta análise de verdade:** nenhuma planilha de exemplo foi
encontrada no repositório, e os campos "onde ficam"/"cópias de exemplo"/"quem edita" do seu pedido
ficaram em branco (com o texto `[PREENCHA...]` do modelo). Uma resposta a essas perguntas **já
existe registrada neste projeto**, de 21/09 (`ARCHITECTURE.md` seção 1.9): Google Sheets, atualizado
todo dia pela equipe. Não sei se isso ainda vale — por isso pergunto de novo na seção 8, em vez de
simplesmente reusar a resposta antiga sem confirmar.

---

## 1. Diagnóstico do sistema atual (Etapa 1)

### 1.1 Stack

- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2.x, Pydantic Settings. Sobe com `uvicorn`.
- **Banco:** Postgres (Supabase, free tier) em produção; SQLite em memória nos testes.
- **Frontend:** páginas HTML renderizadas no servidor (Jinja2), sem framework JS — `app/web/*.py` +
  `app/templates/*.html` + `app/static/{style.css,app.js}`.
- **Hospedagem:** Render (Web Service, free tier), deploy a partir da branch do GitHub. Sem
  `render.yaml`/Procfile no repo — configuração de start command feita direto no painel do Render.
- **CI:** GitHub Actions (`.github/workflows/backend-ci.yml`) — só `ruff check` + `pytest` a cada
  push/PR que toque `backend/**`. Nenhum job agendado (`schedule:`) configurado hoje.
- **Dependências já instaladas** (`backend/requirements.txt`): `fastapi`, `uvicorn`, `pydantic-
  settings`, `sqlalchemy`, `psycopg` (driver Postgres), `pandas`, `openpyxl`, `reportlab` (PDF),
  `python-multipart`, `bcrypt`, `jinja2`. **Nada de Google/Microsoft** (`google-api-python-client`,
  `gspread`, `msal`, `O365` etc. — nenhuma dessas está instalada) e **nenhuma biblioteca de
  agendamento** (`APScheduler`, `celery` etc.).
- **Nenhuma integração externa/rotina agendada existe hoje.** A única automação de e-mail que já
  existiu (alerta de prazo de Processos, via Resend) foi implementada e depois **removida** a pedido
  da Clara (`ARCHITECTURE.md` seção 3.5) — hoje o alerta de prazo fica só dentro do sistema. Um
  segundo mecanismo de e-mail (pop-up de suporte, via SMTP direto) foi adicionado numa sessão
  recente, mas é para abrir chamados, não para sincronizar dado nenhum.

### 1.2 Como os dados entram hoje, área por área

**Nenhuma das 4 áreas tem um formulário de "cadastrar um laudo/uma audiência/um processo à mão"** —
a única via de entrada é o upload de `.xlsx`. O parser (`app/excel_reader.py::load_data_sheets`) é
**compartilhado pelas 4 áreas**: recebe o caminho do arquivo e a lista de cabeçalhos obrigatórios,
varre todas as abas do workbook, aproveita só as que têm esses cabeçalhos nas 5 primeiras linhas, e
devolve tudo empilhado num único DataFrame. Cada área then aplica sua própria regra de negócio em
cima desse DataFrame (`app/services/{laudos,audiencias,pendencias,processos}.py`).

| Área | Operadora | Rota de import (web) | Rota de import (API) | Tabela(s) |
|---|---|---|---|---|
| Laudos | ELITE | `POST /app/laudos/import` | `POST /laudos/import` | `laudos` |
| Audiências | EXIMIA | `POST /app/audiencias/import` | `POST /audiencias/import` | `audiencias` |
| Pendências | ELITE + EXIMIA (mesma planilha) | `POST /app/pendencias/import` | `POST /pendencias/import` | `cobrancas` |
| Gestão de Processos | ELITE | `POST /app/processos/import` | `POST /processos/import` | `processos`, `eventos_processo` |

Todas recebem `multipart/form-data` com o campo `arquivo` (o `.xlsx`), salvam num arquivo temporário
(`app/api/_shared.py::salvar_temp`) e chamam o `service` correspondente. **Reimportar a mesma
planilha não duplica** — cada área tem uma "chave de duplicidade" própria (ver 2.3) que decide se
uma linha já existe; linhas repetidas são só contadas, não gravadas de novo.

### 1.3 Modelo de dados, campos e relacionamentos — por área

Todas as 4 áreas compartilham o cadastro central `empresas_clientes` (~48 empresas, sincronizado
manualmente com uma lista oficial em PDF que a Clara mantém — ver `services/empresas.py`). Não é
"empresa" no sentido EXÍMIA/ELITE (isso é `operadoras`) — é a cliente final de cada laudo/audiência/
cobrança/processo.

**Laudos** (`Laudo`, ligado a `EmpresaCliente` e a `TipoLaudo`):

| Campo no banco | Vem da planilha? | Coluna esperada hoje |
|---|---|---|
| `empresa_cliente_id` | sim (resolvido por nome) | `EMPRESA` |
| `tipo_laudo_nome` | sim (texto livre) | `TIPO DE LAUDO` |
| `data` | sim | `DATA` (mas **prioriza a coluna A por posição**, não por nome — ver 2.4) |
| `nome_cliente` | sim, opcional | `NOME DO CLIENTE` ou `CLIENTE` |
| `status` | sim, opcional (default "SOLICITAÇÃO") | `ENTRADA DE LAUDO` ou `STATUS` |
| `valor` | **não** — sempre recalculado na hora do relatório, a partir de `tipos_laudo.valor_padrao` (cadastro interno, não vem da planilha) | — |

**Audiências** (`Audiencia`, ligado a `EmpresaCliente`):

| Campo no banco | Vem da planilha? | Coluna esperada hoje |
|---|---|---|
| `empresa_cliente_id` | sim | `EMPRESA` |
| `nome_cliente` | sim | `NOME COMPLETO` |
| `cpf` | sim, opcional — **dado pessoal (LGPD)** | `CPF` |
| `data_recebimento` | sim | `DATA DE RECEBIMENTO` |
| `data_agendamento` | sim, opcional (texto livre, não normalizado como data) | `DATA DE AGENDAMENTO` |
| `conciliadora` | sim, opcional | `CONCILIADORA` |
| `advogada` | sim, opcional | `ADVOGADA` |
| — | **não importado hoje** | `LINK` (Google Meet) — existe na planilha real (`ARCHITECTURE.md` 1.4) mas não tem campo correspondente no banco |
| `valor` do relatório | **não** — calculado pela faixa de volume mensal (`faixas_audiencia`, cadastro interno) | — |

A planilha real de Audiências também tem abas `DADOS` (checklist de presença) e `E-MAIL BANCO`
(contatos jurídicos) que **nunca foram lidas pelo sistema** (nem no antigo, nem no atual) — fora de
escopo, confirmar se continua assim (seção 8).

**Pendências / Cobranças** (`Cobranca`, ligado a `EmpresaCliente` — única área que mistura as duas
operadoras na mesma planilha):

| Campo no banco | Vem da planilha? | Coluna esperada hoje |
|---|---|---|
| `empresa_cliente_id` | sim | `EMPRESA` |
| `tipo_cobranca` | sim | `TIPO DE COBRANÇA` |
| `valor` | sim | `VALOR` (aceita alias `VALOR FALTANTE`) |
| `cobrador` | **não** — derivado automaticamente: tipo contendo "AUDIÊNCIA" → EXIMIA, qualquer outro → ELITE | — |
| `status_pagamento` | sim, opcional, texto livre (não é enum) | `PAGO` (aceita alias `PAGO (SIM/NÃO)`) |
| `data` | sim, opcional mas efetivamente obrigatório (sem data a linha é descartada) | `DATA` |

As abas de **contas a pagar internas** (`PAGAMENTOS`, `PAG.<mês>`: aluguel, contabilidade, folha)
existem na planilha real mas estão **explicitamente fora de escopo** — confirmado pela Clara em
21/09 ("sem sistema de fluxo de caixa", `ARCHITECTURE.md` 1.9 item 2).

**Gestão de Processos** (`Processo` + `TipoEvento` + `EventoProcesso`, a área mais complexa — cada
linha da planilha é um **andamento**, não um processo; o mesmo processo aparece várias vezes):

| Campo no banco | Vem da planilha? | Coluna esperada hoje |
|---|---|---|
| `numero_processo` (único, formato CNJ) | sim | `Nº PROCESSO` |
| `empresa_cliente_id` | sim (coluna própria OU embutida em `CLIENTE` como `"EMPRESA - Nome"`) | `EMPRESA` (abas novas) ou parte de `CLIENTE` (abas antigas) |
| `nome_cliente` | sim | `CLIENTE` (ou a parte depois do "-") |
| `advogada` | sim, opcional (texto livre) | `ADVOGADA` (alias: `DRA`) |
| `assistente` | sim, opcional (texto livre) | `ASSISTENTE` |
| `assessoria` | **não** — derivado da primeira palavra antes do "-" em `advogada` | — |
| `eventos_processo.data` | sim | `DATA` (alias: `DIA`) |
| `eventos_processo.tipo_evento_nome` | sim, opcional (texto livre) | `EVENTO` |
| `eventos_processo.prazo_fatal` | sim, opcional (só "SIM" marca fatal) | `PRAZO FATAL` (aliases: `FATAL`, `FATALISSIMO`) |
| `eventos_processo.observacao` | sim, opcional | `OBSERVAÇÃO` |
| `eventos_processo.mes_referencia` | **não** — extraído do **nome da aba**, não de coluna nenhuma | — |
| `eventos_processo.data_prazo` | **não** — nunca vem da planilha, só lançamento manual dentro do sistema (ver 2.4) | — |
| `eventos_processo.resolvido`/`resolvido_em` | **não** — controlados manualmente dentro do sistema | — |

### 1.4 Autenticação e permissões — onde a integração precisa respeitar

- Login individual, sessão por token opaco (cookie para a tela, `Authorization: Bearer` para a API).
- `PAPEIS_GLOBAIS` (`ADMIN_SUPERIOR`, `ADMIN_TI`) veem tudo; qualquer outro usuário só as
  operadoras/módulos que seus setores liberam (`app/auth.py::modulos_acessiveis`, ver sessão
  recente sobre seleção de abas por setor).
- Toda rota de import hoje exige estar logado com acesso ao módulo daquela área (`require_modulo`)
  — uma sincronização automática (sem uma pessoa logada por trás) vai precisar de uma identidade
  própria (ver seção 4, "quem/o quê aciona a sincronização").
- `logs_auditoria` já registra todo import manual hoje (`IMPORTOU_LAUDOS`, `IMPORTOU_PROCESSOS`
  etc., com `usuario_id` de quem fez). Uma sincronização automática deveria seguir o mesmo padrão.

---

## 2. Diagnóstico das planilhas (Etapa 2) — **parcial, com uma lacuna real**

### 2.1 O que eu NÃO consegui analisar

Procurei em todo o repositório por `.xlsx`/`.xls`/`.csv` e por qualquer pasta de exemplos — **não
encontrei nada**. Os três campos do seu pedido ("onde ficam", "cópias de exemplo", "quem edita")
vieram com o texto `[PREENCHA...]` do modelo, sem preenchimento. Por isso a tabela de mapeamento
coluna → campo abaixo (2.2) é construída **só a partir do que o parser já espera hoje** (o lado do
sistema), não a partir de uma planilha real sua — **não posso confirmar se os cabeçalhos que a
equipe usa hoje ainda batem com isso**, nem apontar problemas que só apareceriam olhando pra um
arquivo de verdade. Assim que eu tiver acesso a exemplos (mesmo pequenos/anonimizados), volto e
completo esta seção de verdade.

**O que já sei, de uma resposta anterior sua registrada em `ARCHITECTURE.md` (21/09, seção 1.9,
item 1):** as planilhas ficam no **Google Sheets**, atualizadas todo dia pela equipe. Não presumo
que isso ainda vale — pergunto de novo na seção 8, porque você deixou o campo em branco desta vez
(pode ter mudado, ou só não ter preenchido o modelo).

### 2.2 O que o sistema já espera de cada planilha (visto do lado do código)

A tabela da seção 1.3 já é, na prática, o mapeamento coluna → campo — repito aqui só o resumo por
chave de identificação e chave de duplicidade, que é o que decide "isso é a mesma linha de novo ou
uma nova":

| Área | Identificador único de verdade | Chave de duplicidade usada no import |
|---|---|---|
| Laudos | **não existe um** — não há "número do laudo" | `DATA + NOME DO CLIENTE + EMPRESA + TIPO DE LAUDO` |
| Audiências | **não existe um** — `CPF` seria o candidato natural mas é opcional/pode faltar | `DATA DE RECEBIMENTO + EMPRESA + NOME COMPLETO + CPF` |
| Pendências | **não existe um** | `DATA + EMPRESA + TIPO DE COBRANÇA + VALOR` (quando colide, a linha com `PAGO=SIM` sempre vence) |
| Gestão de Processos | **`Nº PROCESSO`** (formato CNJ) é o único identificador confiável — mas cada linha é um evento, então a chave de duplicidade de evento é `Nº PROCESSO + DATA + EVENTO + CLIENTE` |

Vale registrar: **nenhuma das 4 áreas tem um identificador único de linha de verdade vindo da
planilha** (só Processos tem um identificador de *processo*, não de *evento*/linha). Isso é
relevante pra qualquer forma de sincronização — sem uma chave estável por linha, detectar "essa
linha foi editada" (não só "essa linha é nova") depende de comparar o conteúdo inteiro, não um id.

### 2.3 Problemas de padronização já conhecidos (validados com dado real, não hipótese)

Estes já foram encontrados e tratados no código, com evidência real de produção — é a melhor
aproximação que tenho de "Etapa 2" sem ver sua planilha atual:

1. **Cabeçalho muda de nome entre abas da mesma planilha.** Existe uma tabela de aliases fixa
   (`HEADER_ALIASES`) com casos reais: `"DIA"` ↔ `"DATA"`, `"DRA"` ↔ `"ADVOGADA"`, `"FATAL"`/
   `"FATALISSIMO"` ↔ `"PRAZO FATAL"`, `"ENTRADA DO LAUDO"` ↔ `"ENTRADA DE LAUDO"`, `"PAGO (SIM/
   NÃO)"` ↔ `"PAGO"`. Cada variação nova precisa ser adicionada manualmente a essa lista.
2. **Mesmo nome de coluna, significado diferente conforme a aba.** Em Gestão de Processos, algumas
   abas "coringa" (fatais, por advogada, `DOCS E CUSTAS`) chamam de `"DATA"` o dia em que a Dra
   cadastrou o cliente na planilha — não a data de um andamento de verdade. Resolvido hoje com um
   marcador especial (`_DATA_E_LIBERACAO`) que exclui essas linhas do filtro por período do
   relatório mensal.
3. **Texto livre onde deveria haver opção fixa.** `TIPO DE LAUDO`, `TIPO DE COBRANÇA`, `EVENTO`,
   `ADVOGADA`/`ASSISTENTE` são todos digitados livremente. O sistema tem catálogos internos (`tipos_
   laudo`, `tipos_evento`) mas **não trava** o que vem da planilha contra eles — só avisa quando não
   reconhece (ex.: relatório mostra "(sem valor cadastrado)" pra um tipo de laudo digitado que não
   está na tabela de preços).
4. **Duas informações numa célula só.** A coluna `CLIENTE` de Processos, em abas mais antigas, traz
   `"EMPRESA - Nome do Cliente"` junto; a coluna `ADVOGADA` traz `"ASSESSORIA - Nome da Advogada
   (CONTR. Fulano)"` junto. Separados hoje por uma heurística de hífen — com taxa de erro real
   medida: **484 de ~51 mil linhas** do último import validado de Processos não conseguiram ser
   separadas e foram descartadas.
5. **Desalinhamento de cabeçalho/dado em algumas abas.** Em Processos, um valor de outra coluna
   (às vezes uma data inteira) aparece dentro de `ADVOGADA`/`ASSISTENTE` numa linha que ainda assim
   tem um `Nº PROCESSO` válido — sem tratamento, uma pessoa no relatório apareceria como
   `"2025-12-03 00:00:00"`. E o próprio `Nº PROCESSO` às vezes não bate no formato esperado:
   **6.278 de ~51 mil linhas** foram descartadas por esse motivo no último import validado.
6. **Nome de empresa-cliente grafado de formas diferentes.** Resolvido hoje por normalização (sem
   acento, maiúscula, espaço único) + um cadastro central de ~48 nomes oficiais sincronizado
   manualmente — mas ainda depende de bater exatamente depois de normalizado. Caso real documentado:
   a planilha de processos usa `"WNFAST"` (sem espaço), enquanto o PDF oficial de nomes usa
   `"WN FAST"` — se o sistema tivesse adotado o nome do PDF, teria criado uma empresa-cliente
   duplicada e perdido o vínculo com os processos já importados.
7. **Linhas em branco / abas irrelevantes.** Tratado automaticamente: qualquer aba cujas 5 primeiras
   linhas não tenham os cabeçalhos exigidos é ignorada (abas de dashboard/resumo, por exemplo);
   linhas totalmente vazias são descartadas.

**O que eu NÃO consigo dizer sem ver a planilha real:** se esses mesmos problemas continuam
acontecendo hoje, se apareceram problemas novos, e — o item que você citou explicitamente e que eu
não tenho evidência de ter visto ainda — **nomes de empresa com o nome da Dra/responsável junto na
mesma célula**. O mais próximo que encontrei é a concatenação `"ASSESSORIA - Advogada"` (item 4
acima), que é parecido mas não é exatamente isso. Preciso de um exemplo real pra confirmar.

---

## 3. Opções de integração (Etapa 3)

Comparação assumindo Google Sheets (resposta anterior, a confirmar — seção 8). Se for Microsoft
(Excel no OneDrive/SharePoint), a Opção A troca `google-api-python-client`/`gspread` por Microsoft
Graph (`msal` + chamadas REST) — o resto da comparação (esforço relativo, confiabilidade, frequência,
custo) é essencialmente o mesmo.

### Opção A — Leitura direta via API (Google Sheets API / Microsoft Graph)

**Como eu integraria isso ao que já existe:** em vez de escrever um parser novo pra ler linhas via
API, eu bateria na API só pra **baixar o arquivo inteiro como `.xlsx`** (o Google Sheets API/Drive
API tem um endpoint de exportação nesse formato; o Graph também exporta/baixa o arquivo original) e
entregaria esses bytes pro `load_data_sheets` **exatamente como ele já funciona hoje** — reaproveita
100% das defesas já validadas (aliases, checagens de sanidade, dedup) sem reescrever nada disso.

- **Esforço:** médio na primeira vez (credencial de serviço, biblioteca nova, um endpoint novo por
  área que troca "recebe upload" por "baixa da API"); baixo depois disso — o parser não muda.
- **Confiabilidade:** herda as mesmas defesas já existentes contra dado sujo (seção 2.3). Uma
  coluna renomeada ou aba apagada tem o mesmo comportamento de hoje: linha/aba ignorada, sem
  travar o import inteiro — mas sem alguém "vendo" a planilha antes de subir (como no upload manual),
  um erro de digitação na aba pode entrar sem revisão humana, dependendo da frequência escolhida.
- **Frequência possível:** qualquer uma — sob demanda, agendada, ou quase-tempo-real (webhook, ver
  Opção D) — a API não limita isso, a arquitetura de quem chama ela que decide.
- **Segurança/LGPD:** exige uma credencial de serviço (conta de serviço do Google, ou app registrado
  no Azure AD) com acesso **só de leitura** à planilha — nunca a senha de uma pessoa. Essa credencial
  vai como variável de ambiente no Render, nunca commitada (mesmo cuidado já documentado em
  `SECURITY.md` pra `DATABASE_URL`/credenciais SMTP — e mesmo cuidado que faltou no incidente do
  repositório `leitor-relatorio`, que teve planilha e banco expostos no histórico do Git).
- **Custo/limites:** irrelevante no volume atual (Google Sheets API tem cota gratuita de centenas de
  requisições/minuto; o volume real observado — ~1.900 linhas/ano em audiências, ~800/ano em
  cobranças, alguns milhares/mês em processos — está muito abaixo de qualquer limite gratuito).
- **Impacto na rotina da equipe:** nenhum, se a planilha continuar exatamente como está — a equipe
  não muda nada do jeito que trabalha; só o sistema passa a "ir buscar" em vez de "esperar alguém
  subir".

### Opção B — Sincronização agendada vs. sob demanda (não são a mesma decisão que a Opção A)

Isso é ortogonal à Opção A — é sobre **quando** rodar a leitura, não **como**.

- **Sob demanda (botão "Atualizar agora"):** reaproveita a tela que já existe (troca o botão de
  upload por um botão de "buscar da planilha"), sem precisar de nenhuma peça de infraestrutura nova.
  Uma pessoa decide quando atualizar — dá uma chance de perceber algo estranho antes do relatório
  sair errado. **Esforço mais baixo de todas as opções.**
- **Agendada (cron, ex. a cada hora ou 1x/dia):** exige uma peça de agendamento que **não existe
  hoje no projeto** — três jeitos concretos de resolver isso, nenhum grande: (1) o Render tem um
  tipo de serviço "Cron Job" dedicado (chama um endpoint HTTP na hora certa); (2) o GitHub Actions
  (já usado aqui pro CI) suporta gatilho `schedule:` — grátis, chamaria um endpoint autenticado por
  um segredo; (3) uma biblioteca de agendamento tipo `APScheduler` rodando dentro do próprio
  processo web (mais simples de montar, mas menos confiável se o Render reiniciar/hibernar o serviço
  no free tier). Nenhuma delas é grande esforço, mas é trabalho novo que a opção "sob demanda" não
  precisa.

### Opção C — Importação por upload de arquivo (o que já existe hoje)

- **Esforço:** zero — já está pronto, validado, com testes.
- **Confiabilidade:** a mesma de sempre (já rodando em produção).
- **Frequência:** manual, depende de alguém lembrar.
- **Segurança/LGPD:** nenhuma credencial nova, nenhuma superfície de ataque nova.
- **Limite real:** não resolve o problema que você descreveu — continua exigindo que alguém
  exporte/baixe e suba manualmente toda vez.
- **Não precisa ser descartada:** mesmo migrando pra Opção A, faz sentido **manter o upload manual
  como alternativa** (ex.: se a API cair, ou pra importar um arquivo pontual que não está na
  planilha "oficial") — baixo custo de manter os dois caminhos vivos.

### Opção D — Automação do lado da planilha (Google Apps Script / Power Automate)

Um script rodando dentro do Google Sheets (ou um fluxo no Power Automate, se fosse Microsoft) que
dispara sozinho quando a planilha muda (`onEdit`/`onChange`) e chama um endpoint do sistema.

- **Esforço:** maior que a Opção A pra um resultado parecido — o código de sincronização fica
  dividido entre dois lugares (o script na planilha e o endpoint no sistema), mais difícil de
  depurar/logar (o ambiente de execução do Apps Script é limitado e fora do nosso controle).
- **Confiabilidade:** gatilhos `onEdit` têm cota diária de execução e **não disparam em edições em
  massa feitas via importação/API** dentro do próprio Google Sheets — um jeito comum de editar a
  planilha (colar uma faixa grande de células, importar de outro arquivo) pode não acionar o script.
- **Frequência:** a mais próxima de "tempo real" entre as opções — dispara a cada edição, não numa
  janela fixa.
- **Segurança:** precisa expor um endpoint HTTP que aceita chamadas de fora com uma chave/token fixo
  — mais uma coisa pra proteger (rate limit, validação de origem) do que uma API que só o backend
  chama pra fora.
- **Risco maior:** sem uma etapa de revisão antes de entrar no banco, um erro de digitação na
  planilha vira dado ruim no sistema quase instantaneamente.

### Opção E — Direção inversa/bidirecional (sistema escreve na planilha) — só para comparação

Você não pediu isso, mas o pedido original menciona comparar. Registro rapidamente:

- Some risco real de **conflito de edição concorrente** (alguém editando a célula na planilha no
  mesmo instante em que o sistema escreve nela) — precisa de uma regra clara de "quem ganha".
- Exige credencial com permissão de **escrita**, não só leitura — maior superfície de risco de
  segurança pra um ganho que, pelo que você descreveu ("evitar digitação duplicada"), não parece
  necessário: ninguém digita no sistema hoje, só na planilha.
- **Não recomendo** para este caso, a menos que surja um motivo concreto que eu não enxerguei — fica
  como pergunta em aberto na seção 8, mas minha leitura é que só leitura resolve o problema descrito.

---

## 4. Recomendação final

1. **Direção:** só leitura (sistema lê da planilha) — a menos que você confirme uma necessidade real
   de escrita de volta (ver pergunta 8.1).
2. **Mecanismo:** Opção A (API da plataforma onde as planilhas estão — a confirmar, provavelmente
   Google Sheets pela resposta de 21/09), exportando o arquivo inteiro como `.xlsx` e entregando pro
   `load_data_sheets` já existente — reaproveita tudo que já foi validado com dado real, sem
   reescrever o parser.
3. **Frequência:** começar **sob demanda** (botão "Atualizar agora"), não agendada — menor esforço,
   nenhuma infraestrutura nova, e mantém uma pessoa no controle enquanto a qualidade dos dados de
   origem ainda não foi revalidada com exemplos reais. Agendamento fica como evolução natural depois
   que o botão sob demanda estiver rodando de forma confiável por um tempo.
4. **Escopo inicial:** uma área piloto, não as 4 de uma vez — reduz o raio de um erro de configuração
   de credencial/permissão, e valida o mecanismo (comparando contagens: import via API vs. upload
   manual da mesma planilha no mesmo momento) antes de replicar. **Qual área começar é uma decisão
   sua** (pergunta 8.4) — minha sugestão, só como ponto de partida pra conversa: Laudos ou Pendências
   são estruturalmente mais simples (menos abas, sem a complexidade de "evento dentro de processo"
   que Gestão de Processos tem) — bom primeiro teste do mecanismo antes de encarar a área mais
   complexa e de maior volume.
5. **O upload manual continua existindo** em paralelo, como alternativa — não é substituído, só deixa
   de ser a única via.

**Por que não a Opção D (Apps Script/Power Automate) como primeira fase:** o ganho de "quase tempo
real" não parece necessário pelo que você descreveu (o problema é divergência por upload atrasado,
não por minutos de defasagem) — o custo de manutenção (código em dois lugares, gatilhos com cota e
exceções) não parece compensar nesta fase. Fica como evolução possível depois, se a frequência sob
demanda/agendada não for suficiente na prática.

---

## 5. Plano de implementação em fases

### Fase A — Preparação (sem código)
- Confirmar plataforma, local exato e forma de acesso às planilhas (seção 8).
- Conseguir exemplos reais (mesmo recortados/anonimizados) de cada planilha — sem isso, a Etapa 2
  desta análise fica sempre incompleta, e qualquer código escrito às cegas corre risco de não bater
  com a estrutura real.
- Decidir, com você: área piloto, direção, frequência, e se algum ajuste na estrutura da planilha é
  aceitável (seção 6).
- **Critério de sucesso:** perguntas da seção 8 respondidas; pelo menos um exemplo real por área
  disponível pra mim analisar.

### Fase B — Credencial e acesso (baixo risco, isolado)
- Criar a credencial de serviço (conta de serviço Google, só leitura, OU app registrado no Azure AD,
  conforme a resposta da Fase A) e configurá-la como variável de ambiente no Render — nunca no
  código/commit (mesma disciplina já usada para `DATABASE_URL` e para as credenciais de SMTP).
- Validar, num script isolado (fora do sistema em produção), que dá pra baixar o `.xlsx` da planilha
  real com essa credencial.
- **Critério de sucesso:** arquivo baixado com sucesso, sem tocar em nenhuma rota do sistema ainda.

### Fase C — Piloto sob demanda, uma área
- Endpoint novo que baixa o arquivo da planilha (Fase B) e chama o `service` de import já existente
  da área escolhida — sem mudar o `service` em si.
- Botão "Atualizar agora" na tela daquela área, ao lado do upload manual (que continua funcionando).
- Auditoria: mesmo registro que o import manual já grava hoje (`IMPORTOU_LAUDOS` etc.), com uma
  variação no `detalhes` indicando que veio da API, não de upload.
- **Critério de sucesso:** rodar a sincronização e comparar o resultado (linhas novas/já existentes)
  contra um upload manual da mesma planilha, feito no mesmo momento — os números precisam bater.
  Validado por você em produção, como as fases anteriores deste projeto sempre foram.

### Fase D — Expandir para as outras áreas
- Repetir a Fase C pras 3 áreas restantes, uma de cada vez, sempre com o mesmo critério de validação
  por paridade contra upload manual.
- **Complexidade esperada, da mais simples pra mais complexa:** Pendências/Laudos (mais simples) →
  Audiências (parecido, mais um campo pessoal — CPF — pra atenção de LGPD) → Gestão de Processos
  (mais complexa: 21 abas, volume maior, lógica de evento-dentro-de-processo).
- **Critério de sucesso:** as 4 áreas com o botão "Atualizar agora" funcionando e validado.

### Fase E — Agendamento automático (só se aprovado depois de ver a Fase D em uso real)
- Escolher a peça de infraestrutura (Render Cron Job / GitHub Actions `schedule:` / biblioteca
  interna — ver seção 3, Opção B) e definir a frequência.
- **Critério de sucesso:** sincronização rodando sozinha na frequência combinada, sem intervenção
  manual, por pelo menos uma semana sem divergência not detectada.

### Fase F (opcional, fora do escopo inicial) — Escrita/bidirecional
- Só se você decidir, depois de ver a leitura funcionando, que há um caso real de negócio pra isso
  (ver Opção E, seção 3). Não está no plano por padrão.

---

## 6. Ajustes recomendados nas planilhas (sujeitos à sua confirmação — seção 8.5)

Sem ver a planilha real, estas são sugestões genéricas baseadas nos problemas **já conhecidos**
(seção 2.3) — não uma lista fechada, e nenhuma delas é pré-requisito pra começar a Fase A:

1. **Cabeçalho com o mesmo texto exato em todas as abas do mesmo tipo** (ex. sempre `"DATA"`, nunca
   `"DIA"` numa aba e `"DATA"` noutra) — reduz a lista de aliases que precisa manter/atualizar.
2. **Evitar concatenar duas informações na mesma célula** (ex. `"EMPRESA - Cliente"`,
   `"Assessoria - Advogada"`) quando der pra ter colunas separadas — Processos já migrou pra isso
   nas abas mais novas, segundo o próprio código; vale estender pras que ainda não migraram.
3. **Menu suspenso (validação de dados) nas colunas de valor fixo**, em vez de texto livre — `TIPO
   DE LAUDO`, `STATUS`/`ENTRADA DE LAUDO`, `PAGO`, `PRAZO FATAL`, `TIPO DE EVENTO` — reduz variação
   de grafia na origem, que hoje só é tratada depois (normalização + aviso quando não reconhece).
4. **Data do prazo fatal como data estruturada**, não só texto livre dentro da observação (ex.
   "fatal 20/07") — sem isso, mesmo com a integração pronta, alertas automáticos continuam
   impossíveis pra qualquer novo dado que repita esse padrão (é a mesma limitação que já existe hoje
   com o histórico importado, documentada em `ARCHITECTURE.md` 3.5).
5. **Nome da empresa-cliente igual ao cadastro oficial do sistema** (a lista de ~48 nomes já
   sincronizada em Empresas-clientes) — evita criar uma empresa-cliente duplicada por causa de
   grafia diferente (caso real: `"WNFAST"` vs. `"WN FAST"`).

Nenhuma dessas mudanças a estrutura das abas de um jeito que quebre o trabalho da equipe — são
ajustes de padronização, não de reorganização. Se preferir manter as planilhas exatamente como
estão, a integração ainda funciona — só herda as mesmas limitações que o upload manual já tem hoje.

---

## 7. Riscos, pontos de atenção e LGPD

- **Dados pessoais envolvidos:** CPF (Audiências), nome completo de clientes (Laudos, Audiências,
  Processos) — já classificados como sensíveis em `SECURITY.md`. Uma integração nova não pode
  ampliar quem tem acesso a esse dado; a credencial de leitura da planilha não dá acesso a ninguém
  além de quem já tem acesso ao sistema/banco hoje.
- **Credencial com o menor privilégio possível:** acesso **só leitura** à planilha (nunca edição),
  guardada como variável de ambiente no Render — nunca commitada. É a mesma disciplina que já existe
  para `DATABASE_URL`/SMTP, reforçada pelo incidente real já registrado neste projeto (planilha e
  banco expostos no histórico do Git do sistema antigo, `SECURITY.md` seção 2).
- **Auditoria:** toda sincronização (manual ou automática) precisa continuar gravando em
  `logs_auditoria`, igual o import manual já faz — pra uma sincronização sem uma pessoa logada por
  trás (ex. um cron futuro), decidir na Fase E se ela grava com um usuário de sistema dedicado ou
  sem usuário (`usuario_id` já é opcional na tabela).
- **Nenhum identificador único de linha em 3 das 4 áreas** (seção 2.2) — significa que "detectar uma
  edição" numa linha já importada depende de comparar o conteúdo inteiro, não um id estável; isso já
  é uma limitação de hoje (upload manual), não uma piora introduzida pela integração — mas vale
  deixar registrado como algo a considerar se um dia quiser sincronização mais fina (ex. "só o que
  mudou desde a última vez").
- **Qualidade do dado na origem ainda não revalidada:** os problemas da seção 2.3 foram encontrados
  numa planilha real, mas não sei se a planilha de hoje tem os mesmos problemas, mais, ou menos —
  começar sob demanda (não agendado) dá uma chance de acompanhar isso de perto nas primeiras
  execuções antes de automatizar de vez.
- **Retenção de dados pessoais** já está registrada como pendência em aberto em `SECURITY.md` seção
  6 (por quanto tempo manter CPF/nome de cliente) — não é bloqueante pra esta integração, mas é uma
  decisão de negócio relacionada que continua pendente, independente do que decidirmos aqui.

---

## 8. Perguntas pendentes — preciso da sua resposta antes de qualquer implementação

1. **Onde as planilhas ficam hoje** — Google Sheets, Excel no OneDrive/SharePoint, arquivo `.xlsx`
   em pasta de rede, ou outro? Você tinha confirmado Google Sheets em 21/09 (`ARCHITECTURE.md`
   1.9) — ainda vale, ou mudou?
2. **Cópias de exemplo** — pode me indicar onde estão (ou anexar/colar um recorte pequeno, com dado
   fictício/anonimizado se preferir) de cada uma das 4 planilhas? Sem isso, a Etapa 2 desta análise
   fica sempre parcial (seção 2.1).
3. **Quem edita as planilhas hoje** — assistentes, líderes, outra pessoa?
4. **Direção da integração** — só leitura, só escrita, ou os dois? (Minha recomendação é só
   leitura — seção 4.)
5. **Fonte oficial em caso de conflito** — se um dia o sistema e a planilha divergirem num mesmo
   dado, qual prevalece?
6. **Frequência necessária** — sob demanda (um botão), algumas vezes por dia, tempo real, ou não
   tem preferência ainda?
7. **Escopo — as 4 áreas de uma vez ou por etapas?** Se por etapas, qual é a prioridade? (Minha
   sugestão de ponto de partida, só pra conversa: Laudos ou Pendências, por serem estruturalmente
   mais simples — seção 4, item 4.)
8. **As planilhas podem ter a estrutura ajustada** (cabeçalho padronizado, menus suspensos — seção
   6) ou precisam continuar exatamente como estão?
9. **Minha leitura sobre "digitação duplicada"/"divergência"** — hoje ninguém digita duas vezes no
   sentido literal (só a planilha é editada; o sistema só lê, nunca tem formulário de cadastro
   manual paralelo). O problema que entendi é: alguém precisa lembrar de fazer o upload sempre que a
   planilha mudar, e enquanto isso não acontece, o sistema fica desatualizado em relação à planilha.
   Essa leitura está certa, ou existe outro cenário de duplicidade que eu não enxerguei?
10. **Gestão de Processos especificamente** — a planilha real tem ~21 abas (mensais, por advogada,
    "fatais"). A leitura via API deveria considerar automaticamente todas as abas existentes no
    momento (do jeito que o parser já faz hoje com upload), ou só abas específicas?

Assim que essas respostas chegarem (e, principalmente, assim que eu tiver acesso a um exemplo real
de pelo menos uma planilha), completo a Etapa 2 de verdade e ajusto este plano antes de qualquer
linha de código.
