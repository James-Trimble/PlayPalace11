import json

from server.games.fivecarddraw.game import FiveCardDrawGame, FiveCardDrawOptions
from server.users.test_user import MockUser
from server.users.bot import Bot


def test_draw_game_creation():
    game = FiveCardDrawGame()
    assert game.get_name() == "Five Card Draw"
    assert game.get_type() == "fivecarddraw"
    assert game.get_category() == "category-poker"
    assert game.get_min_players() == 2
    assert game.get_max_players() == 5


def test_draw_options_defaults():
    game = FiveCardDrawGame()
    assert game.options.starting_chips == 20000
    assert game.options.ante == 100


def test_draw_serialization_round_trip():
    game = FiveCardDrawGame()
    user1 = MockUser("Alice")
    user2 = MockUser("Bob")
    game.add_player("Alice", user1)
    game.add_player("Bob", user2)
    game.on_start()
    json_str = game.to_json()
    data = json.loads(json_str)
    assert data["hand_number"] >= 1
    loaded = FiveCardDrawGame.from_json(json_str)
    assert loaded.hand_number == game.hand_number


def test_draw_bot_game_completes():
    options = FiveCardDrawOptions(starting_chips=200, ante=100)
    game = FiveCardDrawGame(options=options)
    for i in range(2):
        bot = Bot(f"Bot{i}")
        game.add_player(f"Bot{i}", bot)
    game.on_start()
    for _ in range(20000):
        if game.status == "finished":
            break
        game.on_tick()
    assert game.status == "finished"
