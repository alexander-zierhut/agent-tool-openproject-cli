"""Attachments: upload, list, download, delete."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


def test_upload_list_download_delete(op, wp, tmp_path):
    src = tmp_path / "hello.txt"
    content = "hello from the op cli test\n"
    src.write_text(content)

    uploaded = op(
        ["attach", "upload", str(wp["id"]), str(src), "--description", "test file"]
    ).ok().json
    assert uploaded["fileName"] == "hello.txt"
    assert uploaded["fileSize"] == len(content.encode())
    att_id = uploaded["id"]

    listed = op(["attach", "list", str(wp["id"])]).ok().json
    assert any(a["id"] == att_id for a in listed)

    dest = tmp_path / "downloaded.txt"
    # Use the LONG form deliberately: `--output` used to be swallowed by
    # _pop_globals as a format and this test's `-O` alias is exactly why CI never
    # noticed. See tests/test_globals_unit.py.
    op(["attach", "download", str(att_id), "--out", str(dest)]).ok()
    assert dest.read_text() == content

    op(["attach", "delete", str(att_id), "-y"]).ok()
    assert all(a["id"] != att_id for a in op(["attach", "list", str(wp["id"])]).ok().json)
