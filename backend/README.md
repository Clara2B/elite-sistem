# Backend — Elite Sistem

API do novo sistema (FastAPI), decisão D2 em `../ARCHITECTURE.md`. Ainda no esqueleto da Fase 2 —
sem regras de negócio, sem banco conectado.

## Rodar localmente

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Acesse `http://localhost:8000/health` — deve responder `{"status": "ok", ...}`.

## Testes

```bash
pytest
```

## Lint

```bash
ruff check .
```
