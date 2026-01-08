# Scopa 游戏消息
# 注：回合开始、轮次开始、目标分数、团队模式等通用消息在 games.ftl 中

# 游戏名称
game-name-scopa = Scopa

# 游戏事件
scopa-initial-table = 桌面牌：{ $cards }
scopa-no-initial-table = 桌面上没有起始牌。
scopa-you-collect = 你用 { $card } 收集了 { $cards }
scopa-player-collects = { $player } 用 { $card } 收集了 { $cards }
scopa-you-put-down = 你打出了 { $card }。
scopa-player-puts-down = { $player } 打出了 { $card }。
scopa-scopa-suffix =  - SCOPA！
scopa-clear-table-suffix = ，清空了桌面。
scopa-remaining-cards = { $player } 获得了桌面上剩余的牌。
scopa-scoring-round = 计算得分...
scopa-most-cards = { $player } 因最多牌数得1分 ({ $count } 张牌)。
scopa-most-cards-tie = 最多牌数平局 - 无人得分。
scopa-most-diamonds = { $player } 因最多方块得1分 ({ $count } 张方块)。
scopa-most-diamonds-tie = 最多方块平局 - 无人得分。
scopa-seven-diamonds = { $player } 因方块7得1分。
scopa-seven-diamonds-multi = { $player } 因最多方块7得1分 ({ $count } × 方块7)。
scopa-seven-diamonds-tie = 方块7平局 - 无人得分。
scopa-most-sevens = { $player } 因最多七得1分 ({ $count } 张七)。
scopa-most-sevens-tie = 最多七平局 - 无人得分。
scopa-round-scores = 回合得分：
scopa-round-score-line = { $player }：+{ $round_score } (总计：{ $total_score })
scopa-table-empty = 桌面上没有牌。
scopa-no-such-card = 该位置没有牌。
scopa-captured-count = 你已收集 { $count } 张牌

# 查看操作
scopa-view-table = 查看桌面
scopa-view-captured = 查看已收集

# Scopa 特定选项
scopa-enter-target-score = 输入目标分数 (1-121)
scopa-set-cards-per-deal = 每次发牌数：{ $cards }
scopa-enter-cards-per-deal = 输入每次发牌数 (1-10)
scopa-set-decks = 牌组数量：{ $decks }
scopa-enter-decks = 输入牌组数量 (1-6)
scopa-toggle-escoba = Escoba 规则 (凑15)：{ $enabled }
scopa-toggle-hints = 显示收牌提示：{ $enabled }
scopa-set-mechanic = Scopa 机制：{ $mechanic }
scopa-select-mechanic = 选择 Scopa 机制
scopa-toggle-instant-win = Scopa 即时胜利：{ $enabled }
scopa-toggle-team-scoring = 团队合并计分：{ $enabled }
scopa-toggle-inverse = 反向模式 (达到目标即淘汰)：{ $enabled }

# 选项变更通知
scopa-option-changed-cards = 每次发牌数已设为 { $cards }。
scopa-option-changed-decks = 牌组数量已设为 { $decks }。
scopa-option-changed-escoba = Escoba 规则 { $enabled }。
scopa-option-changed-hints = 收牌提示 { $enabled }。
scopa-option-changed-mechanic = Scopa 机制已设为 { $mechanic }。
scopa-option-changed-instant = Scopa 即时胜利 { $enabled }。
scopa-option-changed-team-scoring = 团队合并计分 { $enabled }。
scopa-option-changed-inverse = 反向模式 { $enabled }。
