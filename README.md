# PlayPalace V11

PlayPalace is an accessible online gaming platform. This repository contains both the server (v11, modern) and client (ported from v10).

## Quick Start

You need Python 3.11 or later. We use [uv](https://docs.astral.sh/uv/) for dependency management on the server.

### Running the Server

```bash
cd server
uv sync
uv run python main.py
```

The server starts on port 8000 by default. You can specify a different port as the first argument.

### Running the Client

```bash
cd client
python client.py
```

The client requires wxPython and a few other dependencies from v10. It connects to localhost:8000 by default.

## Project Structure

The server and client are separate codebases with different philosophies.

### Server

The server is a complete rewrite for v11. It uses modern Python practices: dataclasses for all state, Mashumaro for serialization, websockets for networking, and Mozilla Fluent for localization.

We hold the view that game simulations should be entirely state-based. If a game can't be saved and loaded without custom save/load code, something has gone wrong. This is why everything is a dataclass, and why games never touch the network directly.

Key directories:
- `server/core/` - Server infrastructure, websocket handling, tick scheduler
- `server/games/` - Game implementations (Pig, Scopa, Threes, Light Turret, etc.)
- `server/game_utils/` - Shared utilities for games (cards, dice, teams, turn order)
- `server/auth/` - Authentication and session management
- `server/persistence/` - SQLite database for users and tables
- `server/messages/` - Localization system
- `server/plans/` - Design documents explaining architectural decisions

### Client

The client is ported from v10. It works, but it carries some technical debt from the older codebase. You may encounter rough edges.

The client is built with wxPython and designed for accessibility. It communicates with the server over websockets using JSON packets.

## Running Tests

The server has comprehensive tests. We run them frequently during development.

```bash
cd server
uv run pytest
```

For verbose output:

```bash
uv run pytest -v
```

The test suite includes unit tests, integration tests, and "play tests" that run complete games with bots. Play tests save and reload game state periodically to verify persistence works correctly.

See also: CLI tool.

## Available Games

- **Pig** - A push-your-luck dice game
- **Threes** - Another push-your-luck game, with a little more complexity
- **Scopa** - A complex game about collecting cards
- **Light Turret** - A dice game from the RB Play Center
- **Chaos Bear** - Another RB Play Center game about getting away from a bear
- **Mile by Mile** - A racing card game
- **Farkle** - A dice game somewhat reminiscent of Yahtzee

## CLI Tool

The server also includes a CLI for simulating games without running the full server. This is useful for testing and for AI agents. It does not supercede play tests, but works alongside them, and allows you to very quickly test specific scenarios.

```bash
cd server

# List available games
uv run python -m server.cli list-games

# Simulate a game with bots
uv run python -m server.cli simulate pig --bots 2

# Simulate with specific bot names
uv run python -m server.cli simulate lightturret --bots Alice,Bob,Charlie

# Output as JSON
uv run python -m server.cli simulate pig --bots 3 --json

# Test serialization (save/restore each tick)
uv run python -m server.cli simulate threes --bots 2 --test-serialization
```

## Architecture Notes

A few things worth understanding about how the server works:

**Tick-based simulation.** The server runs a tick every 50 milliseconds. Games don't use coroutines or async/await internally. All game logic is synchronous and state-based. This makes testing straightforward and persistence trivial.

**User abstraction.** Games never send network packets directly. They receive objects implementing the `User` interface and call methods like `speak()` and `show_menu()`. The actual user might be a real network client, a test mock, or a bot. Games don't need to know or care.

**Actions, not events.** There's a layer between "event received from network" and "action executed in game". Bots call actions directly on tick. Human players trigger actions through network events. The game logic is the same either way.

**Imperative state changes.** We recommend changing game state imperatively, not declaratively. Actions should directly end turns and send messages, not return results describing what should happen.

For more details, see the design documents in `server/plans/`.

## Known Issues

The client is a port from v10 and may have compatibility issues with some v11 features. If something doesn't work as expected, the server is likely fine and the client needs adjustment.

## Development

The server uses uv for dependency management. To add a dependency:

```bash
cd server
uv add <package>
```

For development dependencies:

```bash
uv add --dev <package>
```

When writing new games, look at existing implementations in `server/games/` for patterns. Pig is a good simple example. Scopa demonstrates card games with team support.
