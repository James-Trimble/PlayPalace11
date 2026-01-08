# Mensagens do jogo Scopa
# Nota: Mensagens comuns como round-start, turn-start, target-score, team-mode estão em games.ftl

# Nome do jogo
game-name-scopa = Scopa

# Eventos do jogo
scopa-initial-table = Cartas na mesa: { $cards }
scopa-no-initial-table = Não há cartas na mesa para começar.
scopa-you-collect = Você captura { $cards } com { $card }
scopa-player-collects = { $player } captura { $cards } com { $card }
scopa-you-put-down = Você coloca { $card }.
scopa-player-puts-down = { $player } coloca { $card }.
scopa-scopa-suffix =  - SCOPA!
scopa-clear-table-suffix = , limpando a mesa.
scopa-remaining-cards = { $player } fica com as cartas restantes da mesa.
scopa-scoring-round = Contando pontos...
scopa-most-cards = { $player } ganha 1 ponto por mais cartas ({ $count } cartas).
scopa-most-cards-tie = Empate em mais cartas - nenhum ponto atribuído.
scopa-most-diamonds = { $player } ganha 1 ponto por mais ouros ({ $count } ouros).
scopa-most-diamonds-tie = Empate em mais ouros - nenhum ponto atribuído.
scopa-seven-diamonds = { $player } ganha 1 ponto pelo 7 de ouros.
scopa-seven-diamonds-multi = { $player } ganha 1 ponto por mais 7 de ouros ({ $count } × 7 de ouros).
scopa-seven-diamonds-tie = Empate no 7 de ouros - nenhum ponto atribuído.
scopa-most-sevens = { $player } ganha 1 ponto por mais setes ({ $count } setes).
scopa-most-sevens-tie = Empate em mais setes - nenhum ponto atribuído.
scopa-round-scores = Pontuação da rodada:
scopa-round-score-line = { $player }: +{ $round_score } (total: { $total_score })
scopa-table-empty = Não há cartas na mesa.
scopa-no-such-card = Não há carta nessa posição.
scopa-captured-count = Você capturou { $count } cartas

# Ações de visualização
scopa-view-table = Ver mesa
scopa-view-captured = Ver capturadas

# Opções específicas do Scopa
scopa-enter-target-score = Digite a pontuação alvo (1-121)
scopa-set-cards-per-deal = Cartas por distribuição: { $cards }
scopa-enter-cards-per-deal = Digite cartas por distribuição (1-10)
scopa-set-decks = Número de baralhos: { $decks }
scopa-enter-decks = Digite número de baralhos (1-6)
scopa-toggle-escoba = Regras de Escoba (soma 15): { $enabled }
scopa-toggle-hints = Mostrar dicas de captura: { $enabled }
scopa-set-mechanic = Mecânica de scopa: { $mechanic }
scopa-select-mechanic = Selecione a mecânica de scopa
scopa-toggle-instant-win = Vitória instantânea com scopa: { $enabled }
scopa-toggle-team-scoring = Agrupar cartas da equipe para pontuação: { $enabled }
scopa-toggle-inverse = Modo inverso (atingir alvo = eliminação): { $enabled }

# Anúncios de mudança de opções
scopa-option-changed-cards = Cartas por distribuição definidas para { $cards }.
scopa-option-changed-decks = Número de baralhos definido para { $decks }.
scopa-option-changed-escoba = Regras de Escoba { $enabled }.
scopa-option-changed-hints = Dicas de captura { $enabled }.
scopa-option-changed-mechanic = Mecânica de scopa definida para { $mechanic }.
scopa-option-changed-instant = Vitória instantânea com scopa { $enabled }.
scopa-option-changed-team-scoring = Pontuação de cartas da equipe { $enabled }.
scopa-option-changed-inverse = Modo inverso { $enabled }.
