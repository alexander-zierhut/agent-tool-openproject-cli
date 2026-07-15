"""Unit tests for output rendering (json / table / markdown)."""

from __future__ import annotations

import json

from opcli.output import Emitter, OutputFormat, _dotted_get, _md_cell, _md_table, _project

COLS = [("ID", "id"), ("Name", "name")]
ROWS = [{"id": 1, "name": "alpha"}, {"id": 2, "name": "beta"}]


def test_json_emit_list(capsys):
    Emitter(OutputFormat.json).emit(ROWS)
    out = capsys.readouterr().out
    assert json.loads(out) == ROWS


def test_json_emit_dict(capsys):
    Emitter(OutputFormat.json).emit({"a": 1})
    assert json.loads(capsys.readouterr().out) == {"a": 1}


def test_markdown_table(capsys):
    Emitter(OutputFormat.markdown).emit(ROWS, columns=COLS)
    out = capsys.readouterr().out
    assert out.startswith("| ID | Name |")
    assert "| --- | --- |" in out
    assert "| 1 | alpha |" in out


def test_markdown_single_object(capsys):
    Emitter(OutputFormat.markdown).emit({"id": 1, "name": "alpha"})
    out = capsys.readouterr().out
    assert out.startswith("| Field | Value |")
    assert "| id | 1 |" in out


def test_markdown_list_without_columns_is_fenced_json(capsys):
    Emitter(OutputFormat.markdown).emit(ROWS)
    out = capsys.readouterr().out
    assert out.startswith("```json")
    assert '"name": "alpha"' in out


def test_markdown_empty(capsys):
    Emitter(OutputFormat.markdown).emit([], columns=COLS, empty="nothing here")
    assert "_nothing here_" in capsys.readouterr().out


def test_markdown_title(capsys):
    Emitter(OutputFormat.markdown).emit(ROWS, columns=COLS, title="My Table")
    assert "### My Table" in capsys.readouterr().out


def test_md_cell_escapes_pipes_and_newlines():
    assert _md_cell("a|b") == "a\\|b"
    assert _md_cell("line1\nline2") == "line1<br>line2"
    assert _md_cell(None) == ""
    assert _md_cell(True) == "yes"
    assert _md_cell(["x", "y"]) == "x, y"


def test_md_table_shape():
    md = _md_table(["A", "B"], [["1", "2"], ["3", "4"]])
    lines = md.strip().splitlines()
    assert lines[0] == "| A | B |"
    assert lines[1] == "| --- | --- |"
    assert lines[2] == "| 1 | 2 |"


def test_table_renders_header(capsys):
    Emitter(OutputFormat.table, color=False).emit(ROWS, columns=COLS)
    out = capsys.readouterr().out
    assert "ID" in out and "Name" in out and "alpha" in out


def test_table_empty(capsys):
    Emitter(OutputFormat.table, color=False).emit([], columns=COLS, empty="(none)")
    assert "(none)" in capsys.readouterr().out


def test_column_callable_accessor(capsys):
    cols = [("Upper", lambda r: r["name"].upper())]
    Emitter(OutputFormat.markdown).emit(ROWS, columns=cols)
    assert "| ALPHA |" in capsys.readouterr().out


def test_message_suppressed_in_json(capsys):
    Emitter(OutputFormat.json).message("hello")
    assert capsys.readouterr().out == ""


def test_message_shown_in_table(capsys):
    Emitter(OutputFormat.table, color=False).message("hello")
    assert "hello" in capsys.readouterr().out


def test_print_error_json(capsys):
    from opcli.errors import NotFoundError
    from opcli.output import print_error

    print_error(NotFoundError("missing thing"), OutputFormat.json)
    err = capsys.readouterr().err
    assert json.loads(err)["error"] == "missing thing"


# ---- --fields selection ----
def test_dotted_get():
    row = {"id": 1, "assignee": {"name": "Jane", "id": 5}}
    assert _dotted_get(row, "id") == 1
    assert _dotted_get(row, "assignee.name") == "Jane"
    assert _dotted_get(row, "assignee.missing") is None
    assert _dotted_get(row, "nope.deep") is None


def test_project_list():
    data = [{"id": 1, "name": "a", "extra": 9}, {"id": 2, "name": "b", "extra": 8}]
    assert _project(data, ["id", "name"]) == [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}]


def test_project_dict_with_dotted():
    data = {"id": 1, "assignee": {"name": "Jane"}}
    assert _project(data, ["id", "assignee.name"]) == {"id": 1, "assignee.name": "Jane"}


def test_emitter_fields_json(capsys):
    Emitter(OutputFormat.json, fields=["id", "name"]).emit(
        [{"id": 1, "name": "a", "x": 1}], columns=COLS
    )
    assert json.loads(capsys.readouterr().out) == [{"id": 1, "name": "a"}]


def test_emitter_fields_markdown_overrides_columns(capsys):
    Emitter(OutputFormat.markdown, fields=["name"]).emit(ROWS, columns=COLS)
    out = capsys.readouterr().out
    assert out.startswith("| name |")
    assert "| alpha |" in out


def test_emitter_fields_strip_and_empty():
    e = Emitter(OutputFormat.json, fields=[" id ", "", "name"])
    assert e.fields == ["id", "name"]


# ---- csv ----
def test_csv_output(capsys):
    Emitter(OutputFormat.csv).emit(ROWS, columns=COLS)
    lines = capsys.readouterr().out.strip().splitlines()
    assert lines[0] == "ID,Name"
    assert lines[1] == "1,alpha"
    assert lines[2] == "2,beta"


def test_csv_without_columns_uses_keys(capsys):
    Emitter(OutputFormat.csv).emit([{"a": 1, "b": 2}, {"a": 3, "b": 4}])
    lines = capsys.readouterr().out.strip().splitlines()
    assert lines[0] == "a,b"
    assert lines[1] == "1,2"


def test_csv_cell():
    from opcli.output import _csv_cell

    assert _csv_cell(None) == ""
    assert _csv_cell(True) == "true"
    assert _csv_cell(False) == "false"
    assert _csv_cell({"a": 1}) == '{"a": 1}'
    assert _csv_cell(3) == "3"


def test_coerce_csv():
    assert OutputFormat.coerce("csv") == OutputFormat.csv


# ---- stream (NDJSON) ----
def test_stream_json(capsys):
    n = Emitter(OutputFormat.json).stream_json([{"id": 1}, {"id": 2}])
    lines = capsys.readouterr().out.strip().splitlines()
    assert n == 2
    assert json.loads(lines[0]) == {"id": 1}
    assert json.loads(lines[1]) == {"id": 2}


def test_stream_json_honours_fields(capsys):
    Emitter(OutputFormat.json, fields=["id"]).stream_json([{"id": 1, "x": 9}])
    assert json.loads(capsys.readouterr().out.strip()) == {"id": 1}
