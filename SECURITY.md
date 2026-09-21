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

## 4. Em aberto (a decidir nas próximas fases)

- Política de retenção de dados pessoais (LGPD: por quanto tempo manter CPF/nome de clientes após o
  processo encerrado?) — pergunta de negócio, não técnica; levar à Clara antes da Fase 4.
- Rate limiting / bloqueio de tentativas de login (Fase 4).
- Expiração de sessão e "lembrar-me" (Fase 4).
- Backup automatizado do banco de produção — depende do provedor escolhido em D3 (Fase 2).
- Necessidade (ou não) de reescrever o histórico do Git de `leitor-relatorio` (seção 2).
