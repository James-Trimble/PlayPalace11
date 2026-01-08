# Shared game messages for PlayPalace
# These messages are common across multiple games

# Round and turn flow
game-round-start = Round { $round }.
game-round-end = Round { $round } complete.
game-turn-start = { $player }'s turn.
game-no-turn = No one's turn right now.

# Score display
game-scores-header = Current Scores:
game-score-line = { $player }: { $score } points
game-final-scores-header = Final Scores:

# Win/loss
game-winner = { $player } wins!
game-winner-score = { $player } wins with { $score } points!
game-tiebreaker = It's a tie! Tiebreaker round!
game-tiebreaker-players = It's a tie between { $players }! Tiebreaker round!
game-eliminated = { $player } has been eliminated with { $score } points.

# Common options
game-set-target-score = Target score: { $score }
game-enter-target-score = Enter target score:
game-option-changed-target = Target score set to { $score }.

game-set-team-mode = Team mode: { $mode }
game-select-team-mode = Select team mode
game-option-changed-team = Team mode set to { $mode }.

# Boolean option values
option-on = on
option-off = off

# Status box
status-box-closed = Status information closed.

# Game end
game-leave = Leave game

# Round timer
round-timer-paused = { $player } has paused the game (press p to start the next round).
round-timer-resumed = Round timer resumed.
round-timer-countdown = Next round in { $seconds }...

# Dealing (card games)
game-deal-counter = Deal { $current }/{ $total }.
game-you-deal = You deal out the cards.
game-player-deals = { $player } deals out the cards.

# Card names
card-name = { $rank } of { $suit }
no-cards = No cards

# Suit names
suit-diamonds = diamonds
suit-clubs = clubs
suit-hearts = hearts
suit-spades = spades

# Rank names
rank-ace = ace
rank-two = 2
rank-three = 3
rank-four = 4
rank-five = 5
rank-six = 6
rank-seven = 7
rank-eight = 8
rank-nine = 9
rank-ten = 10
rank-jack = jack
rank-queen = queen
rank-king = king
