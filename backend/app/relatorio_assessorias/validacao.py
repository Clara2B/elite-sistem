"""Avisos e conferências cruzadas (Fase 5).

Nada é corrigido em silêncio: o que o sistema consegue converter, converte;
o resto vira aviso na tela de revisão, com planilha, aba e linha (origem
que cada leitor devolve junto com os dados — ver leitores/base.py).

Conferências cruzadas (avisos, não bloqueiam):
- Processo duplicado dentro da mesma lista (mantém um e avisa).
- Soma da tabela por UF diferente do total de ativos (acontece quando há
  UF inválida).
- Laudo pronto com data de pronto anterior à data de entrada; distribuição
  anterior ao recebimento.
- Linha da assessoria com campo essencial vazio (data, processo, UF).

Erros bloqueantes (impedem gerar a seção): arquivo errado no campo de
upload, aba obrigatória ausente, coluna obrigatória não encontrada.
"""
