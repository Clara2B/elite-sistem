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

### 2.7 Decisões fechadas (2026-09-21)

A Clara aprovou as três recomendações:

- **D1 — Login individual** por pessoa para os 3 Admin Superior (não compartilhado).
- **D2 — Migrar o frontend**: backend API (FastAPI) + frontend próprio, não manter Streamlit.
- **D3 — Supabase** (Postgres + Auth + RLS) como banco/hospedagem de dados.

**Fase 1 concluída e aprovada.** Segue em `ROADMAP.md`. A lista real de setores (item 4 da seção
1.9) segue como pendência menor, não bloqueante — a tabela `setores` do schema é genérica.

### 2.8 Infraestrutura provisionada (Fase 2, 2026-09-22)

- **Backend (Render, Web Service, free tier):** https://elite-sistem.onrender.com — deploy do
  esqueleto FastAPI, branch `claude/relatorios-arquitetura-auditoria-pewhu8`, `/health` confirmado
  respondendo. Nenhuma regra de negócio ainda (Fase 3).
- **Banco (Supabase, free tier):** projeto criado (`ozhvviiidjpgttcayhnv.supabase.co`), ainda **não
  conectado** ao backend — a connection string será adicionada como variável de ambiente no Render
  só quando a Fase 3 precisar dela de fato (ver `SECURITY.md` seção 4 sobre nunca colar esse valor
  em chat/commit).
- **Fase 2 concluída**: critério de conclusão do prompt mestre ("deploy hello world funcionando no
  ambiente gratuito escolhido, sem nenhuma funcionalidade de negócio ainda") atingido.

## 3. Fase 5 — Gestão de Processos (levantamento e proposta)

Diferente de laudos/audiências/pendências, esse módulo não existe no sistema atual — não havia
nada para auditar em código. O levantamento foi feito em duas partes: perguntas diretas à Clara e
análise da planilha real que a equipe usa hoje (`ELITE - GESTÃO DE PROCESSOS.xlsx`).

### 3.1 O que a planilha real revelou

21 abas (mensais, uma por advogada, e abas "fatais" — cópias manuais dos itens urgentes, prova de
que a equipe já sente falta de um filtro assim no sistema). Volume bem maior que os outros módulos:
milhares de linhas por mês. Cada linha é um **andamento** de um **processo** (o mesmo processo
número aparece repetidas vezes, com eventos diferentes ao longo do tempo) — não uma lista de
processos únicos.

**Achado importante:** a data do prazo fatal, hoje, frequentemente não está num campo separado —
aparece só dentro do texto da observação (ex.: "fatal 20/07") ou nem é registrada de forma
estruturada, só uma marcação "SIM"/"FATAL". Isso foi levado à Clara explicitamente porque, sem uma
data estruturada, não é possível gerar alertas automáticos de prazo — que é a prioridade que ela
apontou.

### 3.2 Respostas da Clara (Gate de requisitos da Fase 5)

- **Tipo de processo:** processo judicial (ação na Justiça), não fluxo administrativo interno.
- **Prioridade do módulo:** não perder prazo, e gerar relatórios (individuais por pessoa + geral da
  equipe).
- **Quem usa:** setores Líder - Gestão de Processos e Admin/dona.
- **Data do prazo fatal:** deve ser obrigatória quando o evento for marcado como prazo fatal — sem
  isso, alertas automáticos não seriam possíveis.
- **Status de processo (aberto/encerrado):** não é prioridade agora — módulo foca em
  andamentos/prazos, não em um fluxo formal de abertura/encerramento.
- **Empresa-cliente:** confirmado — é a mesma lista de ~43 empresas-clientes já cadastrada
  (laudos/audiências/cobranças), não um cadastro separado.
- **Tipos de evento:** confirmado como lista mais ou menos fixa (CUSTAS, DOCUMENTOS, PREPARO DE
  APELAÇÃO, PROCURAÇÃO, SOLICITAR HONORÁRIOS SUCUMBENCIAIS...) — vira catálogo, igual tipos de
  laudo.
- **Aviso de prazo:** inicialmente pedido como dentro do sistema **e** por e-mail (WhatsApp fica para
  avaliar depois); na implementação, a Clara decidiu deixar só o alerta dentro do sistema por
  enquanto — ver §3.5 e `DECISIONS.md`.
- **Conteúdo dos relatórios** (pedido literal da Clara): quantidade de processos e eventos por
  pessoa (assistente), com nome e período; prazos cumpridos vs. perdidos; processos parados e há
  quanto tempo sem atualização. Gerado por funcionário individual **e** em modo geral (equipe toda).
  Com o mesmo cabeçalho/identidade visual ELITE dos relatórios já existentes.

### 3.3 Proposta de modelo de dados

Ver `DATABASE.md` seção 6.1 (`processos`, `tipos_evento`, `eventos_processo`, regra de cálculo de
`status_prazo`, critério proposto de "processo parado" — 15 dias sem novo evento, ajustável).

### 3.4 Plano da Fase 5 (aguardando aprovação para começar a implementar)

- **Objetivo:** portar o controle de processos/prazos da planilha para o sistema, com alertas de
  prazo e os relatórios pedidos pela Clara (individual + geral, com identidade visual ELITE).
- **Escopo dentro:** tabelas `processos`/`tipos_evento`/`eventos_processo`; import da planilha atual
  (mesmo padrão de paridade usado nas Fases 3); endpoints de CRUD de processos/eventos; cálculo de
  `status_prazo` e "processo parado"; relatório individual e geral (texto + PDF com o cabeçalho
  ELITE); lista de "prazos próximos" dentro do sistema; envio de e-mail de alerta de prazo (usa
  algum provedor gratuito de e-mail transacional — a escolher, ex. Resend/Brevo free tier).
- **Escopo fora:** WhatsApp; fluxo formal de status de processo (aberto/encerrado); frontend visual
  (API + `/docs`, como nos módulos anteriores).
- **Dependências:** provedor de e-mail transacional gratuito escolhido e configurado (nova conta a
  criar, como Supabase/Render antes).
- **Riscos:** volume real bem maior que os outros módulos (milhares de linhas) — validar performance
  do import; vocabulário de `tipos_evento` tem cauda longa (muitas variações) — mesmo tratamento já
  usado em `tipos_laudo` (avisa quando não reconhece, não trava o lançamento).
- **Critério de conclusão:** import da planilha real validado (contagens batendo), relatório
  individual e geral gerando com os campos pedidos, alerta de prazo (sistema + e-mail) funcionando
  para ao menos um cenário de teste.

### 3.5 Implementação e validação (2026-09-22)

Aprovado e implementado depois da confirmação da Clara de que `advogada`/`assistente` ficam como
texto livre no `Processo` (sem login — só os líderes acessam o sistema; ver `DECISIONS.md`).

- **Construído:** modelos `Processo`/`TipoEvento`/`EventoProcesso`; `app/services/processos.py`
  (import, `status_prazo`, `gerar_relatorio`, `prazos_proximos`); rotas em `app/api/processos.py`
  (`POST /processos/import`, `GET /processos/relatorio`(`.pdf`), `GET /processos/prazos-proximos`,
  `POST /processos/eventos/{id}/resolver`), todas restritas à operadora ELITE; `gerar_pdf_processos`
  reaproveitando a folha timbrada dos laudos.
- **Alerta por e-mail implementado e depois removido:** a primeira versão incluía envio por e-mail
  (Resend) — a Clara decidiu deixar só o alerta dentro do sistema (`GET /processos/prazos-proximos`)
  por ora. `app/email_alertas.py`, a rota `POST /processos/prazos-proximos/notificar` e as
  variáveis `RESEND_API_KEY`/`RESEND_EMAIL_REMETENTE` foram removidos; ver `DECISIONS.md`. Fica como
  extensão futura de baixo esforço se a prioridade mudar.
- **Import validado contra a planilha real** (`ELITE - GESTÃO DE PROCESSOS.xlsx`, 21 abas, 51.116
  linhas brutas): 44.333 eventos novos importados, 5.636 processos distintos, 6.303 marcados como
  `prazo_fatal`. 6.278 linhas descartadas por não bater com o formato CNJ de número de processo
  (defeito de desalinhamento de cabeçalho em algumas abas — mesmo tratamento defensivo do `_RE_CNJ`,
  documentado no módulo); 484 linhas descartadas por não conseguir separar "empresa - cliente" no
  campo `CLIENTE`.
- **Achado durante a validação do relatório:** o mesmo defeito de desalinhamento de cabeçalho que o
  `_RE_CNJ` protege também pôde jogar uma data de outra coluna dentro de `ADVOGADA`/`ASSISTENTE`
  numa linha que, ainda assim, tinha um número de processo válido — um teste real mostrou uma
  "pessoa" no relatório aparecendo literalmente como `2025-12-03 00:00:00`. Corrigido com um guard
  (`_pessoa_valida` em `app/services/processos.py`): valores que parecem data são tratados como
  ausentes (ficam `None`), em vez de descartar a linha inteira — mesmo espírito das outras checagens
  de sanidade do import. Coberto por teste (`test_pessoa_valida_rejeita_valores_parecidos_com_data`).
- **Limitação conhecida, documentada e aceita:** `data_prazo` fica `None` para todo o histórico
  importado (os dados antigos não têm data estruturada — só texto livre como "fatal 20/07", ou só a
  marcação SIM/FATAL sem data nenhuma; ver §3.1). Os recursos de "prazos próximos" e alerta por
  e-mail só funcionam para eventos lançados dali em diante, com data de prazo informada
  explicitamente via API — não há tentativa de adivinhar a data por regex no texto histórico.
  Também esperado: uma fração grande dos processos aparece como "(sem assistente informado)" no
  relatório — várias abas da planilha real não têm uma coluna `ASSISTENTE` utilizável.
- **Testes:** 52/52 passando (`pytest -q`), `ruff check .` limpo.
- **Ajuste na regra de `prazo_fatal`:** a versão original marcava fatal qualquer célula não-vazia na
  coluna `PRAZO FATAL` (`bool(texto)`) — um `"NÃO"` escrito à mão contaria como fatal. Corrigido
  depois de perguntar à Clara: só `SIM` (normalizado) marca o evento como fatal. Ver `DECISIONS.md`.
- **Correção de usabilidade do `/docs`:** o login usava um `Header()` genérico para ler o
  `Authorization`, o que não registra esquema de segurança no OpenAPI — o botão "Authorize" do
  Swagger não aparecia. Trocado por `fastapi.security.HTTPBearer` (`app/auth.py`), sem mudar o
  formato do token na prática; passo a passo em `backend/README.md`.
- **Alerta por e-mail removido:** a Clara decidiu deixar só o alerta dentro do sistema
  (`GET /processos/prazos-proximos`) por enquanto. Ver `DECISIONS.md`.
- **`mes_referencia` (novo, a pedido da Clara):** cada evento importado guarda o mês/ano da aba de
  origem na planilha (ex. `"SETEMBRO/2026"`, extraído do nome da aba — confirmado por ela, não é
  uma coluna nem o nome do arquivo). Só informativo por ora (aparece no painel de prazos), sem
  filtro de relatório nem bloqueio de import. Ver `DATABASE.md` seção 6.1 e `DECISIONS.md`.
- **502 no import em produção — resolvido:** a Clara reportou `502 Bad Gateway` ao importar a
  planilha real pelo `/docs`, com o mesmo arquivo de 21 abas usado na validação local. Causa: N+1
  real em `get_or_create_empresa` (consultava o banco a cada linha em vez de cachear as ~43 empresas
  fixas), consumindo tempo suficiente pra estourar o proxy do Render num import de dezenas de
  milhares de linhas. Corrigido (cache) e confirmado pela Clara — o 502 não voltou.
- **400 "columns mismatch" — resolvido:** apareceu logo depois de corrigir o 502, causado pela
  própria correção de memória (`read_only=True` no `openpyxl`): esse modo não garante que toda linha
  de uma aba tenha o mesmo número de células (linhas "cortadas" no fim, mais comum em arquivos
  gerados por outra ferramenta que não o openpyxl — a planilha real da Clara parece ser um desses
  casos). Corrigido preenchendo linhas curtas com `None` até a largura da mais larga da aba antes de
  montar o DataFrame (`_normalizar_larguras`, `app/excel_reader.py`). Ver `DECISIONS.md`.
- **500 `DataError` — resolvido:** log do Render confirmou `StringDataRightTruncation` — a coluna
  `advogada` (`VARCHAR(80)`) recebeu um valor de 84 caracteres da planilha real
  (`"HUNTING - Fulana de Tal (CONTR. Beltrano)"`, não um nome simples como previsto). Corrigido
  trocando `nome_cliente`/`advogada`/`assistente` (`Processo`) e `tipo_evento_nome`
  (`EventoProcesso`) de `VARCHAR(N)` para `Text` (sem limite) — todos texto livre da mesma planilha,
  que se mostrou consistentemente mais "rica" em conteúdo do que o desenho original previu. Ver
  `DECISIONS.md` e `DATABASE.md` seção 6.1.
- **Planilha "padronizada" validada localmente:** a Clara ajustou a planilha real e pediu conferência.
  Rodei o import completo local contra o arquivo novo — passou sem erro (todas as correções acima
  seguram bem). Achado e corrigido no caminho: abas antigas nomeadas por abreviação de 3 letras
  (`JUN-25`, `SET-25`...) não eram reconhecidas por `_mes_referencia_da_aba` — estendido, cobertura
  subiu de 61% para 76% dos eventos. Achado e **não** corrigido (é erro de digitação na planilha, não
  bug do parser): abas "JANEIRO26" e "Dra Galzo" têm a célula de cabeçalho de `ASSISTENTE`
  sobrescrita com um número de processo, perdendo essa coluna inteira nessas duas abas — avisado à
  Clara em vez de tentar adivinhar. Ver `DECISIONS.md`.
- **Revalidado em produção:** a Clara testou o import via API em produção depois de todas as
  correções acima (incluindo a padronização dela mesma na planilha) — `200 OK`, sem erro. Fase 5
  encerrada — ver `DECISIONS.md` (entrada "Fase 5 validada em produção; encerrada").

### 3.6 Reimport "upsert" + filtro por assessoria (a pedido da Clara, 2026-09-23)

Depois de um reimport da planilha completa, a notificação mostrou "0 evento(s) novo(s), 44353 já
existiam de antes" — a Clara apontou que isso está errado: mesmo um andamento já citado antes deve
ser atualizado com a informação mais recente da planilha, referente àquele registro específico.
Junto, pediu um terceiro filtro de relatório: assessoria, sempre a primeira palavra antes do nome
na coluna `ADVOGADA` (ex.: `"HUNTING - Fulana de Tal"` → assessoria `"HUNTING"`).

- **Import agora atualiza andamento já existente:** antes, uma linha cuja chave
  (`processo`+`data`+`tipo_evento`) já batia com um `eventos_processo` gravado era só contada como
  duplicada — mesmo que trouxesse `OBSERVAÇÃO`/`PRAZO FATAL`/mês de referência diferentes.
  `eventos_existentes` deixou de ser um set de chaves e virou um dict pro objeto, pra poder ser
  atualizado; cada campo só é sobrescrito quando a linha nova traz um valor preenchido (uma linha
  sem `OBSERVAÇÃO` não apaga uma já cadastrada) e `resolvido`/`resolvido_em`/`data_prazo` nunca são
  tocados pelo import (são controlados manualmente dentro do sistema). `Processo.nome_cliente`
  também passou a ser atualizado com o lançamento mais recente, igual já acontecia com
  advogada/assistente. Contador novo `linhas_atualizadas` no resumo, refletido na mensagem da tela.
- **Campo `assessoria`:** coluna nova em `processos` (migração aditiva, mesmo padrão de
  `_garantir_coluna` já usado pra `mes_referencia`), extraída de `ADVOGADA` no import
  (`_separar_assessoria`) sem alterar `advogada` em si. Novo valor válido de `agrupar_por` no
  relatório (`assistente`/`advogada`/`assessoria`), reaproveitando o mesmo campo de filtro
  "pessoa/assessoria" já existente na tela — sem precisar de um controle de UI novo.
- **Testado:** 7 testes novos em `tests/test_processos_service.py` (extração de assessoria,
  relatório agrupado por assessoria, atualização de evento já existente com dado novo, proteção
  contra apagar dado com célula vazia, `resolvido` nunca é desfeito pelo import, atualização de
  `nome_cliente` — 75 testes no total) + verificação visual local (dropdown "Assessoria" na tela,
  relatório filtrado por "HUNTING", mensagem de import mostrando o contador de atualizados).
- **Reversível:** sim — campo novo aditivo e comportamento de import mais permissivo (atualiza em
  vez de ignorar), sem apagar nenhum dado existente; `resolvido`/prazo seguem só sob controle manual.

## 4. Fase 6 — Interface visual (frontend)

### 4.1 Contexto e decisão (D2, fechada)

Até aqui o sistema só tinha API + `/docs` (Swagger, ferramenta de desenvolvedor). A decisão D2
original (seção 2.3/2.7) já tinha aprovado "backend API + frontend próprio", mas deixou em aberto
a escolha entre Jinja2+HTMX (tudo em Python) ou React/Next.js. A Clara pediu a interface de verdade
("ainda não está profissional e funcional como pedido") e decidiu: **Jinja2 + HTMX**, construir as
telas de **todos os módulos de uma vez** (não módulo a módulo), reaproveitando a identidade visual
já usada nos PDFs (azul-marinho `#152A40`). Ver `DECISIONS.md`.

### 4.2 O que foi construído

- **`app/web/`** — rotas HTML, uma por módulo (`routes_laudos.py`, `routes_audiencias.py`,
  `routes_pendencias.py`, `routes_processos.py`, `routes_usuarios.py`), mais `routes_auth.py`
  (login/logout) e `routes_dashboard.py` (`/`). Todas sob o prefixo `/app/...` pra não colidir com
  as rotas JSON já existentes (ex.: `/laudos` continua JSON; `/app/laudos` é a tela).
- **`app/templates/`** (Jinja2) + **`app/static/style.css`** — layout único (`base.html`) com
  navegação, cores e tipografia consistentes; formulários simples (upload de planilha, filtros de
  relatório) com navegação de página inteira (sem dependência de JavaScript pra funcionar — HTMX
  citado na decisão fica como reforço futuro de UX, não bloqueante, porque este ambiente de
  desenvolvimento não tem acesso à internet pra validar scripts de CDN agora).
- **Autenticação por cookie** (`app/web/auth.py`) — ver `SECURITY.md` seção 5.1. Reaproveita a
  mesma tabela `sessoes` e o mesmo `verificar_senha`/`criar_sessao` da API.
- **Menu dinâmico por permissão** (`app/web/menu.py`) — mesma regra de `operadoras_acessiveis`
  já usada pela API: quem só tem acesso à EXIMIA não vê Laudos/Gestão de Processos no menu, etc.
- **`GET /empresas`** (novo endpoint JSON, `app/api/empresas.py`) — faltava uma forma de listar
  empresas-clientes pra montar os seletores das telas; nenhuma rota existente fazia isso.
- **Achados/corrigidos construindo isso:**
  - `PrazoProximo` (Gestão de Processos) não carregava o `evento_id` — impossível montar um botão
    "marcar resolvido" a partir do painel de prazos (nem pela API, nem pela tela). Adicionado.
  - `response.set_cookie(..., expires=...)` do Starlette exige datetime com timezone; o projeto usa
    datetime naive (UTC) por convenção em todo o schema. Resolvido usando `max_age` (segundos) em
    vez de `expires`, evitando abrir uma exceção só pra essa chamada.
  - PDFs baixados pela tela abriam inline no navegador em vez de baixar (sem
    `Content-Disposition: attachment`) — página dizia "Baixar PDF" mas não baixava. Corrigido nas
    três rotas de PDF (`laudos`, `audiencias`, `processos`), com nome de arquivo sensato
    (`nome_arquivo_pdf` em `app/utils.py`).
- **Testado:** `tests/test_web.py` (login, redirecionamento sem sessão, página 403 pra quem não é
  admin, logout, PDF via cookie) + navegação ponta a ponta com Playwright/Chromium local (login,
  todas as telas, gerar relatório, baixar PDF, criar usuário, ativar/desativar) contra a planilha
  real de Gestão de Processos — capturas de tela conferidas visualmente antes de reportar como
  pronto.
- **N+1 real na tela de Gestão de Processos — resolvido:** a Clara testou em produção e reportou
  lentidão. `gerar_relatorio`/`prazos_proximos` acessavam relações (`processo.eventos`,
  `evento.processo`) sem eager loading — com ~5.636 processos isso é até ~11 mil consultas
  separadas numa única requisição. Corrigido com `selectinload`; medido localmente: 13 consultas no
  total pro relatório do ano inteiro, não cresce com o número de processos. Ver `DECISIONS.md`.
- **Mesmo N+1 achado nos outros três importadores:** a lentidão continuava depois da correção
  acima — `laudos.py`, `audiencias.py` e `pendencias.py` tinham o mesmo bug de `processos.py`
  (`get_or_create_empresa` sem cache dentro do loop de import), só não tinha sido corrigido neles
  ainda. Corrigido nos quatro. Provável explicação também do "Audiências não está gerando" — import
  muito lento, não necessariamente quebrado. Ver `DECISIONS.md`.
- **Tela de Empresas-clientes (a pedido da Clara):** cadastro, edição de nome/CNPJ e
  ativar/desativar — antes só existia `GET /empresas` (leitura); adicionado `POST /empresas`,
  `PATCH /empresas/{id}` e `PATCH /empresas/{id}/ativo` (`app/api/empresas.py`, só Admin
  Superior/T.I., mesma regra de `/usuarios`/`/setores`) e a tela `/app/empresas`.
- **Redesign visual (a pedido da Clara — "esteticamente muito simples, nada moderno"):** layout
  trocado de navbar no topo para sidebar fixa à esquerda, com ícones (SVG inline, sem depender de
  fonte de ícone externa) por módulo; cards com sombra e cantos mais arredondados; paleta
  refinada (mantendo o azul-marinho como cor primária); tabelas com cabeçalho em caixa alta;
  responsivo (sidebar vira barra horizontal em telas estreitas). Só `app/static/style.css` e
  `app/templates/base.html` mudaram estruturalmente — as demais páginas herdam o novo visual sem
  precisar reescrever cada uma.
- **Testado:** `tests/test_web.py` (10 testes, cobrindo login/permissões/PDF/empresas) + navegação
  ponta a ponta com Playwright/Chromium local (dashboard, processos, empresas — criar, editar,
  desativar — confirmado também via chamada HTTP direta com cookie de sessão).

### 4.3 Segunda rodada de polimento (a pedido da Clara, 2026-09-23)

Feedback depois do deploy do redesign: botão de voltar em toda tela, upload de planilha "muito
feio", pop-up de erro "antigo de sistema velho" (a bolha nativa do navegador de campo obrigatório),
homepage mais produzida no menu lateral, e exclusão definitiva de empresa-cliente com confirmação.

- **Link "Voltar ao início"** em `base.html` — aparece em toda página exceto o próprio dashboard,
  sem precisar repetir em cada template.
- **Dropzone de upload redesenhada** (`.upload-zona`/`.upload-label` em `style.css`, ícone SVG,
  nome do arquivo escolhido aparece no lugar do texto padrão) — substitui o `<input type="file">`
  puro nos quatro formulários de importação (laudos, audiências, pendências, processos).
- **Toasts em vez de banner fixo:** `.mensagem` virou um toast flutuante no topo (com botão de
  fechar), via macro `_flash.html`; um aviso contextual que precisa ficar dentro do card (ex.: tipo
  de laudo sem valor cadastrado) usa a classe separada `.aviso-inline`, que não é um toast.
- **Bolha nativa de validação do navegador eliminada:** a bolha "Selecione um arquivo." (HTML5)
  aparecia porque o campo de arquivo é `required`. Trocada por um toast estilizado — achado um bug
  real nessa troca: a validação nativa do navegador nunca dispara o evento `submit` quando um campo
  obrigatório está vazio (ela aborta o envio antes disso), então um listener de `submit` sozinho
  nunca seria chamado pra mostrar o toast. Corrigido desligando a validação nativa desse formulário
  específico (`form.noValidate = true`, só nos formulários de import, que não têm outro campo
  obrigatório além do arquivo) e validando à mão em `app.js`.
- **Homepage (`dashboard.html`) redesenhada:** banner "hero" com data por extenso e saudação, grade
  de módulos com ícone/descrição — e adicionada como "Início" no topo do menu lateral (antes não
  aparecia como item de menu).
- **Exclusão definitiva de empresa-cliente** (a pedido explícito da Clara — "apagar por completo"):
  `DELETE /empresas/{id}` (API) e `POST /app/empresas/{id}/excluir` (tela), com confirmação
  obrigatória num modal (`<dialog>` nativo estilizado, não `window.confirm()`) antes do POST ser
  disparado. Bloqueada no backend (`excluir_empresa` em `app/services/empresas.py`) se houver
  laudo, audiência, cobrança ou processo vinculado — apagar apagaria esse histórico junto, o que
  violaria a regra de nunca modificar/apagar dado que não foi alvo direto do pedido; nesse caso a
  orientação na tela é desativar em vez de excluir.
- **Testado:** dois testes novos em `tests/test_web.py` (exclusão bem-sucedida sem vínculos;
  exclusão bloqueada com laudo vinculado — 68 testes no total) + verificação visual ponta a ponta
  com Playwright/Chromium local (dashboard, dropzone de upload, modal de exclusão, toast de erro
  substituindo a bolha nativa — capturas conferidas antes de reportar como pronto).
- **Pendente:** a Clara relatou "quando clico em importar começa a carregar e não para" — sem os
  dados/planilha específicos ou os logs do Render do momento do problema não dá pra reproduzir nem
  diagnosticar; segue como pendência em aberto até ela mandar mais detalhes (qual módulo, qual
  arquivo, quanto tempo esperou, e/ou os logs).

### 4.4 Terceira rodada: CSS em cache após deploy + lentidão geral (2026-09-23)

A Clara testou o deploy da seção 4.3 e mandou print do modal de exclusão sem nenhum estilo (borda
preta padrão do navegador, sem sombra, sem cantos arredondados, sem o ícone estilizado) — só os
botões (`.perigo`/`.secundario`, que já existiam antes desse deploy) apareciam certos. Isso é a
marca registrada de CSS em cache: o navegador (ou um proxy no caminho) continuou servindo a versão
anterior de `style.css` mesmo depois do deploy, porque o link sempre aponta pra mesma URL
(`/static/style.css`, sem nenhuma marca de versão) — localmente, com Playwright, o mesmo arquivo
renderizava perfeito (ver captura da seção 4.3), então o CSS em si nunca esteve errado.

- **Corrigido:** `app/web/templates.py` agora calcula um hash do conteúdo de `style.css`/`app.js`
  na inicialização do processo (`versao_estatico`, injetado como global do Jinja, disponível em
  toda página sem precisar passar no contexto) e `base.html`/`login.html` usam
  `/static/style.css?v=<hash>` / `/static/app.js?v=<hash>`. Como o hash muda sempre que o conteúdo
  muda, cada deploy gera uma URL nova — nenhum cache antigo (navegador ou proxy) pode ser
  reaproveitado por engano de novo.
- **Também relatado:** "o sistema todo está muito devagar, tudo que clico demora muito pra
  carregar" — mais amplo que só o import. Sem conseguir reproduzir localmente (aqui está rápido) e
  sem acesso a métricas de produção, a causa mais provável é o **plano gratuito do Render**
  (`ARCHITECTURE.md` seção 2.8): o serviço "dorme" depois de um período de inatividade e a
  primeira requisição depois disso demora dezenas de segundos pra "acordar" — o que bateria com
  "tudo demora", não um módulo específico. Não dá pra confirmar isso sem ver o padrão real (ex.: só
  o primeiro clique depois de um tempo parado é lento, ou é lento o tempo todo).
- **Adicionado pra próxima vez que isso acontecer:** um middleware simples em `app/main.py`
  (`_medir_tempo_de_requisicao`) loga método, caminho, status e duração de toda requisição nos logs
  do Render (stdout) — antes não existia nenhum log de tempo, só dava pra adivinhar onde estava a
  lentidão. Da próxima vez, os logs do Render do momento do problema já mostram exatamente qual
  requisição demorou e quanto.
- **Testado:** `ruff check`/`pytest -q` (68 testes, sem mudança na contagem — isso é
  infraestrutura, não comportamento) + verificação visual local confirmando a URL do CSS agora
  carrega `?v=<hash>` e o modal renderiza igual à captura da seção 4.3.
- **Pendente:** confirmar com a Clara, depois desse deploy, (1) se o modal aparece estilizado após
  um refresh normal (sem precisar de Ctrl+Shift+R) e (2) se a lentidão segue o padrão de "só o
  primeiro clique depois de um tempo parado" — o que apontaria pro plano gratuito do Render como
  causa raiz, decisão de custo que caberia a ela.

### 4.5 "Internal Server Error" em branco no import de audiências (2026-09-23)

A Clara importou uma planilha de audiências e recebeu uma página em branco do navegador dizendo só
"Internal Server Error", sem nenhum estilo — o mesmo tipo de experiência feia que ela já tinha
reclamado antes (item "pop-up estilizado", seção 4.3), só que nem chegando a ser um pop-up: era o
próprio servidor quebrando sem tratamento nenhum.

- **Causa raiz — confirmada pelo log do Render que a Clara mandou depois:** `character varying(20)`
  no `StringDataRightTruncation`. De todos os campos de `audiencias`, só `cpf` era `VARCHAR(20)` —
  a célula de CPF na planilha real às vezes tem mais que um CPF formatado (14 caracteres), e foi
  isso que estourou, não `advogada` como eu tinha suposto de início (essa suposição não estava de
  todo errada — é o mesmo padrão de texto livre que já causou `StringDataRightTruncation` em
  `processos`/`advogada` — só não era a coluna que quebrou dessa vez). `cpf` virou `Text`, e os
  outros quatro campos (`nome_cliente`/`data_agendamento`/`conciliadora`/`advogada`) continuam
  convertidos também, por precaução, com a mesma migração aditiva (`_garantir_texto_ilimitado`)
  já usada em `processos`.
- **Corrigido também, independente da causa raiz acima:** a rota só capturava `ValueError` — qualquer
  outro tipo de erro (incluindo esse `DataError` do Postgres) derrubava a request inteira sem handler
  nenhum, virando a página em branco do navegador. Adicionado um `@app.exception_handler(Exception)`
  global em `app/main.py`: loga o traceback completo (nos logs do Render, aparece junto com o tempo
  de requisição já instrumentado) e devolve a página `erro.html` já estilizada (mesma usada pra 403)
  em vez do crash cru — só pras rotas de tela (`/`, `/login`, `/app/...`); rotas de API/JSON continuam
  devolvendo JSON, pra não quebrar nenhum cliente que espere isso. Efeito prático: qualquer bug
  futuro não tratado (não só esse) já aparece com uma tela decente pra Clara e um traceback completo
  no log pra mim, em vez de repetir esse mesmo susto.
- **Testado:** 2 testes novos em `tests/test_web.py` simulando um erro genérico numa rota de tela e
  numa rota de API (confirma página estilizada vs. JSON, respectivamente) + 3 testes novos em
  `tests/test_audiencias_service.py` (schema dos cinco campos é `Text`, não `VARCHAR`; import com
  `ADVOGADA` e com `CPF` de texto longo não quebra) — 80 testes no total. Verificação visual local
  confirmando o import de audiências com um valor de `ADVOGADA` de 90+ caracteres funcionando de
  ponta a ponta, e a página `erro.html` (caso 403) continua igual depois da mudança no link do CSS.
- **Reversível:** sim — campo mais permissivo (`Text` em vez de `VARCHAR(N)`) e um handler de erro
  aditivo, que só muda o que acontece quando já ia dar erro sem tratamento nenhum.

### 4.6 Import de planilha lento — dois achados reais (2026-09-23)

A Clara reportou "o sistema precisa ler os arquivos em planilha mais rápido". Em vez de adivinhar,
gerei planilhas sintéticas no tamanho da planilha real (~45 mil linhas / ~5.600 processos, seção
3.5) e no formato real (21 abas, a maioria sem os cabeçalhos exigidos) e medi o import ponta a
ponta localmente, antes e depois de cada correção.

- **Achado 1 — `db.flush()` por processo novo:** `importar_planilha` (Gestão de Processos) dava
  `db.flush()` logo depois de criar cada `Processo` novo, só pra ter `.id` disponível na mesma linha
  (pra montar a chave de evento e pro `processo_id` do evento novo). Com ~5.600 processos novos
  num import, isso é ~5.600 idas e vindas ao banco em vez de umas poucas dúzias (as comissões
  periódicas já existentes, a cada 2.000 eventos). Corrigido em duas partes: (1) a chave de
  deduplicação de evento passou a usar `numero_processo` (já disponível na própria linha) em vez de
  `processo.id`; (2) o evento novo é criado com `EventoProcesso(processo=processo, ...)` — o
  relacionamento do SQLAlchemy, não `processo_id=processo.id` — deixando o próprio SQLAlchemy
  resolver a chave estrangeira sozinho no próximo flush (o periódico, não um por linha), mesmo que o
  processo ainda não tenha `.id` no momento em que o evento é criado. Medido localmente (SQLite, sem
  nenhuma rede — Supabase em produção deve ganhar proporcionalmente mais, já que cada flush ali é
  uma ida e volta de rede de verdade, não só disco local): import de ~45 mil linhas caiu de 17,7s
  para 14,3s.
- **Achado 2 — abas irrelevantes lidas por inteiro antes de descartadas:** `load_data_sheets`
  (`app/excel_reader.py`, usado pelos quatro importadores) lia **cada aba inteira** do arquivo pra
  só depois checar se ela tinha os cabeçalhos exigidos — numa planilha real com ~21 abas (mensais,
  por advogada, "fatais", dashboard/resumo — ver DATABASE.md seção 6), a maioria não bate com os
  cabeçalhos e era descartada, mas só depois de já ter sido inteiramente lida e convertida em linhas
  Python. Corrigido: agora só as 5 primeiras linhas de cada aba (o quanto a checagem de cabeçalho já
  olhava) são lidas antes de decidir se vale a pena continuar lendo o resto daquela aba. Medido
  localmente com um arquivo de 21 abas (6 relevantes, 15 não): `load_data_sheets` sozinho caiu de
  4,96s para 3,29s; o import completo (parse + gravação no banco) caiu de 31,3s para 15,9s — quase
  metade do tempo.
- **Log de diagnóstico adicionado:** `load_data_sheets` e os quatro `importar_planilha` agora logam
  sua própria duração (nos logs do Render, mesmo canal do middleware de tempo de requisição já
  existente) — separando quanto tempo foi parse do arquivo vs. resto do import (consultar dados já
  existentes, gravar no banco). Sem isso, "a planilha demora" só dava pra investigar adivinhando;
  agora, se continuar lento com a planilha real dela, o log já mostra exatamente qual fase.
- **Testado:** 1 teste novo em `tests/test_processos_service.py` (dois eventos de um processo novo
  na mesma planilha continuam corretamente ligados a um único processo, sem duplicar nem perder a
  ligação — o cenário exato que a mudança do `db.flush()` afeta) — 81 testes no total, nenhum
  existente quebrou. Verificação de ponta a ponta local via navegador (Playwright) com um arquivo de
  21 abas/36 mil linhas: import completo em ~18s (incluindo renderizar a tela de volta), log
  confirmando a duração de cada fase separadamente.
- **Reversível:** sim — mesmo comportamento de import, só menos idas e vindas ao banco e menos
  leitura desperdiçada de aba que não interessa.

### 4.7 Log real do Render revela a causa maior: tela de Processos carregava a tabela inteira (2026-09-24)

A Clara mandou o log real do Render depois do deploy da seção 4.6 — as correções de lá ajudaram
(import de ~45s de parse passou pra funcionar), mas o log revelou dois números que eu não esperava:
`GET /app/processos` levando **13-15 segundos**, sem nenhum import acontecendo — só abrindo a tela —
e o import de verdade da planilha real (51.129 linhas, 22 abas) levando **169,8 segundos** (48,9s de
parse + 120,9s do resto). Como o Render free tier tem só 0,1 vCPU (achado numa pesquisa de preços do
Render) e o banco é o Supabase free tier, resolvi montar um Postgres local (o pacote já vem
instalado neste ambiente) com o mesmo volume de dados da planilha real (~5.600 processos, ~45 mil
eventos) pra medir com uma base de comparação mais parecida com produção do que SQLite.

- **Achado — `GET /app/processos` sempre gerava um relatório completo, mesmo sem pedir um:** a rota
  chama `gerar_relatorio()` com o período padrão (dia 1 do mês até hoje) toda vez que a tela abre,
  não só quando alguém aperta "Gerar relatório". E `gerar_relatorio()` carregava **todos** os ~5.600
  processos com `selectinload(Processo.eventos)` — todos os ~45 mil eventos de sempre — e só
  filtrava por período **depois, em Python**. `selectinload` sozinho ainda dividia isso em ~13 idas
  e vindas ao banco (lote de 500 ids por vez). Corrigido: a consulta agora busca só os eventos
  **dentro do período pedido** direto no SQL (`WHERE data >= periodo_ini AND data <= periodo_fim`),
  com `selectinload` só pro processo relacionado a esses eventos — não mais a tabela inteira. A
  contagem de "processo parado" (que precisa do último evento de toda a história, não só do
  período) virou uma consulta agregada separada e leve (`MAX(data) GROUP BY processo_id`), restrita
  só aos processos que já entraram no relatório. Medido com Postgres local + mesmo volume de dados:
  13 consultas / 1,1-1,6s → 7 consultas / 0,14-0,2s (~8-10x mais rápido, e seria bem mais em
  produção, com latência de rede de verdade entre Render e Supabase).
- **Achado — `prazos_proximos()` varria a tabela inteira sem índice, sempre em busca de zero
  resultados:** essa consulta filtra por `data_prazo IS NOT NULL`, mas **nada no sistema hoje
  preenche `data_prazo`** (só fica pronto pra lançamento manual futuro — ver docstring do módulo) —
  ou seja, essa consulta sempre devolve zero linhas, mas ainda assim varria `eventos_processo`
  inteira (sem índice em `prazo_fatal`/`resolvido`/`data_prazo`) toda vez que a tela carregava.
  Testado localmente: nem com nem sem índice isso ficou lento o bastante (< 50ms com ~45 mil linhas)
  pra explicar os 13-15s sozinho — mas é uma correção segura e barata mesmo assim (índice parcial,
  `_garantir_indice_prazos_fatais` em `app/db.py`), e pode importar mais num banco Supabase
  sobrecarregado ou numa tabela bem maior no futuro.
- **Import da planilha real ainda é pesado — mas por volume de dado, não por bug:** o import ainda
  carrega **todos** os processos/eventos já existentes no banco (não só os do arquivo) pra decidir o
  que é novo/atualizado — reproduzido localmente contra Postgres com o mesmo volume (importando o
  mesmo arquivo duas vezes, replicando o cenário real da Clara de "quase tudo já existe"): ~8,65s
  localmente (sem nenhuma latência de rede). Em produção, isso é ~120s — a diferença bate com
  latência de rede real entre Render e Supabase movendo dezenas de milhares de linhas, não com um
  bug de código (o trabalho em si já se mostrou rápido localmente, mesmo com Postgres de verdade).
  Uma correção mais profunda (upsert direto no SQL em vez de carregar tudo em objetos Python antes
  de comparar) reduziria isso ainda mais, mas é uma mudança de maior risco num caminho de dado de
  produção real (prazos de processos judiciais) — fica registrada como próximo passo em aberto, não
  implementada nesta rodada; ver `DECISIONS.md` pendência.
- **Testado:** 2 testes novos em `tests/test_processos_service.py` ("processo parado" considera a
  história inteira, não só o período do relatório; a consulta não volta a carregar a tabela inteira,
  travado por contagem de consultas SQL) — 83 testes no total, nenhum existente quebrou. Validado
  contra um Postgres local de verdade (não só SQLite) com volume de dado igual ao da planilha real,
  incluindo contagem real de consultas SQL antes/depois de cada correção. Verificação visual local
  confirmando que o relatório continua com os números certos depois da reescrita.
- **Reversível:** sim — mesmo resultado de relatório (só a consulta mudou, não a regra de negócio),
  índice é aditivo.

### 4.8 Datas erradas no relatório de Laudos — coluna errada lida no import (2026-09-24)

A Clara comparou o relatório de Laudos da ABSOLUTA (tela do Elite Sistem) com a planilha real, linha
por linha, e achou datas erradas em várias delas — não coincidência: as datas erradas batiam
exatamente com uma das outras colunas de data que aparecem mais à direita na planilha (prazo/
entrega), não com a coluna A (a de entrada do laudo, a que vale pro sistema). Comparação exata:

| Cliente | Data real (coluna A) | Data que o sistema mostrou |
|---|---|---|
| JOSE NUNES DA ROSA FILHO | 26/08 | 27/08 (uma das colunas de data mais à direita) |
| HAFLER SZUBRIS AMORIM | 27/08 | 01/09 (idem) |
| CESAR ELIAS MACHADO | 31/08 | 03/09 (idem) |
| ALBERTO TRAJANO DE ALMEIDA | 02/09 | 02/09 ✓ |
| JAILSON FRANCISCO DE LIMA | 11/09 | 11/09 ✓ |
| VILMAR MARQUES | 11/09 | 11/09 ✓ |

Só 3 das 6 linhas vieram erradas — sinal de que não é a planilha inteira desalinhada, é algo
específico de certas abas/linhas (a mesma classe de defeito já visto em Gestão de Processos:
cabeçalho de colunas variando entre abas da mesma planilha).

- **Causa:** `app/services/laudos.py` buscava a data pelo **nome** do cabeçalho (`_col(df, "DATA")`
  — resolvido no DataFrame já unificado de todas as abas). Quando mais de uma coluna cai no mesmo
  nome canônico "DATA" (a ordem das colunas varia de aba pra aba na planilha real), a busca por nome
  pode resolver pra uma coluna diferente dependendo de qual aba aquela linha veio — puxando a data
  de prazo/entrega em vez da data de entrada do laudo, só nas abas com esse desalinhamento.
- **Corrigido:** a Clara confirmou que a coluna A é sempre a data certa. `load_data_sheets`
  (`app/excel_reader.py`) agora também guarda o valor bruto da coluna A por **posição** (`_COL_A`,
  igual já faz com `_ABA`) — sem depender do nome do cabeçalho daquela célula. O import de laudos
  usa esse valor quando ele já é uma data válida; só cai de volta pro nome "DATA" quando a coluna A
  não é uma data (evita quebrar layouts onde a coluna A é outra coisa, ex. testes existentes com
  "EMPRESA" primeiro — confirmado com um teste de regressão que já existia e continuou passando).
- **Pendência importante, não resolvida nesta rodada:** esse conserto vale só pra **importações
  novas** — laudos que já foram importados com a data errada continuam errados no banco até serem
  reimportados ou corrigidos manualmente, e como a chave de duplicidade do import inclui a data,
  simplesmente reimportar o mesmo arquivo hoje criaria um registro novo (com a data certa) sem
  remover o antigo (com a data errada) — duplicaria em vez de corrigir. Perguntar à Clara como ela
  quer corrigir os dados já importados antes de fazer qualquer limpeza (não é uma decisão pra tomar
  sozinho, é dado real de faturamento).
- **Testado:** 2 testes novos (`tests/test_excel_reader.py` — `_COL_A` captura a coluna A por
  posição, não por nome, mesmo com abas de layout diferente; `tests/test_laudos_service.py` — import
  usa a coluna A quando ela é uma data válida, mesmo com uma coluna extra de data no meio) — 85
  testes no total, nenhum existente quebrou (inclusive um teste antigo com "EMPRESA" na coluna A,
  que serviu de prova de que o fallback funciona).
- **Reversível:** sim — muda só qual coluna o import lê, sem mexer em dado já gravado.

### 4.9 "Apagar todo o histórico de laudos" (a pedido da Clara, 2026-09-24)

Continuação direta da seção 4.8: a Clara confirmou que **todas** as empresas foram afetadas pela
data errada, e pediu explicitamente pra apagar o histórico inteiro de laudos, corrigir o sistema
(já corrigido na 4.8) e reimportar a planilha do zero.

- **`apagar_todos_laudos(db)`** (`app/services/laudos.py`) — apaga todas as linhas de `laudos` num
  `DELETE` só (não carrega os registros um por um antes) e devolve a contagem apagada. Só mexe em
  `laudos`; não toca em empresas-clientes, tipos de laudo cadastrados nem em nenhum outro módulo.
- **Rota web `POST /app/laudos/apagar-tudo`** e **rota API `DELETE /laudos`** — ambas restritas a
  Admin Superior/T.I. (`admin_logado_web`/`require_admin`; nem todo usuário ELITE, diferente das
  outras rotas de laudos). Registrada no log de auditoria (`APAGOU_TODOS_LAUDOS`, com a contagem).
- **Confirmação reforçada na tela:** o modal de confirmação já usado pra excluir empresa (seção 4.x
  anterior) não pareceu proteção suficiente pra apagar uma tabela inteira — adicionado um mecanismo
  novo e reaproveitável (`data-confirmar-texto`/`data-confirmar-alvo` em `app/static/app.js`): o
  botão de confirmar só destrava depois de digitar a palavra pedida ("APAGAR") num campo de texto
  dentro do modal. Fica disponível pra qualquer ação futura de risco parecido, não só essa.
- **Testado:** 4 testes novos (`tests/test_laudos_service.py` — apaga tudo e devolve a contagem
  certa, banco já vazio não quebra; `tests/test_web.py` — admin consegue, não-admin recebe 403 sem
  apagar nada; `tests/test_api_laudos.py` — mesma checagem pela API) — 90 testes no total.
  Verificação visual local ponta a ponta com Playwright: importar um laudo, abrir o modal, confirmar
  que o botão fica desabilitado até digitar "APAGAR" (maiúsculas/minúsculas não importam), e que o
  laudo some de verdade depois de confirmar.
- **Reversível:** não — é uma exclusão real e definitiva, por isso a barreira de confirmação mais
  forte que o padrão do resto do sistema. Usada a pedido explícito da Clara, não por iniciativa
  própria.

### 4.10 Pendências: "Não" também conta como pendência (a pedido da Clara, 2026-09-24)

A regra original (seção 1.2, diagnóstico da Fase 0) tratava o campo PAGO como pendência só quando o
valor era diferente de "SIM" **e** de "NÃO" — ou seja, "NÃO" era tratado como resolvido, igual
"SIM". A Clara pediu explicitamente que "NÃO" também seja lido como pendência: só "SIM" conta como
pago/resolvido; qualquer outro valor não-vazio ("NÃO", "EM ATRASO", "PENDENTE" etc.) é pendência.

- **`STATUS_PAGO_OK`** (`app/services/pendencias.py`) — reduzido de `{"SIM", "NÃO"}` para `{"SIM"}`.
  `_e_pendente()` não mudou de lógica (continua `texto not in STATUS_PAGO_OK`); o comportamento
  muda porque o conjunto de "ok" ficou menor. `_PRIORIDADE_PAGO` (usado só para desempate de linhas
  duplicadas na importação, priorizando manter a linha "SIM" quando duas batem na mesma chave) não
  precisou mudar — "SIM" continua vencendo.
- **Sem migração/reimportação necessária:** diferente do bug de datas de Laudos (seção 4.8), aqui o
  texto bruto de PAGO já é gravado como veio da planilha, sem interpretação no momento do import — a
  regra "isso conta como pendência?" é aplicada ao vivo, a cada geração de mensagem
  (`gerar_mensagens`), lendo o texto já salvo. Assim que o deploy sobe, todo o histórico já
  importado passa a ser reinterpretado corretamente, sem precisar apagar nem reimportar nada.
- **Testado:** novo teste `test_pago_nao_conta_como_pendente`
  (`tests/test_pendencias_service.py`) cobre uma cobrança com PAGO="Não" e confirma que ela aparece
  na mensagem de pendência gerada. Verificação visual local (planilha sintética com linhas "Não"/
  "Sim"/vazio) confirma que só a linha "Não" aparece como pendência.
- **Reversível:** sim — é só uma constante (`STATUS_PAGO_OK`); reverter é trivial se a regra mudar
  de novo no futuro.

### 4.11 "Zona de perigo" estendida para Audiências, Pendências e Gestão de Processos (2026-09-24)

A Clara pediu pra estender o botão "Apagar todo o histórico" (criado na seção 4.9, só em Laudos)
para as outras três telas de import/relatório — mesmo padrão, mesma barreira de confirmação.

- **Serviço:** `apagar_todas_audiencias()` (`app/services/audiencias.py`), `apagar_todas_pendencias()`
  (`app/services/pendencias.py`) e `apagar_todos_processos()` (`app/services/processos.py`) — mesmo
  formato de `apagar_todos_laudos()` (`DELETE` em massa numa transação só, devolve a contagem
  apagada). Gestão de Processos é o único caso com uma particularidade: não há `cascade` configurado
  entre `eventos_processo` e `processos` (ver `app/models.py`), então `apagar_todos_processos()`
  apaga os eventos primeiro e só depois os processos, na mesma função — sem isso a segunda parte
  falharia por violação de chave estrangeira. A contagem devolvida é de PROCESSOS, não de eventos.
- **Rotas web `POST /app/<módulo>/apagar-tudo`** e **rotas API `DELETE /<módulo>`** — todas
  restritas a Admin Superior/T.I. (`admin_logado_web`/`require_admin`), igual Laudos — mais
  restrito que o acesso normal por operadora dessas telas (ex.: Audiências normalmente só exige
  acesso à EXIMIA; apagar tudo exige ser admin, mesmo que o admin veja as duas operadoras).
- **Tela:** mesmo bloco "Zona de perigo" + modal com confirmação por texto digitado ("APAGAR") já
  usado em Laudos, reaproveitando o mecanismo genérico `data-confirmar-texto`/`data-confirmar-alvo`
  (`app/static/app.js`) — nenhum JS novo precisou ser escrito, só o HTML do modal em cada template.
- **Testado:** 12 testes novos — serviço (apaga tudo + devolve a contagem certa, banco já vazio não
  quebra, cada módulo) e rota web (admin consegue com redirecionamento e mensagem, não-admin recebe
  403 sem apagar nada, cada módulo) — 103 testes no total. Verificação visual local com Playwright
  nas três telas: botão aparece só pra admin, modal abre, botão de confirmar fica desabilitado até
  digitar "APAGAR" (maiúsculas/minúsculas não importam), e o registro de teste some de verdade
  depois de confirmar (audiências verificado ponta a ponta; pendências/processos verificados até a
  abertura do modal e o destravamento do botão, mesmo código do backend já coberto por teste
  automatizado).
- **Sem rotas de API JSON dedicadas em teste:** diferente de Laudos (que tem `tests/test_api_laudos.py`),
  Audiências/Pendências/Gestão de Processos nunca tiveram um arquivo de teste de API JSON próprio
  neste projeto (só teste de serviço + teste de tela web) — as novas rotas `DELETE` seguem o mesmo
  padrão de cobertura já existente para essas três telas, não o de Laudos.
- **Reversível:** não — mesma natureza irreversível de Laudos; a barreira de confirmação é a mesma.

