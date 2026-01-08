# Pig 游戏消息 (简体中文)
# 注：回合开始、轮次开始、目标分数等通用消息在 games.ftl 中

# 游戏信息
game-name-pig = 贪心猪
pig-category = 骰子游戏

# 操作
pig-roll = 掷骰子
pig-bank = 存入 { $points } 分

# 游戏事件 (Pig 特有)
pig-rolls = { $player } 掷骰子...
pig-roll-result = 掷出 { $roll }，累计 { $total } 分
pig-bust = 糟糕，掷出 1！{ $player } 失去 { $points } 分。
pig-bank-action = { $player } 决定存入 { $points } 分，总计 { $total } 分
pig-winner = 胜利者诞生，是 { $player }！

# Pig 特有选项
pig-set-min-bank = 最低存入：{ $points }
pig-set-dice-sides = 骰子面数：{ $sides }
pig-enter-min-bank = 输入最低存入分数：
pig-enter-dice-sides = 输入骰子面数：
pig-option-changed-min-bank = 最低存入分数已改为 { $points }
pig-option-changed-dice = 骰子现在有 { $sides } 面
