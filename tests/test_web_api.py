from http.client import HTTPResponse
from io import BytesIO
import json
from types import SimpleNamespace

import pytest

from griductive.roster import MASTER_ROSTER, SQUADS
from griductive.web.game import Match, PUZZLES
from griductive.web.server import Handler


class RequestStream:
    """Exercise BaseHTTPRequestHandler's real HTTP parser without reserving a port."""

    def __init__(self, raw):
        self.input = BytesIO(raw)
        self.output = bytearray()

    def makefile(self, *args):
        return self.input

    def sendall(self, data):
        self.output.extend(data)


def exchange(match, method, path, body=b"", *, session=None):
    session_header = (
        f"X-Griductive-Session: {session}\r\n"
        if session is not None
        else ""
    )

    headers = (
        f"{method} {path} HTTP/1.0\r\n"
        "Host: localhost\r\n"
        "Content-Type: application/json\r\n"
        f"Content-Length: {len(body)}\r\n"
        f"{session_header}\r\n"
    )

    stream = RequestStream(
        headers.encode("ascii") + body
    )

    Handler(
        stream,
        ("127.0.0.1", 12345),
        SimpleNamespace(match=match),
    )

    response = HTTPResponse(
        RequestStream(bytes(stream.output)),
        method=method,
    )
    response.begin()
    return response


@pytest.fixture()
def match(tmp_path):
    return Match(
        PUZZLES / "4x4_easy_training.json",
        portraits=tmp_path,
    )


def api(match, action, **data):
    response = exchange(
        match,
        "POST",
        "/api/" + action,
        json.dumps(data).encode(),
    )

    assert response.status == 200
    return json.loads(response.read())


def test_catalog_and_rosters(match):
    assert (
        len(MASTER_ROSTER)
        == len({player.slug for player in MASTER_ROSTER})
        == 25
    )

    assert [player.name for player in MASTER_ROSTER] == sorted(
        player.name
        for player in MASTER_ROSTER
    )

    assert exchange(match, "GET", "/").status == 200

    catalog = json.loads(
        exchange(match, "GET", "/api/puzzles").read()
    )

    assert len([
        puzzle
        for puzzle in catalog
        if puzzle["diagnostic"]
    ]) == 2

    for puzzle in catalog:
        state = api(
            match,
            "load",
            puzzle=puzzle["id"],
        )["state"]

        n = state["size"]

        assert [card["id"] for card in state["cards"]] == [
            f"{chr(65 + index % n)}{index // n + 1}"
            for index in range(n * n)
        ]

        actual_players = [
            (
                card["name"],
                card["slug"],
                card["profession"],
                card["ovr"],
                card["club"],
                card["nation"],
                card["tier"],
                card["shirt_number"],
            )
            for card in state["cards"]
        ]

        expected_players = [
            (
                player.name,
                player.slug,
                player.pos,
                player.ovr,
                player.club,
                player.nation,
                player.tier,
                player.number,
            )
            for player in SQUADS[n]
        ]

        assert actual_players == expected_players

        assert all(
            card["clue"] is None
            for card in state["cards"]
            if card["status"] == "UNKNOWN"
        )

    assert [player.name for player in SQUADS[3]] == [
        "Bellingham",
        "De Bruyne",
        "Haaland",
        "Mbappe",
        "Messi",
        "Modric",
        "Ronaldo",
        "Salah",
        "Van Dijk",
    ]

    assert [player.name for player in SQUADS[4]] == [
        "Bellingham",
        "Courtois",
        "De Bruyne",
        "Haaland",
        "Iniesta",
        "Kane",
        "Kroos",
        "Mbappe",
        "Messi",
        "Modric",
        "Neymar",
        "Rodri",
        "Ronaldo",
        "Salah",
        "Van Dijk",
        "Vinicius",
    ]

    assert SQUADS[5] == MASTER_ROSTER


def test_manual_and_solver_routes(match):
    hint = api(match, "hint")

    assert (hint["cell"], hint["status"]) == (
        "B1",
        "INNOCENT",
    )

    assert api(
        match,
        "verdict",
        cell="B1",
        status="CRIMINAL",
    )["result"] == "CONTRADICTED"

    assert api(
        match,
        "clue-highlight",
        cell="B1",
    )["clue"] is None

    step = api(match, "step")

    assert step["state"]["trace"][-1]["cell_id"] == "B1"

    assert api(
        match,
        "clue-highlight",
        cell="B1",
    )["clue"]["targets"]

    assert api(match, "solve")["state"]["solved"] == 16
    assert api(match, "uniqueness")["unique"]
    assert api(match, "restart")["state"]["solved"] == 1


def test_untitled_puzzle_has_same_title_in_catalog_and_game(
    tmp_path,
):
    source = PUZZLES / "3x3_binary_chain.json"

    data = json.loads(
        source.read_text(encoding="utf-8")
    )
    del data["title"]

    path = tmp_path / "untitled.json"
    path.write_text(
        json.dumps(data),
        encoding="utf-8",
    )

    match = Match(
        path,
        portraits=tmp_path,
    )

    response = exchange(
        match,
        "GET",
        "/api/puzzles",
    )
    assert response.status == 200

    item = next(
        puzzle
        for puzzle in json.loads(response.read())
        if puzzle["id"] == path.name
    )

    state = api(
        match,
        "load",
        puzzle=path.name,
    )["state"]

    assert (
        item["title"]
        == state["title"]
        == "Untitled Griductive Puzzle"
    )


def test_stale_session_cannot_play_a_move(match):
    state = json.loads(
        exchange(match, "GET", "/api/state").read()
    )

    stale = exchange(
        match,
        "POST",
        "/api/step",
        session="previous-session",
    )
    assert stale.status == 409

    assert json.loads(
        exchange(match, "GET", "/api/state").read()
    ) == state

    accepted = exchange(
        match,
        "POST",
        "/api/step",
        session=state["session"],
    )
    assert accepted.status == 200

    updated = json.loads(accepted.read())["state"]

    assert updated["solved"] == state["solved"] + 1
    assert updated["session"] == state["session"]


@pytest.mark.parametrize(
    ("case", "expected"),
    [
        (
            "3x3_ambiguous_var_check",
            "NOT_PROVABLE",
        ),
        (
            "3x3_inconsistent_scandal",
            "INCONSISTENT",
        ),
    ],
)
def test_diagnostics_preserve_unknown_cards(
    match,
    case,
    expected,
):
    state = api(
        match,
        "load",
        puzzle=f"diagnostics/{case}.json",
    )["state"]

    for action in ("hint", "step", "solve", "verdict"):
        result = api(
            match,
            action,
            cell="C1",
            status="CRIMINAL",
        )

        assert result["result"] == expected
        assert result["state"]["cards"] == state["cards"]
        assert result["state"]["trace"] == []


def test_portrait_priority_content_types_and_removal(match):
    suffixes = [
        ("jPeG", "image/jpeg"),
        ("JpG", "image/jpeg"),
        ("wEBp", "image/webp"),
        ("pNg", "image/png"),
    ]

    for suffix, mime in suffixes:
        path = match.portraits / ("BeLLingHaM." + suffix)
        path.write_bytes(suffix.encode())

        response = exchange(
            match,
            "GET",
            "/assets/players/BELLINGHAM",
        )

        assert (
            response.status,
            response.getheader("Content-Type"),
            response.read(),
        ) == (
            200,
            mime,
            suffix.encode(),
        )

    url = match.snapshot()["cards"][0]["portrait"]
    assert url.startswith("/assets/players/bellingham?")

    for file in match.portraits.iterdir():
        file.unlink()

    assert exchange(match, "GET", url).status == 204
    assert match.snapshot()["cards"][0]["portrait"] is None

    assert exchange(
        match,
        "GET",
        "/assets/players/..%2FREADME",
    ).status == 404