# DATABASE.md — Elite Sistem

> Modelo de dados **v1**, resultado da Fase 1 (Arquitetura). Ainda sujeito a ajuste conforme as
> decisões D1/D2/D3 em `ARCHITECTURE.md` seção 2 forem fechadas, e conforme a lista real de setores
> for confirmada. Convenção: `snake_case`, chave primária `id` (inteiro autoincremento ou UUID —
> a decidir junto com D3), timestamps `criado_em`/`atualizado_em` em todas as tabelas de negócio.

## 1. Organização e acesso

```
operadoras
├── id
├── nome            -- 'EXIMIA' | 'ELITE' (fixo, só 2 linhas)
└── ativo

setores
├── id
├── operadora_id    -- FK operadoras
├── nome            -- ex.: 'Laudos', 'Audiências', 'Financeiro/Cobrança' (a confirmar com a Clara)
└── ativo

usuarios
├── id
├── nome
├── email                  -- login individual (ver decisão D1)
├── senha_hash             -- nunca texto puro (bcrypt/argon2)
├── is_admin_superior       -- bool: acesso total às duas operadoras, sem vínculo de setor
├── ativo
├── criado_em
└── atualizado_em

usuario_setor                        -- vínculo N:N; não se aplica ao Admin Superior
├── usuario_id      -- FK usuarios
├── setor_id        -- FK setores (setor já carrega a operadora)
├── papel           -- 'LIDER' | 'COLABORADOR'
└── PK (usuario_id, setor_id)
```

**Regra de segregação (dura, seção 1.9 item 3):** toda consulta feita por um usuário que não seja
`is_admin_superior` deve ser filtrada obrigatoriamente pela(s) operadora(s)/setor(es) em
`usuario_setor` — nunca confiar só no frontend para esconder dados de outra operadora.

## 2. Empresas-clientes (não confundir com `operadoras` — ver ARCHITECTURE.md 1.3)

```
empresas_clientes
├── id
├── operadora_id    -- de qual operadora é cliente (EXIMIA e/ou ELITE podem atender a mesma?
│                       a confirmar; hipótese v1: uma empresa-cliente pode ter registro em ambas)
├── nome            -- ex.: 'ABSOLUTA', 'ALLURE', 'NEXUS', ... (hoje ~43 cadastradas)
├── cnpj
└── ativo
```

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
> fica para a Fase 4 (depende de `usuarios` existir).

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
├── nome_cliente
├── cpf                 -- dado pessoal — ver SECURITY.md sobre tratamento
├── data_recebimento
├── data_agendamento
├── conciliadora
├── advogada
├── origem              -- 'IMPORT_PLANILHA' | 'MANUAL'
├── criado_por          -- FK usuarios
└── criado_em
```

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
> reimportar. `criado_por` fica para a Fase 4.

## 6. Auditoria (requisito explícito do projeto)

```
logs_auditoria
├── id
├── usuario_id       -- FK usuarios
├── operadora_id     -- FK operadoras (contexto em que a ação ocorreu, quando aplicável)
├── acao             -- ex.: 'GEROU_RELATORIO_LAUDOS', 'EDITOU_VALOR_LAUDO', 'LOGIN', 'LOGIN_FALHOU'
├── entidade          -- ex.: 'laudo', 'tipo_laudo', 'usuario'
├── entidade_id
├── detalhes          -- JSON livre (o que mudou, de/para)
└── criado_em
```

## 7. Fora de escopo (confirmado pela Clara, seção 1.9 item 2)

Não haverá tabelas de contas a pagar / fluxo de caixa interno (o equivalente às abas `PAGAMENTOS` /
`PAG.<mês>` da planilha atual) — o sistema novo cobre laudos, audiências e cobrança de recebimentos,
como o sistema atual já faz.

## 8. Status da implementação (Fase 3, 2026-09-22)

**Implementado e validado** (`backend/app/models.py`, Postgres via Supabase em produção, testado
localmente com SQLite): `operadoras` (tabela existe, ainda sem uso — controle de acesso é Fase 4),
`empresas_clientes` (sem `operadora_id` ainda, ver pendência abaixo), `tipos_laudo`, `laudos`,
`faixas_audiencia`, `audiencias`, `cobrancas`. `id` ficou como inteiro autoincremento (mais simples,
suficiente para o volume real observado — ~2 mil linhas/ano; UUID descartado por ora, evitando
complexidade sem necessidade real).

**Ainda não existem no banco** (Fase 4, dependem das decisões de autenticação): `setores`,
`usuarios`, `usuario_setor`, `logs_auditoria`, e as colunas `criado_por`/`operadora_id` em
`empresas_clientes`.

**Validação de paridade (critério de conclusão da Fase 3):** rodado contra os dados reais
fornecidos pela Clara — **272 combinações empresa×período de audiências** e as **18 empresas com
pendência** da planilha de fluxo de caixa, todas batendo exatamente com a saída do sistema atual
(`leitor-relatorio`). Laudos foi validado só com dados sintéticos (nenhuma das duas planilhas de
exemplo tem coluna `TIPO DE LAUDO`) — mesma lógica, mesmo padrão de teste.

**Bug real encontrado e corrigido durante a validação:** células vazias de data (`PAGO`, `DATA`)
lidas pelo pandas como `NaN`/`NaT` estavam sendo gravadas como o texto literal `"nan"` em vez de
`None` — isso fazia uma pendência já paga (célula `PAGO` vazia) ser contada como pendente por
engano. Corrigido com a função `cell_text()` em `app/utils.py` (ver DECISIONS.md), com teste de
regressão em `tests/test_utils.py`.

## 9. Pendências deste modelo

- Confirmar lista real de `setores` antes da Fase 4.
- Confirmar se uma `empresa_cliente` pode pertencer às duas operadoras ao mesmo tempo, ou se são
  sempre listas separadas por operadora (afeta a FK `operadora_id` em `empresas_clientes`, ainda não
  criada).
- Índices e constraints de unicidade (hoje o dedup de reimportação é feito em Python, comparando
  contra o que já existe no banco — funciona para o volume atual, mas constraints de banco
  (`UNIQUE`) seriam mais robustas; avaliar na Fase 4/6).
