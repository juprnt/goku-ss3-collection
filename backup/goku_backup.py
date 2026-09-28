#!/usr/bin/env python3
"""Sauvegarde hebdomadaire de la base Goku SS3 (PocketBase sur le Mac mini) vers iCloud Drive.

Lancé chaque jour par launchd (voir install.sh) ; si la dernière sauvegarde a plus de 7 jours :
  1. sauvegarde native PocketBase (zip de pb_data : base SQLite + images du catalogue + photos
     de cartes), téléchargée puis supprimée côté serveur ;
  2. export JSON lisible des tables (collection, photos, cartes masquées, catalogue, jeux, séries),
  dans iCloud Drive/Sauvegardes/Goku SS3/AAAA-MM-JJ/. Les 8 sauvegardes les plus récentes sont gardées.

Identifiants : compte superuser PocketBase dans ~/.config/goku-pb/superuser.json — jamais dans le dépôt.
Python 3 standard uniquement (aucune dépendance ; pb.py est copié à côté par install.sh).
Usage : python3 goku_backup.py [--force]   (--force : sauvegarde même si < 7 jours)
"""

from __future__ import annotations

import datetime as dt
import json
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from pb import PB  # noqa: E402

DEST = Path.home() / "Library/Mobile Documents/com~apple~CloudDocs/Sauvegardes/Goku SS3"
# Données personnelles d'abord ; le catalogue est inclus car il représente beaucoup de travail.
# Les tables Cardmarket ne sont pas exportées en JSON (régénérées chaque nuit) mais sont dans le zip.
TABLES = ["collection_items", "card_photos", "hidden_cards", "cards", "games", "game_sets"]
KEEP = 8
MAX_AGE_DAYS = 7


def log(msg: str):
    print(f"{dt.datetime.now():%Y-%m-%d %H:%M:%S} {msg}", flush=True)


def notify(msg: str):
    """Notification macOS en cas d'échec (sinon personne ne lirait le journal)."""
    subprocess.run(["osascript", "-e", f'display notification "{msg}" with title "Sauvegarde Goku SS3"'],
                   check=False, capture_output=True)


def last_backup_date() -> dt.date | None:
    dates = []
    for d in DEST.glob("20??-??-??") if DEST.exists() else []:
        try:
            dates.append(dt.date.fromisoformat(d.name))
        except ValueError:
            pass
    return max(dates, default=None)


def backup(pb: PB):
    today = dt.date.today().isoformat()
    tmp = DEST / f".{today}.en-cours"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)

    # 1. Sauvegarde native (tout pb_data), téléchargée avec un jeton de fichier temporaire.
    name = f"goku-{dt.datetime.now():%Y%m%d-%H%M%S}.zip"
    pb.request("POST", "/api/backups", {"name": name}, timeout=600)
    token = pb.request("POST", "/api/files/token")["token"]
    url = f"{pb.url}/api/backups/{urllib.parse.quote(name)}?token={token}"
    with urllib.request.urlopen(url, timeout=600) as r, open(tmp / "pocketbase.zip", "wb") as f:
        shutil.copyfileobj(r, f)
    pb.request("DELETE", f"/api/backups/{urllib.parse.quote(name)}")
    size = (tmp / "pocketbase.zip").stat().st_size

    # 2. Export JSON lisible.
    counts = {}
    for table in TABLES:
        rows = pb.list_all(table)
        (tmp / f"{table}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))
        counts[table] = len(rows)

    (tmp / "manifest.json").write_text(json.dumps({
        "date": dt.datetime.now().isoformat(timespec="seconds"), "base": pb.url,
        "lignes": counts, "zip_octets": size,
    }, ensure_ascii=False, indent=1))
    (tmp / "LISEZMOI.txt").write_text(
        "Sauvegarde de la base Goku SS3 (PocketBase du Mac mini, goku_backup.py).\n\n"
        "- pocketbase.zip : sauvegarde complète (base + images du catalogue + photos de cartes).\n"
        "- <table>.json : contenu de chaque table, lisible (une liste d'objets JSON).\n\n"
        "Restauration : interface d'admin http://127.0.0.1:8092/_/ › Settings › Backups ›\n"
        "« Upload backup » avec pocketbase.zip, puis « Restore ». Ou, service arrêté, dézipper\n"
        "pocketbase.zip dans ~/Services/goku/pb_data/ et relancer le service.\n")

    final = DEST / today
    shutil.rmtree(final, ignore_errors=True)
    tmp.rename(final)
    log(f"Sauvegarde OK → {final} : {counts}, zip {size / 1e6:.1f} Mo")

    old = sorted(d for d in DEST.glob("20??-??-??") if d.is_dir())[:-KEEP]
    for d in old:
        shutil.rmtree(d)
        log(f"Ancienne sauvegarde supprimée : {d.name}")


def main():
    force = "--force" in sys.argv
    last = last_backup_date()
    if not force and last and (dt.date.today() - last).days < MAX_AGE_DAYS:
        log(f"Dernière sauvegarde le {last} : rien à faire aujourd'hui.")
        return
    try:
        pb = PB()
        DEST.mkdir(parents=True, exist_ok=True)
        backup(pb)
    except Exception as e:
        log(f"Sauvegarde : échec ({e!r})")
        notify("La sauvegarde hebdomadaire a échoué. Voir le journal.")
        sys.exit(1)


if __name__ == "__main__":
    main()
