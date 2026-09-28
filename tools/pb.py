"""Petit client PocketBase (Python standard, sans dépendance) pour les outils Goku SS3.

Identifiants superuser : ~/.config/goku-pb/superuser.json ({"url", "email", "password"}), droits 600,
jamais dans le dépôt (public). Utilisé par l'import depuis Supabase, la synchro Cardmarket, la veille
Bandai et la sauvegarde.
"""

from __future__ import annotations

import json
import mimetypes
import secrets
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

CONFIG = Path.home() / ".config/goku-pb/superuser.json"


class PBError(RuntimeError):
    pass


class PB:
    def __init__(self, url: str | None = None, token: str | None = None):
        cfg = json.loads(CONFIG.read_text()) if CONFIG.exists() else {}
        self.url = (url or cfg.get("url") or "http://127.0.0.1:8092").rstrip("/")
        self.token = token
        if not self.token:
            self.token = self.request("POST", "/api/collections/_superusers/auth-with-password",
                                      {"identity": cfg["email"], "password": cfg["password"]})["token"]

    def request(self, method: str, path: str, body=None, params: dict | None = None, raw: bytes | None = None,
                content_type: str = "application/json", timeout: int = 120):
        url = self.url + path + (("?" + urllib.parse.urlencode(params)) if params else "")
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        headers = {"Content-Type": content_type}
        if self.token:
            headers["Authorization"] = self.token
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                txt = r.read()
                return json.loads(txt) if txt else None
        except urllib.error.HTTPError as e:
            raise PBError(f"{method} {path} → {e.code} {e.read().decode(errors='replace')[:500]}") from None

    # ---- lecture
    def list_all(self, collection: str, **params) -> list[dict]:
        out, page = [], 1
        while True:
            r = self.request("GET", f"/api/collections/{collection}/records",
                             params={"perPage": 500, "page": page, "skipTotal": 1, **params})
            out += r["items"]
            if len(r["items"]) < 500:
                return out
            page += 1

    # ---- écriture
    def create(self, collection: str, record: dict) -> dict:
        return self.request("POST", f"/api/collections/{collection}/records", record)

    def update(self, collection: str, rid: str, record: dict) -> dict:
        return self.request("PATCH", f"/api/collections/{collection}/records/{rid}", record)

    def delete(self, collection: str, rid: str):
        return self.request("DELETE", f"/api/collections/{collection}/records/{rid}")

    def batch(self, requests: list[dict], size: int = 100):
        """requests : [{"method": "POST"|"PATCH"|"PUT"|"DELETE", "url": "/api/collections/x/records[/id]", "body": {...}}]"""
        for i in range(0, len(requests), size):
            self.request("POST", "/api/batch", {"requests": requests[i:i + size]})

    def upload(self, collection: str, rid: str, field: str, filename: str, content: bytes) -> dict:
        boundary = "----goku" + secrets.token_hex(12)
        ctype = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{field}\"; filename=\"{filename}\"\r\n"
                f"Content-Type: {ctype}\r\n\r\n").encode() + content + f"\r\n--{boundary}--\r\n".encode()
        return self.request("PATCH", f"/api/collections/{collection}/records/{rid}", raw=body,
                            content_type=f"multipart/form-data; boundary={boundary}")

    def file_url(self, collection: str, rid: str, filename: str) -> str:
        return f"{self.url}/api/files/{collection}/{rid}/{urllib.parse.quote(filename)}"

    def download(self, url: str) -> bytes:
        req = urllib.request.Request(url, headers={"Authorization": self.token or ""})
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.read()
