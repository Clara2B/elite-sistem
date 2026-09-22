# Backend — Elite Sistem

API do novo sistema (FastAPI), decisão D2 em `../ARCHITECTURE.md`. Laudos, audiências e cobrança de
pendências portados do sistema atual (`leitor-relatorio`), persistindo no banco. Login individual,
setores/operadoras e segregação de acesso implementados (Fase 4). Gestão de Processos (Fase 5)
ainda não existe.

## Autenticação

Toda rota de negócio exige login: `Authorization: Bearer <token>`, obtido em `POST /auth/login`.

- `POST /auth/login` `{email, senha}` → `{token, expira_em, usuario}`
- `POST /auth/logout`, `GET /auth/me`, `POST /auth/senha` `{senha_atual, senha_nova}`
- `GET /usuarios`, `POST /usuarios`, `PATCH /usuarios/{id}/ativo` — só Admin Superior/T.I.
- `GET /setores` — lista de setores/operadoras para montar o cadastro de um usuário

**Primeiro acesso:** o banco começa sem nenhum usuário. Defina as variáveis de ambiente
`ADMIN_BOOTSTRAP_EMAIL` e `ADMIN_BOOTSTRAP_SENHA` no Render — no próximo start do servidor, se ainda
não existir nenhum Admin Superior/T.I., essa conta é criada automaticamente. Faça login com ela e
troque a senha em seguida (`POST /auth/senha`); dali em diante, crie o resto da equipe por
`POST /usuarios`. Ver `SECURITY.md` seção 5.

## Endpoints de negócio

- `POST /laudos/import`, `GET /laudos/relatorio`, `GET /laudos/relatorio.pdf` — exige acesso à ELITE
- `POST /audiencias/import`, `GET /audiencias/relatorio`, `GET /audiencias/relatorio.pdf` — exige acesso à EXIMIA
- `POST /pendencias/import` (login), `GET /pendencias/mensagens` (filtra pelas operadoras que o usuário acessa)

Os `/import` recebem a planilha `.xlsx` (`multipart/form-data`, campo `arquivo`) — mesmo formato
aceito hoje pelo `leitor-relatorio`. Documentação interativa em `/docs` quando o servidor está
rodando (inclui um botão "Authorize" para colar o token).

## Rodar localmente

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env   # preencha DATABASE_URL para usar as rotas de negócio
uvicorn app.main:app --reload
```

Acesse `http://localhost:8000/health` — deve responder `{"status": "ok", ...}`. Sem `DATABASE_URL`
preenchido, o servidor sobe normalmente, mas as rotas de laudos/audiências/pendências retornam erro
(elas dependem do banco).

## Testes

```bash
pytest
```

## Lint

```bash
ruff check .
```
