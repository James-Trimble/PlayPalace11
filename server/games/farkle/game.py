"""
Farkle Game Implementation for PlayPalace v11.

Classic dice game: score combinations and don't Farkle!
Push your luck by rolling again or bank your points.
"""

from dataclasses import dataclass, field
import random

from ..base import Game, Player, GameOptions
from ..registry import register_game
from ...game_utils.actions import Action, ActionSet
from ...game_utils.bot_helper import BotHelper
from ...game_utils.options import IntOption, option_field
from ...messages.localization import Localization
from ...ui.keybinds import KeybindState


@dataclass
class FarklePlayer(Player):
    """Player state for Farkle game."""

    score: int = 0  # Permanent score (banked points)
    turn_score: int = 0  # Points accumulated this turn (lost on farkle)
    current_roll: list[int] = field(default_factory=list)  # Dice available to take
    banked_dice: list[int] = field(default_factory=list)  # Dice taken this turn
    has_taken_combo: bool = False  # True after taking a combo (enables roll)


@dataclass
class FarkleOptions(GameOptions):
    """Options for Farkle game."""

    target_score: int = option_field(
        IntOption(
            default=500,
            min_val=500,
            max_val=5000,
            value_key="score",
            label="farkle-set-target-score",
            prompt="farkle-enter-target-score",
            change_msg="farkle-option-changed-target",
        )
    )


# Scoring combination types
COMBO_SINGLE_1 = "single_1"
COMBO_SINGLE_5 = "single_5"
COMBO_THREE_OF_KIND = "three_of_kind"
COMBO_FOUR_OF_KIND = "four_of_kind"
COMBO_FIVE_OF_KIND = "five_of_kind"
COMBO_SIX_OF_KIND = "six_of_kind"
COMBO_SMALL_STRAIGHT = "small_straight"
COMBO_LARGE_STRAIGHT = "large_straight"
COMBO_THREE_PAIRS = "three_pairs"
COMBO_DOUBLE_TRIPLETS = "double_triplets"
COMBO_FULL_HOUSE = "full_house"

# Combo sounds
COMBO_SOUNDS = {
    COMBO_SINGLE_1: "game_farkle/point10.ogg",
    COMBO_SINGLE_5: "game_farkle/singles5.ogg",
    COMBO_THREE_OF_KIND: "game_farkle/3kind.ogg",
    COMBO_FOUR_OF_KIND: "game_farkle/4kind.ogg",
    COMBO_FIVE_OF_KIND: "game_farkle/5kind.ogg",
    COMBO_SIX_OF_KIND: "game_farkle/6kind.ogg",
    COMBO_LARGE_STRAIGHT: "game_farkle/largestraight.ogg",
    COMBO_SMALL_STRAIGHT: "game_farkle/smallstraight.ogg",
    COMBO_THREE_PAIRS: "game_farkle/3pairs.ogg",
    COMBO_DOUBLE_TRIPLETS: "game_farkle/doubletriplets.ogg",
    COMBO_FULL_HOUSE: "game_farkle/fullhouse.ogg",
}


def count_dice(dice: list[int]) -> dict[int, int]:
    """Count occurrences of each die value (1-6)."""
    counts = {i: 0 for i in range(1, 7)}
    for die in dice:
        counts[die] += 1
    return counts


def has_combination(dice: list[int], combo_type: str, number: int = 0) -> bool:
    """Check if dice contain a specific combination."""
    counts = count_dice(dice)

    if combo_type == COMBO_SINGLE_1:
        return counts[1] >= 1
    elif combo_type == COMBO_SINGLE_5:
        return counts[5] >= 1
    elif combo_type == COMBO_THREE_OF_KIND:
        return counts[number] >= 3
    elif combo_type == COMBO_FOUR_OF_KIND:
        return counts[number] >= 4
    elif combo_type == COMBO_FIVE_OF_KIND:
        return counts[number] >= 5
    elif combo_type == COMBO_SIX_OF_KIND:
        return counts[number] == 6
    elif combo_type == COMBO_LARGE_STRAIGHT:
        if len(dice) != 6:
            return False
        return all(counts[i] == 1 for i in range(1, 7))
    elif combo_type == COMBO_SMALL_STRAIGHT:
        if len(dice) < 5:
            return False
        # Check for 1-2-3-4-5
        has_1_5 = all(counts[i] >= 1 for i in range(1, 6))
        # Check for 2-3-4-5-6
        has_2_6 = all(counts[i] >= 1 for i in range(2, 7))
        return has_1_5 or has_2_6
    elif combo_type == COMBO_THREE_PAIRS:
        if len(dice) != 6:
            return False
        pairs = sum(1 for i in range(1, 7) if counts[i] == 2)
        return pairs == 3
    elif combo_type == COMBO_DOUBLE_TRIPLETS:
        if len(dice) != 6:
            return False
        triplets = sum(1 for i in range(1, 7) if counts[i] == 3)
        return triplets == 2
    elif combo_type == COMBO_FULL_HOUSE:
        if len(dice) != 6:
            return False
        has_quad = any(counts[i] == 4 for i in range(1, 7))
        has_pair = any(counts[i] == 2 for i in range(1, 7))
        return has_quad and has_pair

    return False


def get_combination_points(combo_type: str, number: int = 0) -> int:
    """Get point value for a combination."""
    if combo_type == COMBO_SINGLE_1:
        return 10
    elif combo_type == COMBO_SINGLE_5:
        return 5
    elif combo_type == COMBO_THREE_OF_KIND:
        return 100 if number == 1 else number * 10
    elif combo_type == COMBO_FOUR_OF_KIND:
        return 200 if number == 1 else number * 20
    elif combo_type == COMBO_FIVE_OF_KIND:
        return 400 if number == 1 else number * 40
    elif combo_type == COMBO_SIX_OF_KIND:
        return 800 if number == 1 else number * 80
    elif combo_type == COMBO_SMALL_STRAIGHT:
        return 100
    elif combo_type == COMBO_LARGE_STRAIGHT:
        return 200
    elif combo_type == COMBO_THREE_PAIRS:
        return 150
    elif combo_type == COMBO_DOUBLE_TRIPLETS:
        return 250
    elif combo_type == COMBO_FULL_HOUSE:
        return 150
    return 0


def has_scoring_dice(dice: list[int]) -> bool:
    """Check if dice contain any scoring combinations (for farkle detection)."""
    if not dice:
        return False

    counts = count_dice(dice)

    # Single 1s or 5s
    if counts[1] > 0 or counts[5] > 0:
        return True

    # Three or more of a kind
    if any(counts[i] >= 3 for i in range(1, 7)):
        return True

    # Large straight (1-2-3-4-5-6)
    if len(dice) == 6 and all(counts[i] == 1 for i in range(1, 7)):
        return True

    # Small straight
    if len(dice) >= 5:
        has_1_5 = all(counts[i] >= 1 for i in range(1, 6))
        has_2_6 = all(counts[i] >= 1 for i in range(2, 7))
        if has_1_5 or has_2_6:
            return True

    # Three pairs
    if len(dice) == 6:
        pairs = sum(1 for i in range(1, 7) if counts[i] == 2)
        if pairs == 3:
            return True

    # Double triplets
    if len(dice) == 6:
        triplets = sum(1 for i in range(1, 7) if counts[i] == 3)
        if triplets == 2:
            return True

    return False


def get_available_combinations(dice: list[int]) -> list[tuple[str, int, int]]:
    """Get all available scoring combinations as (combo_type, number, points) tuples."""
    combinations = []

    if not dice:
        return combinations

    counts = count_dice(dice)

    # Six of a kind (check first, highest points)
    for num in range(1, 7):
        if has_combination(dice, COMBO_SIX_OF_KIND, num):
            points = get_combination_points(COMBO_SIX_OF_KIND, num)
            combinations.append((COMBO_SIX_OF_KIND, num, points))

    # Five of a kind
    for num in range(1, 7):
        if has_combination(dice, COMBO_FIVE_OF_KIND, num):
            points = get_combination_points(COMBO_FIVE_OF_KIND, num)
            combinations.append((COMBO_FIVE_OF_KIND, num, points))

    # Four of a kind
    for num in range(1, 7):
        if has_combination(dice, COMBO_FOUR_OF_KIND, num):
            points = get_combination_points(COMBO_FOUR_OF_KIND, num)
            combinations.append((COMBO_FOUR_OF_KIND, num, points))

    # Large straight
    if has_combination(dice, COMBO_LARGE_STRAIGHT):
        points = get_combination_points(COMBO_LARGE_STRAIGHT)
        combinations.append((COMBO_LARGE_STRAIGHT, 0, points))

    # Small straight
    if has_combination(dice, COMBO_SMALL_STRAIGHT):
        points = get_combination_points(COMBO_SMALL_STRAIGHT)
        combinations.append((COMBO_SMALL_STRAIGHT, 0, points))

    # Double triplets (higher priority than three pairs)
    if has_combination(dice, COMBO_DOUBLE_TRIPLETS):
        points = get_combination_points(COMBO_DOUBLE_TRIPLETS)
        combinations.append((COMBO_DOUBLE_TRIPLETS, 0, points))

    # Full house
    if has_combination(dice, COMBO_FULL_HOUSE):
        points = get_combination_points(COMBO_FULL_HOUSE)
        combinations.append((COMBO_FULL_HOUSE, 0, points))

    # Three pairs
    if has_combination(dice, COMBO_THREE_PAIRS):
        points = get_combination_points(COMBO_THREE_PAIRS)
        combinations.append((COMBO_THREE_PAIRS, 0, points))

    # Three of a kind
    for num in range(1, 7):
        if has_combination(dice, COMBO_THREE_OF_KIND, num):
            points = get_combination_points(COMBO_THREE_OF_KIND, num)
            combinations.append((COMBO_THREE_OF_KIND, num, points))

    # Single 1s (always available if there's at least one 1)
    if counts[1] > 0:
        points = get_combination_points(COMBO_SINGLE_1)
        combinations.append((COMBO_SINGLE_1, 1, points))

    # Single 5s
    if counts[5] > 0:
        points = get_combination_points(COMBO_SINGLE_5)
        combinations.append((COMBO_SINGLE_5, 5, points))

    # Sort by points descending
    combinations.sort(key=lambda x: x[2], reverse=True)

    return combinations


@dataclass
@register_game
class FarkleGame(Game):
    """
    Farkle dice game.

    Players take turns rolling 6 dice and selecting scoring combinations.
    After each selection, they can roll remaining dice or bank their points.
    Rolling dice with no scoring combinations (Farkle!) loses all turn points.
    First player to reach the target score wins.
    """

    players: list[FarklePlayer] = field(default_factory=list)
    options: FarkleOptions = field(default_factory=FarkleOptions)

    @classmethod
    def get_name(cls) -> str:
        return "Farkle"

    @classmethod
    def get_type(cls) -> str:
        return "farkle"

    @classmethod
    def get_category(cls) -> str:
        return "category-dice-games"

    @classmethod
    def get_min_players(cls) -> int:
        return 2

    @classmethod
    def get_max_players(cls) -> int:
        return 4

    def create_player(
        self, player_id: str, name: str, is_bot: bool = False
    ) -> FarklePlayer:
        """Create a new player with Farkle-specific state."""
        return FarklePlayer(
            id=player_id,
            name=name,
            is_bot=is_bot,
            score=0,
            turn_score=0,
            current_roll=[],
            banked_dice=[],
            has_taken_combo=False,
        )

    def create_turn_action_set(self, player: FarklePlayer) -> ActionSet:
        """Create the turn action set for a player."""
        user = self.get_user(player)
        locale = user.locale if user else "en"

        action_set = ActionSet(name="turn")

        # Roll action
        action_set.add(
            Action(
                id="roll",
                label=Localization.get(locale, "farkle-roll", count=6),
                handler="_action_roll",
            )
        )

        # Bank action
        action_set.add(
            Action(
                id="bank",
                label=Localization.get(locale, "farkle-bank", points=0),
                handler="_action_bank",
            )
        )

        # Check turn score (F5 menu only)
        action_set.add(
            Action(
                id="check_turn_score",
                label="Check turn score",
                handler="_action_check_turn_score",
                hidden=True,  # Hidden from main menu, shown in F5
            )
        )

        return action_set

    def setup_keybinds(self) -> None:
        """Define all keybinds for the game."""
        super().setup_keybinds()

        # Turn action keybinds
        self.define_keybind("r", "Roll dice", ["roll"], state=KeybindState.ACTIVE)
        self.define_keybind("b", "Bank points", ["bank"], state=KeybindState.ACTIVE)
        self.define_keybind(
            "c", "Check turn score", ["check_turn_score"], state=KeybindState.ACTIVE
        )

    def _get_combo_label(
        self, locale: str, combo_type: str, number: int, points: int
    ) -> str:
        """Get the localized label for a scoring combination."""
        if combo_type == COMBO_SINGLE_1:
            return Localization.get(locale, "farkle-take-single-one", points=points)
        elif combo_type == COMBO_SINGLE_5:
            return Localization.get(locale, "farkle-take-single-five", points=points)
        elif combo_type == COMBO_THREE_OF_KIND:
            return Localization.get(
                locale, "farkle-take-three-kind", number=number, points=points
            )
        elif combo_type == COMBO_FOUR_OF_KIND:
            return Localization.get(
                locale, "farkle-take-four-kind", number=number, points=points
            )
        elif combo_type == COMBO_FIVE_OF_KIND:
            return Localization.get(
                locale, "farkle-take-five-kind", number=number, points=points
            )
        elif combo_type == COMBO_SIX_OF_KIND:
            return Localization.get(
                locale, "farkle-take-six-kind", number=number, points=points
            )
        elif combo_type == COMBO_SMALL_STRAIGHT:
            return Localization.get(
                locale, "farkle-take-small-straight", points=points
            )
        elif combo_type == COMBO_LARGE_STRAIGHT:
            return Localization.get(
                locale, "farkle-take-large-straight", points=points
            )
        elif combo_type == COMBO_THREE_PAIRS:
            return Localization.get(locale, "farkle-take-three-pairs", points=points)
        elif combo_type == COMBO_DOUBLE_TRIPLETS:
            return Localization.get(
                locale, "farkle-take-double-triplets", points=points
            )
        elif combo_type == COMBO_FULL_HOUSE:
            return Localization.get(locale, "farkle-take-full-house", points=points)
        return f"{combo_type} for {points} points"

    def _get_combo_name(self, combo_type: str, number: int) -> str:
        """Get the English name for a combo (for announcements). Matches v10 exactly."""
        if combo_type == COMBO_SINGLE_1:
            return "Single 1"
        elif combo_type == COMBO_SINGLE_5:
            return "Single 5"
        elif combo_type == COMBO_THREE_OF_KIND:
            return f"Three {number}s"
        elif combo_type == COMBO_FOUR_OF_KIND:
            return f"Four {number}s"
        elif combo_type == COMBO_FIVE_OF_KIND:
            return f"Five {number}s"
        elif combo_type == COMBO_SIX_OF_KIND:
            return f"Six {number}s"
        elif combo_type == COMBO_SMALL_STRAIGHT:
            return "Small Straight"
        elif combo_type == COMBO_LARGE_STRAIGHT:
            return "Large Straight"
        elif combo_type == COMBO_THREE_PAIRS:
            return "Three pairs"
        elif combo_type == COMBO_DOUBLE_TRIPLETS:
            return "Double triplets"
        elif combo_type == COMBO_FULL_HOUSE:
            return "Full house"
        return combo_type

    def update_scoring_actions(self, player: FarklePlayer) -> None:
        """Update scoring actions based on current roll.

        Scoring actions are placed BEFORE roll/bank in the menu.
        """
        turn_set = self.get_action_set(player, "turn")
        if not turn_set:
            return

        user = self.get_user(player)
        locale = user.locale if user else "en"

        # Remove old scoring actions from _actions dict
        old_actions = [
            action_id
            for action_id in turn_set._actions.keys()
            if action_id.startswith("score_")
        ]
        for action_id in old_actions:
            del turn_set._actions[action_id]

        # Get available combinations
        combos = get_available_combinations(player.current_roll)

        # Rebuild the order: scoring actions first, then roll, bank, check_turn_score
        turn_set._order.clear()

        # Add scoring actions first (sorted by points, highest first)
        for combo_type, number, points in combos:
            action_id = f"score_{combo_type}_{number}"
            label = self._get_combo_label(locale, combo_type, number, points)

            turn_set._actions[action_id] = Action(
                id=action_id,
                label=label,
                handler="_action_take_combo",
                enabled=True,
            )
            turn_set._order.append(action_id)

        # Add roll, bank, check_turn_score after scoring actions
        for action_id in ["roll", "bank", "check_turn_score"]:
            if action_id in turn_set._actions:
                turn_set._order.append(action_id)

    def update_turn_actions(self, player: FarklePlayer) -> None:
        """Update turn action availability and labels for a player."""
        turn_set = self.get_action_set(player, "turn")
        if not turn_set:
            return

        user = self.get_user(player)
        locale = user.locale if user else "en"
        is_playing = self.status == "playing"
        is_spectator = player.is_spectator
        is_current = self.current_player == player

        if is_playing and is_current and not is_spectator:
            # Roll action: available if no current roll or has taken a combo
            can_roll = len(player.current_roll) == 0 or player.has_taken_combo
            if can_roll:
                turn_set.enable("roll")
                turn_set.show("roll")
                # Update roll label with dice count
                num_dice = self._get_roll_dice_count(player)
                turn_set.set_label(
                    "roll", Localization.get(locale, "farkle-roll", count=num_dice)
                )
            else:
                turn_set.disable("roll")
                turn_set.hide("roll")

            # Bank action: available if turn_score > 0 and no scoring dice left
            can_bank = player.turn_score > 0 and (
                len(player.current_roll) == 0
                or not has_scoring_dice(player.current_roll)
            )
            if can_bank:
                turn_set.enable("bank")
                turn_set.show("bank")
                turn_set.set_label(
                    "bank",
                    Localization.get(locale, "farkle-bank", points=player.turn_score),
                )
            else:
                turn_set.disable("bank")
                turn_set.hide("bank")

            # Scoring actions are always enabled when present
            for action_id in turn_set._actions.keys():
                if action_id.startswith("score_"):
                    turn_set.enable(action_id)
                    turn_set.show(action_id)
        else:
            # Disable all turn actions for non-current players
            turn_set.disable("roll", "bank")
            for action_id in turn_set._actions.keys():
                if action_id.startswith("score_"):
                    turn_set.disable(action_id)

        # Update standard actions (status keybinds)
        self.update_standard_actions(player)

    def update_all_turn_actions(self) -> None:
        """Update turn actions for all players."""
        for player in self.players:
            self.update_turn_actions(player)

    def _get_roll_dice_count(self, player: FarklePlayer) -> int:
        """Get the number of dice that will be rolled."""
        if len(player.current_roll) > 0:
            return len(player.current_roll)
        else:
            num_dice = 6 - len(player.banked_dice)
            if num_dice == 0:
                num_dice = 6  # Hot dice
            return num_dice

    def _action_roll(self, player: Player, action_id: str) -> None:
        """Handle roll action."""
        farkle_player: FarklePlayer = player  # type: ignore

        # Check for hot dice (all 6 banked) and reset
        if len(farkle_player.current_roll) == 0:
            num_dice = 6 - len(farkle_player.banked_dice)
            if num_dice == 0:
                # Hot dice! Reset banked dice and roll all 6
                farkle_player.banked_dice = []
                num_dice = 6
        else:
            num_dice = len(farkle_player.current_roll)

        self.broadcast_l("farkle-rolls", player=player.name, count=num_dice)
        self.play_sound("game_pig/roll.ogg")

        # Jolt bot to pause before next action
        BotHelper.jolt_bot(player, ticks=random.randint(10, 20))

        # Roll the dice
        farkle_player.current_roll = sorted(
            [random.randint(1, 6) for _ in range(num_dice)]
        )

        # Announce the roll
        dice_str = ", ".join(str(d) for d in farkle_player.current_roll)
        self.broadcast_l("farkle-roll-result", dice=dice_str)

        # Check for farkle
        if not has_scoring_dice(farkle_player.current_roll):
            self.play_sound("game_farkle/farkle.ogg")
            self.broadcast_l(
                "farkle-farkle", player=player.name, points=farkle_player.turn_score
            )
            farkle_player.turn_score = 0
            farkle_player.current_roll = []
            farkle_player.banked_dice = []
            self.end_turn()
            return

        # Reset combo flag after roll
        farkle_player.has_taken_combo = False

        # Update scoring actions based on new roll
        self.update_scoring_actions(farkle_player)
        self.update_turn_actions(farkle_player)
        self.rebuild_player_menu(farkle_player)

    def _action_take_combo(self, player: Player, action_id: str) -> None:
        """Handle taking a scoring combination."""
        farkle_player: FarklePlayer = player  # type: ignore

        # Jolt bot to pause before next action
        BotHelper.jolt_bot(player, ticks=random.randint(8, 12))

        # Parse combo type and number from action_id (e.g., "score_three_of_kind_4")
        parts = action_id.split("_", 1)[1]  # Remove "score_" prefix

        # Extract combo type and number
        if parts.startswith("single_1"):
            combo_type = COMBO_SINGLE_1
            number = 1
        elif parts.startswith("single_5"):
            combo_type = COMBO_SINGLE_5
            number = 5
        elif parts.startswith("three_of_kind"):
            combo_type = COMBO_THREE_OF_KIND
            number = int(parts.split("_")[-1])
        elif parts.startswith("four_of_kind"):
            combo_type = COMBO_FOUR_OF_KIND
            number = int(parts.split("_")[-1])
        elif parts.startswith("five_of_kind"):
            combo_type = COMBO_FIVE_OF_KIND
            number = int(parts.split("_")[-1])
        elif parts.startswith("six_of_kind"):
            combo_type = COMBO_SIX_OF_KIND
            number = int(parts.split("_")[-1])
        elif parts.startswith("small_straight"):
            combo_type = COMBO_SMALL_STRAIGHT
            number = 0
        elif parts.startswith("large_straight"):
            combo_type = COMBO_LARGE_STRAIGHT
            number = 0
        elif parts.startswith("three_pairs"):
            combo_type = COMBO_THREE_PAIRS
            number = 0
        elif parts.startswith("double_triplets"):
            combo_type = COMBO_DOUBLE_TRIPLETS
            number = 0
        elif parts.startswith("full_house"):
            combo_type = COMBO_FULL_HOUSE
            number = 0
        else:
            return  # Unknown combo

        points = get_combination_points(combo_type, number)
        combo_name = self._get_combo_name(combo_type, number)

        # Remove dice from current_roll and add to banked_dice
        self._remove_combo_dice(farkle_player, combo_type, number)

        # Add points
        farkle_player.turn_score += points

        # Play sounds
        self.play_sound("game_farkle/takepoint.ogg")
        if combo_type in COMBO_SOUNDS:
            self.schedule_sound(COMBO_SOUNDS[combo_type], delay_ticks=2)

        # Announce what was taken
        user = self.get_user(player)
        if user:
            user.speak_l(
                "farkle-you-take-combo", combo=combo_name, points=points
            )
        # Tell others
        for other in self.players:
            if other != player:
                other_user = self.get_user(other)
                if other_user:
                    other_user.speak_l(
                        "farkle-takes-combo",
                        player=player.name,
                        combo=combo_name,
                        points=points,
                    )

        # Check for hot dice
        if len(farkle_player.banked_dice) == 6 and len(farkle_player.current_roll) == 0:
            self.broadcast_l("farkle-hot-dice")
            self.play_sound("game_farkle/hotdice.ogg")

        # Mark that we've taken a combo
        farkle_player.has_taken_combo = True

        # Update actions
        self.update_scoring_actions(farkle_player)
        self.update_turn_actions(farkle_player)
        self.rebuild_player_menu(farkle_player)

    def _remove_combo_dice(
        self, player: FarklePlayer, combo_type: str, number: int
    ) -> None:
        """Remove dice from current_roll for the given combination."""
        counts = count_dice(player.current_roll)

        if combo_type == COMBO_SINGLE_1:
            # Remove one 1
            player.current_roll.remove(1)
            player.banked_dice.append(1)

        elif combo_type == COMBO_SINGLE_5:
            # Remove one 5
            player.current_roll.remove(5)
            player.banked_dice.append(5)

        elif combo_type == COMBO_THREE_OF_KIND:
            # Remove three of the number
            for _ in range(3):
                player.current_roll.remove(number)
                player.banked_dice.append(number)

        elif combo_type == COMBO_FOUR_OF_KIND:
            # Remove four of the number
            for _ in range(4):
                player.current_roll.remove(number)
                player.banked_dice.append(number)

        elif combo_type == COMBO_FIVE_OF_KIND:
            # Remove five of the number
            for _ in range(5):
                player.current_roll.remove(number)
                player.banked_dice.append(number)

        elif combo_type == COMBO_SIX_OF_KIND:
            # Remove all six of the number
            for _ in range(6):
                player.current_roll.remove(number)
                player.banked_dice.append(number)

        elif combo_type == COMBO_LARGE_STRAIGHT:
            # Remove all dice (1-6)
            player.banked_dice.extend(player.current_roll)
            player.current_roll = []

        elif combo_type == COMBO_SMALL_STRAIGHT:
            # Remove 5 dice for small straight
            counts = count_dice(player.current_roll)
            # Determine which straight we have
            has_1_5 = all(counts[i] >= 1 for i in range(1, 6))
            if has_1_5:
                needed = [1, 2, 3, 4, 5]
            else:
                needed = [2, 3, 4, 5, 6]

            for num in needed:
                player.current_roll.remove(num)
                player.banked_dice.append(num)

        elif combo_type in (
            COMBO_THREE_PAIRS,
            COMBO_DOUBLE_TRIPLETS,
            COMBO_FULL_HOUSE,
        ):
            # Remove all 6 dice
            player.banked_dice.extend(player.current_roll)
            player.current_roll = []

    def _action_bank(self, player: Player, action_id: str) -> None:
        """Handle bank action."""
        farkle_player: FarklePlayer = player  # type: ignore

        # Add turn score to permanent score
        farkle_player.score += farkle_player.turn_score

        self.play_sound(f"game_farkle/bank{random.randint(1, 3)}.ogg")

        self.broadcast_l(
            "farkle-banks",
            player=player.name,
            points=farkle_player.turn_score,
            total=farkle_player.score,
        )

        # Reset turn state
        farkle_player.turn_score = 0
        farkle_player.current_roll = []
        farkle_player.banked_dice = []
        farkle_player.has_taken_combo = False

        self.end_turn()

    def _action_check_turn_score(self, player: Player, action_id: str) -> None:
        """Handle check turn score action."""
        current = self.current_player
        if current:
            farkle_current: FarklePlayer = current  # type: ignore
            self.status_box(
                player,
                [
                    Localization.get(
                        "en",
                        "farkle-turn-score",
                        player=current.name,
                        points=farkle_current.turn_score,
                    )
                ],
            )
        else:
            self.status_box(
                player, [Localization.get("en", "farkle-no-turn")]
            )

    def on_start(self) -> None:
        """Called when the game starts."""
        self.status = "playing"
        self.game_active = True
        self.round = 0

        # Initialize turn order
        active_players = self.get_active_players()
        self.set_turn_players(active_players)

        # Reset all player state
        for p in active_players:
            farkle_p: FarklePlayer = p  # type: ignore
            farkle_p.score = 0
            farkle_p.turn_score = 0
            farkle_p.current_roll = []
            farkle_p.banked_dice = []
            farkle_p.has_taken_combo = False

        # Update action availability for game start
        self.update_all_lobby_actions()
        self.update_all_options_actions()
        self.update_all_turn_actions()

        # Play intro music (using pig music as placeholder)
        self.play_music("game_pig/mus.ogg")

        # Start first round
        self._start_round()

    def _start_round(self) -> None:
        """Start a new round."""
        self.round += 1

        # Refresh turn order
        self.set_turn_players(self.get_active_players())

        self.broadcast_l("game-round-start", round=self.round)

        self._start_turn()

    def _start_turn(self) -> None:
        """Start a player's turn."""
        player = self.current_player
        if not player:
            return

        farkle_player: FarklePlayer = player  # type: ignore

        # Reset turn state
        farkle_player.turn_score = 0
        farkle_player.current_roll = []
        farkle_player.banked_dice = []
        farkle_player.has_taken_combo = False

        # Announce turn
        self.announce_turn()

        # Set up bot if needed
        if player.is_bot:
            BotHelper.set_target(player, 0)  # Bot will calculate during think

        # Update action availability
        self.update_all_turn_actions()
        self.rebuild_all_menus()

    def on_tick(self) -> None:
        """Called every tick. Handle bot AI and scheduled sounds."""
        self.process_scheduled_sounds()

        if not self.game_active:
            return

        BotHelper.on_tick(self)

    def bot_think(self, player: FarklePlayer) -> str | None:
        """Bot AI decision making."""
        turn_set = self.get_action_set(player, "turn")
        if not turn_set:
            return None

        # Take highest-value scoring combo first
        for action in turn_set.get_enabled_actions():
            if action.id.startswith("score_"):
                return action.id

        # If can roll, decide whether to roll or bank
        roll_action = turn_set.get_action("roll")
        bank_action = turn_set.get_action("bank")

        if roll_action and roll_action.enabled:
            # Banking decision based on dice remaining and points
            dice_remaining = 6 - len(player.banked_dice)
            if dice_remaining == 0:
                dice_remaining = 6  # Hot dice

            # Check if someone already reached target score
            score_to_beat = None
            for other in self.players:
                if other != player:
                    other_farkle: FarklePlayer = other  # type: ignore
                    if other_farkle.score >= self.options.target_score:
                        if score_to_beat is None or other_farkle.score > score_to_beat:
                            score_to_beat = other_farkle.score

            potential_total = player.score + player.turn_score

            # If someone has already won, must beat them or bust trying
            if score_to_beat is not None and potential_total <= score_to_beat:
                return "roll"

            # Banking decision based on turn score and dice remaining
            if player.turn_score >= 35:
                # Bank probability increases as fewer dice remain
                bank_probabilities = {
                    6: 0.40,
                    5: 0.50,
                    4: 0.55,
                    3: 0.65,
                    2: 0.70,
                    1: 0.75,
                }
                bank_prob = bank_probabilities.get(dice_remaining, 0.50)

                if random.random() < bank_prob:
                    if bank_action and bank_action.enabled:
                        return "bank"

            return "roll"

        if bank_action and bank_action.enabled:
            return "bank"

        return None

    def _on_turn_end(self) -> None:
        """Handle end of a player's turn."""
        # Check if round is over
        if self.turn_index >= len(self.turn_players) - 1:
            self._on_round_end()
        else:
            self.advance_turn(announce=False)
            self._start_turn()

    def _on_round_end(self) -> None:
        """Handle end of a round."""
        # Check for winners
        active_players = self.get_active_players()
        winners = []
        high_score = 0

        for p in active_players:
            farkle_p: FarklePlayer = p  # type: ignore
            if farkle_p.score >= self.options.target_score:
                if farkle_p.score > high_score:
                    winners = [p]
                    high_score = farkle_p.score
                elif farkle_p.score == high_score:
                    winners.append(p)

        if len(winners) == 1:
            # Single winner
            self.play_sound("game_pig/win.ogg")
            winner_farkle: FarklePlayer = winners[0]  # type: ignore
            self.broadcast_l(
                "farkle-winner", player=winners[0].name, score=winner_farkle.score
            )
            self.finish_game()
            if not self._destroyed:
                self._on_game_end()
        elif len(winners) > 1:
            # Tie - announce winners
            names = [w.name for w in winners]
            for p in self.players:
                user = self.get_user(p)
                if user:
                    names_str = Localization.format_list_and(user.locale, names)
                    user.speak_l("farkle-winners-tie", players=names_str)

            # Mark non-winners as spectators for tiebreaker
            winner_names = [w.name for w in winners]
            for p in active_players:
                if p.name not in winner_names:
                    p.is_spectator = True
            self._start_round()
        else:
            # No winner yet
            self._start_round()

    def _on_game_end(self) -> None:
        """Handle game ending - show final scores."""
        lines = ["Final Scores:"]
        sorted_players = sorted(
            self.get_active_players(),
            key=lambda p: p.score,  # type: ignore
            reverse=True,
        )
        for i, p in enumerate(sorted_players, 1):
            farkle_p: FarklePlayer = p  # type: ignore
            lines.append(f"{i}. {p.name}: {farkle_p.score} points")
        self.show_game_end_menu(lines)

    def end_turn(self, jolt_min: int = 20, jolt_max: int = 30) -> None:
        """End the current player's turn."""
        BotHelper.jolt_bots(self, ticks=random.randint(jolt_min, jolt_max))
        self._on_turn_end()
