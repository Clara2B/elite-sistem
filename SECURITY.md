# SECURITY.md — Elite Sistem

> Segurança é tratada desde a Fase 1, não como etapa posterior (princípio do prompt mestre, seção
> 3). Este documento registra o modelo de ameaças básico, o que já foi decidido, e o que ainda está
> em aberto — atualizado a cada fase que tocar autenticação, dados pessoais ou infraestrutura.

## 1. O que estamos protegendo

- **Dados pessoais (LGPD):** CPF de clientes nas audiências; nome completo de clientes em laudos e
  audiências. Titular dos dados = pessoas físicas atendidas pelas empresas-clientes da
  EXÍMIA/ELITE (não são funcionárias do sistema).
- **Dados comerciais sensíveis:** CNPJ e valores financeiros (laudos, audiências, cobranças) das
  ~43 empresas-clientes — o vazamento já ocorrido (ver seção 3) mostra que isso é risco real, não
  hipotético.
- **Credenciais e sessões** dos usuários do sistema (Admin Superior, Líderes, Colaboradores).

## 2. Incidente conhecido (herdado do sistema atual)

O repositório `leitor-relatorio` teve, publicamente por um período, uma planilha de fluxo de caixa
e o banco SQLite com CNPJs de clientes commitados no histórico do Git (ver `ARCHITECTURE.md` seção
1.5). **Mitigado**: a Clara tornou o repositório privado (2026-09-21). **Em aberto, sem urgência**:
decidir se vale reescrever o histórico do Git para remover os arquivos definitivamente (o dado
ainda existe no histórico de um repositório agora privado). Nenhuma ação foi ou será tomada nesse
repositório sem acesso de escrita explicitamente concedido e autorização direta da Clara.

## 3. Decisões de segurança já tomadas (Fase 1)

- **Senhas:** hash com algoritmo forte (bcrypt ou argon2) — nunca texto puro, nunca no código, nunca
  no `.env` versionado. O sistema atual compara senha em texto puro vinda de `st.secrets`; isso não
  será reaproveitado.
- **Login individual por pessoa** — recomendado (ver `ARCHITECTURE.md` decisão D1), justamente para
  que `logs_auditoria` seja confiável (saber *quem* fez cada ação, não só "Admin Superior").
- **Segregação por operadora é regra de banco, não só de tela:** todo acesso de quem não é Admin
  Superior deve ser filtrado no backend/banco pela(s) operadora(s)/setor(es) do usuário — nunca
  confiar em esconder botões/menus no frontend como única barreira.
- **Segredos** (senha do banco, chaves de API) ficam em variáveis de ambiente do provedor de
  hospedagem escolhido (D3), nunca commitados — seguindo o mesmo cuidado que o sistema atual já
  tinha com `secrets.toml` (isso, ao menos, ele fazia certo).
- **CPF e outros dados pessoais**: tratados como dado sensível desde o desenho do schema
  (`DATABASE.md` seção 4) — acesso restrito pela mesma regra de segregação por operadora/setor;
  avaliar necessidade de criptografia em repouso ou mascaramento em tela conforme o provedor de
  banco escolhido permitir, na Fase 4.

## 4. Segredos vs. dados públicos do Supabase (registro, 2026-09-22)

Ao configurar o projeto Supabase, a Clara compartilhou no chat a URL do projeto e a
*publishable key* (`sb_publishable_...`). **Isso não é um incidente**: essas duas informações são
feitas para ser públicas (a publishable key é o equivalente atual da antiga *anon key* — protegida
por Row Level Security no banco, não por sigilo). Registrando aqui só para deixar claro, daqui pra
frente, o que É segredo de verdade e nunca deve ser colado em chat/commit:

- **Connection string do Postgres** (inclui a senha do banco) — Settings → Database no Supabase.
- **`service_role` key** — dá acesso total ao banco, ignorando RLS.
- Qualquer coisa que o próprio painel do provedor rotular como "secret"/"senha".

Esses valores devem ser inseridos **diretamente no painel do provedor de hospedagem** (Render, nas
variáveis de ambiente do serviço) quando chegar a hora (Fase 3, quando o backend passar a acessar o
banco de verdade) — nunca aqui no chat.

## 5. Autenticação implementada (Fase 4, 2026-09-22)

- **Senha:** hash com `bcrypt` (biblioteca `bcrypt`, não passlib — evita problemas de detecção de
  versão que essa combinação tem dado historicamente). Nunca texto puro, em lugar nenhum.
- **Sessão:** token opaco aleatório (`secrets.token_hex(32)`, não JWT) guardado na tabela `sessoes`,
  válido por 12h (`SESSAO_DURACAO_HORAS` em `app/auth.py`). Escolhido no lugar de JWT para não
  depender de gerenciar um segredo de assinatura, e porque "sair" (logout) apaga a sessão de
  verdade — não fica esperando o token expirar sozinho. Enviado como `Authorization: Bearer
  <token>`.
- **Segregação por operadora aplicada no backend, não só na tela:** toda rota de negócio
  (`/laudos/*`, `/audiencias/*`) tem uma dependency (`require_operadora`) que barra o acesso antes
  de qualquer consulta ao banco; `/pendencias/mensagens` filtra o resultado pelas operadoras que o
  usuário pode ver, já que uma cobrança pode ser de qualquer uma das duas. Dois papéis têm alcance
  total (`ADMIN_SUPERIOR`, `ADMIN_TI`) — o resto do acesso vem só dos vínculos em `usuario_setor`.
  Cobertura de teste: `tests/test_permissoes.py`.
- **Auditoria:** `logs_auditoria` grava login, login falho, logout, troca de senha, criação de
  usuário, import de planilha e geração de relatório — sempre associado ao usuário autenticado.
- **Primeiro acesso (bootstrap):** como não existe usuário nenhum na primeira vez que o banco sobe,
  o Admin Superior inicial é criado a partir das variáveis de ambiente
  `ADMIN_BOOTSTRAP_EMAIL`/`ADMIN_BOOTSTRAP_SENHA` (só uma vez — se já existir algum usuário com
  `papel_global`, essas variáveis são ignoradas). **Ação recomendada:** depois do primeiro login,
  trocar a senha por `POST /auth/senha` — não precisa remover as variáveis do Render depois disso
  (ficam inofensivas), mas também não faz mal remover.
- **Ainda não implementado, sem risco relevante no volume atual (10-20 usuários):** rate limiting /
  bloqueio de tentativas de login repetidas.

## 5.1 Autenticação por cookie para as páginas HTML (Fase 6, 2026-09-23)

A interface visual (`app/web/`) não usa `Authorization: Bearer` (o navegador não anexa isso
sozinho em navegação comum) — usa o **mesmo token opaco** da seção 5, guardado num cookie:

- **`HttpOnly`:** JavaScript no navegador não consegue ler o cookie — mitiga roubo de token via
  XSS (mesmo que algum campo escapasse do escape automático do Jinja2, o token em si não é
  exfiltrável por um script injetado).
- **`Secure` dinâmico:** ligado quando a requisição é HTTPS (produção, Render), desligado em HTTP
  (dev local) — calculado a partir do esquema da própria requisição, sem precisar de uma variável
  de ambiente extra pra diferenciar dev/produção.
- **`SameSite=Lax`:** o navegador não envia o cookie em requisições `POST`/`PUT`/etc. disparadas por
  **outro site** (só em navegação de topo, tipo clicar num link) — isso já barra o vetor principal
  de CSRF (um site malicioso não consegue forjar um `POST /app/usuarios/{id}/ativo` usando a sessão
  de quem está logado) sem precisar de um token CSRF separado. Suficiente para uma ferramenta
  interna com esse volume de usuários; token CSRF explícito fica como possível reforço futuro (não
  bloqueante).
- **A API JSON aceita os dois:** `_extrair_token` (`app/auth.py`) primeiro tenta o cabeçalho
  `Authorization: Bearer`, e cai pro cookie de sessão se não vier — assim um link comum da
  interface (ex. "Baixar PDF") funciona batendo direto nas mesmas rotas que o Swagger/scripts usam,
  sem duplicar rota nenhuma só pra servir HTML vs. JSON.
- **Mesma tabela `sessoes`, mesmo "sair":** login pela tela cria uma linha em `sessoes` igual ao
  login pela API; logout apaga a linha de verdade, não só o cookie do navegador.

## 6. Em aberto (a decidir nas próximas fases)

- Política de retenção de dados pessoais (LGPD: por quanto tempo manter CPF/nome de clientes após o
  processo encerrado?) — pergunta de negócio, não técnica; levar à Clara antes da Gestão de
  Processos (Fase 5), que deve trazer ainda mais dado pessoal.
- Rate limiting / bloqueio de tentativas de login.
- Backup automatizado do banco de produção (verificar o que o plano free do Supabase já oferece).
- Necessidade (ou não) de reescrever o histórico do Git de `leitor-relatorio` (seção 2).
