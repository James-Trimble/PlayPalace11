# Tradeoff 游戏消息 (简体中文)

# 游戏信息
game-name-tradeoff = 交易博弈

# 回合和迭代流程
tradeoff-round-start = 第 { $round } 回合。
tradeoff-iteration = 第 { $iteration } 手，共 3 手。

# 阶段 1：交易
tradeoff-you-rolled = 你掷出了：{ $dice }。
tradeoff-toggle-trade = { $value }（{ $status }）
tradeoff-trade-status-trading = 交易中
tradeoff-trade-status-keeping = 保留中
tradeoff-confirm-trades = 确认交易（{ $count } 个骰子）
tradeoff-keeping = 保留 { $value }。
tradeoff-trading = 交易 { $value }。
tradeoff-player-traded = { $player } 交易了：{ $dice }。
tradeoff-player-traded-none = { $player } 保留了所有骰子。

# 阶段 2：从池中取骰子
tradeoff-your-turn-take = 轮到你从池中取一个骰子。
tradeoff-take-die = 取一个 { $value }（剩余 { $remaining } 个）
tradeoff-you-take = 你取了一个 { $value }。
tradeoff-player-takes = { $player } 取了一个 { $value }。

# 阶段 3：计分
tradeoff-player-scored = { $player }（{ $points } 分）：{ $sets }。
tradeoff-no-sets = { $player }：没有组合。

# 组合描述（简洁）
tradeoff-set-triple = { $value } 的三条
tradeoff-set-group = { $value } 的组
tradeoff-set-mini-straight = 小顺子 { $low }-{ $high }
tradeoff-set-double-triple = 双三条（{ $v1 } 和 { $v2 }）
tradeoff-set-straight = 顺子 { $low }-{ $high }
tradeoff-set-double-group = 双组（{ $v1 } 和 { $v2 }）
tradeoff-set-all-groups = 全组
tradeoff-set-all-triplets = 全三条

# 回合结束
tradeoff-round-scores = 第 { $round } 回合得分：
tradeoff-score-line = { $player }：+{ $round_points }（总计：{ $total }）
tradeoff-leader = { $player } 以 { $score } 分领先。

# 游戏结束
tradeoff-winner = { $player } 以 { $score } 分获胜！
tradeoff-winners-tie = 平局！{ $players } 以 { $score } 分打成平手！

# 状态检查
tradeoff-view-hand = 查看你的手牌
tradeoff-view-pool = 查看池
tradeoff-view-players = 查看玩家
tradeoff-hand-display = 你的手牌（{ $count } 个骰子）：{ $dice }
tradeoff-pool-display = 池（{ $count } 个骰子）：{ $dice }
tradeoff-player-info = { $player }：{ $hand }。交易了：{ $traded }。
tradeoff-player-info-no-trade = { $player }：{ $hand }。没有交易。

# 错误消息
tradeoff-not-trading-phase = 不在交易阶段。
tradeoff-not-taking-phase = 不在取骰阶段。
tradeoff-already-confirmed = 已确认。
tradeoff-no-die = 没有骰子可切换。
tradeoff-no-more-takes = 没有更多可取的骰子。
tradeoff-not-in-pool = 该骰子不在池中。

# 选项
tradeoff-set-target = 目标分数：{ $score }
tradeoff-enter-target = 输入目标分数：
tradeoff-option-changed-target = 目标分数设置为 { $score }。
