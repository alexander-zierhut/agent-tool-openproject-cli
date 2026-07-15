"""Shared helpers for the pure-unit tests (no network).

``FakeClient`` mimics the small surface of :class:`opcli.client.Client` used by
the filter/search/serialize code, so we can unit-test that logic deterministically.
"""

from __future__ import annotations

from typing import Any


class FakeClient:
    def __init__(self, collections: dict | None = None, docs: dict | None = None, me_user: dict | None = None):
        self.collections = collections or {}
        self.docs = docs or {}
        self._me = me_user or {
            "id": 1,
            "login": "me",
            "name": "Me",
            "_links": {"self": {"href": "/api/v3/users/1"}},
        }
        self.calls: list[tuple] = []

    def get(self, path: str, params: dict | None = None) -> dict:
        self.calls.append(("GET", path, params))
        if path in self.docs:
            return self.docs[path]
        last = path.rstrip("/").split("/")[-1]
        val: Any = int(last) if last.isdigit() else last
        return {
            "id": val,
            "identifier": last,
            "name": last,
            "_links": {"self": {"href": "/api/v3/" + path}},
        }

    def collect(self, path: str, params: dict | None = None, page_size: int = 100, limit: int | None = None) -> list:
        self.calls.append(("COLLECT", path, params))
        return self.collections.get(path, [])

    def post(self, path: str, json: Any = None, params: dict | None = None) -> dict:
        self.calls.append(("POST", path, json))
        return self.docs.get(path, {})

    def me(self) -> dict:
        return self._me


def link(href, title=None):
    d = {"href": href}
    if title is not None:
        d["title"] = title
    return d


SAMPLE_WP = {
    "id": 42,
    "subject": "Fix bug",
    "lockVersion": 3,
    "description": {"format": "markdown", "raw": "the description", "html": "<p>the description</p>"},
    "startDate": "2026-07-01",
    "dueDate": "2026-07-10",
    "estimatedTime": "PT3H",
    "spentTime": "PT1H",
    "percentageDone": 25,
    "createdAt": "2026-07-01T00:00:00Z",
    "updatedAt": "2026-07-02T00:00:00Z",
    "customField1": "INV-1",
    "_links": {
        "type": link("/api/v3/types/1", "Task"),
        "status": link("/api/v3/statuses/7", "In progress"),
        "priority": link("/api/v3/priorities/8", "Normal"),
        "project": link("/api/v3/projects/1", "Demo project"),
        "assignee": link("/api/v3/users/4", "Admin User"),
        "responsible": link("/api/v3/users/5", "Jane Doe"),
        "author": link("/api/v3/users/4", "Admin User"),
        "parent": link("/api/v3/work_packages/40", "Parent WP"),
        "customField2": link("/api/v3/custom_options/3", "High"),
        "customFields": link("/api/v3/custom_fields"),  # the admin collection link — must be ignored
    },
}

SAMPLE_PROJECT = {
    "id": 1,
    "name": "Demo project",
    "identifier": "demo-project",
    "active": True,
    "public": True,
    "description": {"format": "markdown", "raw": "about", "html": "<p>about</p>"},
    "createdAt": "2026-01-01T00:00:00Z",
    "updatedAt": "2026-02-01T00:00:00Z",
    "customField1": "ACME",
    "_links": {"parent": link("/api/v3/projects/9", "Portfolio"), "status": link("/api/v3/project_statuses/on_track", "On track")},
}

SAMPLE_TIME_ENTRY = {
    "id": 88,
    "hours": "PT2H30M",
    "spentOn": "2026-07-05",
    "comment": {"format": "plain", "raw": "worked", "html": "worked"},
    "createdAt": "2026-07-05T00:00:00Z",
    "updatedAt": "2026-07-05T00:00:00Z",
    "_links": {
        "user": link("/api/v3/users/4", "Admin User"),
        "workPackage": link("/api/v3/work_packages/42", "Fix bug"),
        "project": link("/api/v3/projects/1", "Demo project"),
        "activity": link("/api/v3/time_entries/activities/3", "Development"),
    },
}

SAMPLE_COMMENT = {
    "id": 100,
    "_type": "Activity::Comment",
    "comment": {"format": "markdown", "raw": "looks good", "html": "<p>looks good</p>"},
    "version": 5,
    "createdAt": "2026-07-05T10:00:00Z",
    "updatedAt": "2026-07-05T10:00:00Z",
    "_links": {"user": link("/api/v3/users/4"), "workPackage": link("/api/v3/work_packages/42")},
}

SAMPLE_NOTIFICATION = {
    "id": 7,
    "subject": "You were mentioned",
    "reason": "mentioned",
    "readIAN": False,
    "createdAt": "2026-07-05T10:00:00Z",
    "updatedAt": "2026-07-05T10:00:00Z",
    "_links": {
        "resource": link("/api/v3/work_packages/42", "Fix bug"),
        "project": link("/api/v3/projects/1", "Demo project"),
        "actor": link("/api/v3/users/5", "Jane Doe"),
    },
}

SAMPLE_ATTACHMENT = {
    "id": 12,
    "fileName": "report.pdf",
    "fileSize": 2048,
    "description": {"format": "plain", "raw": "the report", "html": "the report"},
    "contentType": "application/pdf",
    "createdAt": "2026-07-05T10:00:00Z",
    "_links": {"author": link("/api/v3/users/4", "Admin User"), "downloadLocation": link("/api/v3/attachments/12/content")},
}
