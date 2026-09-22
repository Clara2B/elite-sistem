# ROADMAP.md — Elite Sistem

Status por fase (ver `PROMPT-ARQUITETO-ELITE-SISTEM.md` seção 5 para escopo/critérios de cada uma).

| Fase | Status | Observação |
|---|---|---|
| 0 — Diagnóstico e Auditoria | 🟢 Concluída | Ver `ARCHITECTURE.md` seção 1. Achado crítico de segurança já mitigado pela Clara (repo `leitor-relatorio` tornado privado). Pendências do Gate 0 respondidas em 1.9. |
| 1 — Arquitetura e Proposta Técnica | 🟢 Concluída | D1 (login individual), D2 (backend FastAPI + frontend próprio) e D3 (Supabase) aprovados pela Clara. Ver `ARCHITECTURE.md` seção 2, `DATABASE.md` (v1) e `SECURITY.md`. |
| 2 — Preparação da Fundação | 🟢 Concluída | Backend FastAPI em produção no Render (`https://elite-sistem.onrender.com`, `/health` respondendo), CI configurado. Projeto Supabase provisionado, conexão real fica para a Fase 3. |
| 3 — Migração dos Módulos Existentes | 🟡 Proposta de plano abaixo, aguardando aprovação | Ver mensagem da Clara/arquiteto no histórico — objetivo, escopo, dependências, riscos e critério de conclusão apresentados antes de iniciar. |
| 4 — Autenticação, Multiempresa, Setores e Permissões | ⬜ Não iniciada | |
| 5 — Gestão de Processos (ELITE) | ⬜ Não iniciada | Requer levantamento de requisitos dedicado. |
| 6 — Refinamentos | ⬜ Não iniciada | |
| 7 — Automações | ⬜ Não iniciada | |
| 8 — Deploy Final e Corte de Produção | ⬜ Não iniciada | |

**Legenda:** ⬜ não iniciada · 🟡 em andamento/aguardando decisão · 🟢 concluída e aprovada
