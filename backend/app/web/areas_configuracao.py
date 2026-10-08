"""Lista das áreas administrativas dentro de Configuração — usada pela
tela de entrada (`routes_configuracao.py`) e pela sub-navegação no topo de
cada uma delas (2026-09-29, a pedido da Clara: poder trocar de área sem
precisar voltar pra Configuração toda vez)."""
from __future__ import annotations

AREAS_CONFIGURACAO = [
    {
        "url": "/app/usuarios", "rotulo": "Usuários", "icone": "usuarios",
        "descricao": "Cadastrar, editar e gerenciar acessos da equipe.",
    },
    {
        "url": "/app/empresas", "rotulo": "Empresas-clientes", "icone": "empresas",
        "descricao": "Cadastro, CNPJ e ativação das empresas atendidas.",
    },
    {
        "url": "/app/funcionarios", "rotulo": "Assistentes", "icone": "funcionarios",
        "descricao": "Assistentes de Gestão de Processos — alimenta o relatório.",
    },
    {
        "url": "/app/setores", "rotulo": "Setores", "icone": "setores",
        "descricao": "Setores por operadora — usados nos vínculos de usuário.",
    },
    {
        "url": "/app/chamados", "rotulo": "Chamados", "icone": "suporte",
        "descricao": "Chamados de suporte abertos pelo pop-up, em qualquer tela.",
    },
    {
        "url": "/app/auditoria", "rotulo": "Auditoria", "icone": "auditoria",
        "descricao": "Histórico de ações no sistema — quem fez o quê e quando.",
    },
]
