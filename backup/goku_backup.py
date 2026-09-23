#!/usr/bin/env python3
"""Maintien en éveil + sauvegarde hebdomadaire du projet Supabase de Goku SS3.

Lancé chaque jour par launchd sur le Mac mini (voir install.sh) :
  1. une petite requête à Supabase, pour que le projet gratuit ne soit jamais mis en pause
     (il l'est après ~7 jours sans activité) ;
  2. si la dernière sauvegarde a plus de 7 jours : export JSON des tables + téléchargement
     des photos de cartes, dans iCloud Drive/Sauvegardes/Goku SS3/AAAA-MM-JJ/.
     Les 8 sauvegardes les plus récentes sont conservées.

Clé : clé secrète Supabase (Project Settings › API Keys › « secret », ou l'ancienne
« service_role »), dans ~/.config/goku-backup/secret — jamais dans le dépôt (public).
Elle contourne RLS : c'est nécessaire pour lire les données et photos de tous les comptes.

Python 3 standard uniquement (aucune dépendance).
Usage : python3 goku_backup.py [--force]   (--force : sauvegarde même si < 7 jours)
"""

from __future__ import annotations

import datetime as dt
import json
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

SUPABASE_URL = "https://vtdohksscretlbvhsgfo.supabase.co"
KEY_FILE = Path.home() / ".config/goku-backup/secret"
DEST = Path.home() / "Library/Mobile Documents/com~apple~CloudDocs/Sauvegardes/Goku SS3"
PHOTO_BUCKET = "card-photos"
# Données personnelles d'abord ; le catalogue est inclus car il représente beaucoup de travail.
# Les tables Cardmarket ne sont pas sauvegardées : elles se régénèrent chaque nuit.
TABLES = ["collection_items", "card_photos", "hidden_cards", "cards", "games", "game_sets"]
KEEP = 8
MAX_AGE_DAYS = 7


def log(msg: str):
    print(f"{dt.datetime.now():%Y-%m-%d %H:%M:%S} {msg}", flush=True)


def notify(msg: str):
    """Notification macOS en cas d'échec (sinon personne ne lirait le journal)."""
    subprocess.run(["osascript", "-e", f'display notification "{msg}" with title "Sauvegarde Goku SS3"'],
                   check=False, capture_output=True)


def headers(key: str) -> dict:
    h = {"apikey": key}
    if key.startswith("eyJ"):  # ancienne clé service_role (JWT) : l'en-tête Authorization est requis
        h["Authorization"] = f"Bearer {key}"
    return h


def get(key: str, path: str, params: dict | None = None) -> bytes:
    url = f"{SUPABASE_URL}{path}" + (f"?{urllib.parse.urlencode(params)}" if params else "")
    req = urllib.request.Request(url, headers=headers(key))
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def export_table(key: str, table: str) -> list:
    rows, page = [], 1000
    while True:
        batch = json.loads(get(key, f"/rest/v1/{table}", {"select": "*", "limit": page, "offset": len(rows)}))
        rows += batch
        if len(batch) < page:
            return rows


def last_backup_date() -> dt.date | None:
    dates = []
    for d in DEST.glob("20??-??-??") if DEST.exists() else []:
        try:
            dates.append(dt.date.fromisoformat(d.name))
        except ValueError:
            pass
    return max(dates, default=None)


def backup(key: str):
    today = dt.date.today().isoformat()
    tmp = DEST / f".{today}.en-cours"
    shutil.rmtree(tmp, ignore_errors=True)
    (tmp / "photos").mkdir(parents=True)

    counts = {}
    for table in TABLES:
        rows = export_table(key, table)
        (tmp / f"{table}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))
        counts[table] = len(rows)
        if table == "card_photos":
            photo_rows = rows

    photos_ok, photos_missing = 0, []
    for p in photo_rows:
        path = p["storage_path"]
        try:
            data = get(key, f"/storage/v1/object/{PHOTO_BUCKET}/" + urllib.parse.quote(path))
        except urllib.error.HTTPError as e:
            photos_missing.append(f"{path} ({e.code})")
            continue
        target = tmp / "photos" / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        photos_ok += 1

    (tmp / "manifest.json").write_text(json.dumps({
        "date": dt.datetime.now().isoformat(timespec="seconds"), "supabase": SUPABASE_URL,
        "lignes": counts, "photos": photos_ok, "photos_manquantes": photos_missing,
    }, ensure_ascii=False, indent=1))
    (tmp / "LISEZMOI.txt").write_text(
        "Sauvegarde du projet Supabase de Goku SS3 (goku_backup.py).\n\n"
        "- <table>.json : contenu complet de chaque table (une liste d'objets JSON).\n"
        "- photos/ : fichiers du bucket Storage « card-photos », au même chemin que\n"
        "  card_photos.storage_path.\n\n"
        "Restauration : réinsérer les JSON dans les tables (dans l'ordre games, game_sets, cards,\n"
        "collection_items, card_photos, hidden_cards) puis re-téléverser photos/ dans le bucket\n"
        "card-photos avec les mêmes chemins. Les identifiants (id, user_id) sont conservés : le\n"
        "compte utilisateur doit exister avec le même id dans Supabase Auth.\n")

    final = DEST / today
    shutil.rmtree(final, ignore_errors=True)
    tmp.rename(final)
    log(f"Sauvegarde OK → {final} : {counts}, {photos_ok} photo(s)"
        + (f", {len(photos_missing)} introuvable(s)" if photos_missing else ""))

    old = sorted(d for d in DEST.glob("20??-??-??") if d.is_dir())[:-KEEP]
    for d in old:
        shutil.rmtree(d)
        log(f"Ancienne sauvegarde supprimée : {d.name}")


def main():
    force = "--force" in sys.argv
    if not KEY_FILE.exists() or not KEY_FILE.read_text().strip():
        log(f"Clé absente : {KEY_FILE}")
        notify("Clé Supabase absente, rien n'a été fait.")
        sys.exit(1)
    key = KEY_FILE.read_text().strip()

    try:
        get(key, "/rest/v1/games", {"select": "slug", "limit": 1})
        log("Maintien en éveil : Supabase répond.")
    except Exception as e:
        log(f"Maintien en éveil : échec ({e}). Le projet est peut-être en pause.")
        notify("Supabase ne répond pas (projet en pause ?). Voir le journal.")
        sys.exit(1)

    last = last_backup_date()
    if not force and last and (dt.date.today() - last).days < MAX_AGE_DAYS:
        log(f"Dernière sauvegarde le {last} : rien à faire aujourd'hui.")
        return
    try:
        DEST.mkdir(parents=True, exist_ok=True)
        backup(key)
    except Exception as e:
        log(f"Sauvegarde : échec ({e!r})")
        notify("La sauvegarde hebdomadaire a échoué. Voir le journal.")
        sys.exit(1)


if __name__ == "__main__":
    main()
