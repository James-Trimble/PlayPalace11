# 1-4-24 (Midnight) 游戏消息 (简体中文)
# 注：回合开始、轮次开始、目标分数等通用消息在 games.ftl 中

# 游戏信息
game-name-midnight = 1-4-24
midnight-category = 骰子游戏

# 操作
midnight-roll = 掷骰子
midnight-keep-die = 保留 { $value }
midnight-bank = 保存分数

# 游戏事件
midnight-turn-start = { $player } 的回合。
midnight-you-rolled = 你掷出：{ $dice }。
midnight-player-rolled = { $player } 掷出：{ $dice }。

# 保留骰子
midnight-you-keep = 你保留 { $die }。
midnight-player-keeps = { $player } 保留 { $die }。
midnight-you-unkeep = 你取消保留 { $die }。
midnight-player-unkeeps = { $player } 取消保留 { $die }。

# 回合状态
midnight-you-have-kept = 已保留骰子：{ $kept }。剩余掷骰次数：{ $remaining }。
midnight-player-has-kept = { $player } 已保留：{ $kept }。剩余 { $remaining } 个骰子。

# 计分
midnight-you-scored = 你得到 { $score } 分。
midnight-scored = { $player } 得到 { $score } 分。
midnight-you-disqualified = 你没有同时拥有 1 和 4。被淘汰！
midnight-player-disqualified = { $player } 没有同时拥有 1 和 4。被淘汰！

# 回合结果
midnight-round-winner = { $player } 赢得本回合！
midnight-round-tie = 本回合 { $players } 平局。
midnight-all-disqualified = 所有玩家都被淘汰！本回合无胜者。

# 游戏胜者
midnight-game-winner = { $player } 以 { $wins } 个回合胜利赢得游戏！
midnight-game-tie = 平局！{ $players } 各赢得 { $wins } 个回合。

# 选项
midnight-set-rounds = 游戏回合数：{ $rounds }
midnight-enter-rounds = 输入游戏回合数：
midnight-option-changed-rounds = 游戏回合数已改为 { $rounds }

# 禁用原因
midnight-need-to-roll = 你需要先掷骰子。
midnight-no-dice-to-keep = 没有可保留的骰子。
midnight-must-keep-one = 每次掷骰必须至少保留一个骰子。
midnight-must-roll-first = 你必须先掷骰子。
midnight-keep-all-first = 你必须先保留所有骰子才能保存分数。
