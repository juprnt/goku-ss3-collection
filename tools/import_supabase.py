#!/usr/bin/env python3
"""Copie complète Supabase → PocketBase (Mac mini) pour Goku SS3. Relançable sans risque (upsert).

- Tables : games, game_sets, cards, collection_items, card_photos, hidden_cards, prix Cardmarket
  (vue card_market_info → collection card_market_info, historique des prix).
- Les identifiants (UUID) et dates de création sont conservés.
- Images du catalogue hébergées sur Supabase Storage → champ fichier `cards.image`.
- Photos personnelles (bucket privé card-photos) → `card_photos.photo`.
- Tous les fichiers Storage sont aussi archivés dans ~/Services/goku/supabase-archive/.
- Compte : même id et e-mail ; `--password-hash-file` reprend le hash bcrypt de Supabase (même mot de passe).

Clés : clé secrète Supabase dans ~/.config/goku-backup/secret, superuser PocketBase dans
~/.config/goku-pb/superuser.json.

Usage : python3 tools/import_supabase.py [--password-hash-file FICHIER]
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import secrets
import sqlite3
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pb import PB  # noqa: E402

SB_URL = "https://vtdohksscretlbvhsgfo.supabase.co"
SB_KEY = (Path.home() / ".config/goku-backup/secret").read_text().strip()
DATA_DB = Path.home() / "Services/goku/pb_data/data.db"
ARCHIVE = Path.home() / "Services/goku/supabase-archive"


def sb(path: str, params: dict | None = None, method: str = "GET", body=None) -> bytes:
    url = SB_URL + path + ("?" + urllib.parse.urlencode(params) if params else "")
    h = {"apikey": SB_KEY, "User-Agent": "goku-ss3-import", "Content-Type": "application/json"}
    if SB_KEY.startswith("eyJ"):
        h["Authorization"] = f"Bearer {SB_KEY}"
    req = urllib.request.Request(url, headers=h, method=method, data=json.dumps(body).encode() if body is not None else None)
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def table(name: str) -> list[dict]:
    rows = []
    while True:
        batch = json.loads(sb(f"/rest/v1/{name}", {"select": "*", "limit": 1000, "offset": len(rows)}))
        rows += batch
        if len(batch) < 1000:
            return rows


def pb_time(ts: str | None) -> str | None:
    """'2026-09-23T15:48:49.967462+00:00' → '2026-09-23 15:48:49.967Z' (format PocketBase)."""
    if not ts:
        return None
    d = dt.datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(dt.timezone.utc)
    return d.strftime("%Y-%m-%d %H:%M:%S.") + f"{d.microsecond // 1000:03d}Z"


def clean(row: dict, drop=("created_at", "updated_at", "hidden_at")) -> dict:
    return {k: v for k, v in row.items() if v is not None and k not in drop}


def upsert(pb: PB, coll: str, records: list[dict]):
    pb.batch([{"method": "PUT", "url": f"/api/collections/{coll}/records", "body": r} for r in records])
    print(f"  {coll} : {len(records)}")


def archive_storage():
    def walk(bucket, prefix=""):
        for o in json.loads(sb(f"/storage/v1/object/list/{bucket}", method="POST",
                               body={"prefix": prefix, "limit": 1000, "offset": 0})):
            path = (prefix + "/" if prefix else "") + o["name"]
            if o.get("id") is None:          # dossier
                yield from walk(bucket, path)
            else:
                yield path
    n = 0
    for b in json.loads(sb("/storage/v1/bucket")):
        for path in walk(b["name"]):
            target = ARCHIVE / b["name"] / path
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(sb(f"/storage/v1/object/{b['name']}/" + urllib.parse.quote(path)))
            n += 1
    print(f"  fichiers Storage archivés : {n} → {ARCHIVE}")


def main():
    hash_file = sys.argv[sys.argv.index("--password-hash-file") + 1] if "--password-hash-file" in sys.argv else None
    pb = PB()
    print("Archive des fichiers Supabase…")
    archive_storage()

    print("Compte…")
    users = json.loads(sb("/auth/v1/admin/users"))["users"]
    for u in users:
        rec = {"id": u["id"], "email": u["email"], "emailVisibility": True, "verified": True}
        try:
            pb.request("GET", f"/api/collections/users/records/{u['id']}")
        except Exception:
            tmp = secrets.token_urlsafe(24)
            pb.create("users", {**rec, "password": tmp, "passwordConfirm": tmp})
    print(f"  users : {len(users)}")

    print("Tables…")
    games = table("games")
    upsert(pb, "games", [{**clean(g), "id": g["slug"]} for g in games])
    upsert(pb, "game_sets", [clean(s) for s in table("game_sets")])

    cards = table("cards")
    upsert(pb, "cards", [clean(c) for c in cards])
    items = table("collection_items")
    upsert(pb, "collection_items", [clean(i) for i in items])
    hidden = table("hidden_cards")
    hid = lambda h: hashlib.sha1((h["user_id"] + h["card_id"]).encode()).hexdigest()[:30]
    upsert(pb, "hidden_cards", [{"id": hid(h), "user_id": h["user_id"], "card_id": h["card_id"]} for h in hidden])
    photos = table("card_photos")
    upsert(pb, "card_photos", [{k: v for k, v in clean(p).items() if k != "storage_path"} for p in photos])

    market = table("card_market_info")
    upsert(pb, "card_market_info", [{"id": m["card_id"], "card_id": m["card_id"],
                                     "info": {k: v for k, v in m.items() if k != "card_id"}} for m in market])
    hist = table("cardmarket_price_history")
    upsert(pb, "cardmarket_price_history", [{"id": f"{h['id_product']}-{h['price_date']}", "id_product": h["id_product"],
                                             "price_date": h["price_date"],
                                             "prices": {k: v for k, v in h.items() if k not in ("id_product", "price_date")}}
                                            for h in hist])

    print("Images du catalogue…")
    moved = 0
    existing = {c["id"]: c for c in pb.list_all("cards", fields="id,image")}
    for c in cards:
        url = c.get("official_image_url") or ""
        if "supabase.co/storage" not in url:
            continue
        if not existing.get(c["id"], {}).get("image"):
            name = url.rsplit("/", 1)[-1].split("?")[0]
            pb.upload("cards", c["id"], "image", name, urllib.request.urlopen(url, timeout=120).read())
        pb.update("cards", c["id"], {"official_image_url": ""})
        moved += 1
    print(f"  images déplacées : {moved}")

    print("Photos personnelles…")
    for p in photos:
        content = sb("/storage/v1/object/card-photos/" + urllib.parse.quote(p["storage_path"]))
        pb.upload("card_photos", p["id"], "photo", p["storage_path"].rsplit("/", 1)[-1], content)
    print(f"  photos : {len(photos)}")

    print("Dates de création et mot de passe…")
    con = sqlite3.connect(DATA_DB, timeout=30)
    for coll, rows in (("cards", cards), ("collection_items", items), ("card_photos", photos)):
        for r in rows:
            con.execute(f"UPDATE {coll} SET created_at = ?, updated_at = ? WHERE id = ?",
                        (pb_time(r.get("created_at")), pb_time(r.get("updated_at") or r.get("created_at")), r["id"]))
    for h in hidden:
        con.execute("UPDATE hidden_cards SET hidden_at = ? WHERE id = ?", (pb_time(h.get("hidden_at")), hid(h)))
    for u in users:
        con.execute("UPDATE users SET created = ? WHERE id = ?", (pb_time(u.get("created_at")), u["id"]))
    if hash_file:
        pw_hash = Path(hash_file).read_text().strip()
        if not pw_hash.startswith("$2"):
            raise SystemExit("Le fichier ne contient pas un hash bcrypt.")
        con.execute("UPDATE users SET password = ?, tokenKey = ? WHERE id = ?",
                    (pw_hash, secrets.token_urlsafe(40), users[0]["id"]))
        print("  mot de passe Supabase repris")
    con.commit()
    con.close()

    print("Vérification…")
    for coll, n in (("games", len(games)), ("cards", len(cards)), ("collection_items", len(items)),
                    ("hidden_cards", len(hidden)), ("card_market_info", len(market))):
        got = len(pb.list_all(coll, fields="id"))
        print(f"  {coll} : {got}/{n} {'OK' if got == n else 'ÉCART'}")


if __name__ == "__main__":
    main()
