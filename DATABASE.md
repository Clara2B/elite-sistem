# DATABASE.md — Elite Sistem

> Modelo de dados vivo — rascunhado na Fase 1, implementado nas Fases 3 (laudos/audiências/
> pendências) e 4 (setores/usuários/sessões/auditoria). Convenção: `snake_case`, chave primária
> `id` inteiro autoincremento, timestamp `criado_em` nas tabelas de negócio.

## 1. Organização e acesso (implementado na Fase 4)

```
operadoras
├── id
├── nome            -- 'EXIMIA' | 'ELITE' (fixo, só 2 linhas)
└── ativo

setores                                -- ver lista real abaixo
├── id
├── operadora_id    -- FK operadoras
├── nome
└── ativo

usuarios
├── id
├── nome
├── email                  -- login individual (decisão D1)
├── senha_hash             -- bcrypt, nunca texto puro
├── papel_global            -- NULL | 'ADMIN_SUPERIOR' | 'ADMIN_TI' (acesso total às duas
│                               operadoras, sem depender de vínculo de setor — ver nota abaixo)
├── ativo
└── criado_em

usuario_setor                        -- vínculo N:N; não se aplica a quem tem papel_global
├── usuario_id      -- FK usuarios
├── setor_id        -- FK setores (setor já carrega a operadora)
├── papel           -- 'LIDER' | 'COLABORADOR'
└── PK (usuario_id, setor_id)

sessoes                              -- login = token opaco (não JWT), revogável no logout
├── token (PK)
├── usuario_id      -- FK usuarios
├── criado_em
└── expira_em                        -- 12h após o login (SESSAO_DURACAO_HORAS em app/auth.py)
```

> **`is_admin_superior` (booleano) virou `papel_global` (texto)** em relação ao rascunho da Fase 1:
> a Clara definiu que o setor T.I. também precisa de acesso total (igual Admin Superior), então o
> modelo ficou com dois papéis de alcance global — `ADMIN_SUPERIOR` (dono do negócio, hoje 3
> pessoas) e `ADMIN_TI` (suporte técnico) — em vez de um booleano só. Os dois têm exatamente o
> mesmo alcance de dados hoje; a distinção existe para o log de auditoria mostrar quem é quem.

**Setores reais** (confirmados pela Clara, seeds em `app/db.py DEFAULT_SETORES`):

| Operadora | Setores |
|---|---|
| ELITE | Líder - Gestão de Processos, Doutores(as), Admin/dona, Financeiro |
| EXIMIA | Financeiro |

Confirmado também: **Doutores(as) e Admin/dona enxergam só dados da ELITE** (mesmo aparecendo como
"ADVOGADA" nas planilhas de audiência, que são da EXIMIA — isso é só um registro histórico da
planilha, não implica acesso ao sistema).

**Regra de segregação (dura, seção 1.9 item 3):** toda consulta feita por um usuário sem
`papel_global` deve ser filtrada obrigatoriamente pela(s) operadora(s)/setor(es) em
`usuario_setor` — nunca confiar só no frontend para esconder dados de outra operadora.

## 2. Empresas-clientes (não confundir com `operadoras` — ver ARCHITECTURE.md 1.3)

```
empresas_clientes
├── id
├── nome            -- ex.: 'ABSOLUTA', 'ALLURE', 'NEXUS', ... (hoje ~43 cadastradas)
├── cnpj
└── ativo
```

> Sem `operadora_id`: confirmado que a mesma empresa-cliente é atendida pelas duas operadoras (ver
> `ARCHITECTURE.md` seção 1.9 item 3 nas respostas da Fase 4) — o que diferencia a operadora é o
> tipo de registro (laudo = ELITE, audiência = EXIMIA, cobrança = campo `cobrador`), não a empresa.

## 3. Laudos

```
tipos_laudo
├── id
├── nome            -- ex.: 'AUTO', 'AUTO-BALÃO', 'CONSÓRCIO' ...
├── valor_padrao
└── ativo

laudos
├── id
├── empresa_cliente_id  -- FK empresas_clientes
├── tipo_laudo_nome     -- texto livre (ver nota abaixo), não FK
├── data
├── nome_cliente
├── status              -- 'SOLICITAÇÃO' | 'CORREÇÃO' | outro (texto vindo da planilha)
├── origem              -- 'IMPORT_PLANILHA' | 'MANUAL' (rastreabilidade da migração)
└── criado_em
```

> **Ajuste feito na implementação (Fase 3):** `laudos.tipo_laudo_nome` ficou como texto livre em vez
> de FK para `tipos_laudo`, e o valor **não é congelado** no lançamento — é resolvido a partir de
> `tipos_laudo.valor_padrao` (por nome normalizado, ignorando acento/caixa) **no momento em que o
> relatório é gerado**, exatamente como o sistema atual faz hoje. Isso preserva de propósito o
> comportamento existente: planilhas frequentemente trazem tipos de laudo ainda não cadastrados em
> "Gerenciar valores", e o sistema precisa continuar avisando isso e aceitando o lançamento mesmo
> assim (com valor R$ 0,00 até alguém cadastrar) — uma FK obrigatória quebraria esse fluxo. `criado_por`
> fica pendente — ver seção 9 (não bloqueou a Fase 4).

## 4. Audiências

```
faixas_audiencia
├── id
├── inicio          -- quantidade mínima acumulada no mês
├── fim              -- quantidade máxima
├── valor
└── ativo

audiencias
├── id
├── empresa_cliente_id  -- FK empresas_clientes
├── nome_cliente         -- Text, sem limite (ver nota abaixo)
├── cpf                 -- Text, sem limite (ver nota abaixo) — dado pessoal, ver SECURITY.md
├── data_recebimento
├── data_agendamento     -- Text, sem limite (ver nota abaixo)
├── conciliadora          -- Text, sem limite (ver nota abaixo)
├── advogada              -- Text, sem limite (ver nota abaixo)
├── origem              -- 'IMPORT_PLANILHA' | 'MANUAL'
└── criado_em
```

**Por que `nome_cliente`/`cpf`/`data_agendamento`/`conciliadora`/`advogada` são `Text`, não
`VARCHAR(N)`:** mesmo motivo já documentado pra `processos` (seção 6.1) — texto livre vindo da
mesma planilha/equipe, que já se mostrou mais "rica" em conteúdo do que um VARCHAR(N) previsto.
`cpf` era `VARCHAR(20)` e foi o que realmente estourou em produção (log real confirmou
`StringDataRightTruncation` em `character varying(20)`) — a célula de CPF na planilha às vezes tem
mais que um CPF formatado. Os outros quatro foram convertidos junto por precaução (mesmo padrão de
texto composto já visto em `processos`/`advogada`, ex. `"HUNTING - Fulana de Tal (CONTR.
Beltrano)"`, 84+ caracteres). Ver `DECISIONS.md`.

## 5. Cobrança de pendências

```
cobrancas
├── id
├── empresa_cliente_id  -- FK empresas_clientes
├── data
├── tipo_cobranca        -- texto livre vindo da planilha (ex.: 'MENSALIDADE PROCESSUAL')
├── cobrador             -- 'EXIMIA' | 'ELITE' (classificado automaticamente pelo tipo, como hoje)
├── valor
├── status_pagamento     -- status explícito da planilha (ex.: 'SIM', 'EM ATRASO', 'ACORDO'), ou
│                            nulo quando a célula vem vazia (não conta como pendência — regra já
│                            auditada em ARCHITECTURE.md 1.4)
├── origem
└── criado_em
```

> **Simplificação da Fase 3:** `data_recebimento` e `observacao` (colunas `DATA DO RECEBIMENTO` e
> `OBS` da planilha) ainda não são importadas — nenhuma tela hoje as usa (a mensagem de cobrança não
> exibe isso). Se forem necessárias num refinamento futuro (Fase 6), é só acrescentar as colunas e
> reimportar. `criado_por` continua pendente — ver seção 9.

## 6. Auditoria (requisito explícito do projeto)

```
logs_auditoria
├── id
├── usuario_id       -- FK usuarios (nulo em ações antes do login, ex.: LOGIN_FALHOU sem usuário válido)
├── acao             -- ex.: 'LOGIN', 'LOGIN_FALHOU', 'GEROU_RELATORIO_LAUDOS', 'IMPORTOU_LAUDOS',
│                          'CRIOU_USUARIO', 'TROCOU_SENHA' (lista cresce conforme novas ações)
├── entidade          -- ex.: 'laudo', 'usuario', 'empresa_cliente'
├── entidade_id
├── detalhes          -- texto livre (ex.: resumo do import); sem operadora_id — dá pra inferir
│                          pela ação/entidade quando precisar
└── criado_em
```

## 6.1 Gestão de Processos (Fase 5 — implementado e validado, 2026-09-22)

Levantada a partir da planilha real `ELITE - GESTÃO DE PROCESSOS.xlsx` (21 abas: mensais, por
advogada, e abas "fatais" copiadas manualmente — sinal de que o sistema atual não tem essas
visões). Cada linha da planilha é um **andamento/evento** dentro de um **processo**, não o processo
em si (o mesmo processo aparece várias vezes ao longo do tempo, com eventos diferentes).

```
processos
├── id
├── numero_processo     -- formato CNJ, único
├── empresa_cliente_id  -- FK empresas_clientes (mesma lista já usada em laudos/audiências/cobranças)
├── nome_cliente         -- pessoa física atendida (Text, sem limite — ver nota abaixo)
├── advogada             -- texto livre por enquanto (Text, ver nota abaixo)
├── assistente            -- texto livre por enquanto (Text, ver nota abaixo)
├── assessoria            -- derivado de `advogada` no import (Text, nullable) — ver nota abaixo
└── criado_em

tipos_evento                          -- catálogo (igual tipos_laudo), com "Gerenciar valores"
├── id                                   equivalente pra cadastrar/editar
├── nome                -- ex.: CUSTAS, DOCUMENTOS, PREPARO DE APELAÇÃO, PROCURAÇÃO...
└── ativo

eventos_processo                      -- os "andamentos"
├── id
├── processo_id         -- FK processos
├── data                -- data do lançamento do evento
├── tipo_evento_nome     -- texto livre (Text, resolvido contra tipos_evento por nome, igual laudos)
├── mes_referencia       -- ex. "SETEMBRO/2026" — extraído do nome da aba de origem na planilha
│                            (não de `data`); None quando a aba não é nomeada por mês. Só
│                            informativo (aparece no painel de prazos), não filtra nem trava nada.
├── prazo_fatal          -- bool
├── data_prazo           -- date; obrigatório quando prazo_fatal = true (decisão da Clara — sem
│                            isso não dá pra alertar antes de vencer)
├── resolvido            -- bool, default false
├── resolvido_em         -- datetime, preenchido quando marcado como resolvido
├── status_prazo         -- calculado, não gravado: PENDENTE / CUMPRIDO / PERDIDO (ver regra abaixo)
├── observacao           -- texto livre
├── criado_por           -- FK usuarios (agora dá pra rastrear — Fase 4 já existe)
└── criado_em
```

**Regra de `prazo_fatal`** (confirmada pela Clara): é sempre um atributo do **evento**, não do
processo — o mesmo processo pode ter eventos fatais e não-fatais ao longo do tempo, por isso o campo
fica em `eventos_processo`, não em `processos`. No import, só o valor `SIM` (normalizado — ignora
acento/caixa/espaço, ex. `"Sim "`, `"sim"`) na coluna `PRAZO FATAL` marca o evento como fatal;
qualquer outro valor (vazio, `"NÃO"`, etc.) não é fatal. Ver `app/services/processos.py`.

**Regra de `status_prazo`** (só se aplica quando `prazo_fatal = true`):
- `resolvido = true` e `resolvido_em <= data_prazo` → **CUMPRIDO**
- `resolvido = true` e `resolvido_em > data_prazo` → **CUMPRIDO COM ATRASO** (conta como perdido nas
  métricas, mas fica registrado que foi feito depois)
- `resolvido = false` e hoje `> data_prazo` → **PERDIDO**
- `resolvido = false` e hoje `<= data_prazo` → **PENDENTE**

**"Processo parado"**: calculado como dias desde o último `eventos_processo.data` daquele
`processo_id`. Proposta: considerar "parado" acima de **15 dias sem novo evento** — número
inicial, ajustável depois que a Clara validar com uso real (não é uma regra que estava documentada
em lugar nenhum, é uma proposta para começar).

**`assessoria`** (a pedido da Clara, 2026-09-23): a equipe/escritório terceirizado que atua no
processo — sempre a primeira palavra antes do nome, dentro da própria coluna `ADVOGADA` da planilha
(ex.: `"HUNTING - Fulana de Tal"` → assessoria `"HUNTING"`). `advogada` continua gravado com o texto
original, sem o prefixo removido — `assessoria` é só um valor derivado a mais, usado pra
filtrar/agrupar o relatório (`agrupar_por=assessoria`), igual já existia pra assistente/advogada.
Fica `None` quando a coluna `ADVOGADA` não tem esse padrão de prefixo. Ver
`app/services/processos.py::_separar_assessoria`.

**Import "upsert" de andamento já existente** (a pedido da Clara, 2026-09-23): antes, uma linha da
planilha cuja chave (`processo_id`, `data`, `tipo_evento_nome` normalizado) já batia com um
`eventos_processo` existente era só contada como duplicada e ignorada — mesmo que a linha trouxesse
`OBSERVAÇÃO`/`PRAZO FATAL`/aba (mês de referência) diferentes do que já estava gravado. Agora essa
linha atualiza `observacao`/`prazo_fatal`/`mes_referencia` com o que vier preenchido na planilha
(só quando vier preenchido — uma linha sem `OBSERVAÇÃO`, por exemplo, não apaga uma já cadastrada).
`nome_cliente`/`advogada`/`assistente`/`assessoria` do `processos` já seguiam essa mesma lógica de
"última informação vista no import vale" (ver nota de `advogada`/`assistente` logo abaixo) —
`nome_cliente` foi incluído nela agora também. Nunca toca em `resolvido`/`resolvido_em`/`data_prazo`
— são controlados manualmente dentro do sistema, não vêm da planilha.

**Nota sobre `advogada`/`assistente` como texto livre, não `usuarios`:** confirmado pela Clara —
"os assistentes não acessam o sistema, só seus líderes, mas pode manter apenas como texto pois eles
aparecerão no relatório". Decisão fechada (não mais uma proposta em aberto); ver `DECISIONS.md`.

**Por que `nome_cliente`/`advogada`/`assistente`/`tipo_evento_nome` são `Text`, não
`VARCHAR(N)`:** a planilha real mostrou valores bem mais longos do que um nome simples nesses
campos (ex.: `advogada` = `"HUNTING - Fulana de Tal (CONTR. Beltrano)"`) — um limite errado derrubou
o import em produção com `StringDataRightTruncation`. Ver `DECISIONS.md`.

**Defeito de dados conhecido, com mitigação:** algumas abas da planilha real têm o cabeçalho
desalinhado da linha de dados, o que pode jogar valores de outra coluna dentro de
`ADVOGADA`/`ASSISTENTE` (observado durante a validação: uma data completa, ex.
`2025-12-03 00:00:00`, apareceu como se fosse o nome de uma pessoa). O import filtra valores que
"parecem data" nesses dois campos (viram `None` em vez de serem gravados) — mesmo tratamento
defensivo já usado para o formato do número de processo (CNJ) e para o campo `CLIENTE`. Ver
`app/services/processos.py::_pessoa_valida`.

## 7. Fora de escopo (confirmado pela Clara, seção 1.9 item 2)

Não haverá tabelas de contas a pagar / fluxo de caixa interno (o equivalente às abas `PAGAMENTOS` /
`PAG.<mês>` da planilha atual) — o sistema novo cobre laudos, audiências e cobrança de recebimentos,
como o sistema atual já faz.

## 8. Status da implementação

**Fase 3 (2026-09-22):** `operadoras`, `empresas_clientes`, `tipos_laudo`, `laudos`,
`faixas_audiencia`, `audiencias`, `cobrancas` — validados com dados reais (272 combinações
empresa×período de audiências e as 18 empresas com pendência da planilha de fluxo de caixa, todas
batendo exatamente com a saída do `leitor-relatorio`). `id` ficou como inteiro autoincremento (mais
simples, suficiente para o volume real — ~2 mil linhas/ano; UUID descartado, evitando complexidade
sem necessidade real). Bug real encontrado e corrigido: células vazias de planilha (`PAGO`, `DATA`)
viravam o texto `"nan"` em vez de `None` — corrigido com `cell_text()` em `app/utils.py`, com teste
de regressão.

**Fase 4 (2026-09-22):** `setores` (com a lista real confirmada pela Clara, seção 1), `usuarios`,
`usuario_setor`, `sessoes` (login) e `logs_auditoria` — todos implementados e testados (37 testes
automatizados, incluindo segregação por operadora ponta a ponta via API). `empresas_clientes`
**não** ganhou `operadora_id`: confirmado que a mesma empresa-cliente é atendida pelas duas
operadoras, então essa pendência da Fase 1 está resolvida (não precisa da coluna).

**Fase 5 (2026-09-22):** `processos`, `tipos_evento`, `eventos_processo` — implementados e validados
contra a planilha real `ELITE - GESTÃO DE PROCESSOS.xlsx` (21 abas, 51.116 linhas brutas): 44.333
eventos importados, 5.636 processos distintos, 6.303 marcados como `prazo_fatal`. `data_prazo` fica
`None` em todo o histórico importado (não extraído de texto livre — só passa a existir para eventos
lançados daqui pra frente, com data informada explicitamente). Ver ARCHITECTURE.md seção 3.5 para os
números completos de validação e o defeito de dados encontrado/mitigado.

## 9. Pendências deste modelo

- Índices e constraints de unicidade (hoje o dedup de reimportação é feito em Python, comparando
  contra o que já existe no banco — funciona para o volume atual, mas constraints de banco
  (`UNIQUE`) seriam mais robustas; avaliar num refinamento futuro).
- `criado_por` (FK `usuarios`) ainda não foi adicionado a `laudos`/`audiencias`/`cobrancas` — os
  imports/relatórios já são autenticados e ficam no log de auditoria (`logs_auditoria`), mas o
  registro em si não sabe quem importou aquela linha especificamente. Avaliar se vale a pena para
  rastreabilidade mais fina.
