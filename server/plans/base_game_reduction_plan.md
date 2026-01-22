# Plan: Extract Mixins from games/base.py

## Overview

**Goal:** Reduce `games/base.py` file size by extracting cohesive functionality into reusable mixins while keeping core game infrastructure intact.

**Why:** The base Game class became too large (2,277 lines), making it hard to navigate and maintain. Extracting into mixins improves organization and allows games to potentially opt out of certain functionality.

**Approach:**
- Each mixin is a standalone class in `game_utils/`
- Uses `TYPE_CHECKING` imports to avoid circular dependencies
- Mixins define abstract method stubs for methods they expect the Game class to provide
- Game class inherits from all mixins via multiple inheritance
- Mixins are exported from `game_utils/__init__.py`

**What stays in base.py (core functions):**
- Game state fields and `__post_init__`
- Abstract methods (`get_name`, `get_type`, `on_start`)
- Player/user management (`get_user`, `attach_user`, `get_player_by_id`)
- Action system core (`execute_action`, `find_action`, `resolve_action`, action sets)
- Event handling (`handle_event`)
- `current_player` property and `end_turn`

**To continue extraction:** Follow the existing mixin pattern - create a new file, define the class with docstring listing expected attributes/methods, add TYPE_CHECKING imports, implement methods, then remove from base.py and add to inheritance chain.

---

## Progress Summary

| Phase | Starting Lines | Ending Lines | Reduction |
|-------|---------------|--------------|-----------|
| Phase 1 | 2,277 | 1,687 | 590 (26%) |
| Phase 2 | 1,687 | 1,136 | 551 (33%) |
| **Total** | **2,277** | **1,136** | **1,141 (50%)** |

---

## Phase 1: Initial Mixin Extraction

### Goal
Reduce `games/base.py` (2,277 lines) by at least 30% (~683 lines) by extracting functionality into reusable mixins.

### Mixins Created

| Mixin | Lines to Extract | Approx. Size |
|-------|------------------|--------------|
| `GameSoundMixin` | 898-952, 1029-1067 | ~95 lines |
| `GameCommunicationMixin` | 956-1028 | ~72 lines |
| `GameResultMixin` | 298-451 | ~154 lines |
| `DurationEstimateMixin` | 2105-2277 | ~172 lines |
| `GameScoresMixin` | 1901-1932 | ~32 lines |
| `GamePredictionMixin` | 1934-1996 | ~62 lines |
| **Total** | | **~587 lines** |

### Mixin Specifications

#### 1. GameSoundMixin (`game_utils/game_sound_mixin.py`)
**Methods:**
- `schedule_sound()` - Schedule sound with delay
- `schedule_sound_sequence()` - Schedule multiple sounds
- `clear_scheduled_sounds()` - Clear scheduled sounds
- `process_scheduled_sounds()` - Process and play scheduled sounds
- `broadcast_sound()` - Play sound for all players
- `play_sound()` - Alias for broadcast_sound
- `play_music()` - Play music for all players
- `play_ambience()` - Play ambient sounds
- `stop_ambience()` - Stop ambient sounds

**Expects on Game class:**
- `self.scheduled_sounds: list`
- `self.sound_scheduler_tick: int`
- `self.current_music: str`
- `self.current_ambience: str`
- `self.players: list[Player]`
- `self.get_user(player) -> User | None`

#### 2. GameCommunicationMixin (`game_utils/game_communication_mixin.py`)
**Methods:**
- `broadcast()` - Send text to all players
- `broadcast_l()` - Send localized message to all
- `broadcast_personal_l()` - Personal vs others messages
- `label_l()` - Create localized label callable

**Expects on Game class:**
- `self.players: list[Player]`
- `self.get_user(player) -> User | None`

#### 3. GameResultMixin (`game_utils/game_result_mixin.py`)
**Methods:**
- `finish_game()` - Mark game finished, persist, show end
- `build_game_result()` - Build GameResult object
- `format_end_screen()` - Format end screen lines
- `_persist_result()` - Save to database
- `_update_ratings()` - Update player ratings
- `get_rankings_for_rating()` - Get rankings for rating
- `_show_end_screen()` - Display end screen
- `show_game_end_menu()` - Deprecated legacy method

**Expects on Game class:**
- `self.game_active: bool`
- `self.status: str`
- `self.players: list[Player]`
- `self.sound_scheduler_tick: int`
- `self._table: Any`
- `self.get_user(player) -> User | None`
- `self.get_type() -> str`
- `self.get_active_players() -> list[Player]`
- `self.destroy()`

#### 4. DurationEstimateMixin (`game_utils/duration_estimate_mixin.py`)
**Constants:**
- `NUM_ESTIMATE_SIMULATIONS = 10`
- `HUMAN_SPEED_MULTIPLIER = 2`

**Methods:**
- `_action_estimate_duration()` - Start CLI simulations
- `check_estimate_completion()` - Check if done (called from on_tick)
- `_calculate_std_dev()` - Calculate standard deviation
- `_detect_outliers()` - Detect outliers using IQR
- `_format_duration()` - Format ticks as readable time

**Expects on Game class:**
- `self._estimate_threads: list`
- `self._estimate_results: list`
- `self._estimate_errors: list`
- `self._estimate_running: bool`
- `self._estimate_lock: threading.Lock`
- `self.players: list[Player]`
- `self.get_user(player) -> User | None`
- `self.broadcast_l()` / `self.broadcast()`
- `self.get_type() -> str`
- `self.get_min_players() -> int`
- `self.TICKS_PER_SECOND: int`

#### 5. GameScoresMixin (`game_utils/game_scores_mixin.py`)
**Methods:**
- `_action_whose_turn()` - Announce current player
- `_action_check_scores()` - Brief score announcement
- `_action_check_scores_detailed()` - Detailed scores in status box

**Expects on Game class:**
- `self.current_player: Player | None`
- `self.team_manager: TeamManager`
- `self.players: list[Player]`
- `self.get_user(player) -> User | None`
- `self.status_box(player, lines)`

#### 6. GamePredictionMixin (`game_utils/game_prediction_mixin.py`)
**Methods:**
- `_action_predict_outcomes()` - Show win probability predictions

**Expects on Game class:**
- `self._table: Any`
- `self.players: list[Player]`
- `self.get_user(player) -> User | None`
- `self.get_type() -> str`
- `self.status_box(player, lines)`

---

## Phase 2: Additional Mixin Extraction

### Goal
Reduce `games/base.py` from 1,687 lines by another 30% (~506 lines) to approximately 1,181 lines.

### Mixins Created

| Mixin | Lines to Extract | Approx. Size |
|-------|------------------|--------------|
| `TurnManagementMixin` | 646-746 | ~100 lines |
| `MenuManagementMixin` | 748-818 | ~70 lines |
| `LobbyActionsMixin` | 1404-1579 | ~175 lines |
| `ActionVisibilityMixin` | 985-1160 | ~175 lines |
| **Total** | | **~520 lines** |

### Mixin Specifications

#### 1. TurnManagementMixin (`game_utils/turn_management_mixin.py`)
**Methods:**
- `set_turn_players()` - Set players in turn order
- `advance_turn()` - Move to next player's turn
- `skip_next_players()` - Queue players to skip
- `on_player_skipped()` - Called when player is skipped (hook)
- `reverse_turn_direction()` - Reverse turn order
- `reset_turn_order()` - Reset to first player
- `announce_turn()` - Announce current player's turn
- `turn_players` property - Get players in turn order

**Expects on Game class:**
- `self.turn_player_ids: list[str]`
- `self.turn_index: int`
- `self.turn_direction: int`
- `self.turn_skip_count: int`
- `self.get_player_by_id(player_id) -> Player | None`
- `self.get_user(player) -> User | None`
- `self.broadcast_l(message_id, **kwargs)`
- `self.rebuild_all_menus()`
- `self.current_player` property

#### 2. MenuManagementMixin (`game_utils/menu_management_mixin.py`)
**Methods:**
- `rebuild_player_menu()` - Rebuild menu for one player
- `rebuild_all_menus()` - Rebuild menus for all players
- `update_player_menu()` - Update menu preserving focus
- `update_all_menus()` - Update all menus preserving focus
- `status_box()` - Show status box to player

**Expects on Game class:**
- `self._destroyed: bool`
- `self.status: str`
- `self.players: list[Player]`
- `self._status_box_open: set[str]`
- `self.get_user(player) -> User | None`
- `self.get_all_visible_actions(player) -> list[ResolvedAction]`

#### 3. LobbyActionsMixin (`game_utils/lobby_actions_mixin.py`)
**Methods:**
- `_action_start_game()` - Start the game
- `_bot_input_add_bot()` - Get bot name automatically
- `_action_add_bot()` - Add bot to game
- `_action_remove_bot()` - Remove bot from game
- `_action_toggle_spectator()` - Toggle spectator mode
- `_action_leave_game()` - Leave the game
- `_action_show_actions_menu()` - Show F5 actions menu
- `_action_save_table()` - Save table state

**Expects on Game class:**
- `self.status: str`
- `self.host: str`
- `self.players: list[Player]`
- `self._table: Any`
- `self._users: dict`
- `self._actions_menu_open: set[str]`
- `self.player_action_sets: dict`
- `self.get_user(player) -> User | None`
- `self.broadcast_l()`, `self.broadcast_sound()`
- `self.prestart_validate()`, `self.on_start()`
- `self.create_player()`, `self.setup_player_actions()`
- `self.attach_user()`, `self.rebuild_all_menus()`
- `self.destroy()`
- `self.get_all_enabled_actions()`
- `self._get_keybind_for_action()`

#### 4. ActionVisibilityMixin (`game_utils/action_visibility_mixin.py`)
**Methods (all is_enabled/is_hidden/get_label):**
- `_is_start_game_enabled()`, `_is_start_game_hidden()`
- `_is_add_bot_enabled()`, `_is_add_bot_hidden()`
- `_is_remove_bot_enabled()`, `_is_remove_bot_hidden()`
- `_is_toggle_spectator_enabled()`, `_is_toggle_spectator_hidden()`
- `_get_toggle_spectator_label()`
- `_is_leave_game_enabled()`, `_is_leave_game_hidden()`
- `_is_option_enabled()`, `_is_option_hidden()`
- `_is_estimate_duration_enabled()`, `_is_estimate_duration_hidden()`
- `_is_show_actions_enabled()`, `_is_show_actions_hidden()`
- `_is_save_table_enabled()`, `_is_save_table_hidden()`
- `_is_whose_turn_enabled()`, `_is_whose_turn_hidden()`
- `_is_check_scores_enabled()`, `_is_check_scores_hidden()`
- `_is_check_scores_detailed_enabled()`, `_is_check_scores_detailed_hidden()`
- `_is_predict_outcomes_enabled()`, `_is_predict_outcomes_hidden()`

**Expects on Game class:**
- `self.status: str`
- `self.host: str`
- `self.players: list[Player]`
- `self.team_manager: TeamManager`
- `self.get_user(player) -> User | None`
- `self.get_min_players()`, `self.get_max_players()`
- `self.get_active_player_count()`

---

## Final Inheritance Structure

```python
@dataclass
class Game(
    ABC,
    DataClassJSONMixin,
    GameSoundMixin,
    GameCommunicationMixin,
    GameResultMixin,
    DurationEstimateMixin,
    GameScoresMixin,
    GamePredictionMixin,
    TurnManagementMixin,
    MenuManagementMixin,
    ActionVisibilityMixin,
    LobbyActionsMixin,
):
    """Abstract base class for all games."""
    ...
```

---

## Future Phases (Not Yet Implemented)

Remaining sections in `base.py` that could potentially be extracted:

| Section | Approx. Lines | Notes |
|---------|---------------|-------|
| Event Handling (`handle_event`) | ~140 lines | Complex, handles menu/keybind events |
| Action Set Creation | ~200 lines | Creates lobby/estimate/standard action sets |
| Action System (execute, resolve, find) | ~150 lines | Core action execution logic |
| Options System | ~75 lines | Declarative options handling |
| Player Management | ~50 lines | get_user, attach_user, etc. |

Current base.py is at **1,136 lines** with core game functionality intact.
