# Backend — Elite Sistem

API do novo sistema (FastAPI), decisão D2 em `../ARCHITECTURE.md`. Fase 3: laudos, audiências e
cobrança de pendências já portados do sistema atual (`leitor-relatorio`), persistindo no banco em
vez de recalcular tudo a cada upload. Ainda sem autenticação/permissões (Fase 4) nem Gestão de
Processos (Fase 5).

## Endpoints principais

- `POST /laudos/import`, `GET /laudos/relatorio`, `GET /laudos/relatorio.pdf`
- `POST /audiencias/import`, `GET /audiencias/relatorio`, `GET /audiencias/relatorio.pdf`
- `POST /pendencias/import`, `GET /pendencias/mensagens`

Os três `/import` recebem a planilha `.xlsx` (`multipart/form-data`, campo `arquivo`) — mesmo
formato aceito hoje pelo `leitor-relatorio`. Documentação interativa em `/docs` quando o servidor
está rodando.

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
