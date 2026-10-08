"""Dois mapas do Brasil por relatório — revisional e contrárias (Fase 6),
desenhados com matplotlib puro a partir da mesma contagem {UF: quantidade}
que preenche a tabela por UF ao lado (nunca divergem).

Preparação (uma vez, fora do sistema — script separado, não roda em
produção): baixa a malha de estados do IBGE, simplifica os contornos e
salva `assets/brasil_uf.json`. Em produção não há geopandas nem acesso à
internet — só lê esse JSON já pronto.

Desenho:
- Polígonos com matplotlib.collections.PolyCollection, borda branca fina,
  sem eixos.
- Cor por faixa de valor: 0 = cor base clara; valores maiores em tons mais
  fortes (paleta em config/mapa_rotulos.yaml).
- Rótulo "UF" + valor no centro de cada estado, com posição ajustável.
- Estados pequenos (RN, PB, PE, AL, SE, ES, RJ) têm o valor fora do mapa,
  ligado por linha de chamada (coordenadas em config/mapa_rotulos.yaml).
- Saída PNG em 200 dpi, fundo transparente, inserida no template com
  InlineImage, na largura do modelo.
"""
