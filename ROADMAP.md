# ROADMAP.md — Elite Sistem

Status por fase (ver `PROMPT-ARQUITETO-ELITE-SISTEM.md` seção 5 para escopo/critérios de cada uma).

| Fase | Status | Observação |
|---|---|---|
| 0 — Diagnóstico e Auditoria | 🟢 Concluída | Ver `ARCHITECTURE.md` seção 1. Achado crítico de segurança já mitigado pela Clara (repo `leitor-relatorio` tornado privado). Pendências do Gate 0 respondidas em 1.9. |
| 1 — Arquitetura e Proposta Técnica | 🟢 Concluída | D1 (login individual), D2 (backend FastAPI + frontend próprio) e D3 (Supabase) aprovados pela Clara. Ver `ARCHITECTURE.md` seção 2, `DATABASE.md` (v1) e `SECURITY.md`. |
| 2 — Preparação da Fundação | 🟢 Concluída | Backend FastAPI em produção no Render (`https://elite-sistem.onrender.com`, `/health` respondendo), CI configurado. Projeto Supabase provisionado, conexão real fica para a Fase 3. |
| 3 — Migração dos Módulos Existentes | 🟢 Concluída | Laudos/audiências/pendências portados para `backend/app/services/`, persistindo no Supabase. Paridade validada: 272/272 cenários de audiências e 18/18 empresas de pendências batendo com o sistema atual. Deploy em produção confirmado (`/health` ok, conexão real com o Supabase funcionando após corrigir o driver Postgres). Ver `DATABASE.md` seção 8 e `DECISIONS.md`. |
| 4 — Autenticação, Multiempresa, Setores e Permissões | 🟢 Concluída | Login individual, papéis (Admin Superior, T.I., Líder, Colaborador), setores reais da Clara, segregação por operadora aplicada em todas as rotas, auditoria. 39 testes automatizados. Validado em produção pela Clara (cadastros principais feitos direto na API). Ver `DATABASE.md` seção 8, `SECURITY.md` seção 5, `DECISIONS.md`. |
| 5 — Gestão de Processos (ELITE) | 🟡 Levantamento concluído, proposta pronta, aguardando aprovação para implementar | Planilha real auditada, requisitos confirmados com a Clara (prazo com data obrigatória, relatórios individual+geral, alerta por sistema+e-mail). Ver `ARCHITECTURE.md` seção 3 e `DATABASE.md` seção 6.1. |
| 6 — Refinamentos | ⬜ Não iniciada | |
| 7 — Automações | ⬜ Não iniciada | |
| 8 — Deploy Final e Corte de Produção | ⬜ Não iniciada | |

**Legenda:** ⬜ não iniciada · 🟡 em andamento/aguardando decisão · 🟢 concluída e aprovada
