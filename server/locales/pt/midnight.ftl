# Mensagens do jogo 1-4-24 (Midnight) (Português)
# Nota: Mensagens comuns como round-start, turn-start, target-score estão em games.ftl

# Informações do jogo
game-name-midnight = 1-4-24
midnight-category = Jogos de Dados

# Ações
midnight-roll = Jogar os dados
midnight-keep-die = Guardar { $value }
midnight-bank = Guardar pontos

# Eventos do jogo
midnight-turn-start = Vez de { $player }.
midnight-you-rolled = Você jogou: { $dice }.
midnight-player-rolled = { $player } jogou: { $dice }.

# Guardando dados
midnight-you-keep = Você guarda { $die }.
midnight-player-keeps = { $player } guarda { $die }.
midnight-you-unkeep = Você desguarda { $die }.
midnight-player-unkeeps = { $player } desguarda { $die }.

# Status da rodada
midnight-you-have-kept = Dados guardados: { $kept }. Jogadas restantes: { $remaining }.
midnight-player-has-kept = { $player } guardou: { $kept }. { $remaining } dados restantes.

# Pontuação
midnight-you-scored = Você marcou { $score } pontos.
midnight-scored = { $player } marcou { $score } pontos.
midnight-you-disqualified = Você não tem 1 e 4. Desqualificado!
midnight-player-disqualified = { $player } não tem 1 e 4. Desqualificado!

# Resultados da rodada
midnight-round-winner = { $player } vence a rodada!
midnight-round-tie = Rodada empatada entre { $players }.
midnight-all-disqualified = Todos os jogadores desqualificados! Sem vencedor esta rodada.

# Vencedor do jogo
midnight-game-winner = { $player } vence o jogo com { $wins } vitórias!
midnight-game-tie = Empate! { $players } venceram { $wins } rodadas cada.

# Opções
midnight-set-rounds = Rodadas para jogar: { $rounds }
midnight-enter-rounds = Digite o número de rodadas para jogar:
midnight-option-changed-rounds = Rodadas para jogar alteradas para { $rounds }

# Razões de desabilitação
midnight-need-to-roll = Você precisa jogar os dados primeiro.
midnight-no-dice-to-keep = Não há dados disponíveis para guardar.
midnight-must-keep-one = Você deve guardar pelo menos um dado por jogada.
midnight-must-roll-first = Você deve jogar os dados primeiro.
midnight-keep-all-first = Você deve guardar todos os dados antes de guardar os pontos.
