# Mensagens do jogo Tradeoff (Português)

# Informações do jogo
game-name-tradeoff = Tradeoff

# Fluxo de rodada e iteração
tradeoff-round-start = Rodada { $round }.
tradeoff-iteration = Mão { $iteration } de 3.

# Fase 1: Troca
tradeoff-you-rolled = Você rolou: { $dice }.
tradeoff-toggle-trade = { $value } ({ $status })
tradeoff-trade-status-trading = trocando
tradeoff-trade-status-keeping = guardando
tradeoff-confirm-trades = Confirmar trocas ({ $count } dados)
tradeoff-keeping = Guardando { $value }.
tradeoff-trading = Trocando { $value }.
tradeoff-player-traded = { $player } trocou: { $dice }.
tradeoff-player-traded-none = { $player } ficou com todos os dados.

# Fase 2: Pegar do pool
tradeoff-your-turn-take = Sua vez de pegar um dado do pool.
tradeoff-take-die = Pegar um { $value } ({ $remaining } restantes)
tradeoff-you-take = Você pega um { $value }.
tradeoff-player-takes = { $player } pega um { $value }.

# Fase 3: Pontuação
tradeoff-player-scored = { $player } ({ $points } pts): { $sets }.
tradeoff-no-sets = { $player }: sem conjuntos.

# Descrições de conjuntos (conciso)
tradeoff-set-triple = trinca de { $value }s
tradeoff-set-group = grupo de { $value }s
tradeoff-set-mini-straight = mini sequência { $low }-{ $high }
tradeoff-set-double-triple = dupla trinca ({ $v1 }s e { $v2 }s)
tradeoff-set-straight = sequência { $low }-{ $high }
tradeoff-set-double-group = duplo grupo ({ $v1 }s e { $v2 }s)
tradeoff-set-all-groups = todos os grupos
tradeoff-set-all-triplets = todas as trincas

# Fim da rodada
tradeoff-round-scores = Pontuação da rodada { $round }:
tradeoff-score-line = { $player }: +{ $round_points } (total: { $total })
tradeoff-leader = { $player } lidera com { $score }.

# Fim do jogo
tradeoff-winner = { $player } vence com { $score } pontos!
tradeoff-winners-tie = Empate! { $players } empataram com { $score } pontos!

# Verificações de status
tradeoff-view-hand = Ver sua mão
tradeoff-view-pool = Ver o pool
tradeoff-view-players = Ver jogadores
tradeoff-hand-display = Sua mão ({ $count } dados): { $dice }
tradeoff-pool-display = Pool ({ $count } dados): { $dice }
tradeoff-player-info = { $player }: { $hand }. Trocou: { $traded }.
tradeoff-player-info-no-trade = { $player }: { $hand }. Não trocou nada.

# Mensagens de erro
tradeoff-not-trading-phase = Não está na fase de troca.
tradeoff-not-taking-phase = Não está na fase de pegar.
tradeoff-already-confirmed = Já confirmado.
tradeoff-no-die = Nenhum dado para alternar.
tradeoff-no-more-takes = Não há mais pegadas disponíveis.
tradeoff-not-in-pool = Esse dado não está no pool.

# Opções
tradeoff-set-target = Pontuação alvo: { $score }
tradeoff-enter-target = Digite a pontuação alvo:
tradeoff-option-changed-target = Pontuação alvo definida para { $score }.
