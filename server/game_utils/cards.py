"""
Reusable card and deck utilities for card games.

Provides Card, Deck, and DeckFactory classes that can be used by any card game.
"""

from dataclasses import dataclass, field
import random

from mashumaro.mixins.json import DataClassJSONMixin

from ..messages.localization import Localization


@dataclass
class Card(DataClassJSONMixin):
    """A playing card."""

    id: int  # Unique identifier
    rank: int  # Card rank (1-13 for standard, 1-10 for Italian)
    suit: int  # Suit number (1=diamonds, 2=clubs, 3=hearts, 4=spades)

    def __hash__(self) -> int:
        return self.id

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Card):
            return False
        return self.id == other.id


@dataclass
class Deck(DataClassJSONMixin):
    """A deck of cards with draw/shuffle operations."""

    cards: list[Card] = field(default_factory=list)

    def shuffle(self) -> None:
        """Shuffle the deck in place."""
        random.shuffle(self.cards)

    def draw(self, count: int = 1) -> list[Card]:
        """Draw cards from the top of the deck."""
        drawn = self.cards[:count]
        self.cards = self.cards[count:]
        return drawn

    def draw_one(self) -> Card | None:
        """Draw a single card from the top of the deck."""
        if self.cards:
            return self.cards.pop(0)
        return None

    def add(self, cards: list[Card]) -> None:
        """Add cards to the bottom of the deck."""
        self.cards.extend(cards)

    def add_top(self, cards: list[Card]) -> None:
        """Add cards to the top of the deck."""
        self.cards = cards + self.cards

    def size(self) -> int:
        """Return the number of cards in the deck."""
        return len(self.cards)

    def is_empty(self) -> bool:
        """Check if the deck is empty."""
        return len(self.cards) == 0

    def clear(self) -> list[Card]:
        """Remove and return all cards from the deck."""
        cards = self.cards
        self.cards = []
        return cards


class DeckFactory:
    """Factory for creating common deck types."""

    @staticmethod
    def italian_deck(num_decks: int = 1) -> tuple[Deck, dict[int, Card]]:
        """
        Create Italian 40-card deck (4 suits x 10 ranks).

        Args:
            num_decks: Number of decks to combine.

        Returns:
            Tuple of (shuffled deck, card lookup dict mapping id -> Card)
        """
        cards = []
        card_lookup: dict[int, Card] = {}
        card_id = 0
        for _ in range(num_decks):
            for suit in range(1, 5):  # 1=diamonds, 2=clubs, 3=hearts, 4=spades
                for rank in range(1, 11):  # 1-10
                    card = Card(id=card_id, rank=rank, suit=suit)
                    cards.append(card)
                    card_lookup[card_id] = card
                    card_id += 1
        deck = Deck(cards=cards)
        deck.shuffle()
        return deck, card_lookup

    @staticmethod
    def standard_deck(num_decks: int = 1) -> tuple[Deck, dict[int, Card]]:
        """
        Create standard 52-card deck (4 suits x 13 ranks).

        Args:
            num_decks: Number of decks to combine.

        Returns:
            Tuple of (shuffled deck, card lookup dict mapping id -> Card)
        """
        cards = []
        card_lookup: dict[int, Card] = {}
        card_id = 0
        for _ in range(num_decks):
            for suit in range(1, 5):  # 1=diamonds, 2=clubs, 3=hearts, 4=spades
                for rank in range(1, 14):  # 1-13 (Ace through King)
                    card = Card(id=card_id, rank=rank, suit=suit)
                    cards.append(card)
                    card_lookup[card_id] = card
                    card_id += 1
        deck = Deck(cards=cards)
        deck.shuffle()
        return deck, card_lookup


# Suit localization keys
SUIT_KEYS = {
    1: "suit-diamonds",
    2: "suit-clubs",
    3: "suit-hearts",
    4: "suit-spades",
}

# Rank localization keys (1-13)
RANK_KEYS = {
    1: "rank-ace",
    2: "rank-two",
    3: "rank-three",
    4: "rank-four",
    5: "rank-five",
    6: "rank-six",
    7: "rank-seven",
    8: "rank-eight",
    9: "rank-nine",
    10: "rank-ten",
    11: "rank-jack",
    12: "rank-queen",
    13: "rank-king",
}


def card_name(card: Card, locale: str = "en", italian: bool = True) -> str:
    """
    Get localized card name (e.g., 'Seven of Diamonds').

    Args:
        card: The card to name.
        locale: Locale for localization.
        italian: If True, use Italian deck ranks (1-10). Otherwise standard (1-13).

    Returns:
        Localized card name string.
    """
    rank_key = RANK_KEYS.get(card.rank)
    suit_key = SUIT_KEYS.get(card.suit)

    rank_name = Localization.get(locale, rank_key) if rank_key else str(card.rank)
    suit_name = Localization.get(locale, suit_key) if suit_key else str(card.suit)

    return Localization.get(locale, "card-name", rank=rank_name, suit=suit_name)


def card_name_short(card: Card) -> str:
    """
    Get short card name (e.g., '7D' for Seven of Diamonds).

    Args:
        card: The card to name.

    Returns:
        Short card name string.
    """
    suit_chars = {1: "D", 2: "C", 3: "H", 4: "S"}
    rank_chars = {1: "A", 11: "J", 12: "Q", 13: "K"}
    rank_str = rank_chars.get(card.rank, str(card.rank))
    suit_str = suit_chars.get(card.suit, "?")
    return f"{rank_str}{suit_str}"


def read_cards(cards: list[Card], locale: str = "en", italian: bool = True) -> str:
    """
    Format a list of cards for speech output.

    Args:
        cards: List of cards to read.
        locale: Locale for localization.
        italian: If True, use Italian deck ranks (1-10).

    Returns:
        Formatted string with card names joined by 'and'.
    """
    if not cards:
        return Localization.get(locale, "no-cards")
    names = [card_name(c, locale, italian) for c in cards]
    return Localization.format_list_and(locale, names)


def sort_cards(cards: list[Card], by_suit: bool = True) -> list[Card]:
    """
    Sort cards by suit then rank, or by rank then suit.

    Args:
        cards: List of cards to sort.
        by_suit: If True, sort by suit first. Otherwise by rank first.

    Returns:
        New sorted list of cards.
    """
    if by_suit:
        return sorted(cards, key=lambda c: (c.suit, c.rank))
    else:
        return sorted(cards, key=lambda c: (c.rank, c.suit))
