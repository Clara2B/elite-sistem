# ARCHITECTURE.md — Elite Sistem

> Este documento é vivo. A seção 1 é o resultado da **Fase 0 — Diagnóstico e Auditoria**
> (ver `PROMPT-ARQUITETO-ELITE-SISTEM.md`). A arquitetura proposta (Fase 1) será acrescentada
> **depois** que as pendências abertas na seção 1.9 forem respondidas e a Fase 0 for aprovada.

---

## 1. Fase 0 — Diagnóstico do sistema atual (`leitor-relatorio`)

**Fontes auditadas:**
- Código-fonte: https://github.com/Clara2B/leitor-relatorio (commit único `27bde13`, "Add files via upload")
- App publicado: `leitor-relatorio-kqbadhehgf3cb8zjgqhcqr.streamlit.app`
- Planilhas de exemplo fornecidas: `AGENDAMENTO_6.xlsx` (audiências/agendamentos) e
  `Lançamentos - Fluxo de Caixa.xlsx` (laudos/cobranças — mesma planilha já está, por sinal,
  commitada dentro do próprio repositório, ver risco crítico na seção 1.5).

### 1.1 O que o sistema realmente é

Um app Python/Streamlit **monolítico e sem persistência de dados de negócio**. Ele não guarda
laudos, audiências ou cobranças — cada geração de relatório parte de um **upload manual** da
planilha `.xlsx` correspondente, que é lida, filtrada e descartada na hora (arquivo temporário).
A única coisa persistida é **configuração** (valores de laudo, faixas de audiência, CNPJs), num
SQLite local (`data/leitor_relatorio.sqlite3`).

Ou seja: a "fonte de verdade" dos dados de negócio hoje **não é o sistema** — é a planilha Excel
mantida por fora dele (Google Sheets/Excel local, processo manual da equipe). **Pendência aberta**:
confirmar onde e como essa planilha é mantida/atualizada no dia a dia (seção 1.9).

### 1.2 Funcionalidades mapeadas (4 abas)

| Aba | O que faz | Entrada | Regra central |
|---|---|---|---|
| 📑 Relatório de Laudos | Filtra laudos por empresa-cliente/período/status, calcula valor por tipo, gera texto + PDF (folha ELITE) | upload `.xlsx` de laudos | Período fixo: dia 21 a dia 20 do mês seguinte. Valor vem de tabela editável por tipo de laudo. |
| ⚖️ Relatório de Audiências | Filtra audiências por empresa-cliente/quinzena, calcula valor pela faixa de volume mensal, gera texto + PDF (folha EXIMIA) | upload `.xlsx` de agendamentos | Período quinzenal (1–15 / 16–fim). Valor por audiência = faixa de acumulado mensal da empresa-cliente (400/350/300/250/200 conforme 1–20/21–39/40–60/61–79/80–100); 2ª quinzena usa a faixa nova só para as audiências novas. |
| 💬 Cobrança de Pendências | Lê planilha de fluxo de caixa, monta mensagem de cobrança (WhatsApp) por empresa-cliente | upload `.xlsx` de fluxo de caixa (só ELITE tem) | Pendente = campo PAGO com status explícito ≠ SIM/NÃO (vazio não conta). Dedup por (data+empresa+tipo+valor), SIM sempre vence. Classificação automática do cobrador: tipo contendo "AUDIÊNCIA" → EXIMIA; qualquer outro → ELITE. PIX de cada cobrador está fixo no código. |
| ⚙️ Gerenciar valores | CRUD de valores de laudo e CNPJs por empresa-cliente; **leitura apenas** das faixas de audiência (sem CRUD na tela) | — | Grava direto no SQLite; qualquer usuário logado pode editar. |

**Login**: tela única usuário/senha (`core/auth.py`), lista vinda de `st.secrets["usuarios"]`
(hoje só `funcionario`). Comparação em memória, sem hash, sem RBAC, sem sessão persistente entre
reinícios, sem log de quem fez o quê.

### 1.3 Nomenclatura — atenção a uma ambiguidade real

O termo **"empresa"** é usado com **dois significados diferentes** que não podem ser confundidos
na arquitetura nova:

1. **EXÍMIA e ELITE** — as duas entidades que operam o sistema (a "Câmara de Conciliação" e a
   "Mediações"). É isso que o requisito de "multiempresa/segregação" da Clara quer dizer. Hoje elas
   aparecem só como identidade visual fixa por aba (Laudos = marca ELITE, Audiências = marca
   EXIMIA) e como regra de classificação de cobrador em Pendências — **não existe controle de
   acesso por elas hoje**.
2. **"Empresa" como coluna nas planilhas** (ex.: ABSOLUTA, ALLURE, NEXUS, PLATINO, SIMPLIFICA,
   WN FAST, ...) — são **dezenas de empresas-clientes** da EXIMIA/ELITE, cada uma com laudos,
   audiências e cobranças próprios. É sobre elas que os relatórios são gerados.

A Fase 1 (modelo de dados) precisa tratar isso como **duas entidades distintas**
(`operadoras` × `empresas_clientes`), não uma só — ver pendência 1.9.

### 1.4 Dados observados nas planilhas (estrutura, não conteúdo)

- **Laudos**: `EMPRESA`, `TIPO DE LAUDO`, `DATA`, `NOME DO CLIENTE`/`CLIENTE`,
  `ENTRADA DE LAUDO`/`STATUS` (Solicitação/Corrigido/Cancelado). Tipos de laudo variam por planilha
  — o README do sistema atual já lista ~9 tipos vistos mas não cadastrados (ex.: `AUTO (BALÃO)`,
  `CONSIGNADO`, `PLACA SOLAR`) — sinal de que a tabela de valores está desatualizada em relação ao
  uso real.
- **Audiências/Agendamento** (`AGENDAMENTO_6.xlsx`): aba mestre `AGENDAMENTO` (~1.900 linhas) +
  abas mensais (`JULHO`, `AGOSTO`, ...), com colunas `DATA DE RECEBIMENTO`, `EMPRESA`,
  `NOME COMPLETO`, **`CPF`**, `DATA DE AGENDAMENTO`, `LINK` (Google Meet), `CONCILIADORA`,
  `ADVOGADA`. Há também abas de apoio: `DADOS` (status de presença/checklist por empresa-cliente,
  não é lida pelo relatório) e `E-MAIL BANCO` (contatos jurídicos de bancos, não lida pelo
  relatório).
- **Fluxo de Caixa** (`Lançamentos - Fluxo de Caixa.xlsx`): abas `2025/2026 - RECEBIMENTOS EMPRESAS`
  (~520 e ~830 linhas) com `DATA`, `EMPRESA`, `VALOR`/`VALOR FALTANTE`, `TIPO DE COBRANÇA`,
  `PAGO`/`PAGO (SIM/NÃO)`, `DATA DO RECEBIMENTO`, `OBS`. **Além disso**, a planilha tem abas de
  **contas a pagar internas** (`PAGAMENTOS`, `PAG. NOVEMBRO2025` ... `PAG.ABRIL 2026`: aluguel,
  contabilidade, folha/VT, sistemas) que **o sistema atual ignora** (não têm as colunas exigidas) —
  hoje é controle manual só na planilha. Ver pergunta 1.9 sobre escopo.
- **`CPF` é dado pessoal identificável** (audiências) — reforça a necessidade de tratar o novo
  banco de dados com controle de acesso e criptografia adequados desde o desenho (LGPD).

### 1.5 Riscos — do mais grave ao mais leve

**🔴 CRÍTICO — exposição pública de dados sensíveis no histórico do Git.**
O repositório `Clara2B/leitor-relatorio` é **público**, e o commit único `27bde13` ("Add files via
upload") inclui, mesmo com o `.gitignore` bloqueando `*.xlsx` e `data/`:
- `core/Lançamentos - Fluxo de Caixa (1).xlsx` — a planilha real de recebimentos/cobranças, com
  nomes de empresas-clientes e valores.
- `data/leitor_relatorio.sqlite3` — banco com os 43 CNPJs de empresas-clientes cadastrados.

Isso quase certamente aconteceu porque os arquivos foram enviados pela interface "Add file →
Upload files" do GitHub (que não respeita `.gitignore` local) antes/junto do primeiro commit.
Qualquer pessoa no mundo pode baixar esses dados agora. **Isto não é uma tarefa de
desenvolvimento — é um incidente de segurança em andamento.** Eu tenho apenas acesso de leitura a
esse repositório (por instrução do projeto, nunca ajo em produção sem autorização e acesso
explícitos), então **não posso corrigir isso sozinho**. Recomendação imediata, por ordem de
urgência:
1. Tornar o repositório **privado agora** (Settings → Danger Zone → Change visibility) — mitiga a
   exposição em minutos, mesmo que o histórico "sujo" continue existindo.
2. Depois, com calma: reescrever o histórico para remover esses arquivos (`git filter-repo` ou BFG
   Repo-Cleaner) e forçar push, **ou** simplesmente abandonar esse repositório como código-fonte
   histórico e não reutilizá-lo como está.
3. Avaliar se algum dado exposto (CNPJs, valores) exige alguma comunicação/mitigação adicional.
4. Se quiser que eu ajude a executar isso, preciso de acesso de escrita (`push`) a esse repositório
   e da sua autorização explícita antes de qualquer comando destrutivo (reescrever histórico é
   irreversível sem backup).

**🟠 Alto — autenticação sem controle de acesso real.** Usuário/senha em texto puro, comparados em
memória, um único nível de acesso, sem RBAC, sem segregação EXÍMIA/ELITE, sem expiração de sessão,
sem bloqueio por tentativas.

**🟠 Alto — nenhuma auditoria.** Não há registro de quem gerou qual relatório ou editou qual valor.
Um dos requisitos explícitos do novo sistema.

**🟡 Médio — dado pessoal (CPF) em trânsito sem tratamento especial.** Hoje só passa pela memória
do processo (upload → tempfile → descarte), mas o novo sistema, ao persistir isso em banco,
precisa decidir criptografia em repouso / mascaramento / retenção (LGPD).

**🟡 Médio — cobertura de testes baixa.** Só `core/audiencias.py` tem teste automatizado
(`tests/test_audiencias.py`); `laudos.py` e `pendencias.py` não têm, apesar de terem regras não
triviais (dedup, status, faixas).

**⚪ Observação — tabela de valores desatualizada.** O próprio README já lista tipos de laudo vistos
na planilha sem valor cadastrado — indica que "Gerenciar valores" não é mantido em dia.

### 1.6 Componentes reaproveitáveis para a Fase 1+

- `core/laudos.py`, `core/audiencias.py`, `core/pendencias.py` — lógica de negócio pura (sem
  dependência de Streamlit), praticamente pronta para virar camada de serviço num backend novo;
  só troca a fonte dos dados (planilha → banco).
- `core/excel_reader.py` — parser genérico de abas por cabeçalho (ignora abas de controle
  automaticamente); útil manter durante a fase de migração/importação de planilhas legadas.
- `core/pdf_export.py` + `assets/*_logo_0.jpeg` — geração de PDF com folha timbrada; reaproveitável
  como está.
- `core/utils.normalize` — normalização de texto (acento/caixa/espaço); usar no backend novo
  também, já que os dados de origem vão continuar "sujos" da mesma forma.
- Paleta de identidade visual já embutida no CSS do `app.py`: **ELITE** `#072652` / `#123F6E` /
  acento `#C9A227`; **EXIMIA** `#1A2946` / `#2C3F63` / acento `#B08D57`. Não é um manual de marca
  formal, mas é uma base real já usada nos relatórios oficiais — ponto de partida até a Clara
  confirmar ou substituir (ver pedido de identidade visual no prompt mestre, seção 13).

### 1.7 Deploy atual

Streamlit Community Cloud, a partir do repositório GitHub, `app.py` como entrypoint, secrets via
painel "Secrets" do Streamlit Cloud. Sem CI configurado (não há workflow de testes automáticos).
Free tier do Streamlit Community Cloud tem "sleep" por inatividade — consistente com o objetivo de
achar algo "melhor" para a nova plataforma.

### 1.8 Lacunas em relação ao que a Clara pediu

| Requisito pedido | Situação hoje |
|---|---|
| Banco de dados para os dados de negócio | Não existe — só config é persistida; laudos/audiências/pendências são recalculados a cada upload |
| Autenticação multiusuário real | Só uma lista compartilhada usuário→senha, um usuário só configurado hoje (`funcionario`) |
| Multiempresa (EXÍMIA/ELITE) com segregação | Não existe controle de acesso por operadora — é só identidade visual fixa por aba |
| Setores, permissões, Admin Superior | Não existe nenhum desses conceitos |
| Auditoria/logs | Não existe |
| Gestão de Processos | Não existe |

### 1.9 Pendências do Gate 0 — respostas da Clara (2026-09-21)

1. **Fonte de verdade das planilhas** → **Google Sheets, atualizado todos os dias.** Não é Excel
   local — é uma planilha viva, editada diariamente pela equipe. Implicação para a Fase 1: o
   upload manual de `.xlsx` deixa de ser a única via aceitável a médio prazo; faz sentido planejar
   uma integração direta com a API do Google Sheets (leitura) como evolução natural, sem que isso
   precise entrar já na Fase 3 (ver decisão D5 abaixo).
2. **Escopo das abas de contas a pagar** (`PAGAMENTOS`, `PAG.<mês>`) → **Fora do escopo.** Confirmado:
   "Sem sistema de fluxo de caixa". O novo sistema cobre laudos, audiências e cobrança de
   pendências (recebimentos), como hoje — não um módulo de contas a pagar/fluxo de caixa completo.
3. **Nomenclatura EXÍMIA/ELITE vs. empresa-cliente** → **Confirmado**, com uma regra adicional
   importante: **só o Admin Superior enxerga as duas operadoras** — qualquer outro usuário fica
   restrito à sua própria operadora (e, dentro dela, ao(s) seu(s) setor(es)). Isso vira requisito
   duro de segregação na Fase 4 (RLS/filtro obrigatório por operadora em toda consulta que não seja
   do Admin Superior).
4. **Usuários e papéis reais** → Hoje **3 pessoas atuam como Admin Superior** (podendo compartilhar
   um único login, como é hoje) e a Clara quer **acrescentar um papel de "Líder" por setor**. Ou
   seja, a hierarquia real tem 3 níveis, não 2:
   - **Admin Superior** — acesso total, às duas operadoras, sem restrição de setor.
   - **Líder de setor** — acesso total dentro do(s) setor(es)/operadora(s) a que pertence (provável
     escopo: gerenciar valores do setor, ver tudo do setor, o que um colaborador comum não pode).
   - **Colaborador de setor** — acesso operacional dentro do(s) setor(es) a que pertence (gerar
     relatórios, não necessariamente gerenciar valores/CNPJs).
   Fica como pendência menor, não bloqueante para a Fase 1: **a lista real dos setores** (nomes) —
   uso como hipótese de trabalho: um setor por linha de produto observada no sistema atual (ex.:
   Laudos, Audiências, Financeiro/Cobrança), a confirmar antes da Fase 4.
5. **Decisão de segurança** → **Já resolvido pela Clara**: o repositório `leitor-relatorio` foi
   tornado **privado**. Mitiga a exposição pública imediata. Ainda fica em aberto, sem urgência
   agora, decidir se vale a pena reescrever o histórico do Git para remover os arquivos sensíveis
   definitivamente (ele continua no histórico de um repo agora privado, mas não é mais público).

> Com essas respostas, a Fase 1 (Arquitetura) segue abaixo. As únicas questões que ainda preciso de
> decisão da Clara para fechar a Fase 1 são as marcadas como **[DECISÃO]** na seção 2.

---

## 2. Fase 1 — Arquitetura proposta

### 2.1 Visão geral

Substituir o app monolítico Streamlit (sem persistência de dados de negócio) por:

- Um **backend com API própria**, dono da regra de negócio (reaproveitando a lógica já validada em
  `core/laudos.py`, `core/audiencias.py`, `core/pendencias.py`) e de toda a autorização/segregação
  por operadora/setor.
- Um **banco de dados relacional gerenciado** (free tier), fonte de verdade dos dados de negócio
  (laudos, audiências, pendências, usuários, permissões, auditoria) — não mais "recalcular tudo a
  cada upload".
- Uma **camada de autenticação real** (login individual, senha com hash, sessão com expiração).
- Um **frontend** — decisão em aberto entre continuar com Streamlit ou migrar (ver D2).

Nenhuma dessas peças é escolhida ainda de forma definitiva nesta seção sem a aprovação da Clara —
as decisões com trade-off relevante estão marcadas **[DECISÃO]**, com opções, prós/contras e uma
recomendação, como definido no prompt mestre (seção 7).

### 2.2 [DECISÃO] D1 — Login do Admin Superior: único compartilhado ou individual por pessoa

**Contexto:** hoje 3 pessoas atuam como Admin Superior. A Clara sugeriu que "pode ser um login
único". Isso funciona, mas colide com um requisito explícito do projeto: **auditoria/log de quem
fez o quê**. Com um login compartilhado, o log mostraria sempre "Admin Superior fez X", nunca qual
das 3 pessoas.

- **Opção A — Login individual por pessoa (mesmo papel/permissão para as 3)** — *recomendado*.
  Prós: auditoria de verdade (sabe-se quem gerou/editou o quê), permite revogar acesso de uma
  pessoa sem afetar as outras duas, sem custo extra (não depende de quantidade de usuários em
  nenhum provedor gratuito considerado). Contras: mais um pouco de trabalho inicial de cadastro (3
  contas em vez de 1) — irrelevante em esforço.
- **Opção B — Login único compartilhado entre as 3 pessoas** — como hoje. Prós: simplicidade
  imediata. Contras: nenhuma rastreabilidade individual no log de auditoria; se uma pessoa sair da
  empresa, é preciso trocar a senha e comunicar às outras duas; contraria o requisito de auditoria
  pedido no início do projeto.
- **Reversível?** Sim, dá para migrar de B para A depois — mas com perda do histórico de auditoria
  do período em que foi usado o login único.

### 2.3 [DECISÃO] D2 — Continuar com Streamlit ou migrar o frontend

**Contexto:** o sistema atual usa Streamlit para tudo (telas + estado). Streamlit é ótimo para
protótipos e ferramentas internas simples, mas tem limitações reais para o que está sendo pedido:
multiempresa com RBAC granular, várias telas por papel, auditoria, crescimento a médio prazo.

- **Opção A — Migrar para uma stack web tradicional (backend API + frontend separado)** —
  *recomendado para o objetivo declarado ("mais completa, profissional, escalável")*. Ex.: backend
  em **FastAPI** (Python — reaproveita `core/*.py` quase sem alteração) + frontend simples em
  **server-side rendering com Jinja2 + HTMX** (continua tudo em Python, sem exigir aprender um
  framework JS novo, e ainda assim dá controle real de rotas/permissões por página) **ou** um
  frontend em React/Next.js se a Clara preferir uma cara mais "produto" desde já. Prós: controle
  fino de permissão por rota, melhor UX para telas administrativas (usuários, setores, auditoria),
  sem as limitações de sessão/estado do Streamlit, caminho mais natural para crescer. Contras: mais
  trabalho de desenvolvimento nas Fases 2-3 do que só adaptar o Streamlit existente.
- **Opção B — Manter Streamlit, só trocar a autenticação e ligar num banco de verdade.** Prós:
  reaproveita 100% da interface já pronta e aprovada pela equipe, menor esforço nas Fases 2-3.
  Contras: multiempresa/RBAC granular em Streamlit é mais gambiarra do que suporte nativo (não tem
  roteamento real por permissão, `st.session_state` não foi pensado para isso); tende a esbarrar de
  novo nas mesmas limitações assim que "Gestão de Processos" (Fase 5) trouxer mais telas e papéis.
- **Reversível?** Migrar depois de B para A é possível, mas é retrabalho considerável — por isso
  vale decidir com calma agora, não só "pela pressa".

### 2.4 [DECISÃO] D3 — Banco de dados e hospedagem (combinação gratuita)

Com base na comparação da seção 8 do prompt mestre, e considerando volumetria real observada
(~1.900 linhas/ano em audiências, ~800 linhas/ano em recebimentos — tudo bem dentro de qualquer
free tier de Postgres gerenciado):

- **Opção A — Supabase (Postgres + Auth gerenciados, free tier)** — *recomendado*. Prós: Postgres
  real, painel de administração pronto, autenticação e políticas de acesso por linha (Row Level
  Security) prontas para modelar a segregação por operadora sem reinventar a roda, storage
  incluído (útil para anexos/PDFs se um dia precisar). Contras: projeto free pausa após ~1 semana
  de inatividade total (mitigável com um "ping" agendado gratuito, ou aceitável dado que o sistema
  é usado todo dia).
- **Opção B — Neon (Postgres serverless free) + Render (web service free) separados.** Prós: Neon é
  bem previsível para Postgres puro. Contras: duas contas/provedores para administrar em vez de um,
  sem Auth pronta (precisa implementar login do zero, mais trabalho na Fase 4).
- **Reversível?** Sim — é uma decisão de infraestrutura, não de dados; trocar de provedor de
  hospedagem no futuro não exige remodelar o banco (ambos são Postgres padrão).

### 2.5 D4 — Migração de dados: upload manual primeiro, integração com Google Sheets depois

Dado que a fonte real hoje é uma planilha Google Sheets editada todo dia (seção 1.9, item 1), duas
abordagens de import são possíveis. **Proposta (não é decisão com trade-off forte, é sequenciamento
— mas registro aqui para visibilidade):**

- **Fase 3 (migração dos módulos):** continuar aceitando `.xlsx` (upload manual ou exportado do
  próprio Google Sheets) como fonte de import, gravando os dados no banco novo — evita depender de
  credenciais/API do Google logo de cara, e permite validar a paridade com o sistema atual com o
  mesmo processo que a equipe já usa.
- **Fase 7 (automação), se aprovado depois:** avaliar integração direta via Google Sheets API
  (leitura automática, sem precisar exportar/upload manual) — só depois que o banco e as regras já
  estiverem estáveis e validadas. Evita overengineering na largada.

### 2.6 Modelo de permissões (resultado das respostas do Gate 0)

```
Admin Superior         → acesso total, às duas operadoras (EXÍMIA e ELITE), todos os setores
   └── Líder de setor   → acesso total dentro do(s) setor(es)/operadora(s) a que pertence
         └── Colaborador → acesso operacional dentro do(s) setor(es) a que pertence
```

Um usuário pode ter vínculos com **mais de um setor e mais de uma operadora ao mesmo tempo** (ex.:
Líder do setor de Audiências na EXIMIA e Colaborador do setor de Laudos na ELITE) — modelado como
tabela associativa (ver `DATABASE.md`), exceto o Admin Superior, que é um nível acima disso (global,
sem precisar de vínculo por setor).

### 2.7 O que decidir para fechar a Fase 1

Aguardando da Clara: **D1** (login individual vs. compartilhado do Admin Superior), **D2** (migrar
frontend vs. manter Streamlit) e **D3** (Supabase vs. Neon+Render). A lista real de setores (item 4
da seção 1.9) também é bem-vinda, mas não bloqueia o desenho do schema em `DATABASE.md` (a tabela
`setores` é genérica, aceita qualquer nome cadastrado depois).

Depois dessas decisões, sigo para a Fase 2 (Preparação da Fundação) só com aprovação explícita —
nenhum código de produção será escrito antes disso.
