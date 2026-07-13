import json
from dataclasses import dataclass
from enum import StrEnum

from pfy.app import output


class Color(StrEnum):
    RED = "red"


@dataclass
class Row:
    id: int
    name: str | None = None


def test_jsonable_dataclass_enum_and_nesting():
    assert output.jsonable(Row(1)) == {"id": 1, "name": None}
    assert output.jsonable(Color.RED) == "red"
    assert output.jsonable([Row(1, "y")]) == [{"id": 1, "name": "y"}]


def test_emit_json(capsys):
    output.emit(Row(1, "y"), as_json=True, human=lambda d: None)
    assert json.loads(capsys.readouterr().out) == {"id": 1, "name": "y"}


def test_emit_human_gets_raw_object():
    seen = []
    output.emit(Row(1), as_json=False, human=seen.append)
    assert seen == [Row(1)]


def test_table_is_tab_separated_with_joined_lists(capsys):
    output.table([{"id": "1", "name": "a", "tags": ["x", "y"]}], ["id", "name", "tags"])
    assert capsys.readouterr().out.strip() == "1\ta\tx, y"


def test_emit_rows_json(capsys):
    output.emit_rows([{"id": "1", "name": "a"}], ["id", "name"], as_json=True)
    assert json.loads(capsys.readouterr().out) == [{"id": "1", "name": "a"}]
