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

### 4.12 Relatório de Gestão de Processos contando errado no mês corrente (2026-09-24)

A Clara reportou o relatório geral mostrando 3.552 eventos pro período 01/09–24/09/2026, quando a
aba SETEMBRO26 da planilha real só tem ~2.449 linhas. Investigação (com a planilha real que ela
mandou) encontrou **dois bugs reais**, nas duas direções:

- **Empresa não reconhecida nas abas novas (fazia perder quase todo o mês corrente):** a partir de
  algum mês (confirmado em AGOSTO26/SETEMBRO26), a planilha passou a ter a empresa numa **coluna
  própria** ("EMPRESA"), em vez do formato antigo "EMPRESA - Cliente" embutido na coluna CLIENTE. O
  import só sabia separar o formato antigo (`_separar_empresa_cliente`) — sem reconhecer a coluna
  nova, ~97% das linhas da aba SETEMBRO26 (2.333 de 2.406) eram descartadas por "empresa não
  reconhecida", nunca chegando a virar `Processo`/`EventoProcesso`. **Corrigido:**
  `importar_planilha` (`app/services/processos.py`) agora usa a coluna EMPRESA diretamente quando
  ela existir e vier preenchida na linha; cai pro formato com hífen só quando não tiver essa coluna
  (abas antigas continuam funcionando exatamente como antes).
- **"DATA DE LIBERAÇÃO" sendo contada como se fosse a data do andamento (fazia ganhar eventos de
  outros meses):** algumas abas "coringa" (fatais, Dra Galzo, Dra Kelly, Dra Sleiman, DOCS E
  CUSTAS, JUN-25 a OUT-25) não têm uma coluna de data de andamento real — só "DATA DE LIBERAÇÃO —
  QUANDO A DRA INSERIU O CLIENTE NA PLANILHA" (data de intake do cliente naquela aba, não do
  andamento em si), que o `HEADER_ALIASES` (`app/excel_reader.py`) já equiparava a "DATA" por falta
  de coluna melhor. Isso fazia uma linha entrar no relatório do mês em que o cliente foi
  cadastrado naquela aba, não no mês do andamento de verdade — ex.: a aba "FATAIS 08" sozinha
  contribuiu 333 "eventos de setembro" que eram só datas de liberação. A Clara confirmou: essas
  linhas não devem contar no filtro por período do relatório (continuam existindo no sistema
  normalmente, só não entram nessa contagem mensal). **Corrigido:** novo marcador
  `_DATA_E_LIBERACAO` em `load_data_sheets` (`app/excel_reader.py`), por aba, sinalizando quando o
  que virou "DATA" veio literalmente dessa coluna de liberação — não de "DATA"/"DIA" (essas
  continuam contando normalmente: a aba FATAIS 08, por ex., usa "DIA" com data real do andamento,
  não é afetada). Novo campo `EventoProcesso.data_e_liberacao` (`app/models.py`, migrado via
  `_garantir_coluna` em `app/db.py`) grava esse marcador por evento; `gerar_relatorio` exclui
  eventos com esse marcador do filtro por período.
- **Não é um terceiro bug, mas parte da explicação:** parte da diferença entre 2.449 (contagem
  manual da Clara, só da aba SETEMBRO26) e o total certo do sistema depois da correção (~2.693) é
  legítima — a aba "FATAIS 08" tem ~333 prazos fatais de setembro de verdade (datas reais na coluna
  "DIA"), só que registrados numa aba separada da mensal, que a contagem manual não incluiu.
- **Sem migração de dados corrompidos:** diferente do bug de Laudos (seção 4.8), aqui a `data` já
  gravada nos eventos existentes está correta (o bug era só de contagem — não gravava data errada,
  só deixava de reconhecer empresa ou contava uma data errada como se fosse "a" data certa); a
  contagem de empresa incorreta, porém, significa que a maior parte do mês corrente simplesmente
  **nunca foi importada** — recomendado à Clara apagar o histórico de Gestão de Processos (zona de
  perigo, seção 4.11) e reimportar a planilha completa pra ter certeza de que tudo está coberto com
  a lógica corrigida, em vez de tentar reconciliar incrementalmente.
- **Testado:** 4 testes novos — `test_import_reconhece_empresa_em_coluna_propria_alem_do_formato_com_hifen`,
  `test_import_marca_data_de_liberacao_e_relatorio_a_exclui_do_periodo`,
  `test_import_data_real_de_aba_dia_nao_e_marcada_como_liberacao`
  (`tests/test_processos_service.py`) e `test_load_data_sheets_marca_data_e_liberacao_so_na_aba_que_usa_esse_alias`
  (`tests/test_excel_reader.py`) — 107 testes no total. Validado também rodando o import completo
  contra a planilha real que a Clara mandou (fora da suíte automatizada): "empresa não reconhecida"
  caiu de 6.632 para 450 linhas, e o total de eventos no período 01/09–24/09/2026 foi de 3.552 para
  2.693 (≈2.365 da aba SETEMBRO26 + ≈328 de FATAIS 08, ambos com data real).
- **Reversível:** sim — `data_e_liberacao` é só um booleano; reverter a exclusão do relatório (ou a
  leitura da coluna EMPRESA) é uma mudança pequena e isolada se a regra mudar de novo.

### 4.13 Dropdowns de Empresa e Funcionário no Relatório de Gestão de Processos (2026-09-24)

A Clara pediu pra trocar digitação livre por menus suspensos no Relatório de Processos, usando a
mesma fonte de dados dos menus já existentes noutras telas (sem duplicar lista). Contexto
importante que ela trouxe antes de eu implementar: no futuro vai apagar todas as empresas
cadastradas e recadastrar só as oficiais (com CNPJ), e quer que o sistema pare de criar empresa
nova sozinho a partir da planilha — por isso o dropdown de Empresa lê direto de
`empresas_clientes` (não duplica lista), e a mudança de "parar de auto-criar" fica para depois,
como etapa separada (mexe no import de todos os módulos, não só nesse relatório).

- **Novo cadastro `Funcionario`** (`app/models.py`, tabela `funcionarios`) — mesmo padrão de
  `EmpresaCliente` (nome único, ativo), mas **não é FK** de `Processo.assistente` (que continua
  texto livre, vindo da planilha): é só uma lista de valores pré-definidos pra montar o dropdown,
  sem mexer em como o import já grava assistente. Semeados os 7 nomes que a Clara informou
  (`DEFAULT_FUNCIONARIOS` em `app/db.py`), editável depois pela tela nova.
- **Tela `/app/funcionarios`** (`app/web/routes_funcionarios.py` + `funcionarios.html`) e API
  `/funcionarios` (`app/api/funcionarios.py`) — cadastro/edição/ativação/exclusão, mesmo padrão de
  `/app/empresas`, restrito a Admin Superior/T.I. Exclusão não tem checagem de vínculo (não existe
  FK) — só tira o nome do dropdown, não mexe em processo/evento já gravado.
- **Relatório de Processos** (`app/services/processos.py::gerar_relatorio`) ganhou
  `filtro_empresa` — filtra os eventos por `Processo.empresa_cliente_id`, resolvido por nome
  normalizado (mesmo padrão de `gerar_relatorio` de Laudos/Audiências). Esse filtro **não existia
  antes** nessa tela (só em Laudos/Audiências/Pendências).
- **Campo "Pessoa" no formulário** (`processos.html`) — vira um dropdown de Funcionário quando
  "Agrupar por" = Assistente (única opção com lista fixa; Advogada/Assessoria continuam texto
  livre, sem lista cadastrada). Os dois campos têm o mesmo `name="pessoa"` mas só um fica habilitado
  por vez — `app/static/app.js::iniciarAlternanciaFuncionario()`, alternando com base no valor de
  "Agrupar por" (`[data-mostrar-se-agrupar]`), desabilitando o campo escondido pra não mandar dois
  valores pro mesmo parâmetro no submit.
- **Migração:** `_garantir_coluna` não é necessária (tabela nova, criada por `create_all`); banco
  de produção já ganha `funcionarios` semeada no próximo deploy, sem passo manual.
- **Testado:** 7 testes novos (serviço: filtro por empresa + empresa inexistente; web: CRUD de
  funcionários, página restrita a admin, relatório filtrando por empresa) — 114 no total.
  Verificação visual local com Playwright: dropdown de Empresa/Funcionário populados certinho,
  alternância Funcionário↔texto-livre funcionando (campo escondido fica `disabled`), relatório
  filtrado por empresa mostrando só o processo esperado, tela de Funcionários listando os 7 nomes
  semeados.
- **Reversível:** sim — tabela nova e campo de filtro isolados; reverter é remover a tabela/rota
  sem afetar mais nada (não há FK apontando pra `Funcionario`).

### 4.14 Sincronização com a lista oficial de empresas (2026-09-24)

Continuação direta da 4.13: a Clara mandou um PDF ("INFOS ASSESSORIAS") com nome + CNPJ de cada
empresa-cliente oficial, pedindo pra "limpar o que tem e adicionar os novos". 48 empresas ao todo —
8 a mais do que a lista de 40 que ela tinha digitado de memória no pedido anterior (ANDRADE, JUROS
JUSTOS, PERES, ROYAL, REGULARIZE, REVISALPHA, TEG, WN FAST); ela confirmou incluir todas as 48.

- **`LISTA_OFICIAL_EMPRESAS`** (`app/services/empresas.py`) — lista fixa de 48 tuplas
  `(nome_curto, cnpj)`, extraída do PDF. **Nome curto, não razão social**: o PDF chama de "ABSOLUTA
  SOLUÇÕES FINANCEIRAS", mas o campo `nome` guarda só "ABSOLUTA" — é isso que toda a base (imports
  de Laudos/Audiências/Pendências/Processos, todo o histórico já gravado) já usa pra reconhecer a
  empresa; usar a razão social completa quebraria o reconhecimento em todo import futuro. Uma
  exceção notável: o PDF escreve "WN FAST SOLUCOES LTDA." mas a planilha real de processos já usa
  "WNFAST" (sem espaço) nos registros existentes (confirmado pela Clara) — usado "WNFAST" na lista
  pra não perder o vínculo com processos já importados. "OPÇÃO1" não tem CNPJ no PDF (célula em
  branco) — cadastrada com `cnpj=None`, editável depois.
- **`sincronizar_lista_oficial(db, lista)`** (`app/services/empresas.py`) — pra cada nome da lista:
  cria se não existe, atualiza o CNPJ se existe e mudou (nunca apaga um CNPJ já cadastrado só
  porque a lista trouxe `None` pra aquela entrada). Pra cada empresa cadastrada que NÃO está na
  lista: tenta excluir de verdade via `excluir_empresa` já existente — que **recusa a exclusão** se
  houver laudo/audiência/cobrança/processo vinculado (proteção que já existia antes desta mudança,
  não construída pra isso). Devolve um resumo (criadas/atualizadas/excluídas/não-excluídas-por-
  vínculo) — a Clara vê exatamente quais empresas ficaram de fora da exclusão e por quê, sem eu
  forçar o apagamento de histórico de nenhum outro módulo por baixo dos panos.
- **Rota web `POST /app/empresas/sincronizar-lista-oficial`** e **API `POST /empresas/
  sincronizar-lista-oficial`** — restritas a Admin Superior/T.I., mesmo padrão de confirmação por
  texto digitado ("SINCRONIZAR") das outras zonas de perigo. A rota web precisou ficar **antes** de
  `POST /{empresa_id}` no arquivo de rotas — senão o Starlette casava
  `/app/empresas/sincronizar-lista-oficial` com `empresa_id="sincronizar-lista-oficial"` primeiro e
  devolvia 422 (bug pego pelo próprio teste automatizado, corrigido antes do commit).
- **Testado:** 8 testes novos (`tests/test_empresas_service.py` — cria/atualiza/exclui, não exclui
  com vínculo, não apaga CNPJ existente quando a lista não traz um novo, case-insensitive por nome,
  sanidade da lista oficial em si: 48 sem duplicata e "WNFAST" sem espaço; `tests/test_web.py` —
  rota exige admin, bloqueada pra não-admin) — 122 no total. Validado também rodando de ponta a
  ponta com Playwright contra um banco local com três cenários (empresa antiga sem vínculo — foi
  excluída; empresa antiga com laudo vinculado — não foi excluída, apareceu na mensagem; ABSOLUTA
  já cadastrada com CNPJ errado — CNPJ corrigido): resultado bateu exatamente (47 criadas, 1 CNPJ
  atualizado, 1 excluída, 1 não excluída por vínculo, 49 empresas ao final).
- **Reversível:** não — as exclusões são definitivas (mesma natureza das outras zonas de perigo);
  criação/atualização de CNPJ são triviais de reverter, mas uma empresa excluída não volta sozinha.

### 4.15 Resumo por assessoria em texto simples, na aba Laudos (2026-09-25)

A Clara pediu uma lista-resumo em texto puro (sem PDF), agrupada por assessoria, gerada junto com
o relatório de Laudos — total de laudos e quantidade por tipo (com o valor individual do tipo) por
assessoria. "Assessoria" aqui é o mesmo conceito de `empresas_clientes` de sempre (a mesma tabela
da lista oficial da seção 4.14 — o PDF que a Clara mandou chamava isso de "assessorias").

- **Decisão de escopo (perguntei antes de implementar):** o relatório de Laudos sempre exigiu uma
  empresa específica (campo obrigatório) — mas o exemplo de saída da Clara mostrava várias
  assessorias na mesma lista. Confirmado com ela: a lista-resumo cobre **todas** as assessorias do
  período/status quando o campo "Empresa-cliente" fica em branco (agora opcional), e filtra pra uma
  só quando ele é preenchido — mesmo filtro que já vale pro relatório detalhado de uma empresa.
- **`gerar_resumo_por_assessoria(db, periodo_ini, periodo_fim, status_opcao, filtro_empresa=None)`**
  (`app/services/laudos.py`) — reaproveita literalmente a mesma lógica de filtro de status
  (`_status_bate`/`_resolver_status`, extraídas de dentro de `gerar_relatorio` pros dois
  reaproveitarem) e a mesma resolução de valor por tipo (`_valor_tipo`, direto de `tipos_laudo`,
  igual ao relatório já fazia) — os números batem entre os dois porque é a mesma regra, não uma
  reimplementação paralela, como a Clara pediu explicitamente.
- **Sobre variação de valor dentro do mesmo tipo** (a Clara pediu pra avisar em vez de tirar média):
  não existe, por construção — o valor de um tipo de laudo não é gravado por laudo individual, é
  sempre resolvido na hora a partir de `TipoLaudo.valor_padrao` (mesma tabela de preços atual),
  então todo laudo do mesmo tipo tem sempre o mesmo valor, em qualquer assessoria.
- **Sobre laudo sem assessoria/tipo/valor** (a Clara pediu pra avisar em vez de descartar em
  silêncio): `importar_planilha` já descarta linhas sem empresa ou sem tipo antes de gravar (ver
  seção 4.6) — não existe `Laudo` no banco sem esses dois campos. O único caso real de dado
  faltando é um tipo sem valor cadastrado em `tipos_laudo`; nesse caso `valor_unitario=None` e o
  texto mostra `(sem valor cadastrado)` no lugar do R$, em vez de contar como R$ 0,00 — mesmo
  espírito do aviso `tipos_sem_valor` que o relatório detalhado já tinha.
- **Formato:** `formatar_texto_resumo_assessorias` — texto puro, sem HTML/tabela, um bloco por
  assessoria (`ASSESSORIA: NOME` / `Total de laudos: N` / uma linha por tipo), ordem alfabética
  (`normalize`) tanto de assessoria quanto de tipo dentro dela, e só entra quem tem pelo menos 1
  laudo contado (sem linha de zero).
- **Tela:** campo "Empresa-cliente" do formulário de Laudos deixou de ser obrigatório; novo card
  "Resumo por assessoria (texto)" com um `<textarea readonly>` (selecionável/copiável, sem
  download nem PDF, como pedido) exibido sempre que período+status forem submetidos — junto com o
  relatório detalhado de uma empresa quando ela for selecionada.
- **Testado:** 10 testes novos (`tests/test_laudos_service.py` — agrupamento/ordenação, exclui
  quem não tem laudo no período, filtro por empresa, empresa inexistente gera erro, tipo sem valor,
  mesmo filtro de status do relatório, formato exato de saída batendo com o modelo da Clara;
  `tests/test_web.py` — tela sem empresa mostra todas as assessorias, tela com empresa filtra só
  uma e mantém o relatório detalhado) — 132 no total. Validado também com Playwright contra um
  banco local: a saída bateu exatamente com o exemplo apresentado no plano antes de implementar.
- **Reversível:** sim — funções novas e isoladas; nada muda no relatório detalhado existente
  (`gerar_relatorio`/`formatar_texto` continuam exatamente iguais, só reaproveitados por baixo).

### 4.16 Gestão de Processos: relatórios Geral/Por empresa e remoção de "Agrupar por" (2026-09-25)

A Clara pediu um pacote de mudanças em 4 blocos, descritos por ela como sendo da aba "Laudos" —
investigação mostrou que os Blocos 1-3 (número de processo, evento, fatal, observação, "Agrupar
por") descrevem campos que só existem em **Gestão de Processos** (`Processo`/`EventoProcesso`),
não em Laudos; ela confirmou. Bloco 4 (visual do resumo de Laudos) é tratado à parte (seção 4.17).
Bloco 2 (nomes de Dra junto do nome da empresa) fica pendente até ela mandar a planilha real de
Laudos onde o padrão acontece — não encontrado nos dados de Processos já em mãos.

- **Decisões de interpretação (perguntei/expliquei antes de implementar):**
  - **"Evento"/"Fatal"/"Observação" = do andamento mais recente do processo**, uma linha por
    processo (não por andamento) nos três relatórios — por isso o total no topo bate com o número
    de linhas listadas.
  - **"Mais recente" usa `EventoProcesso.criado_em`** (data/hora real de registro no sistema —
    pedido explícito da Clara), não `data` (a data do andamento em si, sem hora) nem a ordem de
    inserção. Considera toda a história do processo, não só o período filtrado (mesmo raciocínio
    de "processo parado", que esta mudança substitui — ver abaixo) — e exclui eventos
    `data_e_liberacao` (mesmo motivo da seção 4.12: não são andamentos de verdade).
  - **Fonte do "Fatal":** `EventoProcesso.prazo_fatal` (já existia, mesma marcação "SIM"/"NÃO" da
    planilha) do andamento mais recente exibido na linha.
  - **Ordenação:** empresas em ordem alfabética; dentro de cada uma, Parte 1/"Por empresa" por
    Assistente e depois Nº do processo; Parte 2 (Geral) por Cliente (não tem assistente).
  - **"Agrupar por" e o pivô antigo (Cumpridos/Perdidos/Pendentes/Parados/"processo parado") foram
    removidos por completo** — substituídos pelos dois tipos novos. Não havia mais nenhum outro uso
    desse conceito no sistema (confirmado por busca antes de remover).
- **`app/services/processos.py`** — `gerar_relatorio`/`RelatorioProcessos`/`LinhaRelatorioPessoa`/
  `_agrupar_por`/`formatar_texto`/`PROCESSO_PARADO_DIAS` removidos; novos `gerar_relatorio_geral`
  e `gerar_relatorio_por_empresa`, com helpers compartilhados `_processos_em_escopo` (mesmo filtro
  de período/`data_e_liberacao` que já existia, sem carregar processos fora do período) e
  `_ultimo_evento_por_processo` (agregado `MAX(criado_em)` + self-join, sem N+1).
- **PDF** (`app/pdf_export.py`) — `gerar_pdf_processos` (formato antigo) trocado por
  `gerar_pdf_processos_geral`/`gerar_pdf_processos_por_empresa`, uma seção por empresa com
  quebra de página automática.
- **Filtros** (`processos.html`/`routes_processos.py`/`api/processos.py`) — novo seletor "Tipo de
  relatório" (Geral/Por empresa); campo "Empresa" (rótulo sem "cliente") fica oculto/desabilitado
  no tipo Geral (`iniciarAlternanciaTipoRelatorio`, `app/static/app.js`, substitui a função de
  alternância que existia pro "Agrupar por"); "Assistente" (não mais "Funcionário") sempre um
  dropdown, sem alternância pra texto livre — não fazia mais sentido sem Advogada/Assessoria como
  opção de agrupamento.
- **Renomeação visual "Funcionário" → "Assistente"** estendida também à tela de cadastro
  `/app/funcionarios` (título, cabeçalhos, mensagens) e ao rótulo do menu lateral ("Assistentes")
  — mesma lista/tabela/rota por baixo (`Funcionario`, `/app/funcionarios`), só o texto visível
  mudou, pra não ficar inconsistente com o dropdown "Assistente" que essa tela alimenta.
- **Testado:** suíte de `test_processos_service.py` reescrita (36 testes, incluindo o critério de
  "mais recente" por `criado_em` mesmo com `data` menor, total batendo com linhas, ordenação,
  filtro por assistente, empresa sem processo não aparece, regressão de performance) + testes web
  novos (Geral mostra seção por empresa com Fatal Sim/Não, Por empresa filtra uma só, filtro sem
  resultado mostra mensagem amigável) — 139 no total. Validado com Playwright: "Agrupar por"
  sumiu, rótulos corretos em toda a tela (inclusive `/app/funcionarios`), "último evento"/
  "observação" batendo com o andamento certo (não o mais antigo) num processo com dois eventos.
- **Reversível:** sim — mudança de código isolada ao módulo de Processos; o schema do banco não
  mudou (usa campos que já existiam).

### 4.17 Resumo de Laudos: sempre geral, visual em cards (Bloco 4, 2026-09-25)

Continuação do pedido de 4 blocos (seção 4.16) — Bloco 4, da aba Laudos de verdade dessa vez.

- **Sempre geral, ignorando o filtro de Empresa:** antes (seção 4.15), selecionar uma empresa no
  relatório detalhado também filtrava a lista-resumo pra essa mesma empresa. A Clara pediu
  explicitamente o contrário: o resumo é **sempre** um único consolidado com todas as empresas,
  não importa o que estiver selecionado no filtro de Empresa do relatório detalhado —
  `routes_laudos.py::tela` parou de passar `filtro_empresa` pra
  `gerar_resumo_por_assessoria` (a função em si manteve o parâmetro, só não é mais usado por essa
  rota). Continua respeitando período/status, que são os únicos filtros que fazem sentido pra ele.
- **Posição:** movido pra baixo do relatório detalhado (antes ficava logo depois do formulário,
  acima de tudo) — agora fica entre o relatório e a "Zona de perigo".
- **Visual novo** (`laudos.html`) — trocado o `<textarea readonly>` monoespaçado por um card
  "Resumo de Laudos" + um `.card` por assessoria (mesmo componente usado em todo o resto do
  sistema, e no relatório "Geral" novo de Processos — seção 4.16), com uma tabela Tipo/Quantidade/
  Valor individual, números e valores alinhados à direita, `R$ 1.234,56` no padrão brasileiro
  (já era assim antes). Responsivo/legível em tela pequena pelo mesmo CSS que já cobre `.card` e
  `table` no resto do sistema — nada dedicado precisou ser escrito.
- **Cópia mantida, sem campo de texto visível:** um botão "Copiar resumo" (`data-copiar-resumo`,
  `app/static/app.js::iniciarCopiaDeResumo`) lê o mesmo texto simples de antes
  (`formatar_texto_resumo_assessorias`, sem mudança de formato) de um
  `<script type="application/json">` escondido — escapado com segurança pelo filtro `tojson` do
  Jinja2 (não é HTML cru) — e copia pra área de transferência via `navigator.clipboard.writeText`,
  com um toast de confirmação (reaproveita `mostrarToast`, já existente).
- **Testado:** 2 testes web reescritos/novos (cards visíveis por assessoria, sem mais
  `<textarea>`, resumo continua mostrando todas as empresas mesmo com o relatório filtrado por
  uma) — 139 no total. Validado com Playwright: ordem das seções na página, botão de copiar
  realmente copiando o texto certo pra área de transferência (com toast de sucesso), captura de
  tela do visual novo.
- **Reversível:** sim — mudança de template/rota isolada; a função que gera os dados
  (`gerar_resumo_por_assessoria`) não mudou de assinatura nem de regra.

### 4.18 Cartas — Carta Convite Cliente e Carta Convite Banco (2026-09-25)

Nova aba "Cartas" (só EXIMIA), gerando cartas-convite em PDF prontas pra envio. Regra explícita
da Clara para toda essa feature: qualquer dúvida de texto/layout/comportamento é perguntada antes
de decidir (nunca assumida) — ver DECISIONS.md para o histórico completo de perguntas/respostas.
Implementado em duas rodadas, uma carta de cada vez, com aprovação visual da Cliente antes de
começar a Banco (pedido explícito da Clara), e a Carta Banco colocada abaixo da Cliente na mesma
tela, na mesma ordem em que foram pedidas.

- **Sem persistência:** cada carta é gerada e baixada na hora — nada fica salvo no banco (decisão
  explícita da Clara). `app/services/cartas.py` só valida/formata os dados recebidos do
  formulário e devolve um dataclass (`ConviteCliente`/`ConviteBanco`) pro `pdf_export.py` desenhar.
- **Detecção de plataforma pelo link** (`detectar_plataforma`), usada pelas duas cartas — o texto
  fixo original dizia "GOOGLE MEET"/"GOGGLE MEET" (com erro de digitação, na Banco) fixo; agora é
  dinâmico: reconhece `meet.google.com/...` → "Google Meet" e `teams.microsoft.com/...` → "Teams",
  com ou sem prefixo `https://` (Clara, 2026-09-25). Link que não bate com nenhum dos dois
  **bloqueia a geração** com uma mensagem de erro clara — não existe carta sem plataforma
  reconhecida pra preencher "pela plataforma ___"/"através do aplicativo ___".
- **Validação de CPF** (`cpf_valido`, dígitos verificadores) só na Carta Banco (único campo de
  CPF) — **CPF inválido bloqueia a geração**, com uma mensagem de erro explicando o motivo (não é
  só aviso, Clara 2026-09-25). CPF válido é normalizado pro formato `000.000.000-00`
  (`formatar_cpf`) no PDF, não importa como foi digitado no formulário.
- **PDF** (`app/pdf_export.py`) — primeira geração de PDF do sistema que não é tabela: usa
  `reportlab.platypus` (`Paragraph`/`Frame`, dentro do mesmo reportlab já usado em todo o resto,
  nenhuma lib nova) pra desenhar texto corrido com negrito/itálico/cor por trecho e quebra de
  linha automática, dentro do mesmo timbrado (`FUNDO_AUDIENCIAS`, a mesma marca EXIMIA — não
  existe fundo próprio pra Cartas e nenhum foi pedido). Link da audiência sai como hyperlink
  clicável de verdade no PDF (`<a href=...>`, sublinhado e azul) nas duas cartas, mesmo se
  digitado sem "https://". As duas cabem numa página só.
  - `gerar_pdf_carta_cliente` — texto fixo idêntico ao modelo `CARTA_CONVITE_CLIENTE.pdf`
    (Pré-Processual / Métodos Consensuais / avisos em negrito-itálico / fechamento), com três
    mudanças aprovadas pela Clara: data com ano (antes só "dia/mês"), plataforma dinâmica (acima)
    e uma linha nova de telefone ("Telefone: 55 11 93234-6989") logo abaixo do e-mail de contato
    — só nesta carta, não na do Banco.
  - `gerar_pdf_carta_banco` — texto fixo idêntico ao modelo `NOVA_CARTA_CONVITE_-_BANCO.pdf`
    (trechos em negrito mantidos fixos como identificados: nome, CPF, nº do contrato, "AUDIÊNCIA
    EXTRAJUDICIAL ADMINISTRATIVA", "juros, encargos, capitalização, tarifas etc", a frase de
    data/hora inteira, a frase de anúncio da plataforma inteira), com data também passando a
    incluir o ano (mesma decisão da Cliente, confirmada separadamente pra essa carta) e dois
    erros do próprio modelo oficial corrigidos, ambos aprovados pela Clara: "GOGGLE MEET" (faltava
    um "O") vira a plataforma certa e dinâmica; a pontuação "CNPJ : -" do destinatário vira
    "CNPJ: ..." limpo. Nome do banco e CNPJ do banco são 2 campos novos (não estavam nos 6
    campos originais do pedido) — aprovados pela Clara — e saem em caixa alta e negrito no PDF,
    igual ao Nome do titular.
- **Acesso:** `require_operadora_web("EXIMIA")`/`require_operadora("EXIMIA")`, mesmo padrão de
  Audiências — item de menu só aparece pra quem tem acesso à EXIMIA.
- **Rotas:** `GET /app/cartas` (tela, com os dois formulários), `POST /app/cartas/convite-cliente`
  e `POST /app/cartas/convite-banco` (cada um gera e devolve o PDF direto, ou re-renderiza a tela
  com erro se a validação falhar) + espelhos em `GET /cartas/convite-cliente.pdf` e
  `GET /cartas/convite-banco.pdf` (`app/api/cartas.py`), mesmo par api/web dos outros módulos.
- **Testado:** suíte completa (139 testes) sem regressão + lint limpo, nas duas rodadas. Validado
  end-to-end fora da suíte automatizada (Playwright real, com login): tela renderiza igual ao
  resto do sistema, item "Cartas" aparece no menu na posição certa, os dois cards aparecem na
  ordem certa (Cliente acima, Banco abaixo), submissão de cada formulário devolve
  `Content-Disposition: attachment` com o PDF certo, link inválido e CPF inválido bloqueiam com a
  mensagem de erro certa na tela. PDFs de exemplo com dados fictícios conferidos manualmente:
  texto fixo idêntico aos modelos (com as mudanças aprovadas), acentuação correta, link clicável,
  detecção de plataforma testada com Meet e com Teams, cabem em uma página.
- **Reversível:** sim — módulo novo e isolado (`services/cartas.py`, `api/cartas.py`,
  `web/routes_cartas.py`, `templates/cartas.html`, funções novas em `pdf_export.py`); não mudou
  nenhum módulo existente além do registro das rotas em `main.py` e do item de menu.
- **Ajuste de fechamento (2026-09-25, depois da aprovação visual):** espaçamento maior no bloco
  final (contato/despedida/assinatura) das duas cartas, com um espaço extra entre
  "Atenciosamente," e a assinatura — estilos dedicados só pra essa parte, sem afetar o resto do
  texto. Texto de contato da Carta Cliente reestruturado em 3 linhas ("...por meio dos contatos:
  / E-mail: ... / Telefone: ..."); a Carta Banco manteve o texto igual, só com o espaçamento
  maior — ver DECISIONS.md pra decisão completa (inclusive a dúvida levantada sobre se o
  telefone também entraria na Banco, e por que não).

### 4.19 Configuração/Processos — plano de 5 blocos apresentado; Bloco 1 (editar usuário) implementado com urgência (2026-09-28)

Pedido novo da Clara, com a mesma regra de "pergunte antes de decidir" e um plano único exigido
antes de qualquer implementação, cobrindo: Bloco 1 (editar usuário), Bloco 2 (separar
Usuário/Empresa/Cliente como área administrativa), Bloco 3 (`papel_global` vira só 4 valores:
Administrador Geral/T.I./Gerente/Líder), Bloco 4 (tirar Assistente do relatório de Processos) e
Bloco 5 (coluna de Observação sem corte/rolagem horizontal). Explorei o projeto inteiro
(modelo de permissões, telas de Usuário/Empresa/Assistente, relatório de Processos) e apresentei
o plano com todas as perguntas pendentes dos 5 blocos — **nenhum dos outros 4 blocos foi
implementado ainda**, aguardando as respostas da Clara.

**Achado que muda o risco do Bloco 2:** as 3 áreas administrativas (Usuários, Empresas-clientes,
Assistentes) **já são bloqueadas para quem não é admin, nas duas camadas** hoje —
`admin_logado_web`/`require_admin` em toda rota de listar/criar/editar/excluir (web e API), e
`menu.py` já esconde os 3 itens do menu de quem não tem `papel_global` em `PAPEIS_GLOBAIS`. O que
falta pro Bloco 2 é só a reorganização visual (uma área "Administração" separada, mais destacada),
não uma correção de brecha de segurança.

**Bloco 1 — editar usuário, implementado sob pedido de urgência da Clara** (antes das respostas
do plano completo — usando as opções que eu mesma já tinha proposto no plano, sem contestação):

- **`app/auth.py::restaria_sem_admin`** — helper compartilhado (web + API) que impede uma edição
  de deixar o sistema sem nenhum usuário com `papel_global` em `PAPEIS_GLOBAIS`. Bloqueia com
  mensagem clara ("Não é possível remover o papel administrativo do último administrador do
  sistema") em vez de aplicar a mudança.
- **Campos editáveis:** nome, e-mail, papel global, senha (opcional — vazio mantém a atual) e os
  vínculos de setor/papel-no-setor (substituição completa do conjunto, mesmo padrão do cadastro).
  Status ativo/inativo **não** entrou no formulário de edição — continua só no botão dedicado
  Ativar/Desativar que já existia, pra não duplicar o mesmo controle de duas formas.
- **Formato:** reaproveita o layout do formulário "Novo usuário" (mesmos campos/tabela de
  setores), mas dentro de um `<details>` nativo por linha da tabela ("▸ Editar" expande, "▾
  Editar" fecha) — sem JavaScript novo, mesmo padrão visual do resto do sistema. Pré-preenchido
  com os dados atuais do usuário (`vinculos_por_usuario`, um dict pré-computado na rota pra achar
  o papel de cada setor sem lógica pesada no template).
- **Rotas:** `POST /app/usuarios/{id}` (web, re-renderiza a tela com erro ou com o toast de
  sucesso) e `PATCH /usuarios/{id}` (API, mesma validação, `setores: None` significa "não mexe
  nos vínculos atuais" — diferente do form web, que sempre reenvia o conjunto completo).
- **Testado:** 6 testes novos (edição bem-sucedida com troca de e-mail/senha/setor, edição sem
  senha mantém a atual, bloqueio do último admin — web e API — e edição permitida quando existe
  outro admin) — 145 no total, sem regressão. Validado com Playwright real (login, expandir
  "Editar", trocar nome e papel global, salvar, confirmar toast + dados atualizados na tabela).
- **Reversível:** sim — rotas/template novos, isolados; nenhuma coluna de banco mudou.

**Pendente:** Blocos 3-5 continuam aguardando as respostas da Clara ao plano (ver mensagem
correspondente no histórico da conversa — contagem de usuários por papel para o Bloco 3 ainda
precisa vir dela, já que este ambiente não tem acesso ao banco de produção).

**Bloco 2 — área administrativa separada, adiantado junto com pedidos extras (2026-09-28):**
a Clara pediu, no mesmo fôlego, 3 coisas: (1) permitir alterar/adicionar setores e o papel de um
usuário dentro de cada setor; (2) deixar a edição de usuário mais bonita; (3) separar
Usuário/Empresa/Assistentes numa aba "Configuração" — essa última resolve a dúvida em aberto do
Bloco 2 sobre o que era "Cliente" (era a mesma coisa que ela já tinha chamado de "Assistentes"
nessa mensagem, não uma área nova).

- **Setores — CRUD novo** (antes só existiam pré-cadastrados via `DEFAULT_SETORES`, sem tela
  nenhuma): `app/web/routes_setores.py` (`GET/POST /app/setores`, `POST /app/setores/{id}`,
  `POST /app/setores/{id}/ativo`) + `app/templates/setores.html`, mesmo padrão de edição inline
  em tabela que "Empresas-clientes"/"Assistentes" já usam. Sem exclusão — só ativar/desativar,
  igual ao resto do sistema (um setor com usuários vinculados não pode sumir sem quebrar
  histórico). Espelho em `app/api/usuarios.py` (`POST /setores`, `PATCH /setores/{id}`,
  `PATCH /setores/{id}/ativo`) pra manter o par api/web dos outros módulos. O vínculo
  usuário-setor-papel (LIDER/COLABORADOR) em si não mudou — já existia desde o Bloco 1 e
  continua na tela de Usuários; o que faltava era só criar/editar o Setor em si.
- **Edição de usuário — visual (`usuarios.html`/`style.css`):** painel de edição redesenhado —
  ícone de lápis no "Editar", fundo levemente destacado com borda de acento à esquerda (mesma cor
  do `--navy`), duas seções com título ("Dados do usuário" / "Setores e papéis"), e a linha do
  setor marcado (`tr:has(input:checked)`) ganha um leve destaque azul — tudo em CSS puro, sem
  JavaScript novo. Um link "Cadastre em Configuração → Setores" nos dois formulários (editar e
  criar usuário) avisa que dá pra criar um setor novo sem sair da tela de Usuários.
- **Área "Configuração"** (`app/web/routes_configuracao.py` + `templates/configuracao.html`):
  uma tela de entrada só com cards (reaproveitando o mesmo componente `.grid-modulos`/`.modulo`
  da tela inicial) pras 4 áreas administrativas — Usuários, Empresas-clientes, Assistentes,
  Setores. As 4 telas **continuam com suas rotas e lógica exatamente como estavam** (nada foi
  reescrito) — só o menu lateral mudou: em vez de 3 itens separados (Usuários/Empresas-
  clientes/Assistentes), agora é um item só, "Configuração", que fica destacado (classe `ativo`)
  em qualquer uma das 4 telas por baixo dela (`item.tambem_ativo_em` em `menu.py`, checado no
  `base.html` via `namespace()` do Jinja). Cada uma das 4 telas ganhou um link "Voltar à
  Configuração" no lugar do "Voltar ao início" genérico (`{% block voltar %}` novo em
  `base.html`, sobrescrito nelas).
- **Testado:** 7 testes novos (Configuração lista as 4 áreas e é bloqueada pra não-admin; menu
  destaca "Configuração" nas 4 telas; criar/editar/desativar setor pela tela; setores bloqueado
  pra não-admin; API de setor com o mesmo padrão) + 2 API — 152 no total, sem regressão. Validado
  com Playwright real: dashboard mostra só o card "Configuração", tela de Configuração com os 4
  cards, painel de edição de usuário com o visual novo (captura de tela conferida), setor criado
  pela tela aparece imediatamente no checklist de setores do formulário de usuário.
- **Reversível:** sim — rotas/templates novos e isolados; `menu.py`/`base.html` mudaram só a
  navegação (nenhuma rota antiga foi removida, só deixou de estar solta no menu principal);
  nenhuma coluna de banco mudou.

**Confirmação da Clara sobre "Cliente":** não existe (nem deve existir) uma área "Cliente"
separada — era "Assistentes" mesmo, resolvendo a dúvida em aberto. Ela também deu sinal verde
("pode prosseguir com as alterações") pra continuar o plano.

### Bloco 4 — Assistente fora do relatório de Processos (2026-09-28)

Removida a coluna/menção ao assistente do relatório de Gestão de Processos em TODAS as saídas
(tela, PDF e o texto simples que a API JSON devolve), mantendo o filtro por assistente
funcionando normalmente — o campo continua nos dataclasses internos (`LinhaProcessoGeral.
assistente`/`LinhaProcessoPorEmpresa.assistente`), usado pra filtrar e ordenar; só não é mais
desenhado em nenhuma saída.

- **`processos.html`:** removida a coluna "Assistente" das duas tabelas que a mostravam (tipo
  "Por empresa", 5→4 colunas; tabela principal do tipo "Geral", 4→3 colunas). A "Resumo por
  cliente" já não tinha essa coluna, não mudou.
- **`pdf_export.py`:** mesma remoção nas duas funções de PDF, com as colunas restantes
  redistribuindo o espaço liberado (a "Última observação" ganha mais largura, seguindo o mesmo
  espírito do Bloco 5).
- **`services/processos.py::formatar_texto_geral`/`formatar_texto_por_empresa`:** essa era a
  "versão exportada" que a Clara tinha perguntado se existia — é o campo `texto` que a API JSON
  devolve (sem botão na tela hoje). Também perdeu a coluna Assistente, pela mesma regra.
- **Testado:** 2 testes web atualizados (confirmam "DANILO" — nome de assistente de teste — não
  aparece mais no HTML) + 2 testes novos de serviço (`formatar_texto_geral`/`_por_empresa` sem
  "ASSISTENTE"/o nome) — 154 no total, sem regressão.
- **Reversível:** sim — mudança de apresentação isolada; nenhuma lógica de filtro/ordenação
  mudou.

### Bloco 5 — Coluna de Observação sem corte nem rolagem horizontal da página (2026-09-28)

Aplicado a **todas** as tabelas de Gestão de Processos (Prazos próximos, tipo "Por empresa", tipo
"Geral" — tabela principal e "Resumo por cliente"), por consistência, não só às que têm
Observação — decisão minha, já proposta no plano original sem objeção da Clara.

- **`app/static/style.css`:** `overflow-wrap: anywhere` adicionado a `tbody td` **globalmente**
  (afeta todas as tabelas do sistema, não só Processos) — palavra ou link sem espaço quebra
  dentro da célula em vez de estourar a largura. `.tabela-wrap` (já existia, usado por Laudos)
  agora envolve todas as tabelas de Processos — contém a rolagem horizontal **dentro da tabela**,
  nunca deixa a página inteira rolar de lado.
- **Largura das colunas:** "Última observação" ganhou `width: 40%` (a maior fatia) nas duas
  tabelas que têm essa coluna, com `min-width` em todas as colunas pra evitar espremer demais em
  telas muito estreitas — nesse caso, a tabela vira mais larga que a tela e passa a rolar
  **dentro do `.tabela-wrap`** (confirmado: a página em si nunca ganha rolagem horizontal, testado
  em 1440px/768px/390px).
- **Decisão de mostrar inteiro (não resumir com "ver mais"):** seguida a recomendação que eu
  tinha proposto no plano — mostra o texto completo, quebrando linha, sem JS de expandir/
  recolher.
- **Testado:** Playwright em 3 larguras (1440/768/390px) confirmando `scrollWidth ==
  clientWidth` do `<html>` (nunca há rolagem horizontal da página) mesmo com uma observação de
  teste propositalmente longa e sem espaços (incluindo um link comprido); em 390px, confirmado
  que a tabela passa a rolar dentro do próprio `.tabela-wrap` (não da página) e que a coluna
  Observação continua alcançável rolando lateralmente dentro dela.
- **Reversível:** sim — mudança de CSS/template; nenhuma lógica de dados mudou.

### 4.20 Modo escuro (2026-09-28)

Pedido direto da Clara, sem ambiguidade estrutural (só apresentação, nada de banco) —
implementado direto.

- **Variáveis CSS** (`style.css`) — o sistema já era todo construído em cima de variáveis
  (`--bg`, `--card`, `--border`, `--text`, `--accent`, `--danger`, `--ok`, etc. em `:root`), o que
  tornou o modo escuro uma questão de redefinir essas variáveis, não reescrever regras. Precisei
  separar duas famílias de cor que estavam misturadas atrás de `--navy`: a marca em si
  (`--navy`/`--navy-deep`/`--navy-light` — sidebar, hero, botão primário) fica **fixa** nas duas
  aparências; texto de destaque em cima de uma superfície clara (títulos, cabeçalho de tabela,
  "Editar") passou a usar uma variável nova, `--heading`, que aí sim muda de cor no escuro (senão
  ficaria texto quase preto em fundo escuro). Outras variáveis novas: `--heading`, `--surface-alt`
  (fundo levemente destacado — cabeçalho de tabela, linha "total"), `--row-hover`,
  `--highlight-soft` (linha de setor marcado em Usuários), `--muted-soft` (badge "Inativo"),
  `--danger-border`/`--ok-border` (bordas dos avisos/toasts), `--overlay` (fundo do backdrop do
  modal). Sombras (`--shadow-sm/md/lg`) também ganharam uma variante mais escura/opaca — sombra
  clara não aparece em cima de fundo escuro.
- **Como o tema é decidido** — três camadas, da mais específica pra mais geral:
  1. Escolha manual salva (`localStorage`, atributo `data-theme="dark"|"light"` na tag
     `<html>`) — sempre vence, se existir.
  2. Sem escolha manual: `@media (prefers-color-scheme: dark)` — segue o sistema operacional
     automaticamente, sem precisar de JS pra decidir a cor (só CSS).
  3. Nenhum dos dois: tema claro (o de sempre).
  `color-scheme: light`/`dark` também é setado, pra controles nativos do navegador (date/time
  picker, checkbox) já nascerem no tom certo.
- **Sem "flash" de tema errado ao carregar a página** — um script pequeno e síncrono logo no
  `<head>` (`templates/_tema_inline.html`, novo) lê o `localStorage` e aplica o `data-theme` antes
  do CSS ser avaliado, então a página nunca pisca no tema errado por uma fração de segundo.
  Incluído nos 3 templates HTML completos do sistema (`base.html`, `login.html`, `erro.html`) —
  login e a página de erro não usam o layout principal, então precisavam do include à parte.
- **Botão** — no menu lateral, acima de "Sair" (`base.html`), alterna entre os ícones de sol/lua
  novos (`_icones.html`) e o rótulo "Modo escuro"/"Modo claro" conforme o tema atual.
  `app.js::iniciarAlternanciaTema` decide o tema efetivo (olhando `data-theme` já aplicado, ou o
  `prefers-color-scheme` se não houver escolha manual), atualiza o botão no carregamento, e ao
  clicar troca o atributo + grava no `localStorage` (com try/catch — não quebra em navegação
  privada, só não persiste entre visitas nesse caso).
- **Testado:** suíte completa sem regressão (155 testes, 1 novo) + lint limpo + Playwright:
  alternância manual, persistência ao navegar entre páginas e depois de sair/entrar de novo,
  Usuários (com o painel de edição do Bloco 1), Empresas-clientes (com modal de confirmação e
  toast), dashboard e login — em desktop e num viewport de celular (390px). Conferido visualmente
  por captura de tela em cada uma.
- **Reversível:** sim — só CSS/HTML/JS; nenhuma rota, coluna de banco ou lógica de backend mudou.

### 4.21 "Excluir todas as empresas inativas" (2026-09-28)

A Clara pediu pra apagar direto no banco de produção as empresas que já tinha desativado —
recusei (sem acesso direto ao banco daqui, e mesmo com acesso um `DELETE` bruto pularia a
proteção contra apagar histórico vinculado que a tela já tem) e ofereci um botão que faz a mesma
coisa com segurança. Ela topou.

- **`services/empresas.py::excluir_empresas_inativas`** — nova função, `ResumoExclusaoInativas`
  (`excluidas`/`nao_excluidas_por_vinculo`). Busca toda `EmpresaCliente` com `ativo=False` e chama
  `excluir_empresa` (já existente, com a proteção contra laudo/audiência/cobrança/processo
  vinculado) pra cada uma — mesmo padrão de `sincronizar_lista_oficial`, só que o critério de
  seleção é "está inativa" em vez de "não está na lista oficial".
- **Rotas:** `POST /app/empresas/excluir-inativas` (web) e `POST /empresas/excluir-inativas`
  (API), ambas admin-only, registrando `EXCLUIU_EMPRESAS_INATIVAS` na auditoria. A rota web
  precisa ficar ANTES de `POST /{empresa_id}` no arquivo (mesma regra de ordenação de rotas do
  Starlette já documentada pra `sincronizar-lista-oficial`).
- **Tela (`empresas.html`):** novo botão na "Zona de perigo", mesmo padrão visual/de confirmação
  do "Sincronizar com a lista oficial" (modal com contagem de quantas empresas inativas existem
  hoje, botão travado até digitar "EXCLUIR"). Fica desabilitado quando não há nenhuma inativa.
- **Testado:** suíte completa sem regressão (160 testes, 5 novos) + lint limpo + Playwright
  end-to-end (modal, confirmação por texto, exclusão real, proteção de vínculo, empresa ativa
  nunca tocada) — ver DECISIONS.md pra decisão completa.
- **Reversível:** sim — função/rotas novas e isoladas; reaproveita a exclusão individual já
  existente, não introduz um caminho de exclusão novo/menos seguro.

### 4.22 Seleção de abas por setor + exclusão de empresa com reatribuição (2026-09-28)

Dois pedidos na mesma mensagem: "quando eu adiciono um setor, ele me permita selecionar quais
abas do site aquele setor pode acessar" e "preciso que seja possível apagar empresas mesmo que
estejam vinculadas a outros processos". Ambos mexem em várias partes do sistema e tinham
ambiguidade estrutural real — fiz duas perguntas focadas antes de codar (ver DECISIONS.md pra
respostas completas da Clara): (1) se a Configuração (Usuários/Empresas/Assistentes/Setores)
entraria na seleção de abas ou continuaria só por `papel_global`, e se um setor podia ganhar
acesso a aba fora da sua própria operadora; (2) que caminho ela queria pra "apagar mesmo com
vínculo" (cascata vs. reatribuir) e se era só pra processos ou pros quatro tipos de vínculo.
Respostas: Configuração fica só por `papel_global`, sem mudança; seleção de abas de um setor fica
restrita às abas da própria operadora dele; reatribuição (não cascata), com pop-up um a um.

**Parte 1 — Módulos por setor**

- **`app/models.py::SetorModulo`** — tabela nova, chave composta `(setor_id, modulo)`. Ausência de
  qualquer linha pra um `setor_id` é o estado padrão/retrocompatível: "acesso a todas as abas
  válidas pra operadora do setor" — igual ao comportamento de antes dessa feature. Só passa a
  restringir quando o setor tem pelo menos uma linha, gravada explicitamente na tela de Setores.
  Nenhum setor existente perdeu acesso por essa mudança (não precisou de backfill/migração de
  dados).
- **`app/auth.py`** — `MODULOS_OPERADORA` (registro módulo → operadora dona, `None` = vale pras
  duas — hoje só `PENDENCIAS`, que já misturava cobranças EXIMIA/ELITE na mesma tela antes disso);
  `MODULOS_ROTULO` (rótulo de exibição); `modulos_validos_para_operadora()`; `modulos_acessiveis(db,
  usuario)` (admin vê tudo; outro usuário vê a união dos módulos liberados pelos setores a que
  pertence, aplicando a regra de retrocompatibilidade acima por setor); `require_modulo()` — tudo
  espelhando o padrão já existente de `operadoras_acessiveis`/`require_operadora`.
  `app/web/auth.py::require_modulo_web` é o par web, igual a `require_operadora_web`.
- **Rotas migradas de `require_operadora(_web)` pra `require_modulo(_web)`:** Laudos → LAUDOS,
  Gestão de Processos → PROCESSOS, Audiências → AUDIENCIAS, Cartas → CARTAS. Pendências (que não
  tinha gate de operadora nenhum — só exigia login, com o filtro por `operadoras_acessiveis`
  aplicado só no resultado) ganhou o gate `require_modulo(_web)("PENDENCIAS")` na tela/import/
  mensagens, mantendo intacto o filtro pós-consulta e o `apagar-tudo` (que já era admin-only).
  `app/web/menu.py::itens_menu` passou a montar a lista de abas a partir de `modulos_acessiveis`
  em vez de `operadoras_acessiveis` — Configuração continua controlada só por `papel_global`, sem
  mudança nenhuma nessa parte.
- **Tela de Setores (`app/web/routes_setores.py`, `templates/setores.html`)** — cada linha da
  tabela ganhou uma coluna "Abas liberadas" com um `<details>` compacto: um checkbox "Restringir
  abas" (desmarcado = sem restrição, estado padrão) que revela a lista de módulos quando marcado;
  os checkboxes de módulo só mostram os válidos pra operadora selecionada naquele momento (JS,
  `app.js::iniciarModulosPorOperadora`, reaproveitando o padrão `data-mostrar-se-*` já usado no
  filtro de tipo de relatório de Processos) — nunca deixa marcar uma aba fora da operadora do
  setor, tanto na tela (JS esconde/desmarca) quanto no backend (`_ler_modulos_do_form` filtra pra
  `modulos_validos_para_operadora` antes de salvar). O formulário "Novo setor" ganhou o mesmo
  bloco. Regra de validação: marcar "Restringir abas" sem escolher nenhum módulo é rejeitado
  (mensagem de erro) — evita criar sem querer um setor "restrito a nada", que seria indistinguível
  de "sem restrição" no banco (zero linhas em `SetorModulo` nos dois casos).
  **API** (`app/api/usuarios.py`): `NovoSetor`/`EdicaoSetor` ganharam `modulos: list[str] | None`
  (`None` = sem restrição; lista filtrada pra operadora, vazia após o filtro = rejeitado com 400).
- **Testado:** testes de unidade de `modulos_acessiveis` (admin vê tudo; setor sem configuração
  libera tudo da operadora; setor restrito fica só com o configurado; união de vários setores);
  403 web (setor restrito a LAUDOS não acessa Processos nem Pendências) e a menu.py refletindo a
  restrição; API (criar/editar setor com `modulos`, remover restrição com `modulos: null`, módulo
  de operadora errada rejeitado); tela web (criar setor com restrição pelo formulário, tirar a
  restrição depois). Verificado visualmente com Playwright: restringir um setor existente pela
  tabela, criar um setor novo já restrito, os checkboxes de módulo mudando conforme a operadora
  selecionada.

**Parte 2 — Exclusão de empresa com reatribuição de vínculo**

- **`app/services/empresas.py`** — `contar_vinculos_empresa()` extraída de dentro de
  `excluir_empresa` (reuso). `excluir_empresa(db, empresa_id, empresa_destino_id=None)` ganhou o
  parâmetro opcional: sem ele, comportamento idêntico a antes (bloqueia se houver vínculo,
  `sincronizar_lista_oficial`/`excluir_empresas_inativas` continuam chamando sem esse parâmetro e
  não mudam); com ele, e havendo vínculo, todo laudo/audiência/cobrança/processo apontando pra
  `empresa_id` é reatribuído (`UPDATE ... SET empresa_cliente_id = destino`) pra `empresa_destino_id`
  antes de excluir — nunca apaga o histórico em si, só muda pra qual empresa-cliente ele aponta.
  Validado: destino precisa existir e ser diferente da origem.
  **Decisão minha, não perguntada explicitamente:** a Clara pediu isso citando "processos", mas
  os quatro tipos de vínculo (laudo/audiência/cobrança/processo) têm exatamente a mesma FK
  NOT NULL pra empresa-cliente e o mesmo problema — generalizei pros quatro em vez de deixar
  laudo/audiência/cobrança ainda bloqueando a exclusão. Sinalizado a ela depois de entregue.
- **Rotas:** `POST /app/empresas/{id}/excluir` (web, `Form(empresa_destino_id)`) e
  `DELETE /empresas/{id}` (API, query param) passam o destino opcional adiante pra
  `excluir_empresa`.
- **Tela (`empresas.html`):** o modal de exclusão por linha (já existia) passou a calcular, por
  empresa, se ela tem vínculo (`vinculos_por_empresa`, novo no contexto) — se tiver, mostra um
  `<select>` "Mover histórico vinculado para" (as outras empresas, obrigatório) antes do botão de
  excluir; se não tiver, o modal fica como sempre foi (sem o select). Um único modal por linha
  cobre os dois casos.
- **Testado:** serviço (reatribuição dos quatro tipos confirmada linha a linha; bloqueio sem
  destino inalterado; destino precisa existir/ser diferente); web (exclusão com destino reatribui
  e apaga a origem). Verificado visualmente com Playwright: modal mostrando a contagem de vínculo
  e o select, exclusão completada, e o laudo de teste confirmado na empresa de destino depois.
- **Reversível:** sim — os dois são aditivos (parâmetro opcional, coluna de módulo nova) e
  preservam o comportamento anterior por padrão; nenhuma rota/comportamento existente muda pra
  quem não usa as opções novas.

### 4.23 Layout de Setores, exclusão de setor e pop-up de suporte (2026-09-28)

A Clara mandou um screenshot da tela de Setores (modo escuro) marcando o card "Novo setor" e
pedindo três coisas: (1) melhorar o layout daquela área, (2) uma opção de "selecionar todas as
abas" (ela viu só 3 checkboxes, com a operadora ELITE escolhida, e achou pouco), (3) poder apagar
setor (só existia ativar/desativar). Junto, pediu um pop-up de suporte novo — circular, no canto
da tela, que abre um pop-up maior com "Assunto do chamado" e "Descrição", e manda isso por e-mail
pra ela.

Duas perguntas antes de codar (ver DECISIONS.md pras respostas completas): (1) se "selecionar
todas as abas" era um atalho "marcar todas" (dentro da restrição por operadora que ela mesma
decidiu antes) ou se era pra abrir as 5 abas pra qualquer setor, inclusive fora da operadora dele;
(2) como enviar o e-mail de verdade, já que o sistema não tinha nenhuma configuração de SMTP/
serviço de e-mail. Respostas: atalho "marcar todas" (mantendo a restrição por operadora); SMTP
com usuário/senha de app (Gmail/Outlook).

**Layout do card "Novo setor" — bug de raiz, não só estética.** O problema real por trás do
layout ruim: o checkbox "Restringir abas" e o bloco de módulos estavam dentro de
`<form class="formulario">` (um flex-row) — a mesma classe de bug já visto antes no painel de
edição de usuário (ver seção 4.19): qualquer bloco full-width dentro de um flex-row vira item da
fileira e espreme tudo pro lado. Corrigido tirando os dois de dentro do `<form>` (que ganhou um
`id="novo-setor"`) e referenciando os campos pelo atributo `form="novo-setor"` — mesmo padrão já
usado nas linhas de tabela de Empresas/Setores. O mesmo tratamento foi aplicado ao painel
`<details>` de cada linha existente da tabela.

- **"Marcar todas" / "Limpar seleção"** — dois botões de texto acima da grade de módulos
  (`app.js::iniciarSelecionarTodosModulos`), tanto no formulário "Novo setor" quanto em cada linha
  da tabela. Só mexem nas caixas **visíveis no momento** (`offsetParent !== null`) — as que a
  filtragem por operadora já escondeu ficam de fora, então "Marcar todas" nunca marca uma aba fora
  da operadora do setor (preserva a decisão da Clara de manter a restrição).
- **Grade de módulos** — trocada de lista vertical (`flex-direction: column`) por
  `grid-template-columns: repeat(auto-fill, minmax(170px, 1fr))` (`.modulos-setor-grade`), mais
  compacta e organizada.
- **Exclusão de setor** — `services/setores.py::excluir_setor` (novo), mesmo padrão de
  `excluir_empresa`: bloqueia se houver `UsuarioSetor` vinculado (mensagem de erro pedindo pra
  desativar ou desvincular os usuários primeiro), e apaga as linhas de `SetorModulo` do setor
  junto (config, não histórico — seguro remover). Botão de lixeira + modal de confirmação em cada
  linha da tabela, mesmo padrão visual de Empresas-clientes. Rotas: `POST /app/setores/{id}/excluir`
  (web) e `DELETE /setores/{id}` (API), ambas admin-only.

**Pop-up de suporte**

- **`app/config.py`** — `smtp_host`/`smtp_porta`/`smtp_usuario`/`smtp_senha`/`smtp_remetente`
  (opcionais, `None` por padrão) e `smtp_destinatario_suporte` (padrão
  `claracosta@elitemediacoes.com.br`). Sem as três primeiras configuradas, o botão continua
  aparecendo normalmente, mas o envio recusa com uma mensagem amigável em vez de estourar erro.
- **`services/suporte.py::enviar_chamado`** — SMTP direto via `smtplib` (STARTTLS + login), sem
  serviço terceiro. Monta um `EmailMessage` com assunto `[Elite Sistem] {assunto}`, corpo com quem
  abriu (nome/e-mail) + a descrição, `Reply-To` = e-mail de quem abriu (responder o e-mail já cai
  direto pra pessoa certa). Erros de SMTP/rede viram `ValueError` com mensagem amigável.
- **`web/routes_suporte.py`** (novo) — `POST /app/suporte/chamado`, autenticado por cookie
  (`usuario_logado_web`), sem gate de operadora/módulo (é um recurso do sistema como um todo).
  Devolve JSON sempre — chamado via `fetch()` do JS, não form/redirect, porque o pop-up precisa
  funcionar de qualquer página do sistema (vive em `base.html`, não numa tela específica). Isso
  exigiu um ajuste pequeno em `main.py::_e_rota_html`: por padrão qualquer rota sob `/app/*`
  devolve a página de erro HTML num erro não tratado, mas essa rota precisa continuar JSON —
  tratada como exceção nesse helper.
- **Interface (`templates/base.html`)** — botão circular fixo (`position: fixed`, canto inferior
  direito, ícone de suporte) que abre um `<dialog class="modal-confirmacao popup-suporte">` maior,
  reaproveitando o mecanismo genérico de abrir/fechar modal já existente
  (`data-abrir-confirmacao`/`data-fechar-modal`) — só o envio é JS próprio
  (`app.js::iniciarPopupSuporte`), com o botão desabilitado + "Enviando..." durante a chamada,
  toast de sucesso (limpa os campos e fecha) ou erro (mantém o pop-up aberto com o texto digitado,
  pra não perder o que a pessoa escreveu).
- **Testado:** suíte completa sem regressão (188 testes, 12 novos: exclusão de setor via API/web +
  bloqueio por vínculo, `enviar_chamado` com SMTP mockado — sucesso e validação de campos vazios —
  e recusa amigável sem SMTP configurado) + lint limpo + Playwright: layout novo em claro/escuro e
  desktop/mobile, "Marcar todas"/"Limpar seleção" funcionando, exclusão de setor bloqueada/
  permitida, pop-up de suporte abrindo/preenchendo/enviando (com a mensagem de "não configurado"
  aparecendo corretamente, já que as credenciais reais de SMTP ainda não foram fornecidas).
- **Pendência:** falta a Clara passar as credenciais reais de SMTP (host, porta, e-mail e senha de
  app) como variáveis de ambiente no Render — sem isso, o botão de suporte fica visível mas o envio
  não funciona de verdade em produção ainda.
- **Reversível:** sim — tudo aditivo (rota nova, tabela/coluna nenhuma mudou, variáveis de
  ambiente novas e opcionais); nenhum comportamento existente de Setores/Empresas mudou.

### 4.24 Integração com planilhas — análise e recomendação (2026-09-28, Fase 8)

A Clara pediu uma análise (explicitamente **sem implementação**) de como integrar Laudos,
Audiências, Pendências e Gestão de Processos com as planilhas que a equipe usa hoje, pra evitar
digitação duplicada/divergência — corresponde à Fase 8 (Automações) do `ROADMAP.md`, ainda não
iniciada.

Análise completa em **`docs/integracao-planilhas.md`**. Resumo: as 4 áreas já leem `.xlsx` hoje
(upload manual é a única via de entrada em todas — não existe formulário de cadastro paralelo em
nenhuma delas), com um parser compartilhado (`app/excel_reader.py`) já defendido contra vários
problemas reais de planilha (cabeçalho que muda de nome entre abas, "DATA" significando coisas
diferentes conforme a aba, campo composto tipo "EMPRESA - Cliente", número de processo fora do
padrão — ver evidência real: 6.278 de ~51 mil linhas de Processos descartadas por número inválido,
484 por falha ao separar empresa/cliente, no último import validado). Recomendação: manter esse
parser como está e só trocar a origem dos bytes (upload → baixado via API da plataforma onde as
planilhas estão), começando por sincronização **sob demanda** (botão "Atualizar agora") numa única
área piloto — sem agendamento automático nem escrita de volta na planilha por enquanto (nenhuma das
duas peças de infraestrutura existe hoje no projeto).

**Bloqueio real, não contornável:** nenhuma planilha de exemplo foi encontrada no repositório, e os
campos do pedido original sobre onde elas ficam/quem edita ficaram em branco. Uma resposta anterior
já registrada (seção 1.9 item 1, 21/09: Google Sheets, atualizado todo dia) pode ou não continuar
valendo — não presumida, pendente de confirmação. A Etapa 2 da análise (mapeamento de colunas da
planilha real) ficou parcial por esse motivo — feita só a partir do que o sistema já espera hoje,
não de um exemplo real. Lista completa de perguntas pendentes na seção 8 do documento.

**Atualização 28/09 — respostas da Clara:** confirmado Google Sheets/Google Drive, só leitura (o
sistema nunca escreve na planilha), mecanismo via API, frequência mínima de 10x/mês. O motivo real
por trás do pedido, confirmado por ela, é o trabalho manual de subir a planilha toda vez — não duas
fontes de dado concorrentes. Isso mudou a recomendação de "sob demanda primeiro" para
**sincronização automática agendada desde o início** (ex. algumas vezes por dia), com um botão
manual como complemento, não como a via principal. Área piloto ficou a critério da Clara — escolhida
Laudos (operadora única, menor conjunto de colunas, sem CPF). Único bloqueio real que continua em
aberto: exemplo real de pelo menos uma planilha (Laudos, a piloto) — sem isso a Fase B (credencial)
ainda não pode começar. Documento atualizado com todos os detalhes.
- **Reversível:** não se aplica — nenhum código, dado ou planilha foi alterado; só o documento de
  análise foi criado.

### 4.25 Sub-navegação em Configuração, cards 3x3 na tela inicial e redesenho do pop-up de suporte (2026-09-29)

Três pedidos visuais da Clara na mesma mensagem. Antes deles, ela também perguntou por que a aba
"Cartas" (EXIMIA) não aparecia na lista de módulos de um setor — não era bug: é a mesma filtragem
por operadora que ela já tinha pedido pra manter (um setor da EXIMIA mostra Audiências/Cartas/
Pendências; um da ELITE mostra Laudos/Gestão de Processos/Pendências) — expliquei e ela confirmou
que fazia sentido, sem nenhuma mudança de código. Ela também pediu, antes dessas três, que a área de
Configuração ficasse selecionável por setor igual as outras abas — perguntei, já que isso reverteria
uma decisão dela de um dia antes (Configuração só por `papel_global`, nunca por setor, por ser uma
área que inclui criar/editar outros usuários) — ela confirmou manter como estava, nada mudou aí.

- **Sub-navegação entre as 4 áreas de Configuração** — cada uma delas (Usuários/Empresas-clientes/
  Assistentes/Setores) ganhou uma fileira de abas/pills no topo (logo abaixo de "Voltar à
  Configuração"), com as 4 áreas sempre visíveis e a atual destacada — antes só dava pra trocar de
  área voltando pra tela de Configuração primeiro. `app/web/areas_configuracao.py` (novo) centraliza
  a lista das 4 áreas (antes só existia dentro de `routes_configuracao.py`), reaproveitada pelas 5
  rotas (a própria Configuração + as 4 sub-telas); `templates/_config_subnav.html` (novo) é um macro
  Jinja reaproveitado nos 4 templates.
- **Cards da tela inicial em 3x3, maiores** — `dashboard.html` ganhou as classes `grid-modulos-
  inicio`/`modulo-grande` (novas, não reaproveitam a grade responsiva de largura variável que
  Configuração usa — de propósito, pra não afetar aquela tela) — 3 colunas fixas, ícone/título/
  texto maiores. Responsivo: 2 colunas entre 861-1100px, 1 coluna abaixo de 860px (mobile).
- **Pop-up de suporte redesenhado** — botão circular com gradiente (`--navy-light` → `--navy` →
  `--navy-deep`) e um anel sutil (`--accent-soft`) que cresce no hover; o pop-up maior ganhou um
  cabeçalho com fundo em gradiente + ícone circular (mesmo padrão visual do botão), texto branco, e
  o botão "Enviar chamado" passou a usar `--accent` (azul) com ícone, se diferenciando visualmente
  do "Cancelar". Achado durante a implementação: a regra genérica `dialog.modal-confirmacao h3/p`
  tem mais especificidade CSS que um seletor de uma classe só — o texto branco do cabeçalho não
  aplicava até eu prefixar o seletor com `dialog.popup-suporte` pra vencer a regra genérica.
- **Testado:** suíte completa sem regressão (188 testes, nenhum novo — mudança puramente visual/
  estrutural de template, sem lógica nova) + lint limpo + Playwright: sub-navegação nas 4 telas,
  grade 3x3 em claro/escuro/mobile (1 coluna), pop-up de suporte pequeno e grande em claro/escuro.
- **Reversível:** sim — só CSS/HTML/rotas passando um dado extra pro template; nenhuma coluna de
  banco, permissão ou lógica de negócio mudou.

### 4.26 Pop-up de suporte: "[Errno 101] Network is unreachable" ao enviar por Gmail (2026-09-29)

A Clara configurou as variáveis de SMTP no Render (Gmail) e testou o pop-up de suporte — o envio
falhava com `[Errno 101] Network is unreachable`. Diagnosticado sem acesso aos logs do Render (só
com o texto do erro que ela colou): é um problema técnico conhecido de plataformas em nuvem, não
erro de configuração dela — `smtplib.SMTP` comum deixa o sistema operacional escolher IPv4 ou IPv6
ao resolver `smtp.gmail.com`; no ambiente do Render, a resolução às vezes devolve o endereço IPv6
primeiro, mas o container não tem rota de saída por IPv6 configurada, e a conexão cai antes mesmo de
tentar autenticar.

- **`app/services/suporte.py::_SMTPForcandoIPv4`** — subclasse de `smtplib.SMTP` que sobrescreve
  `_get_socket` pra resolver e conectar **só** em endereços IPv4 (`socket.getaddrinfo(..., socket.
  AF_INET, ...)`), em vez de deixar `socket.create_connection` escolher com `AF_UNSPEC`.
  `self._host` continua sendo o nome (`smtp.gmail.com`), não o IP resolvido — importante porque
  `starttls()` usa `server_hostname=self._host` pra verificar o certificado TLS; se o host virasse
  um IP, a verificação de certificado quebraria.
- **Testado:** teste novo isolado (`test_smtp_forcando_ipv4_so_pede_enderecos_af_inet`) confirma que
  `_get_socket` só pede/usa endereços `AF_INET`, sem depender de rede de verdade (mocka `socket.
  getaddrinfo`/`socket.socket`); os dois testes que já mockavam o envio (`enviar_chamado` e a rota)
  foram ajustados pra mockar `_SMTPForcandoIPv4` em vez de `smtplib.SMTP` diretamente (a classe nova
  não herda dinamicamente do que está no módulo `smtplib` — o mock antigo parou de interceptar a
  chamada real). Suíte completa sem regressão (189 testes, 1 novo) + lint limpo.
- **Reversível:** sim — troca só a classe usada internamente pra abrir a conexão SMTP; nenhuma
  variável de ambiente, rota ou comportamento visível mudou.

### 4.27 Pop-up de suporte: SMTP trocado pela API HTTP da Resend (2026-09-29)

A correção de IPv4 (seção 4.26) não resolveu — o erro mudou de `[Errno 101] Network is unreachable`
pra `timed out` (a Clara testou de novo depois do deploy e mandou o texto exato). Diferença
importante: "rede inalcançável" falha na hora; "timed out" é uma conexão que fica esperando resposta
até estourar o limite de 15s — sintoma clássico de firewall de saída **derrubando o pacote em
silêncio**, não recusando — comum em plataformas de hospedagem que bloqueiam SMTP de saída pra
evitar virar relay de spam, mesmo na porta 587. Não era mais nada corrigível só ajustando o
`smtplib` — o problema é a conexão TCP em si nunca completar, não uma etapa depois dela.

**Evidência a favor de migrar pra HTTP, não insistir em mais uma variante de SMTP:** este mesmo
projeto já enviou e-mail com sucesso nesse mesmo Render antes — não por SMTP, por uma API HTTP
(Resend), no alerta de prazo de Gestão de Processos (removido depois por decisão de produto da
Clara, não por falha técnica — ver seção 3.5). Perguntei à Clara se queria migrar pra uma API HTTP
(recomendado, ganho garantido de confiabilidade) ou tentar mais uma porta de SMTP antes (mudança
menor, mas alto risco de ser a mesma causa raiz e não resolver) — ela escolheu migrar.

- **`app/services/suporte.py`** reescrito do zero — sem `smtplib`/`_SMTPForcandoIPv4` (removidos por
  completo, não deixados como caminho morto). Usa `urllib.request` (biblioteca padrão do Python, sem
  dependência nova) pra um `POST` simples em `https://api.resend.com/emails` com `Authorization:
  Bearer <chave>` — é só uma chamada HTTPS normal, a mesma porta 443 que qualquer requisição do
  navegador já usa, contornando de vez a classe de problema de firewall/porta de SMTP.
- **`app/config.py`** — `smtp_*` (host/porta/usuário/senha/remetente/destinatário) substituídos por
  `resend_api_key` (opcional — sem ela, mesmo fallback amigável de antes), `resend_remetente`
  (padrão: o endereço de teste `onboarding@resend.dev` da própria Resend, que funciona sem precisar
  verificar domínio próprio — pode trocar depois de verificar elitemediacoes.com.br no painel deles)
  e `destinatario_suporte` (sem o prefixo `smtp_`, já que não é mais específico de SMTP).
- **Testado:** suíte reescrita pra mockar `urllib.request.urlopen` em vez de `smtplib`/SMTP (mesma
  cobertura de antes: sem chave configurada, envio com sucesso, recusa HTTP da Resend virando erro
  amigável, rota web completa) — 189 testes, lint limpo. Verificado visualmente com Playwright que
  o fallback "não configurado" continua funcionando (sem `RESEND_API_KEY` neste ambiente).
- **Pendência da Clara:** trocar a variável de ambiente no Render — remover as `SMTP_*` antigas
  (inofensivas se ficarem, mas não fazem mais nada) e adicionar `RESEND_API_KEY` (conta grátis em
  resend.com, gera a chave no painel deles — não precisa de senha de app nem verificação em duas
  etapas, é só copiar a chave de API).
- **Reversível:** sim — é uma troca de mecanismo de envio isolada; nenhuma rota, permissão ou
  comportamento visível pra quem usa o pop-up mudou.

### 4.28 Pop-up de suporte: `User-Agent` explícito, bloqueio do Cloudflare (2026-09-29)

Mesmo dia, terceiro erro diferente na mesma funcionalidade — a Clara testou de novo depois do
deploy da Resend e recebeu `error code: 1010`. Esse código **não é da Resend** — é um código de
erro padrão da **Cloudflare** (que protege a API da Resend): "acesso negado com base na assinatura
do navegador", um bloqueio anti-bot que acontece antes da requisição sequer chegar no backend da
Resend. Diagnosticado sem precisar pedir mais nada à Clara — o texto "error code: 1010" já é
autoexplicativo pra quem reconhece o padrão de erro da Cloudflare (tentei confirmar batendo direto
na API real a partir deste ambiente, mas o próprio proxy de rede daqui bloqueia a chamada por outro
motivo, sem relação com a Resend — segui só com o diagnóstico teórico, bem documentado).

- **Causa provável:** `urllib.request` sem um `User-Agent` próprio se identifica como
  `Python-urllib/3.x` — uma assinatura genérica que ferramentas anti-bot (Cloudflare incluso)
  reconhecem e bloqueiam por padrão, independente de credencial/chave estarem certas.
- **`app/services/suporte.py`** — adicionados `User-Agent: EliteSistem/1.0 (+https://elite-
  sistem.onrender.com)` e `Accept: application/json` aos cabeçalhos da requisição.
- **Testado:** teste ajustado pra confirmar que o cabeçalho `User-Agent` enviado não é mais a
  assinatura padrão do `urllib`. 189 testes, lint limpo. Não foi possível validar contra a API real
  da Resend a partir deste ambiente (rede sandboxed) — a Clara precisa confirmar em produção depois
  do próximo deploy.
- **Reversível:** sim — só um cabeçalho HTTP a mais na requisição existente; nada mais mudou.

### 4.29 Cartas: botão "Copiar texto" (2026-09-29)

A Clara pediu: "na parte de Cartas, preciso que exatamente o mesmo conteúdo que vem escrito no PDF
(e com a mesma formatação) venha escrito em formato de texto para copiar e colar" — as duas cartas
(Convite Cliente e Convite Banco) só existiam como download de PDF; sem visualização/texto na tela.

- **`app/services/cartas.py`** ganhou `formatar_texto_carta_cliente(convite)` e
  `formatar_texto_carta_banco(convite)` — mesma convenção já usada em Laudos/Audiências/Processos/
  Pendências (`formatar_texto*` ao lado do gerador de PDF, construído a partir do mesmo dataclass de
  resultado, não derivado do PDF em si). O texto reproduz cada parágrafo do PDF
  (`pdf_export.py::gerar_pdf_carta_cliente`/`gerar_pdf_carta_banco`) na mesma ordem, separados por
  linha em branco (mesma quebra visual que o PDF já tem entre parágrafos); a marcação do PDF
  (`<b>`, `<font color>`, `<a href>`, `<u>`, usada pelo `Paragraph` do reportlab) não existe em texto
  puro — as tags foram simplesmente omitidas, mantendo só o conteúdo textual (negrito/cor/link viram
  texto normal).
- **`app/web/routes_cartas.py`** ganhou `POST /app/cartas/convite-cliente/texto` e
  `POST /app/cartas/convite-banco/texto` — mesma validação dos endpoints de PDF (`montar_convite_*`,
  então o mesmo erro de link inválido/CPF inválido aparece nos dois), mas devolvem JSON
  (`{"texto": ...}` ou `{"erro": ...}`, status 400 no erro) em vez do PDF. Chamados via fetch, igual
  ao pop-up de suporte — por isso `app/main.py::_e_rota_html` ganhou a mesma exceção já feita pra
  `/app/suporte` (erro inesperado nessas duas rotas continua JSON, não vira `erro.html`).
- **Por que uma rota nova em vez de reaproveitar o padrão "Copiar resumo" de Laudos tal como está:**
  em Laudos o texto já está pronto no HTML quando a página carrega (a tela é um GET com os filtros
  na querystring, redesenhada no servidor). Em Cartas, o `POST` de gerar PDF devolve o arquivo
  diretamente (download, sem re-render da página) — não haveria onde embutir o texto de antemão. O
  botão "Copiar texto" busca o texto sob demanda (fetch) e copia direto pro clipboard
  (`navigator.clipboard.writeText`), sem alterar em nada o botão "Gerar PDF" existente.
- **UI:** `templates/cartas.html` — botão "Copiar texto" (`class="secundario"`) ao lado de "Gerar
  PDF" nos dois formulários. `app.js::iniciarCopiaDeTextoCartas()` — valida o formulário
  (`reportValidity()`) antes de buscar, mesmo toast de sucesso/erro do resto do sistema.
- **Testado:** `tests/test_cartas.py` (novo — Cartas não tinha nenhum teste até então) cobre as duas
  funções de formatação (conteúdo esperado, sem sobra de marcação do PDF) e as duas rotas (sem
  login, validação de link/CPF, sucesso). 196 testes, lint limpo. Verificado com Playwright: texto
  copiado bate exatamente com o conteúdo do PDF, toast de sucesso e de erro (link inválido)
  funcionando.
- **Reversível:** sim — duas rotas e um botão novos, aditivos; nada do fluxo de geração de PDF
  existente mudou.

### 4.30 Carta Banco: campo "CPF" aceita CNPJ (identificação automática, 2026-09-30)

A Clara pediu: "o campo CPF do cliente seja possível inserir CNPJ e, para o texto da carta, ela
precisa identificar se é CPF ou CNPJ e colocar de forma correta no texto do pdf e para colar" — o
titular da unidade, na Carta Convite Banco, às vezes é pessoa jurídica, não só pessoa física.

- **`app/services/cartas.py`** ganhou `cnpj_valido()`/`formatar_cnpj()` (mesmo algoritmo de dígito
  verificador do CPF, pesos diferentes — padrão oficial da Receita) e `identificar_documento(valor)`,
  que decide pelo tamanho dos dígitos (11 -> CPF, 14 -> CNPJ), valida com a função certa e devolve
  `(rótulo, formatado)`; erro claro nos três casos (CPF com dígito errado, CNPJ com dígito errado,
  nem 11 nem 14 dígitos). O regex de limpeza (`_RE_CPF_DIGITOS`) foi renomeado pra
  `_RE_SOMENTE_DIGITOS`, já que agora serve os dois.
- **`ConviteBanco`** — o campo `cpf` virou `documento` (valor formatado) + `tipo_documento`
  (`"CPF"` ou `"CNPJ"`); `montar_convite_banco` chama `identificar_documento` em vez de `cpf_valido`
  direto. `pdf_export.py::gerar_pdf_carta_banco` e
  `services/cartas.py::formatar_texto_carta_banco` usam `{convite.tipo_documento}:
  {convite.documento}` em vez do "CPF:" fixo — o PDF e o texto pra copiar mostram "CPF: ..." ou
  "CNPJ: ..." automaticamente, sempre iguais entre si.
- **UI:** `templates/cartas.html` — rótulo do campo trocado de "CPF" pra "CPF/CNPJ", placeholder
  mostrando os dois formatos aceitos. O `id`/`name` do campo continuam `cpf` (só muda o rótulo
  visível) — não precisou tocar em `routes_cartas.py`/`api/cartas.py`, que já passavam o valor bruto
  adiante pra `montar_convite_banco` sem validar o formato ali.
- **Testado:** `tests/test_cartas.py` — `identificar_documento` com CPF válido/inválido, CNPJ
  válido/inválido, e quantidade de dígitos que não é nem 11 nem 14; texto e rota com titular pessoa
  jurídica mostrando "CNPJ" corretamente (e não "CPF"); regressão confirmando CPF continua
  funcionando igual; PDF gerado sem erro com CNPJ. 204 testes, lint limpo. Verificado com Playwright
  na tela real: CNPJ válido copia o texto certo, CNPJ com dígito verificador errado mostra o erro
  "CNPJ inválido" (não mais a mensagem genérica de CPF), CPF válido continua funcionando.
- **Reversível:** sim — extensão aditiva da validação existente; quem já usa CPF normalmente não
  percebe diferença nenhuma.

### 4.31 Cartas: tela genérica de erro ao gerar PDF — `entidade_id` VARCHAR(40) (2026-09-30)

A Clara reportou (print da tela "Algo deu errado") que clicar em "Gerar PDF" nas Cartas estava
quebrando. Diagnóstico sem precisar pedir mais detalhes a ela — reconheci o padrão de imediato,
porque **este projeto já teve esse exato bug antes**, em outras tabelas (ver
`_garantir_texto_ilimitado` em `app/db.py`, e o comentário de `main.py::_erro_nao_tratado` que cita
`StringDataRightTruncation` como exemplo motivador do handler genérico de erro):

- `registrar(..., entidade_id=convite.autor)` (Carta Cliente) e `entidade_id=convite.nome` (Carta
  Banco) gravam o nome/autor **em texto livre, já em maiúsculas**, na coluna `entidade_id` de
  `logs_auditoria` — que era `String(40)`. Nomes completos ou razões sociais passam de 40
  caracteres com facilidade (ex.: "Construtora e Incorporadora Atlântica Empreendimentos
  Imobiliários Ltda").
- **Postgres (produção) aplica o limite de `VARCHAR(40)` de verdade** e recusa o `INSERT` com
  `StringDataRightTruncation` — exceção que não é `ValueError`, então não cai no `except ValueError`
  das rotas de Cartas (que só protege a validação de negócio, tipo CPF/link inválido); vira um erro
  não tratado, e a Clara vê a tela genérica "Algo deu errado". **SQLite (testes) não aplica limite
  de `VARCHAR` nenhum** — por isso os 204 testes anteriores passaram sem pegar esse bug; ele só
  aparece com dados reais em produção.
- **Correção:** `app/models.py::LogAuditoria.entidade_id` virou `Text` (sem limite), igual ao mesmo
  ajuste já feito antes em `Processo.advogada`/`assistente`/`Audiencia.nome_cliente` etc. — mesma
  causa raiz, tabela diferente. `app/db.py::init_db()` ganhou
  `_garantir_texto_ilimitado(engine, "logs_auditoria", "entidade_id")`, que faz o `ALTER TABLE ...
  ALTER COLUMN entidade_id TYPE TEXT` na tabela já existente em produção no próximo deploy (esse
  projeto não usa Alembic — `create_all` só cria tabela nova, não altera coluna de tabela que já
  existe).
- **Testado:** `tests/test_cartas.py::test_gerar_convite_cliente_com_nome_longo_nao_trunca_no_log_auditoria`
  — gera a Carta Cliente com um autor de 73 caracteres e confirma que o log de auditoria guarda o
  valor inteiro (esse teste não reproduz o crash de Postgres em si, já que SQLite não aplica limite
  de `VARCHAR`, mas protege a coluna do modelo contra voltar a ser `String(N)` por engano). 205
  testes, lint limpo.
- **Pendência:** nenhuma da parte da Clara — é só o próximo deploy pegar essa mudança; o `ALTER
  TABLE` roda sozinho na inicialização, não precisa de nenhum passo manual no Render/Supabase.
- **Reversível:** sim — só alarga uma coluna existente (de `VARCHAR(40)` pra `TEXT`); nenhum dado é
  perdido, nenhum comportamento visível muda além do bug corrigido.

### 4.32 Pop-up de suporte: abandonado e-mail, chamado guardado no sistema + aviso no Discord (2026-10-01)

Depois de três tentativas sem sucesso de enviar o chamado por e-mail em produção (seções 4.26-4.28:
`[Errno 101]` → `timed out` → migração pra Resend → bloqueio do Cloudflare → `error code: 1010`
corrigido → e por fim a verificação de domínio da Resend não completando pra Clara, mesmo em duas
tentativas dela), a Clara perguntou se havia outra forma e o que empresas costumam fazer. Resposta:
a maioria guarda o chamado no próprio sistema (nunca depende de provedor externo) e usa um canal
mais simples que e-mail corporativo pra avisar na hora — ela escolheu Discord.

- **`app/models.py`** — nova tabela `Chamado` (`chamados`): `usuario_id`, `assunto`, `descricao`
  (ambos `Text`, sem limite), `resolvido`/`resolvido_em`. Tabela nova — `create_all` cria sozinho,
  sem precisar de `_garantir_coluna`/`_garantir_texto_ilimitado` (esses só existem pra alterar
  tabela que **já existe** em produção).
- **`app/services/suporte.py`** reescrito — `abrir_chamado(db, usuario, assunto, descricao)` salva
  o `Chamado` no banco e só depois chama `_avisar_discord` (best-effort): se
  `DISCORD_WEBHOOK_SUPORTE` não estiver configurado, ou o POST pro Discord falhar por qualquer
  motivo, o chamado **já foi salvo** — só fica sem o aviso em tempo real (log de warning, não
  exceção). Diferença de design importante em relação à versão por e-mail: antes, falha no provedor
  = chamado inteiro recusado; agora, o registro (o que a Clara realmente precisa) nunca depende do
  aviso funcionar.
- **`app/web/routes_chamados.py`** (novo) — `GET /app/chamados` (lista, mais recentes/abertos
  primeiro) e `POST /app/chamados/{id}/resolvido?resolvido=true|false` (marcar/reabrir), ambos só
  Admin (`admin_logado_web`, mesmo padrão de Usuários/Empresas/Setores). Vira a 5ª área de
  Configuração (`areas_configuracao.py` + `templates/chamados.html`, mesmo sub-nav das outras 4) —
  `menu.py` ganhou `/app/chamados` em `tambem_ativo_em` do item "Configuração".
- **`app/web/routes_suporte.py`** — `POST /app/suporte/chamado` (o pop-up, inalterado pro usuário:
  mesmo botão flutuante, mesmo fetch) agora chama `abrir_chamado` em vez de `enviar_chamado` — só
  recusa por campo vazio, nunca mais por "não configurado" (o registro no banco sempre funciona).
- **`app/config.py`** — `resend_api_key`/`resend_remetente`/`destinatario_suporte` removidos por
  completo (não deixados como caminho morto); `discord_webhook_suporte: str | None = None` no
  lugar — opcional, sem ele o chamado só não avisa ninguém na hora.
- **Testado:** `tests/test_suporte.py` reescrito (mocka `urllib.request.urlopen` pro aviso do
  Discord, não mais pra um envio obrigatório — inclui teste específico confirmando que uma falha no
  Discord não impede o chamado de ser salvo); `tests/test_chamados.py` novo (lista, gate de Admin,
  marcar/reabrir resolvido). 208 testes, lint limpo. Verificado com Playwright: chamado aberto pelo
  pop-up sem nenhum Discord configurado neste ambiente — sucesso imediato (toast "Chamado enviado!",
  sem erro nenhum, diferente de antes); aparece na lista de Configuração > Chamados; "Marcar
  resolvido"/"Reabrir" funcionando; card "Chamados" aparece na tela de Configuração.
- **Pendência da Clara:** se quiser o aviso em tempo real, criar um webhook num canal do Discord
  (Configurações do canal → Integrações → Webhooks → Criar Webhook → copiar URL) e configurar
  `DISCORD_WEBHOOK_SUPORTE` no Render — mas isso é totalmente opcional agora: mesmo sem fazer nada,
  os chamados já aparecem na tela de Chamados normalmente.
- **Reversível:** sim — tabela nova, nenhuma estrutura existente alterada; voltar a usar e-mail
  (ou qualquer outro provedor) exigiria só reescrever `abrir_chamado`/`_avisar_discord`, sem perder
  nenhum chamado já salvo.

### 4.33 Gestão de Processos: fatal só na aba FATAIS (sem data real) agora entra no relatório (2026-10-02)

A Clara perguntou se o relatório pega os fatais das abas "FATAIS [mês]". Investigando: a maioria
dessas abas tem uma coluna de data real do andamento ("DIA") e já entra normalmente — mas abas (ou
linhas) que só têm a "DATA DE LIBERAÇÃO — QUANDO A DRA INSERIU O CLIENTE NA PLANILHA" (sem nenhuma
data de andamento de verdade) são marcadas `data_e_liberacao=True` e **totalmente excluídas** do
relatório por período (seção 4.12, decisão da Clara em 2026-09-24) — inclusive da determinação do
"Fatal" (que olha pro último andamento real do processo). Resultado: um processo cujo único
registro é um "SIM" na aba FATAIS, sem nenhum andamento datado em outro lugar, nunca aparecia em
relatório nenhum, fatal ou não.

A Clara confirmou (via pergunta): quer que esses apareçam mesmo assim, usando a data de liberação
como se fosse a data do andamento (opção recomendada, em vez de uma lista separada fora do filtro
por período) — mesmo comportamento que qualquer outra data de andamento já tem no resto do sistema.

- **`app/services/processos.py::_processos_em_escopo`** e **`_ultimo_evento_por_processo`** — a
  exclusão `EventoProcesso.data_e_liberacao.is_(False)` virou
  `or_(EventoProcesso.data_e_liberacao.is_(False), EventoProcesso.prazo_fatal.is_(True))` nas duas
  funções (únicos dois lugares do arquivo que aplicavam essa exclusão, compartilhados pelos
  relatórios Geral e Por Empresa). Uma linha `data_e_liberacao=True` **sem** `prazo_fatal="SIM"`
  continua excluída, exatamente como antes (comportamento da seção 4.12 preservado para o caso
  comum) — só fatal ganha a exceção.
- **Sem migração de dados:** `data_e_liberacao`/`prazo_fatal` já eram gravados corretamente no
  import desde a seção 4.12 — o problema era só o filtro na hora de ler o relatório, não o que foi
  salvo. A mudança vale pra dados já importados, sem precisar reimportar a planilha.
- **Testado:** novo teste `test_import_fatal_so_na_aba_fatais_entra_no_relatorio_mesmo_sem_data_real`
  (`tests/test_processos_service.py`) — processo só com um "SIM" numa aba com apenas data de
  liberação aparece no relatório Geral e Por Empresa, com `fatal=True`; o teste existente que cobre
  o caso "sem fatal" (`test_import_marca_data_de_liberacao_e_relatorio_a_exclui_do_periodo`) segue
  passando sem alteração — confirma que só fatal ganhou a exceção. 209 testes, lint limpo.
- **Efeito colateral esperado:** a contagem de processos por mês pode subir um pouco depois desse
  deploy, onde houver fatal só na aba FATAIS dentro do período — isso é o comportamento pedido, não
  uma regressão.
- **Reversível:** sim — trocar o `or_(...)` de volta por só `.is_(False)` nas duas funções desfaz,
  sem precisar reimportar nada.

### 4.34 Relatórios em Excel (2026-10-05)

A Clara pediu: "preciso que todos os relatórios do sistema tenham a opção de serem baixados em
formato de excel". Os relatórios tabulares do sistema já baixavam em PDF (Laudos, Audiências,
Gestão de Processos — Geral e Por Empresa, todos via `/<módulo>/relatorio.pdf` em `app/api/*.py`,
autenticados pelo mesmo cookie da sessão web, ver `app/auth.py`). Cartas e Pendências ficam de
fora: Cartas é texto de carta-convite, não uma lista/tabela (já tem "Copiar texto", ver seção
4.29); Pendências gera uma mensagem de cobrança em texto corrido, não um relatório tabular — nenhum
dos dois tem PDF hoje por esse mesmo motivo, então nenhum ganhou Excel.

- **`app/excel_export.py`** (novo) — `gerar_excel_laudos`/`gerar_excel_audiencias`/
  `gerar_excel_processos_geral`/`gerar_excel_processos_por_empresa`, cada uma recebendo o mesmo
  dataclass de resultado que a função `gerar_pdf_*` correspondente (`app/pdf_export.py`) já usa —
  mesmos dados, sem repetir nenhuma consulta ao banco. Usa `openpyxl` (já era dependência, só pra
  leitura de planilha até então) pra escrever — sem lib nova. Datas e valores viram célula de
  verdade (`datetime`/`float` com `number_format`), não texto formatado à mão, pra dar pra somar/
  filtrar/ordenar direto no Excel.
- **Processos Geral é "achatado":** o PDF mostra duas tabelas por empresa (Parte 1: Assistente/Nº
  processo/Evento/Fatal; Parte 2: Cliente/Nº processo/Último evento/Última observação, mesmo
  processo repetido nas duas). No Excel isso vira uma linha por processo só, com as colunas das
  duas partes juntas (casadas pelo nº do processo) e Empresa como coluna — mais fácil de filtrar/
  somar numa planilha só do que duas tabelas por seção/empresa como no PDF.
- **Rotas novas:** `GET /laudos/relatorio.xlsx`, `/audiencias/relatorio.xlsx`,
  `/processos/relatorio.xlsx` (mesmos parâmetros dos `.pdf` equivalentes, inclusive `tipo=geral|
  empresa` em Processos) — `Content-Type:
  application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`, mesmo padrão de nome de
  arquivo (`app/utils.py::nome_arquivo_xlsx`, generalizado a partir de `nome_arquivo_pdf` sem mudar
  nenhum call site existente).
- **UI:** botão "Baixar Excel" ao lado de "Baixar PDF" em `laudos.html`/`audiencias.html`/
  `processos.html` (nos dois tipos de relatório de Processos) — mesmo link direto (sem JS), mesma
  autenticação por cookie que o PDF já usava.
- **Bug pego nos próprios testes, antes de chegar em produção:** `ws.append([])` (linha em branco
  separando o bloco de cabeçalho da tabela) não avança `ws.max_row` do jeito previsível no
  openpyxl — calcular a posição da linha de cabeçalho da tabela de antemão (`max_row + 1`, antes de
  escrevê-la) saiu errado por uma linha, fazendo a formatação de data/moeda vazar pro texto do
  cabeçalho e faltar na última linha de dado. Corrigido capturando a posição **depois** de escrever
  o cabeçalho, nunca antes — ver comentário em `gerar_excel_laudos`.
- **Testado:** `tests/test_excel_export.py` (novo) — conteúdo/formatação das 4 planilhas, inclusive
  o caso sem CNPJ (testa que a tabela não desalinha) e a junção Parte 1 + Parte 2 de Processos
  Geral; mais os testes de rota (auth por cookie, Content-Type, nome de arquivo) em
  `test_api_laudos.py` e `test_web.py`. 218 testes, lint limpo. Verificado com Playwright nas 4
  telas reais: os 4 downloads completam e o conteúdo da planilha bate exatamente com o que a tela
  mostra.
- **Reversível:** sim — rotas e módulo novos, aditivos; nada do fluxo de PDF existente mudou.

### 4.35 Novo módulo: Correspondências (Fase 9, ELITE, 2026-10-05)

A Clara pediu um ambiente novo ("Correspondências") no mesmo padrão de Laudos: upload de planilha,
filtro por mês + empresa, relatório em PDF e Excel. Planilha de exemplo anexada por ela
(`PLANILHA_2026.xlsx`) — a aba real com os dados é "ADV. CONTRATOS" (as outras 7 abas do arquivo
são de outras áreas, sem relação, ignoradas). Antes de implementar, segui a regra mais importante
que ela deu ("qualquer dúvida, pergunte antes de decidir"): perguntei o nome do ambiente (sua
mensagem original tinha "[NOME DO AMBIENTE]" sem preencher) e pedi pra completar uma frase que
cortou no meio ("Regras de leitura da planilha... - Linhas"). Depois de ler o código de Laudos de
ponta a ponta, apresentei um plano com o que seria reaproveitado vs. novo e perguntei 4 decisões
em aberto (persistência, fonte da lista de empresas, tratamento de VALOR inválido, linha de total)
— ver DECISIONS.md 2026-10-05 pras respostas.

- **`app/models.py::Correspondencia`** — tabela nova (`correspondencias`), mesmo padrão de `Laudo`:
  acumula histórico entre uploads. `mes` é o texto literal da planilha ("JANEIRO"), sem controle de
  ano — a planilha real não tem coluna de ano, e a Clara confirmou que não precisa por enquanto.
  `valor` fica `None` quando a célula não é um número reconhecível; `valor_texto` guarda o texto
  original pra mostrar no relatório (decisão da Clara: não zerar nem travar o import).
- **`app/services/correspondencias.py`** (novo) — `importar_planilha`/`gerar_relatorio`/
  `apagar_todas_correspondencias`/`parse_valor`. Usa `load_data_sheets` igual a todo o resto do
  sistema (varre todas as abas, pega as que batem os cabeçalhos exigidos, por nome — tolerante a
  maiúscula/acento/espaço). Diferente de Laudos: só `MÊS`+`EMPRESA` ancoram a seleção de aba; as
  outras 5 colunas são checadas uma a uma depois, pra dar uma mensagem específica de qual coluna
  falta (a Clara pediu isso explicitamente) em vez da mensagem genérica de "nenhuma aba com essas
  colunas".
  - **`parse_valor`** — "R$ 180,00"/"R$160,00" (sem espaço)/"R$ 1.234,56" → número; `None` quando
    não reconhece (ex.: "a combinar"). Achado real testando contra a planilha da Clara: "R$
    280,00." (ponto final sobrando, digitação) não batia o regex original — ajustado pra tolerar
    ponto final solto, recuperando 6 das 9 linhas que teriam ficado "sem valor" por causa só de um
    típo de digitação, não por serem genuinamente não numéricas.
- **`app/pdf_export.py::gerar_pdf_correspondencias`** — único relatório do sistema que usa
  `reportlab.platypus.Table` (com `repeatRows=1`) em vez de desenhar linha a linha no `canvas` como
  os outros. Motivo: a Clara pediu que texto longo quebre linha dentro da célula (altura de linha
  variável) e que o cabeçalho da tabela repita quando passa de uma página — as duas coisas já vêm
  prontas do `Table`, enquanto os outros relatórios (`canvas` cru) exigiriam reimplementar os dois
  na mão. A faixa azul (Empresa/Mês) só aparece na 1ª página, igual ao padrão que Laudos já tinha
  (as páginas seguintes não repetem a faixa, só os dados) — confirmado com 7 páginas de teste
  (textos propositalmente longos), cabeçalho da tabela repetindo certinho em todas.
- **`app/excel_export.py::gerar_excel_correspondencias`** — mesmo padrão dos outros 4 relatórios em
  Excel (seção 4.34): VALOR vira célula numérica com formato de moeda quando reconhecido, célula de
  texto comum quando não (mesma regra do PDF); `wrap_text` nas colunas de texto corrido.
- **Rotas:** `app/web/routes_correspondencias.py` (`/app/correspondencias`, mesmo padrão de
  `routes_laudos.py` — importar/gerar relatório/zona de perigo) e `app/api/correspondencias.py`
  (`/correspondencias/relatorio`, `.pdf`, `.xlsx`, mesma autenticação por cookie). Novo módulo
  `CORRESPONDENCIAS` em `app/auth.py::MODULOS_OPERADORA` (ELITE, confirmado com a Clara) e
  `MODULOS_ROTULO`; item novo no menu lateral (`app/web/menu.py`); ícone novo (`correspondencias`,
  avião de papel) em `_icones.html`.
- **Bug real encontrado e corrigido durante o teste end-to-end:** a tela de importar renderizava o
  dropdown de empresas **antes** de rodar o import — uma empresa nova trazida pela própria planilha
  (ex.: "EROS", que não existia ainda no banco) não aparecia no filtro logo depois de importar, só
  depois de recarregar a página na mão. Corrigido montando o contexto da página **depois** do
  import. Não existe em Laudos (não mexido) — mas vale considerar o mesmo ajuste lá depois, como
  tarefa separada, se a Clara quiser.
- **Laudos não foi tocado:** nenhuma função de `services/laudos.py`, `pdf_export.py::gerar_pdf_laudos`
  nem `excel_export.py::gerar_excel_laudos` foi alterada — tudo que Correspondências reaproveita
  são peças já genéricas/compartilhadas (`_fundo`, `_cabecalho_empresa`, `NAVY`, `MARGEM`,
  `format_brl`, `nome_arquivo_pdf/xlsx`, `load_data_sheets`, classes CSS). Suíte de testes de
  Laudos passa sem nenhuma mudança.
- **Testado:** `tests/test_correspondencias_service.py` (22 testes — parse_valor, import,
  colunas obrigatórias faltando, relatório, total), `tests/test_api_correspondencias.py` (3),
  `tests/test_web_correspondencias.py` (5, incluindo o bug do dropdown acima),
  `tests/test_correspondencias_export.py` (6 — PDF/Excel, valor inválido, paginação). 254 testes no
  total, lint limpo. Verificado com Playwright: upload da planilha real da Clara (155 linhas
  novas), filtro Empresa/Mês mostrando só as linhas certas, PDF e Excel baixados batendo com a
  tela, mês/empresa sem resultado mostrando mensagem amigável (sem erro), Laudos intacto.
- **Reversível:** sim — módulo, tabela e rotas novos, 100% aditivo; nada existente foi alterado
  além da correção isolada do bug do dropdown (só em código novo desta sessão).

### 4.36 Excel dos 5 relatórios com o mesmo visual do PDF (2026-10-06)

A Clara viu as amostras de Correspondências e pediu: PDFs mantêm a formatação atual, mas as
planilhas devem "ser geradas na mesma configuração dos PDFs, mas com o formato de planilha para
editar nomes e valores se necessário". Perguntei se era só pra Correspondências ou pros 5
relatórios em Excel — ela confirmou: todos.

- **`app/excel_export.py`** reescrito — três funções compartilhadas novas usadas pelos 5
  geradores: `_faixa_titulo` (faixa navy no topo, uma linha mesclada por item — mesmo texto/ordem
  que `pdf_export.py::_cabecalho_empresa` desenha no PDF, ex.: "Empresa: X", "CNPJ: Y", "Status:
  Z"), `_cabecalho_tabela` (linha de cabeçalho da tabela com fundo navy/texto branco, em vez de só
  negrito) e `_estilizar_linhas_dados` (borda fina + quebra de texto em toda linha de dado, com
  fundo alternado claro/branco — mesma ideia do `ROWBACKGROUNDS` que o PDF de Correspondências já
  tinha). A linha de Total virou uma barra navy com texto branco negrito em todas as colunas —
  mesmo destaque que Laudos/Audiências/Processos já tinham no PDF (faixa navy cheia), só que agora
  reproduzido no Excel também.
- **Estrutura dos dados continua "achatada"** (uma linha por item, sem as múltiplas tabelas/seções
  por página que alguns PDFs mostram) — isso não mudou: só o visual (cores/faixa/cabeçalho)
  replica o PDF, não a paginação. É o que mantém a planilha fácil de editar/filtrar/somar, que é
  literalmente o que a Clara pediu ("formato de planilha para editar nomes e valores").
- **Achado ao replicar a faixa do PDF:** o Excel de "Processos — Geral" não tinha "Empresa: ELITE
  MEDIAÇÕES" nem "Relatório geral de processos" na faixa (só "Período") — o PDF tinha essas duas
  linhas e o Excel não. Corrigido pra bater exatamente com o que o PDF mostra.
- **Pequena simplificação de estrutura:** o Total de Audiências, que antes ficava em duas linhas
  (rótulo "Total" numa linha, valor na linha de baixo), virou uma linha só (rótulo + valor juntos)
  — mesmo padrão de Laudos/Processos, mais simples de estilizar com a barra navy e mais consistente
  entre os relatórios.
- **Testado:** todos os testes de `tests/test_excel_export.py`/`test_correspondencias_export.py`/
  `test_api_laudos.py`/`test_api_correspondencias.py` ajustados pra nova estrutura de linha (faixa
  mesclada em vez de "rótulo | valor" em duas células) — nenhum teste novo precisou ser criado, os
  mesmos continuam cobrindo conteúdo/formatação. 254 testes, lint limpo. Verificado inspecionando
  as propriedades de cada célula (cor de fundo, negrito, texto branco, mesclagem, `wrap_text`) nos
  5 relatórios — o renderizador de PDF/visualização de planilha deste ambiente (LibreOffice
  headless) não conseguiu converter nenhum .xlsx pra imagem por um problema de ambiente não
  relacionado ao conteúdo dos arquivos (nem um `.xlsx` em branco, recém-criado, converteu) — a
  verificação ficou na inspeção direta das propriedades de célula em vez de uma captura visual.
- **Reversível:** sim — é só o visual da função de export; nenhuma estrutura de dado/banco mudou.

### 4.37 Bug: excluir empresa com correspondência vinculada dava erro genérico (2026-10-06)

A Clara reportou: "Quando apago uma empresa o sistema da erro e aparece a página dizendo para
chamar o suporte, e ai eu recarrego a página e tudo se repete".

- **Causa raiz:** `app/services/empresas.py::_ENTIDADES_VINCULADAS` — o dicionário que
  `contar_vinculos_empresa`/`excluir_empresa` usam pra saber o que está "preso" a uma empresa antes
  de apagar — tinha `Laudo`, `Audiencia`, `Cobranca` e `Processo`, mas não `Correspondencia` (o
  modelo novo da seção 4.35, que tem FK `empresa_cliente_id` NOT NULL igual aos outros). Faltando
  ali, o código não detectava o vínculo, não caía no aviso amigável ("não é possível excluir...") e
  seguia direto pro `db.delete(empresa)` — em produção (Postgres, que aplica a FK de verdade) isso
  vira `IntegrityError` não tratado, cai na tela genérica de erro, e como a transação é desfeita a
  cada tentativa (nenhum dado é perdido), recarregar e tentar de novo repete o mesmo erro. O SQLite
  usado nos testes não aplica FK por padrão, por isso a suíte inteira passava sem pegar esse caso.
- **Correção:** adicionado `"correspondências": Correspondencia` em `_ENTIDADES_VINCULADAS`
  (`app/services/empresas.py`). Agora excluir uma empresa com correspondência vinculada: sem
  informar empresa de destino, bloqueia com a mensagem amigável já existente (em vez do erro
  genérico); informando um destino, reatribui as correspondências pra ela antes de apagar — mesmo
  comportamento que já existia pra laudos/audiências/cobranças/processos.
  Nenhum outro arquivo/comportamento foi alterado.
- **Testado:** `tests/test_empresas_service.py` — teste existente renomeado e estendido
  (`test_excluir_empresa_com_destino_reatribui_os_cinco_tipos_de_vinculo`, agora cobrindo também
  Correspondencia) e um teste novo (`test_excluir_empresa_com_correspondencia_vinculada_sem_destino_e_bloqueada`)
  reproduzindo exatamente o bug relatado e confirmando o bloqueio amigável. 255 testes no total,
  lint limpo.
- **Reversível:** sim — uma linha adicionada a um dicionário de registro; nenhuma migração ou
  mudança de banco.

### 4.38 Exclusão e realocação de empresas em massa (2026-10-06)

A Clara pediu: "preciso de alguma forma de selecionar e apagar empresas em massa, além de
realocá-las em massa se necessário". Antes de implementar, perguntei 3 pontos de comportamento
(regra de sempre perguntar antes de decidir sozinho):

1. **Exclusão em massa com vínculo misto** (algumas selecionadas têm histórico vinculado, outras
   não): ela escolheu **uma única empresa de destino pra todas** — as sem vínculo são excluídas
   direto, as com vínculo são movidas pra esse destino antes de excluir.
2. **Realocação em massa** (mover histórico sem excluir): ela confirmou que é uma **ação
   separada** da exclusão, não só uma etapa dela.
3. **Depois de realocar**, as empresas de origem (que ficam sem vínculo): ela escolheu que
   **ficam como estão, ativas** — decide depois, manualmente, o que fazer com cada uma.

- **`app/services/empresas.py`** — duas funções novas, reaproveitando ao máximo o que já existia:
  - `excluir_empresas_em_massa(db, empresa_ids, empresa_destino_id=None)`: chama `excluir_empresa`
    uma vez por id selecionado, sempre com o mesmo `empresa_destino_id` (ou `None`). Recusa de
    cara se o destino estiver entre os próprios selecionados, ou se o destino informado não
    existir. Cada id que falhar (vínculo sem destino) entra em `nao_excluidas_por_vinculo` sem
    travar os demais — mesmo texto de erro de sempre, só que por lote.
  - `realocar_empresas_em_massa(db, empresa_ids, empresa_destino_id)`: pra cada id selecionado,
    conta os vínculos (`contar_vinculos_empresa`) e, se houver, reatribui todos pro destino (mesmo
    loop de `_ENTIDADES_VINCULADAS` que `excluir_empresa` já usa) — sem chamar `db.delete` em
    nenhum momento. Quem não tiver nada vinculado entra em `sem_vinculo` (não é erro, só não há o
    que mover). Também recusa destino entre os selecionados ou destino inexistente.
- **Tela (`empresas.html` + `static/app.js` + `static/style.css`)** — reaproveitando o padrão
  existente de modal de confirmação (`dialog.modal-confirmacao`, `data-abrir-confirmacao`) com uma
  variação nova (`data-abrir-selecao-massa`) pra seleção em lote:
  - Uma caixa de seleção por linha (`.chk-empresa-massa`) + uma no cabeçalho pra marcar/desmarcar
    todas (com estado indeterminado quando a seleção é parcial).
  - Uma barra de ações (`#barra-selecao-empresas`) que só aparece com pelo menos 1 selecionada,
    com os botões "Excluir selecionadas" e "Realocar selecionadas".
  - No modal de excluir, o campo de empresa de destino só aparece (e só fica obrigatório) se
    alguma das selecionadas tiver vínculo — decidido no navegador, comparando com
    `vinculos_por_empresa` que a tela já carregava. No modal de realocar, o destino é sempre
    obrigatório.
  - Em ambos os modais, as próprias empresas selecionadas nunca aparecem como opção de destino.
  - Os ids selecionados são injetados como campos ocultos dentro do `<form>` de cada modal no
    momento de abrir (as caixas de seleção não pertencem a nenhum form — vivem soltas na tabela,
    igual ao padrão de editar nome/CNPJ que já existia).
  - As duas rotas novas (`POST /app/empresas/excluir-em-massa` e `POST /app/empresas/
    realocar-em-massa`) são admin-only (mesma proteção da "Zona de perigo" existente), registram
    auditoria (`EXCLUIU_EMPRESAS_EM_MASSA`/`REALOCOU_EMPRESAS_EM_MASSA`) e precisam ficar
    registradas ANTES de `POST /{empresa_id}` — mesmo motivo de sempre (`sincronizar-lista-
    oficial`/`excluir-inativas`): o Starlette casaria a rota genérica primeiro e devolveria 422.
- **Testado:** `tests/test_empresas_service.py` (8 testes novos cobrindo sem vínculo, vínculo
  misto sem destino, vínculo com destino, destino entre as selecionadas, realocação com/sem
  vínculo, destino inexistente) e `tests/test_web_empresas.py` (novo arquivo, 7 testes — fluxo
  completo pela tela, sem seleção, exige admin). 270 testes no total, lint limpo. Verificado com
  Playwright de ponta a ponta: selecionar 2 empresas (uma sem vínculo, uma com laudo vinculado),
  excluir em massa sem destino (confirma que o campo de destino aparece automaticamente por ter
  vínculo selecionado, que nenhuma das próprias selecionadas aparece como opção de destino),
  excluir com destino escolhido (as duas somem da tela, o laudo migra pro destino), depois
  selecionar uma empresa com audiência vinculada e realocar pro mesmo destino (a empresa de
  origem continua cadastrada e ativa na tela, só a audiência migra).
- **Reversível:** sim — duas funções de serviço e duas rotas 100% novas, aditivas; nenhum
  comportamento existente (exclusão individual, zona de perigo) foi alterado.

### 4.39 Bug: "apagar em massa" não apagava todas as selecionadas (2026-10-06)

A Clara testou a seção 4.38 e reportou: "Eu clico em apagar em massa e ele continua apagando um
só" — e, ao eu perguntar se o campo de destino aparecia e se ela chegava a escolher uma empresa
ali, confirmou: "Eu seleciono o campo para mover o histórico, e mesmo assim n apaga todos os
selecionados."

- **Causa raiz, reproduzida localmente:** o fluxo mais natural pra "excluir várias empresas e
  manter uma como sobrevivente" é clicar em "Selecionar todas" (marca TODAS as linhas, inclusive a
  que ela queria manter) e then escolher essa mesma empresa como destino no modal. Mas
  `excluir_empresas_em_massa` recusa de propósito uma empresa de destino que esteja entre as
  próprias selecionadas (não dá pra uma empresa ser destino de si mesma) — e quando isso acontece,
  a operação inteira falha (0 excluídas) com um erro que não deixava claro o motivo. Reproduzi com
  Playwright: 5 empresas com todos os 5 tipos de vínculo (laudo, audiência, cobrança, processo,
  correspondência) + 1 candidata a destino, "Selecionar todas", escolher a candidata como destino
  → falha total. Selecionando as 5 SEM a candidata (ela fica de fora da seleção) → as 5 são
  excluídas corretamente com o histórico movido pro destino, confirmando que o motor de exclusão
  em si (serviço + rota) sempre funcionou certo — o problema era só esse caso de seleção.
- **Correção — `static/app.js`:** em vez de só recusar (ou só esconder a opção no dropdown, que já
  acontecia mas não ajudava quem usa "Selecionar todas"), agora, ao escolher uma empresa no campo
  de destino, se ela estiver marcada pra exclusão/realocação, a caixa dela é **desmarcada
  automaticamente** (`iniciarAutoDesmarcarDestino`), com um toast explicando o que aconteceu ("A
  empresa escolhida como destino foi retirada da seleção"). O fluxo "selecionar tudo e escolher
  quem sobrevive" passa a funcionar sem exigir que a pessoa lembre de desmarcar manualmente. O
  modal aberto (contador, campos ocultos, lista de opções de destino) é recalculado na hora
  (`atualizarModalAberto`, extraído do código que já existia pra abrir o modal). Nenhuma mudança
  no backend (`excluir_empresas_em_massa`/`realocar_empresas_em_massa`) — a proteção contra
  destino-entre-selecionadas continua lá, só deixou de ser alcançável pelo fluxo normal da tela.
- **Testado:** suíte completa sem alteração (270 testes, a proteção do backend contra destino
  entre as selecionadas já tinha teste — `test_excluir_em_massa_destino_entre_selecionadas_e_
  recusada`/`test_realocar_em_massa_destino_entre_selecionadas_e_recusada`, continuam passando,
  confirmando que o backend ainda recusa se algum dia o JS for contornado). Verificado com
  Playwright reproduzindo o cenário exato da Clara (selecionar todas, escolher a própria candidata
  a destino) — a caixa dela desmarca sozinha, o contador do modal atualiza de 6 pra 5, e a
  exclusão em massa conclui com sucesso, deixando a empresa-destino intacta com o histórico das
  outras 5 nela. Esse é um bug só de JavaScript (lógica de seleção no navegador) — este projeto
  não tem infraestrutura de teste automatizado de navegador na suíte (só `TestClient` server-side),
  então a verificação ficou no teste manual com Playwright, documentado aqui.
- **Reversível:** sim — mudança isolada em `static/app.js`; nenhum HTML, rota ou lógica de
  serviço foi alterado.

### 4.40 Bug (continuação): clique impreciso na caixinha de seleção (2026-10-06)

A correção da seção 4.39 não resolveu — a Clara testou de novo e reportou o mesmo sintoma:
"Seleciono mais de dois, escolho a empresa que deve ser passada os processos e ele apaga apenas
um dos selecionados." Perguntei se aparecia erro, se demorava, quanto histórico as empresas
tinham e quantas ela selecionava; ela respondeu: sem erro (mensagem verde normal, só que "1
empresa(s) excluída(s)"), demora bastante, pouco histórico, e repetiu com empresas diferentes com
o mesmo resultado — sempre exatamente 1 de N.

- **Investigação:** reproduzi o cenário (mais de duas selecionadas, destino separado, sem estar
  entre as selecionadas) de três formas — direto no serviço, via requisição HTTP crua, e com
  navegador automatizado — **inclusive contra um Postgres real** (subi um cluster local,
  `postgresql+psycopg://`, com FK aplicada de verdade, igual produção) com empresas tendo os 5
  tipos de vínculo simultaneamente. Em todos os casos as empresas foram excluídas corretamente, as
  4 de uma vez. A mensagem "sem erro, sempre exatamente 1 de N, não depende de quais empresas" é
  incompatível com um erro de banco (apareceria vermelho) ou com o backend recebendo os ids
  errados de forma aleatória — aponta pra alguma empresa na seleção dela nunca chegar a ficar
  marcada de fato.
- **Hipótese mais provável:** a caixinha de seleção (`.chk-empresa-massa`) é pequena numa tabela
  densa — fácil clicar ao lado dela (no texto do nome, na célula de status) sem perceber que não
  marcou. A pessoa "sente" que selecionou várias, mas só uma (a que acertou o clique) realmente
  ficou marcada — exatamente o padrão "sempre 1, não importa quais" que ela descreveu.
- **Correção — `static/app.js` (`iniciarCliqueNaLinhaParaSelecionar`):** clicar em qualquer espaço
  vazio da linha (não só na caixinha) agora também alterna a seleção — clicar de novo desmarca.
  Cliques nos campos de nome/CNPJ, botões (Salvar/Desativar/excluir) e links continuam com o
  comportamento normal deles, sem disparar a seleção. Cursor vira "pointer" só nas linhas que têm
  checkbox (não mexe em nenhuma outra tabela do sistema).
- **Testado:** suíte completa sem alteração (270 testes, nada no backend mudou). Verificado com
  Playwright: clicar na célula de "Status" (não na caixinha) de 4 linhas diferentes marca as 4
  corretamente, clicar de novo desmarca, clicar no campo de texto do nome não interfere na seleção
  — e o fluxo completo (selecionar por clique na linha, escolher destino, excluir) excluiu as 3
  selecionadas corretamente, com o histórico reatribuído pro destino, confirmado direto no banco.
- **Em aberto (na época):** a causa real só foi confirmada na seção 4.41, abaixo — a Clara mesma
  encontrou o motivo de verdade.
- **Reversível:** sim — mudança isolada em `static/app.js`.

### 4.41 Bug (causa raiz real, encontrada pela Clara): hábito do ícone de lixeira por linha (2026-10-06)

Depois de três rodadas de investigação (seções 4.38-4.40, incluindo reproduzir contra Postgres
real sem achar nada de errado no backend), a própria Clara encontrou a causa: "Quando apago elas
eu clico em um único símbolo de lixo em uma única empresa, mesmo depois de selecionar todos os
que quero apagar." Ou seja — ela marcava as caixinhas de várias empresas, mas pra excluir clicava
no ícone de lixeira de UMA linha específica (o controle que já existia antes da seleção em massa
existir, hábito de uso anterior), em vez do botão "Excluir selecionadas" na barra azul. Esse ícone
sempre excluiu só aquela empresa — nunca leu a seleção em massa — então sempre "funcionava", só
que exclui exatamente 1, por design (não é um bug no sentido de comportamento incorreto: o ícone
fez exatamente o que sempre fez). Isso explica cada sintoma das rodadas anteriores: sem erro
(exclusão individual funciona normal), sempre exatamente 1 (sempre foi a exclusão de 1 empresa só,
nunca em massa de verdade), independente de quais empresas (não é dado-dependente, é hábito de
clique). O "demora bastante"/"Method Not Allowed ao recarregar" da rodada anterior foi uma pista
real mas secundária — não investigada a fundo porque a causa principal já foi resolvida aqui;
registrado como possível acompanhamento futuro se ela notar lentidão de novo.
- **Correção — `static/app.js`/`empresas.html`:** em vez de só confiar que a pessoa vai notar a
  barra de seleção, os ícones de lixeira de CADA linha agora ficam desativados (cinza, com
  `title` explicando o motivo) sempre que houver qualquer seleção em massa ativa (1 ou mais
  caixinhas marcadas) — tanto nas linhas selecionadas quanto nas não selecionadas. Isso torna
  fisicamente impossível repetir esse engano: ou a pessoa desmarca tudo e usa a lixeira individual
  normalmente, ou usa "Excluir selecionadas"/"Realocar selecionadas" pra lidar com o lote inteiro.
  Sem seleção ativa, os ícones continuam funcionando exatamente como sempre funcionaram.
- **Testado:** suíte completa sem alteração (270 testes — isso é só HTML/JS, backend intocado).
  Verificado com Playwright: lixeira habilitada sem seleção, desativada (nas 3 linhas, inclusive
  a não marcada) assim que 2 ficam marcadas, com o texto do `title` explicando, e reabilitada ao
  desmarcar tudo.
- **Reversível:** sim — mudança isolada em `static/app.js` + uma classe nova no botão existente
  em `empresas.html`; nenhuma rota ou lógica de serviço foi tocada.

### 4.42 Varredura de otimização/produtividade + tela de Auditoria (2026-10-08)

A Clara pediu uma varredura geral ("elevar o nível do sistema com foco em otimização e
produtividade"). Levantamento (sem mexer em nada ainda) encontrou 4 pontos: (1) `_contexto_base`
de Empresas roda 5 consultas por empresa cadastrada a cada carga de página (até 240 consultas só
pra calcular vínculos); (2) nenhuma das 5 tabelas com `empresa_cliente_id` tem índice nessa
coluna; (3) o log de auditoria (`LogAuditoria`/`services/auditoria.py::registrar`) é gravado desde
o início do projeto pra praticamente toda ação, mas não existe tela nenhuma pra consultar; (4)
nenhuma tela do sistema tem campo de busca/filtro de texto. Ela escolheu priorizar a (3) primeiro,
depois pediu pra fazer as 4 em ordem de dificuldade (mais fácil → mais difícil), parando uma a uma
pra ela confirmar antes de seguir pra próxima.

- **Tela nova: Auditoria** (`web/routes_auditoria.py`, `templates/auditoria.html`,
  `services/auditoria.py`) — área de Configuração, admin-only (mesmo padrão de Usuários/Empresas-
  clientes/Assistentes/Setores/Chamados, adicionada em `AREAS_CONFIGURACAO`). Lista paginada
  (50/página), mais recente primeiro, com filtro por usuário, ação (dropdown com as ações que já
  aconteceram de verdade — `acoes_distintas`, sem lista fixa pra não desatualizar) e período.
  `humanizar_acao()` converte o código interno (`EXCLUIU_EMPRESAS_EM_MASSA`) pro texto exibido
  ("Excluiu empresas em massa") com uma regra genérica (troca `_` por espaço, só a primeira letra
  maiúscula) — funciona pra qualquer uma das ~50 ações existentes ou futuras, sem precisar manter
  um dicionário de tradução.
- **`LogAuditoria` ganhou `index=True`** em `usuario_id`/`acao`/`criado_em` — é a tabela que mais
  cresce no sistema (toda ação grava uma linha, inclusive cada download de PDF/Excel), então os
  índices entraram já na primeira versão da tela, não só se ela ficasse lenta depois. Migração
  manual em `db.py::_garantir_indices_logs_auditoria` (mesmo padrão de
  `_garantir_indice_prazos_fatais`) — `index=True` no modelo só vale pra tabela criada do zero,
  produção já tem a tabela.
- **Bug real encontrado e corrigido antes de entregar:** o formulário de filtro é um GET normal —
  campos de usuário/data deixados em branco mandam string vazia (`usuario_id=&data_inicio=`) em
  vez de omitir o parâmetro, e o FastAPI recusava (422 `Method Not Allowed`-like, na verdade
  erro de validação) converter `""` direto pra `int`/`date` nos parâmetros da rota. Corrigido
  recebendo os 4 filtros como `str | None` e convertendo manualmente (string vazia = sem filtro).
  Pego durante a verificação com Playwright, antes de qualquer entrega — não chegou a acontecer
  em produção.
- **Testado:** `tests/test_auditoria.py` (16 testes — listar com cada filtro, paginação, página
  além do fim, `humanizar_acao`, `acoes_distintas`, tela exige admin, filtros pela URL, campos de
  filtro vazios). 283 testes no total, lint limpo. Verificado com Playwright: card novo aparece em
  Configuração, ações aparecem humanizadas com detalhes, filtro por usuário funciona.
- **Reversível:** sim — tudo aditivo (tabela já existia, só ganhou índice + tela de consulta);
  nenhum comportamento existente foi alterado.

### 4.43 Índices em `empresa_cliente_id` (item 2 da varredura) (2026-10-08)

Segundo item da varredura 4.42, na ordem de dificuldade que a Clara pediu (mais fácil primeiro).

- **O quê:** `index=True` em `empresa_cliente_id` nas 5 tabelas que têm essa coluna — `laudos`,
  `correspondencias`, `audiencias`, `cobrancas`, `processos`. É a consulta mais comum do sistema
  (todo relatório filtra por empresa; `contar_vinculos_empresa`/`_ENTIDADES_VINCULADAS` também) e
  nenhuma das 5 tinha índice nela — FK não ganha índice automático no Postgres (diferente da chave
  primária).
- **Migração:** `db.py::_garantir_indices_empresa_cliente_id`, mesmo padrão de
  `_garantir_indice_prazos_fatais`/`_garantir_indices_logs_auditoria` (`CREATE INDEX IF NOT
  EXISTS`, só Postgres, roda em todo startup). `index=True` no modelo não retroage sobre uma
  tabela que já existe em produção — por isso a migração manual.
- **Testado:** suíte completa sem alteração (283 testes — não é um comportamento observável em
  SQLite, só em Postgres). Verificado contra um Postgres real local (não só o SQLite dos testes):
  `init_db()` criando os 5 índices do zero, rodando duas vezes seguidas sem erro (idempotente), e
  — o cenário que replica produção de verdade — removendo os índices de tabelas já populadas e
  confirmando que a migração sozinha (sem recriar nada) os recria corretamente.
- **Reversível:** sim — índice é só um atalho de consulta, não muda nenhum dado nem comportamento
  visível; pode ser removido a qualquer momento sem perda.

### 4.44 Fim das consultas repetidas na tela de Empresas (item 1 da varredura) (2026-10-08)

Terceiro item da varredura 4.42, seguindo a ordem de dificuldade que a Clara pediu.

- **O quê:** `_contexto_base` (routes_empresas.py) montava `vinculos_por_empresa` chamando
  `contar_vinculos_empresa` uma vez PRA CADA empresa cadastrada (5 consultas por empresa — uma por
  tipo de vínculo) — com as 48 da lista oficial, até 240 consultas numa única carga de página,
  repetido a cada ação (editar, excluir, importar redireciona de volta pra essa mesma tela).
- **Correção — `services/empresas.py::contar_vinculos_todas_empresas`:** nova função que faz 5
  consultas agregadas (`GROUP BY empresa_cliente_id`), uma por tipo de vínculo, cobrindo TODAS as
  empresas de uma vez — sempre 5 consultas no total, não importa se há 1 ou 500 empresas
  cadastradas. `contar_vinculos_empresa` (a versão de uma empresa só) continua existindo sem
  alteração — ainda é a certa pra `excluir_empresa`/`realocar_empresas_em_massa`, que só
  precisam do total de UMA empresa por vez. `routes_empresas.py` trocou de uma pra outra; nenhuma
  mudança em `empresas.html` foi necessária (o template já tratava empresa ausente do dict como 0
  vínculos, que é exatamente o que a nova função também faz).
- **Testado:** 2 testes novos de serviço confirmando que o resultado da versão em lote bate com a
  soma da versão individual, e 1 teste novo que efetivamente conta quantas consultas SQL rodam
  numa carga de `/app/empresas` com 10 empresas cadastradas (usando o hook `before_cursor_execute`
  do SQLAlchemy) — garante abaixo de 15 consultas, bem longe do antigo "10 × 5 = 50", e serve de
  trava: se o padrão N+1 voltar algum dia, esse teste quebra mesmo que o resultado da tela
  continue visualmente idêntico. 286 testes no total, lint limpo. Verificado com Playwright que o
  aviso de "X registro(s) vinculado(s)" ao tentar excluir uma empresa continua exatamente igual.
- **Reversível:** sim — só uma função de consulta nova + troca de uma chamada; nenhum dado,
  template ou comportamento visível mudou.

### 4.45 Busca por nome/CNPJ em Empresas-clientes (item 4, último da varredura) (2026-10-08)

Último item da varredura 4.42, o mais trabalhoso.

- **O quê:** campo de busca no cabeçalho do card "Cadastradas" em Empresas-clientes — filtra as
  linhas por nome ou CNPJ enquanto digita, sem ir ao servidor (a lista inteira já está na página;
  com o volume atual isso é instantâneo). Ignora acento/maiúscula (mesma ideia de
  `app/utils.py::normalize`, reimplementada em JS). Mostra "Nenhuma empresa encontrada" quando o
  filtro não bate com nada.
- **Por que só Empresas por enquanto:** foi a tela que o levantamento (4.42) citou como exemplo
  concreto (48+ linhas, cresce com o tempo) — o padrão é simples e reaproveitável; dá pra levar
  pra outras listas (Usuários, por exemplo) depois, se a Clara quiser.
- **Integração com a seleção em massa (4.38/4.39):** "Selecionar todas" agora só marca as linhas
  visíveis no momento (mesma ideia já usada em Setores — `iniciarSelecionarTodosModulos`/
  `caixasVisiveis`) — filtrar por "ABSOLUTA" e clicar em "Selecionar todas" não marca,
  escondidas, as outras 47 empresas. Já a seleção em si não é desfeita por filtrar: marcar uma
  empresa, buscar por outro termo (que esconde a primeira) e marcar mais uma mantém as duas
  selecionadas — só a busca é visual, não mexe no que já foi marcado.
- **Testado:** suíte completa sem alteração (286 testes — mudança só em JS/CSS/HTML, nenhuma rota
  ou lógica de serviço tocada). Verificado com Playwright: busca sem acento encontra nome
  acentuado, busca por CNPJ parcial, mensagem de "nenhuma encontrada", limpar o campo mostra tudo
  de novo, e "Selecionar todas" com um filtro ativo marca só o que está visível.
- **Reversível:** sim — aditivo em `app.js`/`style.css`/`empresas.html`; nenhuma rota ou dado
  tocado.

## 5. Gerador de Relatórios Mensais das Assessorias

Novo módulo (2026-10-08, pedido da Clara), a partir de
`docs/especificacao-relatorios-assessorias.pdf` (ela anexou por upload — não está versionada no
repo). Objetivo: ler 6 planilhas enviadas uma vez por mês e gerar o relatório mensal de cada
assessoria (empresa-cliente ELITE) em .docx/.pdf, no layout do modelo atual
(`Relatório_EWS_8.docx`). Trabalho feito seguindo as 10 fases da especificação (Fase 0 a 9),
registradas abaixo.

### 5.1 Fase 0 — Reconhecimento e plano

Antes de ler a especificação, 4 bloqueios reais impediram começar — nenhum foi contornado sem a
Clara resolver:
1. A especificação não estava no repositório (ela precisou anexar via upload).
2. O repositório **não tem branch `main`** — confirmado por `git ls-remote` e pela API do GitHub
   (`list_branches`): só existe `claude/relatorios-arquitetura-auditoria-pewhu8`. A Clara confirmou
   usar essa branch mesmo (sem criar uma `feature/relatorios-assessorias` separada, já que não há
   `main` pra ramificar).
3 e 4. Os caminhos do modelo `.docx` e da pasta de planilhas vieram como placeholder literal no
   pedido original — resolvidos com upload direto na conversa.

**Achados da exploração do sistema atual:**
- Padrão de automação: `services/` (lógica) + `web/routes_X.py` (telas) + `api/X.py` (rotas
  externas PDF/Excel) + `templates/X.html`, registrados em `main.py`.
- Permissões: módulos ficam em `app.auth.MODULOS_OPERADORA` (ELITE/EXIMIA/None), gateados por
  setor; a área de Configuração (Usuários/Empresas/Setores/Chamados) é a exceção — só
  `papel_global in PAPEIS_GLOBAIS`, sem setor.
- Armazenamento: hoje nada fica em disco — PDF/Excel de Laudos etc. são gerados na hora e
  devolvidos direto na resposta HTTP; upload usa arquivo temporário do SO, descartado depois.
- **Não existe conversor de .docx pra PDF no sistema.** `pdf_export.py` desenha o PDF do zero com
  `reportlab` (texto, tabela, cabeçalho em código) — não converte um documento existente. Não há
  LibreOffice, não há `docxtpl`, não há `render.yaml`/`Dockerfile` no repo (Render configurado só
  pelo painel deles). Qualquer caminho docx→pdf pra esse módulo é infraestrutura nova.
- Dependências já presentes: `pandas`, `openpyxl`, `reportlab`. Novas, precisando aprovação:
  `docxtpl`, `matplotlib`, `holidays` (e o binário LibreOffice, se for o caminho escolhido pra PDF
  — não uma lib Python).
- Modelo `Relatório_EWS_8.docx` conferido contra a especificação: 16 tabelas, bate exatamente com
  as 4 seções + 2 mapas + listas + campos manuais descritos. Os erros de digitação que a
  especificação pede pra corrigir (`REFRÊNCIA`, `ASSESSSORIA`, `QUATIDADE`, `distribuidos`) estão
  todos lá, confirmados. Os números que a especificação já avisa que o modelo mostra errado (28 em
  vez de 27, 30 em vez de 29, 14 processos distribuídos sem origem) também batem — sem surpresa
  nova, só confirmação de que modelo e especificação são consistentes entre si.

**Decisões tomadas com a Clara (todas por pergunta explícita, nenhuma assumida):**

| # | Pergunta | Decisão |
|---|---|---|
| a | Prazo dos laudos | 7 dias úteis (demais tipos); 15 dias úteis CONSÓRCIO/LOTEAMENTO — confirmado |
| b | Faixas das Iniciais | "Até 7" e "8 a 20" (cobre todos os casos — diferente do modelo, que deixava 1-4 e 8-9 dias de fora) |
| c | Armazenamento do resultado mensal | Banco do sistema (Postgres, tabela nova e aditiva) |
| g | Onde ficam os arquivos gerados | Não ficam — .docx/.pdf/.zip gerados sob demanda a cada download, mesmo padrão de Laudos/Audiências hoje (disco do Render não é persistente entre deploys) |
| d | Conversor de PDF | LibreOffice headless (recomendação, pelo motivo abaixo) — pendente a Clara confirmar disponibilidade no Render antes da Fase 7; Fases 1-6 não dependem disso |
| e | Feriados | Biblioteca `holidays`, só nacionais (processos são de vários estados — feriado estadual/municipal ficaria complexo pra pouco ganho) |
| f | Quem acessa | Só admin por enquanto (`papel_global in PAPEIS_GLOBAIS`) — mesmo padrão de Configuração; resolve "deixar oculta até a liberação" sem precisar de flag separada |
| h | Cadastro de assessorias | YAML só pra apelidos; nome oficial e lista completa vêm de `EmpresaCliente` (já existe, 48 empresas — evita duas listas da mesma coisa fora de sincronia) |

**Sobre o conversor de PDF (pergunta d):** recomendei LibreOffice headless em vez de uma API
externa de conversão — enviar documentos com nome/processo/valor de cliente pra um serviço de
terceiro é mais um ponto de exposição LGPD, na contramão do cuidado que a Clara já pede em todo o
projeto, além de ter custo por conversão. LibreOffice headless é gratuito e mantém os dados dentro
do próprio servidor. Meu limite: não tenho como confirmar nem instalar isso no Render sozinho —
fica como decisão pendente, sem bloquear as Fases 1-6.

### 5.2 Incidente: planilhas reais commitadas e removidas do histórico

Durante a Fase 0, a Clara subiu as 6 planilhas reais (nomes, processos, valores) direto num commit
("Planilhas utilizadas") na branch — contradizendo a própria regra de LGPD do pedido original
("NÃO faça commit delas... pasta ignorada pelo Git"). Ver DECISIONS.md 2026-10-08 pro registro
completo: cópia local preservada em `dados_locais_nao_versionados/` (gitignored) antes de qualquer
remoção, estrutura das 6 planilhas conferida contra a especificação, commit removido do histórico
via `git reset --hard` (era a ponta da branch) + `git push --force-with-lease` — com aprovação
explícita da Clara pra essa operação especificamente. Confirmado via API do GitHub que o commit não
aparece mais no histórico.

### 5.3 Fase 1 — Estrutura e configuração

Módulo criado em `app/relatorio_assessorias/` (dentro do pacote `app` existente, não como um
pacote Python separado na raiz — adaptação pra caber na estrutura já usada por
`services/`/`web/`/`api/`, sem mudar o que a especificação descreve). Árvore igual à especificação:
`config/`, `leitores/`, `normalizacao/`, `secoes/`, mais `validacao.py`, `mapas.py`, `render.py`,
`armazenamento.py`, `templates/`, `assets/`. Cada arquivo-módulo tem só um docstring por enquanto,
descrevendo a responsabilidade dele (a lógica de verdade vem nas Fases 2-7) — nada de
implementação pela metade.

- **`config/__init__.py`**: `carregar(nome)` — único ponto que lê os YAMLs desta pasta (sem
  cache: arquivos pequenos, lidos poucas vezes por requisição, e não cachear evita servir versão
  antiga depois de editar com o servidor no ar).
- **`config/fontes.yaml`**: as 6 planilhas/7 fontes, transcrito direto da tabela da especificação
  (arquivo, padrão de leitura, aba, linha do cabeçalho, colunas e sinônimos).
- **`config/regras.yaml`**: prazos (7/15 dias úteis), faixas das Iniciais ("até 7"/"8 a 20"),
  status excluídos de Contrárias (ARQUIVADO) — os valores das decisões da Fase 0.
- **`config/assessorias.yaml`**: só apelidos (decisão "Cadastro de assessorias") — hoje só os 2
  exemplos que a própria especificação confirma (EWS/SW, WNR/WNR CONSULTORIA); o resto é
  descoberto empiricamente na Fase 3, rodando os leitores contra as planilhas reais e cruzando com
  `EmpresaCliente` — tentar adivinhar os 48 agora arriscaria dado errado silencioso.
- **`config/mapa_rotulos.yaml`**: posição dos rótulos dos 7 estados pequenos (RN, PB, PE, AL, SE,
  ES, RJ) e paletas de cor — marcado como placeholder explícito; coordenadas reais só dá pra
  ajustar olhando o PNG de verdade, na Fase 6.
- **Dependência nova**: `pyyaml` (adicionada a `requirements.txt`) — já estava disponível no
  ambiente por algum motivo indireto, mas não era uma dependência declarada do projeto; sem
  declarar, não haveria garantia de estar presente num ambiente novo/produção.
- **Testado**: `tests/test_relatorio_assessorias_config.py` (4 testes — cada YAML carrega e tem a
  estrutura esperada). Suíte completa do projeto rodada depois (290 testes, os 286 de antes +
  esses 4) — nada fora do módulo novo foi tocado. Lint limpo.
- **Reversível:** sim — módulo 100% novo e isolado; nenhuma rota, menu ou tabela existente foi
  alterada nesta fase.

### 5.4 Fase 2 — Leitores

Os três padrões de leitura da especificação, todos devolvendo `leitores/base.py::LinhaBruta`
(valores crus + `Origem(planilha, aba, linha)`) — nenhuma normalização ainda (Fase 3).

- **`leitores/base.py`** — núcleo compartilhado pelos três padrões:
  - `localizar_cabecalho`: procura, nas primeiras 10 linhas, a que contém todas as colunas
    esperadas (por sinônimo, via `app.utils.normalize` reaproveitado — mesma função já usada no
    resto do sistema pra comparar nome de empresa/tipo, sem reescrever a mesma lógica).
  - **Colunas duplicadas resolvidas sem código especial**: basta listar o mesmo sinônimo pras duas
    colunas canônicas em `fontes.yaml` (ex.: Laudos tem `data: ["DATA"]` e
    `data_pronto: ["DATA"]`) — `_achar_coluna` nunca reusa um índice de coluna já atribuído, então
    a 1ª ocorrência de "DATA" cai pra primeira canônica (na ordem em que aparecem no YAML) e a 2ª
    pra segunda. O mesmo mecanismo também resolve "usa a 1ª ocorrência" quando só UMA canônica
    aponta pra um nome que se repete (ex.: "EMPRESA" duas vezes em Judicial).
  - Coluna sem título (ex.: coluna A em JUDICIAL) via `colunas_fixas` no `fontes.yaml` — fica de
    fora da busca por cabeçalho, mapeada direto pro índice configurado.
  - Linha vazia e linha de título repetida no meio da aba são descartadas em `ler_linhas`.
  - Erros bloqueantes (`AbaNaoEncontrada`, `CabecalhoNaoEncontrado`) — vocabulário usado pelos 3
    padrões.
- **`leitores/aba_mensal.py`** (Laudos, Iniciais) — `encontrar_aba_do_mes` reconhece nome por
  extenso/abreviado + ano 2 ou 4 dígitos, com ou sem espaço; `encontrar_todas_abas_do_ano` (usado
  pela Fase 4, Iniciais, pra resolver "aguardando distribuição" cruzando meses).
- **`leitores/aba_unica.py`** (Judicial, Pauta da Semana Contrária, Agendamento) — sem código
  especial pras particularidades (coluna sem título, cabeçalho fora da linha 1, coluna duplicada
  usando a 1ª ocorrência): tudo já resolvido genericamente por `base.py` a partir do `fontes.yaml`.
- **`leitores/aba_por_assessoria.py`** (Contrárias, Procons) — lê toda aba cujo nome bate com
  algum apelido conhecido (recebe `{apelido: nome oficial}` já pronto — não acessa
  `EmpresaCliente`/banco diretamente, mantendo a camada de leitura independente); soma as linhas
  de abas diferentes que apontam pra mesma assessoria (EWS + SW). Aba de assessoria conhecida mas
  com coluna faltando levanta erro de verdade (não é silenciado) — só abas que não batem com
  nenhum apelido são ignoradas (não são abas de assessoria).

**Achado real ao validar contra as 6 planilhas (não só as fixtures pequenas dos testes):** a aba
EWS de `CONTRÁRIAS - NOVO.xlsx` usa `"N° DO PROCESSO"` com o símbolo de **grau** (°, U+00B0), não
`"Nº DO PROCESSO"` com o indicador **ordinal masculino** (º, U+00BA) que eu tinha posto em
`fontes.yaml` — visualmente quase idênticos, caracteres Unicode diferentes, então a normalização
de acento não unifica os dois. `fontes.yaml` corrigido com os dois sinônimos. Confirmado também:
o leitor de Laudos, rodado contra a planilha real de agosto/2026, já devolve **14 linhas para
EWS/SW sem nenhum cancelamento** — batendo exatamente com "Laudos elaborados no mês: 14" do
critério de aceite, mesmo sem nenhuma regra de negócio aplicada ainda (Fase 4) — é a leitura crua
já correta pra esse caso específico (Laudos não precisa de filtro de data além de "está na aba do
mês certo", diferente de Iniciais/Judicial/Contrárias, que ainda precisam de filtro de período —
por isso os números brutos dessas outras fontes ainda não batem com o critério, como esperado
nesta fase).

**Testado:** `tests/test_relatorio_assessorias_leitores.py`, 29 testes — cada regra de
`base.py` isolada (cabeçalho em várias posições, sinônimo, colunas duplicadas por posição, coluna
fixa, linha vazia, título repetido, origem), reconhecimento flexível de aba do mês (todos os
formatos, com/sem acento), e um teste de ponta a ponta por padrão com planilha pequena construída
em memória. Além disso, validação manual (não committada — só local) rodando os 4 leitores contra
as 6 planilhas reais de agosto/2026, confirmando leitura sem erro em todas e o achado do símbolo
de grau acima. Suíte completa do projeto: 319 testes (290 de antes + 29 novos), lint limpo.

**Reversível:** sim — módulo 100% novo e isolado; nenhuma rota, menu, tabela ou comportamento
existente foi tocado.

### 5.5 Fase 3 — Normalização

Cinco funções puras `bruto → dataclass(valor, aviso?)`, cada uma num módulo próprio de
`normalizacao/`, consumindo `LinhaBruta.valores` da Fase 2 — nenhuma delas acessa planilha ou
`Origem` diretamente (isso é responsabilidade de quem chama, nas Fases 4+, que já tem a origem
pra anexar ao aviso).

- **`normalizacao/datas.py`** — aceita `datetime`/`date`, serial do Excel (base `1899-12-30`, por
  causa do bug de ano bissexto de 1900 que o Lotus 1-2-3 tinha e o Excel manteve por
  compatibilidade) e texto `dd/mm/aaaa` (com ou sem `- hh:mm`, hora descartada). Antes de
  escrever o parser, confirmei direto no openpyxl que uma célula com "serial fora do limite pra
  data" chega como a **string `"#VALUE!"`** (erro do próprio Excel), não como um número fora do
  intervalo — então o parser cobre os dois jeitos de dar errado (texto não reconhecido E serial
  numérico inválido) em vez de só um. Data fora de 2020-2030 fica com **aviso mas mantém o
  valor** (sinaliza pra conferência, não zera nem bloqueia — leitura literal da especificação).
- **`normalizacao/valores.py`** — formato brasileiro (1.234,56) vs americano (1,234.56) decidido
  pela posição do ÚLTIMO separador; texto não numérico (ex.: "NÃO INFORMADO", ou "TRABALHISTA"
  vazado de outra coluna, visto em dado real) vira `nao_informado=True` **sem aviso** — é caso de
  negócio esperado, não erro. Valor devolvido como `float` (não `Decimal`), pra bater com a
  convenção já usada no resto do sistema (`Laudo.valor`, `Cobranca.valor` etc. são `Float`);
  `app.utils.format_brl`, que já existe, é reaproveitado na renderização (Fase 7) em vez de
  duplicar formatação aqui.
- **`normalizacao/processo.py`** — chave de comparação = só os dígitos (usada pela deduplicação
  por CNJ entre Contrárias e Procon, Fase 4); com exatamente 20 dígitos, reformata no padrão CNJ
  (`NNNNNNN-DD.AAAA.J.TR.OOOO`); diferente de 20, mantém o texto original e avisa quantos dígitos
  encontrou, sem tentar adivinhar o que falta.
- **`normalizacao/texto.py`** — `normalizar_nome` só colapsa espaço, mantém grafia (diferente da
  normalização ESTRUTURAL de `app.utils.normalize`, que ignora acento/caixa e serve pra COMPARAR
  nome de coluna/aba/assessoria, não pra exibir); `normalizar_uf` maiusculiza e valida contra as
  27 UFs.
- **`normalizacao/assessoria.py`** — único módulo desta fase que acessa banco:
  `construir_nomes_por_apelido(db)` combina `EmpresaCliente.nome` (lista oficial, decisão da Fase
  0) com os apelidos de `config/assessorias.yaml`, usando a mesma normalização estrutural de
  `app.utils.normalize`; `resolver(bruto, nomes_por_apelido)` separa célula com mais de uma
  empresa (`/`, `,` ou ` E `) e devolve os nomes oficiais resolvidos + os fragmentos não
  reconhecidos (vira aviso global agregado na Fase 4, não aqui — este módulo só resolve uma
  célula por vez).

**Validado contra as 6 planilhas reais** (local, não committado): Laudos de agosto/2026 geraram
só 7 avisos de data em 780 linhas — todos problemas reais e esperados ("14/O8/2026" com letra O
no lugar de zero, "3108/2026" sem separador, "25/08/0202" ano trocado, célula malformada que
chega como `"#VALUE!"`) — nenhum crash, nenhum valor silenciosamente errado. Contrárias EWS/SW:
confirmado que "TRABALHISTA" vazado na coluna de valor (dado real) vira `nao_informado=True` sem
aviso, como projetado. Procons: números de protocolo administrativo (não-CNJ, ex.: "MP",
"11110/2025") corretamente avisados com a contagem de dígitos, sem tentar forçar formato CNJ.

**Testado:** `tests/test_relatorio_assessorias_normalizacao.py`, 42 testes — um por função,
cobrindo os valores problemáticos literais da especificação ("R$ 53.128,60\t", "$64,000.00",
"21800.0", "R$15.295,68.", "NÃO INFORMADO", "TRABALHISTA", "2026.0", "--", processo com ponto no
lugar de hífen/dígito faltando/espaço-tab no início, nome com tab, UF vazia/minúscula/inválida) +
casos de `assessoria.py` (apelido batendo com `EmpresaCliente` cadastrada via fixture `db`,
apelido órfão ignorado, célula multi-empresa nos 3 separadores). Suíte completa do projeto: 361
testes (319 de antes + 42 novos), lint limpo.

**Reversível:** sim — módulo 100% novo e isolado; nenhuma rota, menu, tabela ou comportamento
existente foi tocado.

### 5.6 Fase 4 — Seções

Os 7 módulos de `secoes/` (laudos, iniciais, extrajudiciais, judiciais — serve as duas fontes de
audiência, judicial e contrária —, contrarias, procons, manuais), cada um com uma função
`calcular(linhas, ...)` que recebe `LinhaBruta` já filtradas pra uma assessoria (e, no caso de
Iniciais, de todas as abas do ano) e devolve um dataclass com os números, listas e avisos daquela
seção. `manuais.py` não tem `calcular` — só define o formato dos campos digitados na tela de
revisão (Fase 8).

Peças novas de apoio, compartilhadas entre seções:
- **`dias_uteis.py`** — conta dias úteis via `holidays.Brazil` (nova dependência, só feriados
  nacionais, decisão da Fase 0). Convenção adotada (sem número do critério de aceite pra testar
  diretamente): dias úteis "entre" duas datas = estritamente depois do início, até o fim
  inclusive — `início == fim` conta 0. **Sinalizado pra confirmação da Clara.**
- **`avisos.py`** — `Aviso(origem, mensagem)`, o tipo usado por todo `secoes/` pra marcar linha
  com problema sem bloquear a seção.
- **`datas_utilitarias.py`** — limites de mês (`primeiro_dia_do_mes`, `ultimo_dia_do_mes`,
  `dentro_do_mes`), evitando repetir a conta em cada seção.
- **`normalizacao/assessoria.py::filtrar_linhas`** — novo (Fase 4): filtra uma lista de
  `LinhaBruta` pras que pertencem a uma assessoria, resolvendo o campo de empresa de cada linha
  (usa `resolver`, já existente da Fase 3). Usado pelas fontes de `aba_mensal`/`aba_unica`
  (Contrárias/Procons não precisam, porque `aba_por_assessoria.ler` já agrupa por assessoria).
- **Dedup entre arquivos (Contrárias × Procon):** `secoes/contrarias.py::calcular` aceita
  `chaves_cnj_de_outras_fontes` opcional — quem orquestra as seções (Fase 8) pode passar as
  chaves CNJ já vistas no Procon, pra um processo TRABALHISTA listado nos dois arquivos não contar
  duas vezes. Testado isoladamente; não teve efeito nos dados de agosto/2026 (sem sobreposição
  real nas 6 planilhas), mas o parâmetro existe pro caso geral.

**Validado contra as 6 planilhas reais (EWS, agosto/2026, corte 04/09/2026) — comparação direta
com a tabela de critérios de aceite da especificação:**

| Campo | Esperado | Obtido |
|---|---|---|
| Laudos elaborados no mês | 14 | **14** ✅ |
| Extrajudiciais enviadas no mês | 16 | **16** ✅ |
| Extrajudiciais realizadas no mês | 10 | **10** ✅ |
| Extrajudiciais pendentes | 19 | **19** ✅ |
| Clientes ausentes | 1 (Antonio Beserra da Costa) | **1 (Antonio Beserra da Costa)** ✅ |
| Audiências judiciais (acumulado no ano) | 11 | **10** ❌ — ver abaixo |
| Audiências contrárias (acumulado no ano) | 5 | **5** ✅ |
| Contrárias judiciais (ativos) | 27 | **27** ✅ |
| Contrárias trabalhistas (ativos) | 2 | **2** ✅ |
| Contrárias ativos total | 29 | **29** ✅ |
| Contrárias ativos RJ (mapa) | 3 | **3** ✅ |
| Processos distribuídos no mês (Iniciais) | 2 | **2** ✅ |

11 de 12 números batem exatamente. Dois ajustes reais encontrados na validação (corrigidos, não
forçados):
- **`fontes.yaml`, Iniciais:** a coluna de recebimento muda de nome entre abas do mesmo arquivo —
  "DATA DE RECEBIMENTO" só em agosto/2026, "DATA RECEBIDO" na maioria dos outros meses, "DATA" em
  junho/2026. Como Iniciais lê todas as abas do ano (não só a do mês de referência), os três
  sinônimos precisaram entrar.
- **`assessorias.yaml`:** a Pauta da Semana Contrária tem uma célula `"SW EWS"` (linha 40) — as
  duas grafias juntas, sem separador (nem `/`, `,` nem ` E `, os três documentados na
  especificação). Em vez de alargar a lógica geral de separação de células com múltiplas empresas
  (arriscado: um espaço como separador quebraria nomes com espaço de verdade, tipo "WN FAST"),
  `"SW EWS"` virou um apelido literal de EWS — mesmo mecanismo já usado pra outras variações de
  nome, sem tocar em `normalizacao/assessoria.py`. Resolveu Audiências contrárias (4 → 5) sem
  afetar nada mais.

**Não bate, investigado, não forçado:** Audiências judiciais deu 10, não 11. As 12 linhas da aba
JUDICIAL com empresa "SW" (nenhuma com "EWS" nem variação composta) foram conferidas uma a uma:
10 têm data entre 01/01/2026 e 04/09/2026 (as duas de fora: 22/09 e 01/10, depois da data de
corte). Testado contra as duas cópias disponíveis do arquivo (a de `dados_locais_nao_versionados`
e a enviada antes, com 3 linhas de diferença no total da aba) — mesmo resultado nas duas. Não
achei nenhuma 13ª linha, célula composta tipo "SW EWS" (conferido também na 2ª coluna "EMPRESA"
da aba, que na verdade guarda o nome da(o) advogada(o), não uma 2ª empresa) nem padrão de
herança de linha em branco que explicasse a diferença. Fica pra Clara decidir — talvez a
planilha tenha mudado desde que ela validou os números originalmente.

**Testado:** `tests/test_relatorio_assessorias_secoes.py`, 27 testes — um conjunto por seção,
com `LinhaBruta` construídas diretamente (equivalente a fixtures pequenas: o que entra numa seção
é sempre essa lista de linhas já lidas, não um arquivo .xlsx). Validação manual (não committada)
contra as 6 planilhas reais, como acima. Suíte completa: 384 testes, lint limpo.

**Reversível:** sim — módulo 100% novo e isolado; nenhuma rota, menu, tabela ou comportamento
existente foi tocado. Nova dependência: `holidays` (adicionada a `requirements.txt`), puro Python,
sem acesso à rede em produção (cálculo de feriados é local).
