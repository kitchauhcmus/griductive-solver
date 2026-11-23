"""Public card data, in board order. Verdicts and clues live in the puzzle files."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Player:
    name: str
    slug: str
    pos: str
    ovr: int
    club: str
    nation: str
    tier: str
    number: int


MASTER_ROSTER = (
    Player("Alisson", "alisson", "GK", 108, "LIV", "BRA", "TOTY", 1),
    Player("Bellingham", "bellingham", "CAM", 111, "RMA", "ENG", "TOTY", 5),
    Player("Courtois", "courtois", "GK", 109, "RMA", "BEL", "UCL", 1),
    Player("De Bruyne", "de_bruyne", "CM", 112, "MCI", "BEL", "ICON", 17),
    Player("Ederson", "ederson", "GK", 106, "MCI", "BRA", "UCL", 31),
    Player("Foden", "foden", "RW", 108, "MCI", "ENG", "UCL", 47),
    Player("Griezmann", "griezmann", "CAM", 107, "ATM", "FRA", "HERO", 7),
    Player("Haaland", "haaland", "ST", 112, "MCI", "NOR", "TOTY", 9),
    Player("Iniesta", "iniesta", "CM", 113, "BAR", "ESP", "ICON", 8),
    Player("Kane", "kane", "ST", 110, "BAY", "ENG", "CAPTAIN", 9),
    Player("Kroos", "kroos", "CM", 112, "RMA", "GER", "ICON", 8),
    Player("Lewandowski", "lewandowski", "ST", 109, "BAR", "POL", "UCL", 9),
    Player("Mbappe", "mbappe", "ST", 113, "RMA", "FRA", "TOTY", 9),
    Player("Messi", "messi", "RW", 114, "INT", "ARG", "ICON", 10),
    Player("Modric", "modric", "CM", 112, "RMA", "CRO", "ICON", 10),
    Player("Neymar", "neymar", "LW", 111, "SAN", "BRA", "HERO", 10),
    Player("Odegaard", "odegaard", "CAM", 108, "ARS", "NOR", "CAPTAIN", 8),
    Player("Pedri", "pedri", "CM", 107, "BAR", "ESP", "UCL", 8),
    Player("Rodri", "rodri", "CDM", 112, "MCI", "ESP", "TOTY", 16),
    Player("Ronaldo", "ronaldo", "ST", 114, "ALN", "POR", "ICON", 7),
    Player("Saka", "saka", "RW", 108, "ARS", "ENG", "UCL", 7),
    Player("Salah", "salah", "RW", 111, "LIV", "EGY", "CAPTAIN", 11),
    Player("Son", "son", "LW", 109, "TOT", "KOR", "CAPTAIN", 7),
    Player("Van Dijk", "van_dijk", "CB", 111, "LIV", "NED", "TOTY", 4),
    Player("Vinicius", "vinicius", "LW", 112, "RMA", "BRA", "TOTY", 7),
)
BY_SLUG = {player.slug: player for player in MASTER_ROSTER}

SQUADS = {
    3: tuple(BY_SLUG[slug] for slug in (
        "bellingham", "de_bruyne", "haaland", "mbappe", "messi", "modric",
        "ronaldo", "salah", "van_dijk",
    )),
    4: tuple(BY_SLUG[slug] for slug in (
        "bellingham", "courtois", "de_bruyne", "haaland", "iniesta", "kane",
        "kroos", "mbappe", "messi", "modric", "neymar", "rodri", "ronaldo",
        "salah", "van_dijk", "vinicius",
    )),
    5: MASTER_ROSTER,
}
