"""Unit tests for the HAL serializers (no network)."""

from __future__ import annotations

from opcli import serialize
from support import (
    SAMPLE_ATTACHMENT,
    SAMPLE_COMMENT,
    SAMPLE_NOTIFICATION,
    SAMPLE_PROJECT,
    SAMPLE_TIME_ENTRY,
    SAMPLE_WP,
)


def test_work_package_core_fields():
    wp = serialize.work_package(SAMPLE_WP)
    assert wp["id"] == 42
    assert wp["subject"] == "Fix bug"
    assert wp["type"] == "Task"
    assert wp["status"] == "In progress"
    assert wp["priority"] == "Normal"
    assert wp["lockVersion"] == 3
    assert wp["percentageDone"] == 25
    assert wp["estimatedTime"] == "PT3H"


def test_work_package_links_resolved():
    wp = serialize.work_package(SAMPLE_WP)
    assert wp["project"] == {"id": 1, "name": "Demo project", "href": "/api/v3/projects/1"}
    assert wp["assignee"]["id"] == 4 and wp["assignee"]["name"] == "Admin User"
    assert wp["responsible"]["id"] == 5
    assert wp["parent"]["id"] == 40


def test_work_package_description_and_custom_fields():
    wp = serialize.work_package(SAMPLE_WP)
    assert wp["description"] == "the description"
    cf = wp["customFields"]
    assert cf["customField1"] == "INV-1"
    assert cf["customField2"] == "High"  # link title
    assert "customFields" not in cf  # the admin collection link must be ignored


def test_work_package_without_description():
    wp = serialize.work_package(SAMPLE_WP, include_description=False)
    assert "description" not in wp


def test_project_serializer():
    p = serialize.project(SAMPLE_PROJECT)
    assert p["id"] == 1
    assert p["identifier"] == "demo-project"
    assert p["active"] is True
    assert p["description"] == "about"
    assert p["parent"]["id"] == 9
    assert p["customFields"]["customField1"] == "ACME"


def test_time_entry_serializer():
    t = serialize.time_entry(SAMPLE_TIME_ENTRY)
    assert t["id"] == 88
    assert t["hours"] == "PT2H30M"
    assert t["hoursDecimal"] == 2.5
    assert serialize.time_entry({"hours": "P1D"})["hoursDecimal"] == 24.0  # 24h/day (calendar)
    assert serialize.time_entry({})["hoursDecimal"] is None
    assert t["activity"] == "Development"
    assert t["workPackage"]["id"] == 42
    assert t["project"]["id"] == 1
    assert t["comment"] == "worked"


def test_comment_serializer():
    c = serialize.comment(SAMPLE_COMMENT)
    assert c["id"] == 100
    assert c["comment"] == "looks good"
    assert c["_type"] == "Activity::Comment"
    assert c["workPackage"]["id"] == 42


def test_notification_serializer():
    n = serialize.notification(SAMPLE_NOTIFICATION)
    assert n["id"] == 7
    assert n["reason"] == "mentioned"
    assert n["readIAN"] is False
    assert n["resource"]["id"] == 42
    assert n["actor"]["id"] == 5


def test_attachment_serializer():
    a = serialize.attachment(SAMPLE_ATTACHMENT)
    assert a["id"] == 12
    assert a["fileName"] == "report.pdf"
    assert a["fileSize"] == 2048
    assert a["contentType"] == "application/pdf"
    assert a["downloadLocation"] == "/api/v3/attachments/12/content"


def test_user_serializer():
    u = serialize.user({"id": 4, "login": "admin", "name": "Admin", "email": "a@b.c", "admin": True, "status": "active"})
    assert u["login"] == "admin" and u["admin"] is True


def test_principal_serializer():
    p = serialize.principal({"id": 5, "name": "Jane", "login": "jane", "_type": "User"})
    assert p["type"] == "User" and p["id"] == 5


def test_membership_serializer():
    doc = {
        "id": 3,
        "_links": {
            "principal": {"href": "/api/v3/users/5", "title": "Jane"},
            "project": {"href": "/api/v3/projects/1", "title": "Demo"},
            "roles": [{"href": "/api/v3/roles/4", "title": "Member"}, {"href": "/api/v3/roles/5", "title": "Reader"}],
        },
    }
    m = serialize.membership(doc)
    assert m["principal"]["id"] == 5
    assert m["roles"] == ["Member", "Reader"]


def test_custom_field_schema_list_type():
    spec = {
        "name": "Severity",
        "type": "CustomOption",
        "required": False,
        "writable": True,
        "_links": {"allowedValues": [{"href": "/api/v3/custom_options/1", "title": "Low"}]},
    }
    out = serialize.custom_field_schema("customField2", spec)
    assert out["key"] == "customField2"
    assert out["type"] == "CustomOption"
    assert out["allowedValues"][0]["name"] == "Low"


def test_file_link_serializer():
    doc = {
        "id": 9,
        "originData": {"id": "123", "name": "Contract.pdf", "mimeType": "application/pdf"},
        "_links": {"storage": {"href": "/api/v3/storages/1", "title": "Nextcloud"}, "status": {"title": "view_allowed"}},
    }
    fl = serialize.file_link(doc)
    assert fl["originName"] == "Contract.pdf"
    assert fl["originId"] == "123"
    assert fl["storage"] == "Nextcloud"
