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
├── tipo_laudo_id       -- FK tipos_laudo
├── data
├── nome_cliente
├── status              -- 'SOLICITACAO' | 'CORRECAO' | 'CANCELADO'
├── valor               -- congelado no momento do lançamento (histórico não muda se o valor padrão mudar depois)
├── origem              -- 'IMPORT_PLANILHA' | 'MANUAL' (rastreabilidade da migração)
├── criado_por          -- FK usuarios
└── criado_em
```

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
├── status_pagamento     -- 'SIM' | 'NAO' | outro status explícito (ex.: 'EM ATRASO', 'ACORDO')
├── data_recebimento
├── observacao
├── origem
├── criado_por
└── criado_em
```

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

## 8. Pendências deste modelo

- Confirmar lista real de `setores` antes da Fase 4.
- Confirmar se uma `empresa_cliente` pode pertencer às duas operadoras ao mesmo tempo, ou se são
  sempre listas separadas por operadora (afeta a FK `operadoras_id` em `empresas_clientes`).
- `id` inteiro autoincremento vs. UUID — depende do banco escolhido em D3 (Supabase/Neon, ambos
  Postgres, suportam qualquer um; UUID facilita merge de dados migrados de fontes diferentes).
- Índices e constraints de unicidade (ex.: `laudos` não deveria duplicar o mesmo
  data+cliente+empresa+tipo, replicando a regra de dedup que hoje existe em `excel_reader.py`) serão
  detalhados na Fase 2 (fundação), junto com as migrations.
