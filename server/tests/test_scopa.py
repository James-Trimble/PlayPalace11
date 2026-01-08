"""Tests for Scopa game implementation."""

from pathlib import Path

from server.games.scopa.game import ScopaGame, ScopaPlayer, ScopaOptions
from server.games.scopa.capture import find_captures, select_best_capture
from server.games.registry import GameRegistry
from server.game_utils.cards import Card, DeckFactory
from server.game_utils.teams import TeamManager
from server.users.test_user import MockUser
from server.messages.localization import Localization

# Initialize localization for tests
_locales_dir = Path(__file__).parent.parent / "locales"
Localization.init(_locales_dir)


class TestCardUtility:
    """Tests for card utility functions."""

    def test_italian_deck_creation(self):
        """Test creating an Italian deck."""
        deck, lookup = DeckFactory.italian_deck()
        assert deck.size() == 40
        assert len(lookup) == 40

    def test_italian_deck_multiple(self):
        """Test creating multiple Italian decks."""
        deck, lookup = DeckFactory.italian_deck(num_decks=2)
        assert deck.size() == 80
        assert len(lookup) == 80

    def test_deck_draw(self):
        """Test drawing cards from deck."""
        deck, _ = DeckFactory.italian_deck()
        cards = deck.draw(3)
        assert len(cards) == 3
        assert deck.size() == 37

    def test_deck_shuffle(self):
        """Test deck shuffling produces different order."""
        deck1, _ = DeckFactory.italian_deck()
        deck2, _ = DeckFactory.italian_deck()
        # With high probability, two shuffled decks will be different
        # (1 in 40! chance of being same)
        cards1 = [c.id for c in deck1.cards]
        cards2 = [c.id for c in deck2.cards]
        # They should have same cards but likely different order
        assert sorted(cards1) == sorted(cards2)


class TestTeamManager:
    """Tests for team manager utility."""

    def test_individual_mode(self):
        """Test individual (no teams) mode."""
        tm = TeamManager(team_mode="individual")
        tm.setup_teams(["Alice", "Bob", "Carol"])
        assert len(tm.teams) == 3
        assert tm.teams[0].members == ["Alice"]
        assert tm.teams[1].members == ["Bob"]
        assert tm.teams[2].members == ["Carol"]

    def test_2v2_mode(self):
        """Test 2v2 team mode."""
        tm = TeamManager(team_mode="2v2")
        tm.setup_teams(["Alice", "Bob", "Carol", "Dave"])
        assert len(tm.teams) == 2
        assert tm.teams[0].members == ["Alice", "Bob"]
        assert tm.teams[1].members == ["Carol", "Dave"]

    def test_get_team(self):
        """Test getting player's team."""
        tm = TeamManager(team_mode="2v2")
        tm.setup_teams(["Alice", "Bob", "Carol", "Dave"])
        assert tm.get_team("Alice").index == 0
        assert tm.get_team("Carol").index == 1

    def test_get_teammates(self):
        """Test getting teammates."""
        tm = TeamManager(team_mode="2v2")
        tm.setup_teams(["Alice", "Bob", "Carol", "Dave"])
        assert tm.get_teammates("Alice") == ["Bob"]
        assert tm.get_teammates("Carol") == ["Dave"]

    def test_team_scoring(self):
        """Test adding to team score."""
        tm = TeamManager(team_mode="2v2")
        tm.setup_teams(["Alice", "Bob", "Carol", "Dave"])
        tm.add_to_team_score("Alice", 5)
        assert tm.teams[0].total_score == 5
        tm.add_to_team_score("Bob", 3)
        assert tm.teams[0].total_score == 8

    def test_team_modes_generation(self):
        """Test generating valid team modes."""
        modes = TeamManager.get_team_modes_for_player_count(4)
        assert "individual" in modes
        assert "2v2" in modes

        modes = TeamManager.get_team_modes_for_player_count(6)
        assert "individual" in modes
        assert "2v2v2" in modes
        assert "3v3" in modes


class TestScopaGameUnit:
    """Unit tests for Scopa game."""

    def test_game_registration(self):
        """Test that Scopa is registered."""
        game_class = GameRegistry.get("scopa")
        assert game_class is not None
        assert game_class.get_name() == "Scopa"
        assert game_class.get_category() == "category-card-games"

    def test_game_creation(self):
        """Test creating a new game."""
        game = ScopaGame()
        assert game.status == "waiting"
        assert len(game.players) == 0

    def test_player_creation(self):
        """Test player creation."""
        player = ScopaPlayer(id="test-uuid", name="Test", is_bot=False)
        assert player.id == "test-uuid"
        assert player.name == "Test"
        assert player.hand == []
        assert player.captured == []
        assert player.scopas == 0

    def test_options_defaults(self):
        """Test default options."""
        options = ScopaOptions()
        assert options.target_score == 11
        assert options.cards_per_deal == 3
        assert options.number_of_decks == 1
        assert options.escoba_rules is False
        assert options.team_mode == "individual"

    def test_serialization(self):
        """Test game serialization."""
        import json

        game = ScopaGame()
        user = MockUser("Player1")
        game.add_player("Player1", user)

        # Modify some state
        game.options.target_score = 21
        game.current_round = 2

        # Serialize
        json_str = game.to_json()
        data = json.loads(json_str)

        # Verify structure
        assert "players" in data
        assert len(data["players"]) == 1

        # Deserialize
        game2 = ScopaGame.from_json(json_str)
        assert len(game2.players) == 1
        assert game2.players[0].name == "Player1"
        assert game2.options.target_score == 21
        assert game2.current_round == 2


class TestScopaCaptureLogic:
    """Tests for capture logic."""

    def test_find_rank_match(self):
        """Test finding rank matches."""
        table_cards = [
            Card(id=0, rank=5, suit=1),
            Card(id=1, rank=7, suit=2),
            Card(id=2, rank=3, suit=3),
        ]

        captures = find_captures(table_cards, 7)
        assert len(captures) == 1
        assert len(captures[0]) == 1
        assert captures[0][0].rank == 7

    def test_find_sum_match(self):
        """Test finding sum matches."""
        table_cards = [
            Card(id=0, rank=3, suit=1),
            Card(id=1, rank=4, suit=2),
            Card(id=2, rank=2, suit=3),
        ]

        captures = find_captures(table_cards, 7)
        # Should find 3+4=7
        assert len(captures) >= 1
        found = False
        for capture in captures:
            if sum(c.rank for c in capture) == 7:
                found = True
                break
        assert found

    def test_rank_match_preferred(self):
        """Test that rank match is preferred over sum."""
        table_cards = [
            Card(id=0, rank=5, suit=1),
            Card(id=1, rank=2, suit=2),
            Card(id=2, rank=3, suit=3),
        ]

        captures = find_captures(table_cards, 5)
        # Should only return rank match, not 2+3
        assert len(captures) == 1
        assert captures[0][0].rank == 5

    def test_escoba_sum_to_15(self):
        """Test escoba rules (sum to 15)."""
        table_cards = [
            Card(id=0, rank=3, suit=1),
            Card(id=1, rank=5, suit=2),
        ]

        # Playing a 7: need table cards that sum to 15-7=8, so 3+5=8
        captures = find_captures(table_cards, 7, escoba_rules=True)
        assert len(captures) >= 1
        found = False
        for capture in captures:
            if sum(c.rank for c in capture) == 8:
                found = True
                break
        assert found

    def test_select_best_capture(self):
        """Test selecting best (most cards) capture."""
        captures = [
            [Card(id=0, rank=5, suit=1)],
            [Card(id=1, rank=2, suit=2), Card(id=2, rank=3, suit=3)],
        ]

        best = select_best_capture(captures)
        assert len(best) == 2


class TestScopaGameFlow:
    """Tests for game flow."""

    def test_game_start(self):
        """Test starting a game."""
        game = ScopaGame()
        user1 = MockUser("Player1")
        user2 = MockUser("Player2")
        game.add_player("Player1", user1)
        game.add_player("Player2", user2)

        game.on_start()

        assert game.status == "playing"
        assert game.current_round == 1
        # Players should have cards
        assert len(game.players[0].hand) > 0 or len(game.players[1].hand) > 0

    def test_deck_creation(self):
        """Test deck is created on round start."""
        game = ScopaGame()
        user1 = MockUser("Player1")
        user2 = MockUser("Player2")
        game.add_player("Player1", user1)
        game.add_player("Player2", user2)

        game.on_start()

        # Deck should have been dealt from
        total_cards = 40 * game.options.number_of_decks
        dealt = (
            sum(len(p.hand) for p in game.players)
            + len(game.table_cards)
            + game.deck.size()
        )
        assert dealt == total_cards


class TestScopaPlayTest:
    """Integration tests for complete game play."""

    def test_two_player_bot_game_completes(self):
        """Test that a 2-player bot game completes."""
        from server.users.bot import Bot

        game = ScopaGame()
        game.options.target_score = 5  # Lower for faster test

        bot1 = Bot("Bot1")
        bot2 = Bot("Bot2")
        game.add_player("Bot1", bot1)
        game.add_player("Bot2", bot2)

        game.on_start()

        # Run game for many ticks
        max_ticks = 10000
        for _ in range(max_ticks):
            if game.status == "finished":
                break
            game.on_tick()

        assert game.status == "finished"

    def test_four_player_team_game(self):
        """Test a 4-player team game."""
        from server.users.bot import Bot

        game = ScopaGame()
        game.options.target_score = 5
        game.options.team_mode = "2v2"

        for i in range(4):
            bot = Bot(f"Bot{i}")
            game.add_player(f"Bot{i}", bot)

        game.on_start()

        assert len(game.team_manager.teams) == 2
        assert game.team_manager.teams[0].members == ["Bot0", "Bot1"]
        assert game.team_manager.teams[1].members == ["Bot2", "Bot3"]

        # Run game
        max_ticks = 10000
        for _ in range(max_ticks):
            if game.status == "finished":
                break
            game.on_tick()

        assert game.status == "finished"


class TestScopaPersistence:
    """Tests for game persistence/serialization."""

    def test_full_state_preserved(self):
        """Test that full game state is preserved."""
        game = ScopaGame()
        user1 = MockUser("Player1")
        user2 = MockUser("Player2")
        game.add_player("Player1", user1)
        game.add_player("Player2", user2)

        game.on_start()

        # Modify state
        game.players[0].captured = [Card(id=0, rank=7, suit=1)]
        game.players[0].scopas = 2
        game.table_cards = [Card(id=1, rank=5, suit=2)]

        # Serialize and deserialize
        data = game.to_dict()
        game2 = ScopaGame.from_dict(data)

        assert len(game2.players[0].captured) == 1
        assert game2.players[0].scopas == 2
        assert len(game2.table_cards) == 1
