# Auditoria do sistema — melhorias identificadas

Auditoria somente de leitura (nenhum arquivo de código, configuração, banco ou dependência foi
alterado). Cobriu: Laudos, Gestão de Processos, Audiências, Pendências, Cartas,
Correspondências, Relatório Mensal das Assessorias, Configuração (Usuários, Empresas-clientes,
Setores, Funcionários), autenticação/permissões, infraestrutura/dependências e frontend
(templates, CSS, JS).

Metodologia: revisão direta dos arquivos centrais (modelos, autenticação, banco, geração de
PDF/Excel, módulo de relatórios de assessorias) + 5 revisões especializadas em paralelo por área.
Teste de referência roda limpo: **426 testes passam, 0 falham** (`pytest`), `ruff check` sem
nenhum apontamento. Nenhuma senha, chave de API ou token foi encontrado hardcoded no código.

---

## 1. Resumo executivo

**Estado geral do sistema:** sólido. O código é incomum em qualidade para um sistema desse porte
— comentários extensos explicam o "porquê" de decisões de design, vários bugs de produção
passados estão documentados em `DECISIONS.md` com a correção aplicada, há 426 testes passando e
zero problema de segurança grave (sem segredo exposto, sem SQL injection, sem execução de código
arbitrário, permissões checadas de forma consistente em praticamente toda rota revisada). Os
problemas encontrados são, em sua maioria, do tipo "lacuna pontual" ou "padrão já corrigido uma
vez em outro módulo e não replicado" — não falhas estruturais.

**Os itens mais importantes, em linguagem simples:**

1. **Os links "Baixar PDF" e "Baixar Excel" de Laudos (e dois filtros de Processos) estão
   quebrados para o filtro padrão de status** — o relatório volta vazio (R$ 0,00) sem avisar
   nada, por um caractere especial (`+`) no nome do status que não é codificado corretamente no
   link. Confirmado e reproduzido de ponta a ponta nesta auditoria. É o item de maior impacto e
   mais barato de corrigir de toda a lista — prioridade máxima. **(M01)**
2. Duas colunas de texto livre (`Cobranca.tipo_cobranca`, `Laudo.nome_cliente`/`tipo_laudo_nome`)
   ainda não foram convertidas para o tipo "sem limite" que já corrigiu, três vezes, o mesmo
   travamento em produção (`StringDataRightTruncation`) em colunas-irmãs. É só repetir uma
   correção já aplicada e documentada. **(M02)**
3. Todo upload de planilha (Laudos, Processos, Audiências, Pendências, Correspondências,
   Relatório de Assessorias — 12 pontos no total) grava o arquivo num diretório temporário e
   **nunca apaga**. Isso é tanto um problema de disco crescendo sem limite quanto uma questão de
   LGPD (nome de cliente, CPF, número de processo ficam fora do controle de acesso do banco,
   indefinidamente). **(M03)**
4. Toda navegação de usuários que não são Admin Superior/T.I. dispara hoje cerca de 10 consultas
   extras ao banco por página carregada (checagem de módulos/operadoras), o mesmo tipo de
   problema de performance que já foi identificado e corrigido uma vez em outro lugar do sistema
   (Empresas-clientes), mas não nesse. **(M04)**
5. Se algum cliente passar de 100 audiências cobráveis em um mês, a geração do relatório de
   Audiências para esse cliente simplesmente para de funcionar o resto do mês, sem nenhuma tela
   para corrigir — só editando o banco diretamente. **(M05)**
6. Não há confirmação (documento testado e com restore verificado) de que o banco de produção
   tem backup automático — o próprio time já tinha essa pendência registrada antes desta
   auditoria. **(M06)**
7. Não existe limite de tentativas de login (força bruta teoricamente viável, mitigado hoje pelo
   volume baixo de usuários — já é uma decisão conhecida do time, não uma surpresa). **(M08)**
8. Falta CORS/cabeçalhos de segurança básicos (CSP, X-Frame-Options) em todas as respostas HTML.
   **(M09)**
9. Uma validação que já existe na API (não aceitar um papel de usuário inválido) não existe na
   tela equivalente — só é explorável por quem já é admin e manda a requisição manualmente, não
   é um risco de invasão, mas é uma lacuna de consistência de dados. **(M10)**
10. Cinco telas de upload têm uma caixa de arrastar-arquivo que pode ultrapassar a largura da
    tela em celular, e cinco tabelas (inclusive a lista principal de usuários) não têm barra de
    rolagem horizontal própria — ambos problemas puramente visuais em telas estreitas. **(M26,
    M27)**

**Nenhum dos itens encontrados é um incidente em andamento ou uma brecha de segurança crítica
exposta publicamente.** O item M01 já pode estar afetando a cobrança/controle real de Laudos hoje
(todo relatório gerado pelo botão padrão da tela, sem trocar o filtro de status, está vindo
vazio) — vale verificar com prioridade.

### Contagem de itens por prioridade sugerida

| Prioridade | Quantidade |
|---|---|
| Crítica | 1 |
| Alta | 5 |
| Média | 25 |
| Baixa | 12 |
| **Total** | **43** |

---

## 2. Tabela completa de itens (M01–M43)

Ordenada da prioridade mais alta para a mais baixa.

| ID | Área | Categoria | Descrição | Onde (arquivo:linha) | Impacto | Esforço | Risco de implementar | Prioridade |
|---|---|---|---|---|---|---|---|---|
| M01 | Laudos / Gestão de Processos | Bug | Links de download sem `\|urlencode`: filtro padrão de status quebra o relatório silenciosamente | `app/templates/laudos.html:68,72`; `app/templates/processos.html:108,112,190,194` | Alto | Pequeno | Baixo | **Crítica** |
| M02 | Laudos / Pendências | Bug latente / Integridade | Colunas `VARCHAR` ainda sujeitas ao mesmo truncamento que já quebrou produção 3x | `app/models.py:70,72` (`Laudo`), `:156` (`Cobranca.tipo_cobranca`) | Médio-Alto | Pequeno | Baixo | Alta |
| M03 | Transversal (uploads) | Confiabilidade / LGPD | Arquivo de upload nunca é apagado do disco temporário (12 pontos de upload) | `app/api/_shared.py:4-7` + 12 chamadores | Médio | Pequeno | Baixo | Alta |
| M04 | Configuração / Transversal | Performance | N+1 de consultas em toda navegação web de usuário não-admin (módulos/operadoras) | `app/auth.py:133-199`, chamado via `app/web/menu.py:12` | Médio-Alto | Médio | Baixo | Alta |
| M05 | Audiências | Confiabilidade | Faixa de preço de audiências limitada a 100/mês sem tela para ampliar | `app/db.py:37-43`, `app/services/audiencias.py:160-164` | Médio | Médio-Grande | Médio | Alta |
| M06 | Infraestrutura | Infra | Sem confirmação/teste de backup-restore do banco de produção | `SECURITY.md` (pendência já registrada) | Alto | Médio | Baixo | Alta |
| M07 | Configuração | Segurança | Token de sessão guardado em texto puro na chave primária, sem hash | `app/models.py` (`Sessao.token`), `app/auth.py:91-99` | Médio | Médio | Médio | Média |
| M08 | Configuração | Segurança | Sem limite de tentativas de login (rate limiting/lockout) | `app/api/auth.py:45-54`, `app/web/routes_auth.py:30-51` | Médio | Pequeno | Baixo | Média |
| M09 | Transversal | Segurança | Sem CORS middleware / cabeçalhos de segurança (CSP, X-Frame-Options, HSTS) | `app/main.py` (nenhum middleware desse tipo) | Baixo-Médio | Pequeno | Baixo | Média |
| M10 | Configuração | Bug / Integridade | Validação de `papel_global` ausente nas rotas **web** de usuário (já existe na API) | `app/web/routes_usuarios.py:58,102` vs `app/api/usuarios.py:168,207` | Baixo | Pequeno | Baixo | Média |
| M11 | Configuração | Confiabilidade | Sessões expiradas nunca são removidas da tabela `Sessao` | `app/models.py`/`app/auth.py` (nenhuma rotina de limpeza) | Baixo-Médio | Pequeno | Baixo | Média |
| M12 | Audiências | Integridade | CNPJ pode ser sobrescrito via parâmetro da API sem validação nem registro | `app/services/audiencias.py:172,203` | Médio | Pequeno | Baixo | Média |
| M13 | Audiências | Bug | Parâmetro `quinzena` com valor inválido é tratado como "2ª quinzena" silenciosamente | `app/services/audiencias.py:31-35` | Médio | Pequeno | Baixo | Média |
| M14 | Audiências | Integridade | CPF não normalizado na deduplicação (nome é normalizado, CPF não) | `app/services/audiencias.py:76,98` | Baixo-Médio | Pequeno | Baixo | Média |
| M15 | Correspondências | Bug / Integridade | Comparação do "mês" é sensível a acento, diferente do resto do módulo | `app/services/correspondencias.py:178` | Baixo-Médio | Pequeno | Baixo | Média |
| M16 | Configuração | Integridade / Qualidade | Validador de CNPJ já existe no sistema mas não é reaproveitado no cadastro de Empresas | `app/services/cartas.py:67` vs `app/services/empresas.py:163-191` | Baixo-Médio | Pequeno | Baixo | Média |
| M17 | Infraestrutura | Dependências | `requirements.txt` sem lockfile e sem scanner de vulnerabilidade no CI | `backend/requirements.txt`, `.github/workflows/backend-ci.yml` | Médio | Pequeno | Baixo | Média |
| M18 | Infraestrutura | Infra | Sem ambiente de homologação nem procedimento de rollback documentado | `ARCHITECTURE.md`/`ROADMAP.md` (ausente) | Médio | Médio | Baixo | Média |
| M19 | Laudos | Performance / Qualidade | Importação de Laudos sem commit incremental (Processos já corrigiu o mesmo risco) | `app/services/laudos.py:81-154` vs `app/services/processos.py:330-331` | Baixo-Médio | Pequeno | Baixo | Média |
| M20 | Configuração | Integridade / Performance | Checagem de nome duplicado (Empresas/Funcionários) é varredura completa em Python + janela de corrida | `app/services/empresas.py:163-191,128-151`, `app/services/funcionarios.py:22-45` | Baixo | Médio | Baixo | Média |
| M21 | Audiências / Pendências / Correspondências | Performance / Qualidade | Busca de empresa por nome duplicada 3x como varredura linear sem índice | `app/services/audiencias.py:174-180`, `pendencias.py:208-215`, `correspondencias.py:165-170` | Baixo | Médio | Baixo | Média |
| M22 | Configuração | Performance | Exclusão de empresas em massa não reaproveita otimização já existente para contagem de vínculos | `app/services/empresas.py:249-277` | Baixo | Pequeno-Médio | Baixo | Média |
| M23 | Relatório de Assessorias | UX | Tela de upload (6 arquivos) não usa o padrão visual de upload das outras 5 telas | `app/templates/relatorio_assessorias_upload.html:41-61` | Médio | Médio | Baixo | Média |
| M24 | Configuração | UX | Exclusão/realocação em massa de empresas sem exigir digitar palavra de confirmação (diferente de ações igualmente destrutivas) | `app/templates/empresas.html:131-187` | Médio | Pequeno | Baixo | Média |
| M25 | Gestão de Processos | UX | "Marcar resolvido" (prazo fatal) é irreversível e não pede confirmação | `app/templates/processos.html:47-51`, `app/services/processos.py:359-366` | Médio | Pequeno | Baixo | Média |
| M26 | Configuração / Laudos / Audiências | UX | 5 tabelas sem `.tabela-wrap` — sem rolagem horizontal em tela estreita | `usuarios.html` (3x), `audiencias.html:81`, `laudos.html:87` | Médio | Pequeno | Baixo | Média |
| M27 | Transversal (uploads) | UX | Caixa de upload pode ultrapassar a largura da tela em celular (5 telas) | `app/static/style.css:999` sem ajuste no `@media (max-width:860px)` | Médio | Pequeno | Baixo | Média |
| M28 | Configuração | Acessibilidade | Caixas de seleção de setor sem rótulo/`aria-label` | `app/templates/usuarios.html:90,150` | Médio | Pequeno | Baixo | Média |
| M29 | Cartas / Audiências / Pendências / Gestão de Processos | Testes | Lacunas de cobertura na camada de API (Cartas sem nenhum teste de API; Audiências/Pendências só testam permissão, não conteúdo; Processos sem `test_api_processos.py`) | `app/api/cartas.py`, `app/api/audiencias.py`, `app/api/pendencias.py`, `app/api/processos.py` | Médio | Médio | Baixo | Média |
| M30 | Configuração | Testes | Rotas web de Usuários/Setores/Funcionários sem testes próprios (só a API é testada) | `app/web/routes_{usuarios,setores,funcionarios}.py` | Médio | Médio | Baixo | Média |
| M31 | Gestão de Processos / Laudos | Testes | Funções operacionalmente críticas sem nenhum teste: alerta de prazo fatal e deduplicação de Laudos | `app/services/processos.py:633-660` (`prazos_proximos`), `app/services/laudos.py:95-98,136-138` | Médio | Médio | Baixo | Média |
| M32 | Audiências | Confiabilidade | Mês/ano fora do intervalo válido escapa do tratamento de erro amigável | `app/web/routes_audiencias.py:55`, `app/api/audiencias.py:58-60,90-92,114-116` | Baixo | Pequeno | Baixo | Baixa |
| M33 | Cartas | Confiabilidade / UX | Hora em formato inválido mostra erro técnico em inglês ao usuário | `app/services/cartas.py:31-34` | Baixo | Pequeno | Baixo | Baixa |
| M34 | Configuração | Integridade | E-mail sem validação de formato no backend (só no HTML) | `app/api/usuarios.py:30,38`, `app/api/auth.py:23` | Baixo | Pequeno | Baixo | Baixa |
| M35 | Infraestrutura | Infra | Versão fixa do Python (`runtime.txt`) com ~2 anos de patches de segurança não aplicados | `backend/runtime.txt` | Baixo-Médio | Pequeno | Baixo | Baixa |
| M36 | Infraestrutura | Infra | Sem `Dockerfile`/`render.yaml` versionado — configuração de deploy só no painel do Render | (ausente no repositório) | Médio | Médio | Baixo | Baixa |
| M37 | Transversal | Segurança | CSRF sem defesa em profundidade além do `SameSite=Lax` do cookie | `app/web/auth.py:41-54` | Baixo | Médio | Médio | Baixa |
| M38 | Configuração | UX | Desativar usuário não tem confirmação nem destaque visual de ação de risco | `app/templates/usuarios.html:38-42` | Baixo | Pequeno | Baixo | Baixa |
| M39 | Gestão de Processos | UX | Rótulo "Empresa" em vez de "Empresa-cliente", inconsistente com as outras 4 telas de filtro | `app/templates/processos.html:81` | Baixo | Pequeno | Baixo | Baixa |
| M40 | Frontend (transversal) | Qualidade | Duplicação de estilo/lógica no frontend: `style="..."` repetido em 8+ arquivos, função JS duplicada, bloco CSS de modo escuro repetido | `app/static/app.js` (`caixasVisiveis`), `app/static/style.css:40-93`, 8+ templates | Baixo | Pequeno-Médio | Baixo | Baixa |
| M41 | Gestão de Processos | Qualidade (código morto) | Catálogo `TipoEvento`/`tipos_evento_cadastrados()` nunca usado em lugar nenhum | `app/models.py` (`TipoEvento`), `app/services/processos.py:355-356` | Baixo | Pequeno | Baixo | Baixa |
| M42 | Audiências | Qualidade (código morto) | `AudienciasResult.valor_cadastrado` sempre `True` — condição que o tornaria `False` já vira erro antes | `app/services/audiencias.py:143,193-196,209` | Baixo | Pequeno | Baixo | Baixa |
| M43 | Audiências | Qualidade | Erros de regra de negócio (ex.: faixa de preço não cadastrada) voltam como HTTP 404, igual a "não encontrado" | `app/api/audiencias.py:61-62` e equivalentes `.pdf`/`.xlsx` | Baixo | Pequeno | Baixo | Baixa |

---

## 3. Detalhe por item

### M01 — Links de download sem `urlencode` quebram o relatório silenciosamente — **Crítica**
**O que está acontecendo:** os links "Baixar PDF"/"Baixar Excel" em `laudos.html` (e os filtros
de empresa/assistente em `processos.html`) são montados por interpolação direta no HTML
(`href="/laudos/relatorio.pdf?...&status={{ filtro.status }}"`), sem o filtro `| urlencode` que o
próprio sistema já usa para o mesmo propósito em `relatorio_assessorias_painel.html`.

**Por que é um problema:** a opção padrão de status é `"Solicitação + Corrigido (cobrança)"` —
contém um `+` literal. O navegador não altera esse caractere ao montar a URL, mas o servidor
(parsing padrão de query string) interpreta `+` como espaço. O status chega como
`"Solicitação   Corrigido (cobrança)"`, que não bate com nenhuma opção cadastrada — o relatório
retorna 0 linhas e R$ 0,00, sem nenhum aviso. Foi reproduzido ponta a ponta nesta auditoria:
com o link correto (`urlencode`), o mesmo laudo aparece (total R$ 40,00); com o link como está
hoje, o total vem zerado. Isso não foi pego por nenhum teste existente porque os testes de API
chamam a rota com parâmetros já corretamente codificados (via `httpx`), não through o HTML real.

**Solução proposta:** adicionar `| urlencode` em `empresa`, `status` (e, por consistência,
`ano`/`mes`/`assistente`) nos links de download de `laudos.html` e `processos.html`.

**Dependências:** nenhuma — correção isolada e imediata.

---

### M02 — Colunas `VARCHAR` ainda sujeitas ao truncamento que já quebrou produção 3 vezes — Alta
**O que está acontecendo:** `Laudo.nome_cliente` (`VARCHAR(200)`), `Laudo.tipo_laudo_nome`
(`VARCHAR(60)`) e `Cobranca.tipo_cobranca` (`VARCHAR(200)`) continuam com limite de tamanho, vindo
de colunas de planilha em texto livre.

**Por que é um problema:** `DECISIONS.md` documenta pelo menos três incidentes reais de produção
em que um valor de planilha (nome de cliente, advogada, tipo de evento) excedeu o limite de uma
coluna `VARCHAR` e quebrou a importação inteira com `StringDataRightTruncation` — cada vez
corrigido convertendo a coluna para `Text` (sem limite). Essas três colunas de Laudos/Pendências
vêm do mesmo tipo de planilha, da mesma equipe, e nunca passaram pela mesma correção — é só uma
questão de tempo até um nome de cliente ou tipo de cobrança mais longo repetir o incidente. Em
Laudos o risco é agravado por não haver commit incremental na importação (ver M19): um único
valor problemático derruba o lote inteiro.

**Solução proposta:** converter as três colunas para `Text`, seguindo exatamente o padrão já
usado nas correções anteriores (sem mudança de comportamento, só remove o limite).

**Dependências:** nenhuma técnica; é uma migração de schema simples (`ALTER COLUMN ... TYPE
TEXT`), no mesmo estilo dos `_garantir_*` já existentes em `app/db.py`.

---

### M03 — Arquivos de upload nunca são apagados do disco — Alta
**O que está acontecendo:** `app/api/_shared.py::salvar_temp` grava cada planilha enviada
(`.xlsx`) com `tempfile.NamedTemporaryFile(delete=False, ...)` e nenhum dos 12 pontos de chamada
(`app/api/{audiencias,pendencias,correspondencias,processos,laudos}.py`,
`app/web/routes_{laudos,relatorio_assessorias,processos,pendencias,audiencias,correspondencias}.py`)
remove o arquivo depois de processá-lo.

**Por que é um problema:** cada upload cria um arquivo temporário permanente no disco do
container — nomes de clientes, CPFs, números de processo e valores ficam fora do banco de dados
(sem os controles de acesso/auditoria que o banco tem) e nunca são removidos. Com uso frequente,
isso é um crescimento silencioso de disco (que no Render é limitado), além de uma exposição de
dados pessoais sem necessidade — exatamente o tipo de ponto que a Clara pediu para olhar sob a
ótica de LGPD.

**Solução proposta:** trocar `delete=False` + esquecer por um `try/finally` com `os.remove()`
depois do processamento (ou um `tempfile.TemporaryDirectory()` como context manager envolvendo
todo o fluxo de upload) em cada um dos 12 pontos.

**Dependências:** nenhuma — é o mesmo padrão em todos os 12 lugares, pode ser uma função utilitária
única reaproveitada.

---

### M04 — N+1 de consultas em toda navegação web para usuário não-admin — Alta
**O que está acontecendo:** `modulos_acessiveis`/`operadoras_acessiveis`
(`app/auth.py:133-199`), chamadas por `itens_menu` (`app/web/menu.py:12`) em praticamente toda
rota de tela (via `_contexto_base`), fazem, para cada setor do usuário, um lazy-load de `Setor`,
um lazy-load de `Operadora` e uma consulta separada em `SetorModulo` — para um usuário em 3
setores isso é algo como 10 consultas, repetidas em toda navegação, não só em relatórios pesados.

**Por que é um problema:** é exatamente o mesmo padrão de N+1 que o próprio projeto já identificou
e corrigiu uma vez (`contar_vinculos_todas_empresas`, comentário documentando a otimização de
240→5 consultas), só que aqui ainda não foi aplicado — e afeta a maioria dos usuários (todos que
não são Admin Superior/T.I.) em toda página que carregam, não só uma tela específica.

**Solução proposta:** usar `selectinload(UsuarioSetor.setor).selectinload(Setor.operadora)` e uma
única consulta agregada em `SetorModulo`, ou cachear o resultado por requisição (o menu já é
montado uma vez por request).

**Dependências:** nenhuma — é uma otimização isolada em duas funções.

---

### M05 — Faixa de preço de audiências limitada a 100/mês sem tela para ampliar — Alta
**O que está acontecendo:** `app/db.py:37-43` cadastra exatamente 5 faixas de preço cobrindo de 1
a 100 audiências por mês; não existe rota, API nem tela em lugar nenhum do sistema para
criar/editar/listar `FaixaAudiencia` (confirmado por busca em todo o código).

**Por que é um problema:** se qualquer cliente acumular mais de 100 audiências cobráveis em um
mês, `gerar_relatorio` levanta um erro ("Não existe faixa de preço cadastrada...") e a geração do
relatório daquele cliente para de funcionar pelo resto do mês — sem nenhuma tela para a Clara
corrigir, só editando o banco diretamente.

**Solução proposta:** uma tela administrativa simples de CRUD para `FaixaAudiencia` (lista +
criar/editar faixa), do mesmo padrão das telas de Configuração já existentes.

**Dependências:** nenhuma técnica — mas vale confirmar com a Clara se 100/mês é um limite que
algum cliente já está perto de atingir (ver Pergunta correspondente).

---

### M06 — Sem confirmação/teste de backup-restore do banco de produção — Alta
**O que está acontecendo:** não há, em nenhum documento do repositório, confirmação de que o
plano do Supabase usado em produção tem backup automático, nem qualquer menção a um teste de
restore já realizado. O próprio `SECURITY.md` já lista isso como pendência em aberto.

**Por que é um problema:** o banco guarda dados pessoais (CPF, nomes) e dados comerciais de
dezenas de empresas-clientes; sem um backup testado, qualquer perda de dados (erro humano, falha
do provedor, bug de migração) é irreversível.

**Solução proposta:** verificar no painel do Supabase se o plano atual oferece backup
automático/point-in-time recovery; caso não, avaliar upgrade de plano ou uma rotina própria de
`pg_dump` periódico; fazer pelo menos um teste de restore real para validar o processo.

**Dependências:** depende do plano contratado no Supabase — ação primeiro administrativa, não
só de código.

---

### M07 — Token de sessão em texto puro na chave primária — Média
**O que está acontecendo:** `Sessao.token` é gravado e lido diretamente (sem hash) como chave
primária da tabela.

**Por que é um problema:** qualquer leitura do banco (backup exposto, dump, acesso indevido de
quem tem acesso ao banco) entrega o token pronto para uso — ao contrário de senhas (que usam
bcrypt), o token de sessão é o próprio segredo. A entropia do token é boa (256 bits), então o
risco é de vazamento do armazenamento, não de força bruta.

**Solução proposta:** guardar `sha256(token)` como chave, comparando pelo hash; o valor original
continua existindo só no cookie/resposta do login, nunca no banco.

**Dependências:** migração de schema (nova coluna/chave) + ajuste dos dois pontos que leem
`Sessao` por token (`app/auth.py`, `app/web/auth.py`).

---

### M08 — Sem limite de tentativas de login — Média
**O que está acontecendo:** nenhuma das duas rotas de login (`POST /auth/login`, `POST /login`)
tem qualquer bloqueio por tentativas repetidas; falhas só são registradas em log de auditoria
(`LOGIN_FALHOU`), sem travar nada.

**Por que é um problema:** um ataque de força bruta contra uma senha fraca é teoricamente
viável; o custo do bcrypt ajuda, mas não impede tentativa automatizada distribuída. O próprio
`SECURITY.md` já registra essa decisão como consciente, dado o volume baixo de usuários (10-20)
— o item fica aqui para que a Clara decida se continua aceitando esse risco ou se vale endurecer.

**Solução proposta:** um contador simples por e-mail/IP (ex.: bloquear por alguns minutos após 5
tentativas falhas), ou a biblioteca `slowapi`.

**Dependências:** nenhuma.

---

### M09 — Sem CORS/cabeçalhos de segurança básicos — Média
**O que está acontecendo:** `app/main.py` não tem `CORSMiddleware` nem nenhum middleware que
define `Content-Security-Policy`, `X-Frame-Options` ou `Strict-Transport-Security`.

**Por que é um problema:** como a sessão web usa cookie com `SameSite=Lax`, a ausência de CORS
não abre uma brecha óbvia hoje (não há frontend separado cross-origin), mas a falta de
`X-Frame-Options`/CSP é uma defesa padrão contra clickjacking para qualquer sistema com sessão
por cookie — hoje ausente.

**Solução proposta:** middleware simples de 5-10 linhas adicionando esses cabeçalhos em toda
resposta.

**Dependências:** nenhuma.

---

### M10 — Validação de papel de usuário ausente nas rotas web — Média
**O que está acontecendo:** `app/web/routes_usuarios.py` (criar/editar usuário) salva
`papel_global` direto do formulário sem checar se o valor está entre os papéis válidos
(`ADMIN_SUPERIOR`/`ADMIN_TI`/vazio) — a API equivalente (`app/api/usuarios.py`) já faz essa
checagem.

**Por que é um problema:** a tela só oferece um `<select>` com valores válidos, então não é
explorável por um usuário comum da interface — mas qualquer POST manual (ou um bug futuro no
template) grava um `papel_global` arbitrário, criando um usuário "quebrado": nem admin, nem
comum reconhecido.

**Solução proposta:** replicar a mesma checagem (`if papel_global not in PAPEIS_GLOBAIS: erro`)
já existente na rota de API.

**Dependências:** nenhuma.

---

### M11 — Sessões expiradas nunca são removidas — Média
**O que está acontecendo:** não existe rotina (cron, tarefa de início do servidor, comando) que
apague linhas de `Sessao` com `expira_em` no passado.

**Por que é um problema:** a tabela cresce indefinidamente — uma linha por login, válida por 12h,
nunca removida depois de expirar. Não trava o sistema rapidamente, mas é uma tabela sem limite de
crescimento, nunca podada.

**Solução proposta:** uma rotina simples (`DELETE FROM sessoes WHERE expira_em < now()`),
executada no início do servidor (mesmo padrão dos `_garantir_*` de `app/db.py`) ou periodicamente.

**Dependências:** nenhuma.

---

### M12 — CNPJ sobrescrevível via parâmetro da API sem validação — Média
**O que está acontecendo:** a API de relatório de Audiências aceita um parâmetro `cnpj` que
substitui o CNPJ real da empresa no PDF/Excel/JSON gerado, sem validação de formato e sem
registro em log de auditoria. Não é alcançável pela tela web (o formulário nunca envia esse
parâmetro), só por quem chama a API diretamente.

**Por que é um problema:** qualquer usuário autenticado com acesso ao módulo Audiências pode
fazer o relatório oficial mostrar um CNPJ diferente do cadastrado, sem rastro.

**Solução proposta:** remover a possibilidade de sobrescrever (sempre usar o CNPJ cadastrado), ou,
se houver um motivo de negócio para a sobrescrita, validar o formato e registrar a divergência no
log de auditoria.

**Dependências:** depende de confirmar a intenção original (ver Pergunta correspondente).

---

### M13 — Parâmetro `quinzena` inválido tratado como "2ª quinzena" — Média
**O que está acontecendo:** `periodo_quinzenal` (`app/services/audiencias.py:31-35`) só checa
`quinzena == 1`; qualquer outro valor (`0`, `3`, `99`...) cai no `else` e devolve o período da 2ª
quinzena, sem erro.

**Por que é um problema:** a tela web só oferece 1 ou 2, mas a API aceita um inteiro livre — uma
chamada externa com erro de digitação recebe, silenciosamente, o período e o valor errados, sem
nenhuma indicação de que algo está errado.

**Solução proposta:** validar explicitamente `quinzena in (1, 2)`, levantando erro claro para
qualquer outro valor.

**Dependências:** nenhuma.

---

### M14 — CPF não normalizado na deduplicação de Audiência — Média
**O que está acontecendo:** a chave de deduplicação de `Audiencia`
(`app/services/audiencias.py:76,98`) normaliza o nome do cliente (sem acento, maiúsculo), mas só
faz `.strip()` no CPF — sem remover pontuação.

**Por que é um problema:** reimportar a mesma pessoa com o CPF formatado diferente entre uma
planilha e outra (`"123.456.789-01"` vs `"12345678901"`) é tratado como um registro diferente,
criando uma duplicata silenciosa que infla a contagem usada para calcular a faixa de cobrança.

**Solução proposta:** normalizar o CPF para só dígitos antes de comparar (reaproveitando o mesmo
padrão de regex já usado em `app/services/cartas.py`).

**Dependências:** nenhuma.

---

### M15 — Comparação de "mês" sensível a acento em Correspondências — Média
**O que está acontecendo:** `app/services/correspondencias.py:178` compara o mês com
`.strip().upper()` simples, enquanto a comparação de nome de empresa no mesmo módulo já usa a
função `normalize()` (que remove acentos).

**Por que é um problema:** se uma célula da planilha importada tiver `"MARCO"` sem o acento
(plausível, já há outros erros de digitação documentados no sistema, como "FATALISSIMO"), o
relatório simplesmente mostra "Nenhuma correspondência encontrada" mesmo havendo linhas
correspondentes — um erro silencioso de relatório vazio.

**Solução proposta:** aplicar `normalize()` também na comparação de mês, tanto na importação
quanto na consulta.

**Dependências:** nenhuma.

---

### M16 — Validador de CNPJ existente não reaproveitado no cadastro de Empresas — Média
**O que está acontecendo:** `app/services/cartas.py:67` já define `cnpj_valido()` (checa os
dígitos verificadores), mas `app/services/empresas.py` (criar/atualizar empresa) não valida o
CNPJ de forma alguma — qualquer texto é aceito.

**Por que é um problema:** um CNPJ incorreto cadastrado aparece depois em relatórios e PDFs
oficiais; o validador que resolveria isso já existe no mesmo código-base, só não é reaproveitado.

**Solução proposta:** mover `cnpj_valido()` para `app/utils.py` (ou importar diretamente) e usá-lo
em `criar_empresa`/`atualizar_empresa`.

**Dependências:** nenhuma.

---

### M17 — Dependências sem lockfile e sem scanner de vulnerabilidade no CI — Média
**O que está acontecendo:** `requirements.txt` só usa `>=` (sem versão travada, sem lockfile); o
CI roda apenas `ruff check` e `pytest`, sem `pip-audit`/Dependabot.

**Por que é um problema:** builds não são reprodutíveis (uma dependência pode subir de versão a
qualquer novo deploy sem revisão) e uma biblioteca com vulnerabilidade conhecida pode entrar em
produção sem ningém notar.

**Solução proposta:** gerar um `requirements-lock.txt` via `pip freeze` (ou migrar para
`pip-tools`/`uv`), e adicionar `pip-audit` como passo do CI.

**Dependências:** nenhuma.

---

### M18 — Sem ambiente de homologação nem rollback documentado — Média
**O que está acontecendo:** toda a documentação do projeto só menciona produção; não há branch
de homologação, ambiente de teste com dados reais, nem um procedimento de rollback documentado
além do nativo do Render.

**Por que é um problema:** o histórico do projeto já registra incidentes reais de mudança de
schema/import quebrando em produção — sem um ambiente intermediário, o primeiro lugar onde um
problema aparece é na frente da Clara.

**Solução proposta:** documentar pelo menos um procedimento de rollback passo a passo; avaliar se
o plano gratuito do Render permite um segundo serviço de homologação sem custo.

**Dependências:** depende do plano do Render (limitação de custo, não de código).

---

### M19 — Importação de Laudos sem commit incremental — Média
**O que está acontecendo:** `processos.py` já comita a cada 2000 linhas novas (comentário
explicando que evita uma transação gigante aberta no pooler do Supabase); `laudos.py` faz um
único commit no final do loop inteiro.

**Por que é um problema:** se uma linha no meio de um lote grande falhar (por exemplo, pelo
truncamento do item M02), o lote inteiro é revertido — o mesmo risco que já foi corrigido em
Processos, mas não espelhado em Laudos.

**Solução proposta:** replicar o mesmo padrão de commit incremental usado em `processos.py`.

**Dependências:** nenhuma; reduz o risco prático do item M02 em Laudos.

---

### M20 — Checagem de nome duplicado: varredura completa + corrida — Média
**O que está acontecendo:** `criar_empresa`/`atualizar_empresa`/`get_or_create_empresa`
(`app/services/empresas.py`) e as funções equivalentes de Funcionários carregam todas as linhas
da tabela em Python para comparar nomes normalizados (sem acento) — a constraint `unique` do
banco é sensível a acento/maiúscula, então não cobre esse caso.

**Por que é um problema:** é uma varredura O(n) por chamada (hoje barato, ~48-100 linhas); mais
importante, como a checagem e a inserção não são atômicas, duas requisições simultâneas criando
"Absoluta" e "ABSOLUTA" podem ambas passar pela checagem e ambas inserir — criando duas empresas
"iguais" pela regra de negócio.

**Solução proposta:** uma constraint funcional no banco (índice único sobre a versão normalizada
do nome) ou tratamento de `IntegrityError` com retry.

**Dependências:** nenhuma; é um cenário de baixa probabilidade (cadastro não é uma ação de alta
concorrência).

---

### M21 — Busca de empresa por nome duplicada 3 vezes sem índice — Média
**O que está acontecendo:** `app/services/audiencias.py`, `pendencias.py` e
`correspondencias.py` implementam, cada um separadamente, a mesma busca: carregar todas as
`EmpresaCliente` e comparar nome normalizado uma a uma — a cada requisição de relatório, não só
na importação (onde já existe um cache).

**Por que é um problema:** é a mesma lógica copiada 3 vezes em vez de uma função compartilhada;
não é lento hoje, mas não escala se o cadastro de empresas crescer, e qualquer correção futura
precisa ser replicada nos 3 lugares.

**Solução proposta:** extrair um único helper (`resolver_empresa_por_nome`) reaproveitado nos 3
módulos.

**Dependências:** nenhuma.

---

### M22 — Exclusão de empresas em massa não reaproveita otimização existente — Média
**O que está acontecendo:** `excluir_empresas_em_massa` chama `excluir_empresa` (que faz 5
consultas de contagem de vínculos) uma vez por empresa selecionada, mais um commit por empresa —
quando a própria função `contar_vinculos_todas_empresas` (já existente, criada justamente para
evitar esse padrão) poderia pré-calcular tudo de uma vez.

**Por que é um problema:** para listas grandes (ex.: excluir as ~48 empresas da lista oficial),
é N×5 consultas + N commits — o mesmo tipo de problema que o próprio projeto já corrigiu uma vez
em outro fluxo.

**Solução proposta:** usar `contar_vinculos_todas_empresas` para pré-calcular os vínculos antes do
loop de exclusão.

**Dependências:** nenhuma.

---

### M23 — Tela de upload do Relatório de Assessorias sem padrão visual de upload — Média
**O que está acontecendo:** as 5 telas de upload existentes (Pendências, Audiências,
Correspondências, Laudos, Processos) usam uma zona de arrastar-arquivo com confirmação visual
(fica verde, mostra o nome do arquivo escolhido); a tela do Relatório de Assessorias, com 6
campos de arquivo obrigatórios, usa inputs nativos simples, sem esse padrão.

**Por que é um problema:** com 6 arquivos para escolher, a ausência de confirmação visual por
campo é mais sensível a erro (anexar o arquivo errado no campo errado) do que nas outras telas,
que têm só 1 campo.

**Solução proposta:** reaproveitar o mesmo HTML/JS (`data-upload`/`upload-zona`) já usado nas
outras telas, para os 6 campos.

**Dependências:** nenhuma.

---

### M24 — Exclusão/realocação em massa de empresas sem confirmação de texto — Média
**O que está acontecendo:** os modais "Excluir selecionadas" e "Realocar em massa"
(`empresas.html`) não exigem digitar uma palavra de confirmação, diferente de "Sincronizar com a
lista oficial" e "Excluir todas as inativas", que exigem.

**Por que é um problema:** excluir/realocar um conjunto de empresas escolhido pelo usuário é, em
alcance, potencialmente mais arriscado que as duas ações que já têm a barreira extra — um clique
apressado é suficiente para apagar o histórico de várias empresas de uma vez.

**Solução proposta:** aplicar o mesmo mecanismo (`data-confirmar-texto`, já existente em
`app.js`) aos dois modais.

**Dependências:** nenhuma.

---

### M25 — "Marcar resolvido" em prazo fatal é irreversível e sem confirmação — Média
**O que está acontecendo:** o botão "Marcar resolvido" num prazo fatal (`processos.html:47-51`)
é um envio de formulário simples, sem modal de confirmação; `resolvido`/`resolvido_em` nunca
voltam a `False` em nenhum fluxo do sistema — não existe "reabrir".

**Por que é um problema:** um clique errado remove permanentemente um item da lista de alertas de
prazo fatal (dado jurídico sensível a tempo), sem forma de desfazer a não ser intervenção direta
no banco.

**Solução proposta:** adicionar o mesmo modal de confirmação usado em outras ações, e considerar
uma ação de "reabrir" para desfazer um marcado por engano.

**Dependências:** nenhuma.

---

### M26 — Tabelas sem rolagem horizontal própria em tela estreita — Média
**O que está acontecendo:** a lista principal de Usuários (e duas tabelas de setor dentro da
mesma tela), além das tabelas de resultado de Audiências e Laudos, não estão dentro de
`<div class="tabela-wrap">` (que já é o padrão usado em todas as outras telas de listagem do
sistema).

**Por que é um problema:** em tela estreita, essas tabelas não têm a barra de rolagem horizontal
que o resto do sistema já tem — o conteúdo só pode se espremer, sem escape.

**Solução proposta:** envolver as 5 tabelas na mesma `div.tabela-wrap` já usada em todo o resto do
sistema (nenhum CSS novo necessário).

**Dependências:** nenhuma.

---

### M27 — Caixa de upload pode ultrapassar a largura da tela em celular — Média
**O que está acontecendo:** `.upload-label` tem `min-width: 320px` fixo, sem ajuste dentro do
bloco `@media (max-width: 860px)` já existente no CSS.

**Por que é um problema:** em um celular com ~360-390px de largura, depois da margem lateral e do
padding do card, o espaço disponível fica abaixo de 320px — a caixa de upload (e possivelmente a
página) ultrapassa a tela horizontalmente, em 5 telas de upload.

**Solução proposta:** adicionar `min-width: 0` (ou um valor menor) para `.upload-label` dentro do
`@media` já existente.

**Dependências:** nenhuma.

---

### M28 — Caixas de seleção de setor sem rótulo de acessibilidade — Média
**O que está acontecendo:** as caixas de seleção de setor em `usuarios.html` (tela de edição e
de novo usuário) não têm `<label>` nem `aria-label` — o cabeçalho da coluna é vazio.

**Por que é um problema:** um leitor de tela anuncia essas caixas sem nenhuma descrição; a mesma
necessidade em `empresas.html` (seleção em massa) já está corretamente resolvida com
`aria-label`.

**Solução proposta:** adicionar `aria-label="Vincular ao setor {{ s.nome }}"` em cada caixa.

**Dependências:** nenhuma.

---

### M29 — Lacunas de cobertura de teste na camada de API — Média
**O que está acontecendo:** as rotas de API (`Authorization: Bearer`, usadas por qualquer
integração externa) de Cartas não têm nenhum teste; as de Audiências e Pendências só testam
permissão (403/filtro), nunca o conteúdo da resposta; não existe `test_api_processos.py`.

**Por que é um problema:** é exatamente a camada que uma integração externa (não a tela web)
usaria — um bug introduzido ali não seria pego pelos testes de tela.

**Solução proposta:** criar `test_api_cartas.py`/`test_api_processos.py`, e estender os testes de
Audiências/Pendências para checar o conteúdo da resposta, no padrão já usado em
`test_api_correspondencias.py`.

**Dependências:** nenhuma.

---

### M30 — Rotas web administrativas sem testes próprios — Média
**O que está acontecendo:** não existe `test_web_usuarios.py`, `test_web_setores.py` nem testes
para `app/web/routes_funcionarios.py` — só a API equivalente é testada
(`tests/test_permissoes.py`).

**Por que é um problema:** é exatamente por isso que o item M10 (validação de papel de usuário
ausente na rota web) não foi pego por nenhum teste existente.

**Solução proposta:** replicar os casos de `test_permissoes.py` para as rotas web equivalentes.

**Dependências:** o teste do item M10 só tem sentido depois (ou junto) da correção desse item.

---

### M31 — Funções operacionalmente críticas sem nenhum teste — Média
**O que está acontecendo:** `prazos_proximos()` (alimenta o painel "Prazos próximos" mostrado em
toda tela de Processos, e a API equivalente) não tem nenhum teste; a deduplicação na
reimportação de Laudos também não (Processos tem 4 testes equivalentes para o mesmo tipo de
situação).

**Por que é um problema:** `prazos_proximos` é, possivelmente, a função mais sensível do módulo
de Processos (alerta de prazo fatal, dado jurídico) e está sem qualquer rede de segurança
automatizada.

**Solução proposta:** escrever testes básicos de limite (prazo exatamente em 30 dias, já vencido,
sem data) para `prazos_proximos`, e um teste de reimportação para Laudos no mesmo padrão dos 4 já
existentes em Processos.

**Dependências:** nenhuma.

---

### M32 — Mês/ano fora do intervalo escapa do tratamento de erro amigável — Baixa
**O que está acontecendo:** a chamada a `periodo_quinzenal` em `routes_audiencias.py` e nas 3
rotas de API de Audiências fica fora do bloco `try/except ValueError` que trata outros erros de
validação — `mes=13` ou `mes=0` levanta um erro não capturado ali.

**Por que é um problema:** o handler global de exceção do sistema já evita uma tela de erro crua,
mas a mensagem específica e amigável que outras validações do mesmo sistema dão é perdida nesse
caso.

**Solução proposta:** mover a chamada para dentro do bloco `try`, ou validar `mes`/`ano` antes.

**Dependências:** nenhuma.

---

### M33 — Erro de hora inválida em inglês técnico — Baixa
**O que está acontecendo:** `formatar_hora` (`app/services/cartas.py:31-34`) deixa escapar um
`ValueError` padrão do Python ("not enough values to unpack...") para campos de hora malformados,
diferente dos outros validadores do mesmo arquivo, que já têm mensagem em português.

**Por que é um problema:** o campo `<input type="time">` do navegador normalmente evita isso, mas
a API e os endpoints de "/texto" aceitam a hora como texto livre, então qualquer chamador externo
encontra facilmente essa mensagem técnica.

**Solução proposta:** envolver em uma mensagem clara em português, no mesmo padrão dos outros
validadores do arquivo.

**Dependências:** nenhuma.

---

### M34 — E-mail sem validação de formato no backend — Baixa
**O que está acontecendo:** os campos de e-mail nas rotas de API (`usuarios.py`, `auth.py`) são
tipados como `str` simples, não `EmailStr` do Pydantic; o único controle é o atributo HTML
`type="email"` do lado do navegador.

**Por que é um problema:** qualquer string sem `@` é aceita como "e-mail" de um usuário via POST
direto.

**Solução proposta:** trocar para `EmailStr` nas rotas de API.

**Dependências:** nenhuma.

---

### M35 — Versão fixa do Python com ~2 anos de patches de segurança não aplicados — Baixa
**O que está acontecendo:** `runtime.txt` fixa `python-3.12.7` (lançada por volta de
outubro/2024); o CI usa a última versão 3.12.x disponível, diferente da produção.

**Por que é um problema:** a série 3.12 já passou por vários releases de patch desde então
(normalmente incluindo correções de segurança do CPython); fixar uma versão de ~2 anos atrás
significa não aproveitar essas correções, e CI/produção podem estar em patches diferentes sem
ninguém notar.

**Solução proposta:** atualizar para a última versão de patch 3.12.x disponível.

**Dependências:** nenhuma.

---

### M36 — Sem `Dockerfile`/`render.yaml` versionado — Baixa
**O que está acontecendo:** não há `Dockerfile` nem `render.yaml` no repositório — toda a
configuração de build/start/variáveis de ambiente do Render vive só no painel deles, já
documentado como decisão deliberada em `ARCHITECTURE.md`.

**Por que é um problema:** essa configuração não tem controle de versão nem histórico de quem
mudou o quê — perder acesso ao painel do Render significa perder essa configuração sem backup em
código.

**Solução proposta:** migrar para um `render.yaml` versionado, mantendo o mesmo comportamento de
hoje.

**Dependências:** é uma mudança de infraestrutura, não de código da aplicação — vale planejar
separado do resto.

---

### M37 — CSRF sem defesa em profundidade além do `SameSite=Lax` — Baixa
**O que está acontecendo:** nenhuma rota que muda estado (`/app/empresas/...`,
`/app/usuarios/...`, etc.) tem token CSRF — a proteção depende inteiramente do cookie
`SameSite=Lax`.

**Por que é um problema:** `SameSite=Lax` já bloqueia o vetor clássico de CSRF (formulário
cross-site com POST), então o risco prático hoje é baixo — mas é uma dependência única (sem
defesa em profundidade): um bug de navegador, ou uma rota futura que aceite GET para mudança de
estado, abriria a porta.

**Solução proposta:** considerar token CSRF nos formulários mais sensíveis (exclusão em massa,
mudança de papel de usuário), como defesa adicional.

**Dependências:** nenhuma; risco já mitigado hoje, prioridade baixa.

---

### M38 — Desativar usuário sem confirmação nem destaque de risco — Baixa
**O que está acontecendo:** o botão "Desativar" de um usuário (`usuarios.html:38-42`) usa estilo
neutro, sem confirmação, diferente do "Desativar" de empresas/setores (que já usa estilo de
perigo).

**Por que é um problema:** desativar um usuário corta o acesso de um colega imediatamente — hoje
sem nenhuma barreira extra, embora seja reversível (pode reativar depois).

**Solução proposta:** aplicar o mesmo estilo de "ação de risco" já usado em outras telas.

**Dependências:** nenhuma.

---

### M39 — Rótulo "Empresa" inconsistente com "Empresa-cliente" — Baixa
**O que está acontecendo:** o filtro de relatório de Processos usa o rótulo "Empresa", enquanto o
mesmo campo nas outras 4 telas de filtro (Pendências, Audiências, Correspondências, Laudos) usa
"Empresa-cliente".

**Solução proposta:** renomear o rótulo em `processos.html` para "Empresa-cliente".

**Dependências:** nenhuma.

---

### M40 — Duplicação de estilo/lógica no frontend — Baixa
**O que está acontecendo:** o mesmo `style="padding:7px 12px; font-size:0.8rem;"` é copiado em
8+ templates; a função `caixasVisiveis()` em `app.js` está implementada duas vezes de forma quase
idêntica; o bloco de variáveis CSS do modo escuro é repetido byte-a-byte em dois lugares.

**Por que é um problema:** qualquer ajuste futuro de tamanho/espaçamento ou de cor do modo escuro
precisa ser replicado manualmente em vários lugares, com risco de divergência silenciosa.

**Solução proposta:** introduzir uma classe utilitária para o estilo repetido, extrair um helper
compartilhado para `caixasVisiveis()`.

**Dependências:** nenhuma; a duplicação do CSS de modo escuro pode ser intencional — confirmar
antes (ver Pergunta correspondente).

---

### M41 — Catálogo `TipoEvento` nunca usado — Baixa
**O que está acontecendo:** o modelo `TipoEvento` e a função `tipos_evento_cadastrados()`
(`app/services/processos.py:355-356`) são seedados no banco mas nunca lidos por nenhuma rota,
tela ou teste.

**Solução proposta:** confirmar com a Clara se é scaffolding de uma funcionalidade nunca
finalizada (ver Pergunta correspondente) antes de remover.

**Dependências:** depende da resposta da pergunta correspondente.

---

### M42 — `valor_cadastrado` de Audiências é código morto — Baixa
**O que está acontecendo:** o campo `AudienciasResult.valor_cadastrado` é calculado como
`faixa is not None or not clientes`, mas a linha anterior já levanta um erro sempre que essa
condição seria `False` — ou seja, na prática o campo é sempre `True`, e não é lido por nenhum
template, PDF ou Excel.

**Solução proposta:** remover o campo, a menos que a intenção original fosse avisar (como o campo
equivalente de Laudos faz) em vez de bloquear — nesse caso, redesenhar para ser realmente
alcançável.

**Dependências:** nenhuma.

---

### M43 — Erro de regra de negócio retorna HTTP 404 — Baixa
**O que está acontecendo:** qualquer `ValueError` do cálculo de relatório de Audiências
(incluindo "empresa não encontrada", que é de fato um 404, e "faixa de preço não cadastrada", que
é uma regra de negócio) é mapeado para o mesmo código HTTP 404.

**Solução proposta:** diferenciar "recurso não encontrado" (404) de "erro de regra de negócio"
(ex.: 422), para quem consome a API conseguir distinguir os dois casos.

**Dependências:** nenhuma.

---

## 4. Ganhos rápidos (alto impacto + baixo esforço)

| ID | Item | Por que vale a pena primeiro |
|---|---|---|
| M01 | Links de download sem `urlencode` | Maior impacto de toda a lista, correção de poucas linhas, risco de implementar baixo |
| M02 | Colunas VARCHAR sujeitas a truncamento | Mesma correção já aplicada 3x em outras colunas — só repetir o padrão conhecido |
| M03 | Arquivos temporários de upload nunca apagados | Afeta LGPD e disco em 12 pontos ao mesmo tempo, com uma correção simples e repetível |
| M10 | Validação de papel de usuário ausente na rota web | Já existe pronta na API — é copiar a mesma checagem |
| M16 | Validador de CNPJ já existe mas não é reaproveitado | Já existe pronto em outro módulo — é só importar |
| M26 | Tabelas sem rolagem horizontal | Envolver em uma `div` já existente, sem CSS novo |
| M27 | Caixa de upload ultrapassa tela em celular | Um ajuste de CSS dentro de um `@media` que já existe |
| M28 | Checkboxes sem rótulo de acessibilidade | Adicionar `aria-label`, sem mudança de comportamento |
| M09 | Sem CORS/cabeçalhos de segurança | Middleware pequeno e padrão, sem mudança de comportamento visível |

---

## 5. Perguntas (intenção não clara — aguardando confirmação da Clara antes de tratar como problema)

1. **Convenção de contagem de dias úteis** (Laudos e Iniciais do Relatório de Assessorias,
   `app/relatorio_assessorias/dias_uteis.py`): foi adotada a convenção "dias úteis decorridos a
   partir do dia seguinte à data inicial", mas isso nunca foi confirmado diretamente com nenhum
   número do critério de aceite — já estava sinalizado como pendente desde a Fase 4 do próprio
   módulo.
2. **Faixa de preço de Audiências limitada a 100/mês (M05):** é um limite conhecido e aceito, ou
   simplesmente nenhum cliente ainda chegou perto disso e a tela de ampliação nunca foi
   priorizada?
3. **Parâmetro `cnpj` sobrescrevível na API de Audiências (M12):** existe algum motivo de negócio
   para permitir essa sobrescrita (por exemplo, empresa sem CNPJ cadastrado), ou é um resquício
   sem uso real hoje?
4. **Catálogo `TipoEvento` nunca finalizado (M41):** era para validar/alertar "tipo de evento não
   cadastrado" do mesmo jeito que `TipoLaudo` já faz para Laudos, e a integração ficou pela
   metade, ou é scaffolding seguro de remover?
5. **Reimportação de Laudos não atualiza o status de uma linha já existente** (chave de
   deduplicação não inclui status, `app/services/laudos.py:95-98,136-138`): é intencional (porque
   um laudo "Corrigido" sempre chega com uma data diferente na planilha real, tornando-se uma
   linha nova por natureza), ou é uma lacuna que Processos já resolveu para o caso equivalente e
   Laudos deveria espelhar?
6. **Duplicação do bloco de variáveis CSS do modo escuro** (`style.css:40-93`, repetido
   byte-a-byte entre `prefers-color-scheme` e `data-theme="dark"`): foi deliberado, para os dois
   gatilhos (preferência do sistema vs. escolha manual) ficarem independentes, ou um compartilhamento
   seria preferível?
7. **"Sobrescrever um número" na tela de revisão do Relatório de Assessorias** não tem nenhuma
   confirmação antes de salvar (diferente de toda ação de exclusão em massa do sistema, que exige
   confirmação) — o texto da tela já avisa que a mudança fica registrada no log de auditoria;
   isso foi considerado suficiente como proteção (auditoria como rede de segurança), ou faltou
   adicionar uma confirmação também aqui?
8. **Dados pessoais de `Usuario` sem mecanismo de anonimização:** hoje um usuário só pode ser
   desativado, nunca removido ou anonimizado — nome/e-mail ficam permanentemente, inclusive
   referenciados por log de auditoria e chamados de suporte (chave estrangeira obrigatória). Isso
   pode ser uma decisão consciente (preservar o rastro de "quem fez o quê" é, em si, um requisito
   de negócio legítimo que entra em tensão com o "direito ao esquecimento" da LGPD), mas não há
   nenhum comentário no código confirmando isso — diferente de outras decisões do projeto, que
   costumam vir documentadas. Vale confirmar se é necessário um fluxo de anonimização (ex.:
   substituir nome/e-mail por um identificador genérico ao desativar) quando alguém pede a
   remoção dos próprios dados.

---

## Lembrete sobre os próximos passos

Esta auditoria é só de análise — nenhum item foi implementado. Para seguir, a Clara escolhe os
itens pelos IDs (ex.: "implementar M01, M04 e M07"); a implementação segue em uma branch separada
da `main`, com um plano apresentado antes de começar, um commit por item (com os testes
executados ao final de cada um), e só vai para a `main` com aprovação explícita.
