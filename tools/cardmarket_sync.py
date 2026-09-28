#!/usr/bin/env python3
"""Synchro quotidienne des prix Cardmarket → PocketBase (Mac mini). Remplace `private.sync_cardmarket(13)` de Supabase.

Source : fichiers officiels et publics de Cardmarket (jeu n°13 = Dragon Ball Super, Masters et Fusion World) :
- catalogue produits : products_singles_13.json
- guide des prix     : price_guide_13.json (régénéré par Cardmarket vers 02h50, heure de Paris)

Le catalogue complet (~13 000 produits) et les derniers prix restent dans une base SQLite locale
(~/Services/goku/cardmarket.db) ; seules les données utiles à l'app vont dans PocketBase :
- `card_market_info` : une ligne par carte confirmée (champ JSON `info`, même contenu que l'ancienne vue) ;
- `cardmarket_price_history` : un point par jour pour les produits liés à une carte ;
- `cardmarket_sync_log` : journal de chaque exécution.

Lancé chaque jour à 05:15 par launchd (backend/com.goku.cardmarket.plist). À la main :
  python3 ~/Services/goku/tools/cardmarket_sync.py
"""

from __future__ import annotations

import datetime as dt
import json
import re
import sqlite3
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pb import PB  # noqa: E402

GAME = 13
PRODUCTS = f"https://downloads.s3.cardmarket.com/productCatalog/productList/products_singles_{GAME}.json"
PRICES = f"https://downloads.s3.cardmarket.com/productCatalog/priceGuide/price_guide_{GAME}.json"
LOCAL_DB = Path.home() / "Services/goku/cardmarket.db"
PRICE_KEYS = ("avg", "low", "trend", "avg1", "avg7", "avg30",
              "avg-foil", "low-foil", "trend-foil", "avg1-foil", "avg7-foil", "avg30-foil")
# Ordre de préférence du prix affiché (premier non nul) et libellé correspondant.
BASIS = (("trend", "tendance"), ("trend_foil", "tendance foil"), ("avg30", "moyenne 30 j"),
         ("avg30_foil", "moyenne 30 j foil"), ("low", "à partir de"), ("low_foil", "à partir de (foil)"))


def log(msg: str):
    print(f"{dt.datetime.now():%Y-%m-%d %H:%M:%S} {msg}", flush=True)


def fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "goku-ss3-cardmarket-sync"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read())


def local_db() -> sqlite3.Connection:
    con = sqlite3.connect(LOCAL_DB)
    con.executescript("""
      create table if not exists products (id_product integer primary key, name text, id_category integer,
        category_name text, id_expansion integer, id_metacard integer, date_added text,
        first_seen_at text default (datetime('now')), updated_at text);
      create table if not exists prices (id_product integer primary key, price_date text, data text);
    """)
    return con


def market_info(card: dict, product: tuple | None, price: dict | None, price_date: str | None) -> dict:
    p = price or {}
    row = {
        "cardmarket_id": card.get("cardmarket_id") or None,
        "cardmarket_match": card.get("cardmarket_match") or None,
        "cardmarket_name": product[0] if product else None,
        "price_date": price_date if price else None,
        "trend": p.get("trend"), "avg30": p.get("avg30"), "low": p.get("low"),
        "trend_foil": p.get("trend-foil"), "avg30_foil": p.get("avg30-foil"), "low_foil": p.get("low-foil"),
    }
    row["price_eur"], row["price_basis"] = next(((row[k], label) for k, label in BASIS if row[k]), (None, None))
    src = card.get("source_url") or ""
    if src.lower().startswith("https://www.cardmarket.com/"):
        row["cardmarket_url"] = src
    elif row["cardmarket_id"]:
        name = row["cardmarket_name"] or ""
        m = re.search(r"\(([A-Z0-9]+-[0-9]+)\)", name)
        row["cardmarket_url"] = ("https://www.cardmarket.com/fr/DragonBallSuper/Products/Search?searchString="
                                 + urllib.parse.quote_plus(m.group(1) if m else name))
    else:
        row["cardmarket_url"] = None
    return row


def main():
    pb = PB()
    try:
        con = local_db()
        started = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        # 1. Catalogue produits
        products = fetch_json(PRODUCTS)["products"]
        before = con.total_changes
        con.executemany("""
          insert into products (id_product, name, id_category, category_name, id_expansion, id_metacard, date_added, updated_at)
          values (?, ?, ?, ?, ?, ?, ?, datetime('now'))
          on conflict (id_product) do update set name = excluded.name, id_category = excluded.id_category,
            category_name = excluded.category_name, id_expansion = excluded.id_expansion,
            id_metacard = excluded.id_metacard, date_added = excluded.date_added, updated_at = datetime('now')
          where (name, id_expansion, id_metacard) is not (excluded.name, excluded.id_expansion, excluded.id_metacard)
        """, [(e["idProduct"], e.get("name"), e.get("idCategory"), e.get("categoryName"), e.get("idExpansion"),
               e.get("idMetacard"), e.get("dateAdded")) for e in products])
        n_prod = con.total_changes - before
        n_new = con.execute("select count(*) from products where first_seen_at >= ?", (started,)).fetchone()[0]

        # 2. Guide des prix (date du guide, à l'heure de Paris)
        guide = fetch_json(PRICES)
        # « 2026-09-27T02:44:58+0200 » (le Python 3.9 de macOS ne lit pas ce décalage avec fromisoformat)
        created = dt.datetime.strptime(re.sub(r"Z$", "+0000", guide["createdAt"]).replace("+00:00", "+0000"),
                                       "%Y-%m-%dT%H:%M:%S%z")
        price_date = created.astimezone(ZoneInfo("Europe/Paris")).date().isoformat()
        con.executemany("insert or replace into prices (id_product, price_date, data) values (?, ?, ?)",
                        [(e["idProduct"], price_date, json.dumps({k: e.get(k) for k in PRICE_KEYS}))
                         for e in guide["priceGuides"]])
        con.commit()
        n_price = len(guide["priceGuides"])

        # 3. Infos affichées dans l'app + historique des produits liés
        cards = pb.list_all("cards", fields="id,cardmarket_id,cardmarket_match,source_url,review_status")
        names = dict(con.execute("select id_product, name from products").fetchall())
        prices = {pid: json.loads(d) for pid, d in con.execute("select id_product, data from prices")}
        confirmed = [c for c in cards if c.get("review_status") == "confirmed"]
        infos = []
        for c in confirmed:
            pid = c.get("cardmarket_id") or None
            infos.append({"id": c["id"], "card_id": c["id"],
                          "info": market_info(c, (names[pid],) if pid in names else None, prices.get(pid), price_date)})
        pb.batch([{"method": "PUT", "url": "/api/collections/card_market_info/records", "body": r} for r in infos])
        keep = {c["id"] for c in confirmed}
        stale = [r["id"] for r in pb.list_all("card_market_info", fields="id") if r["id"] not in keep]
        pb.batch([{"method": "DELETE", "url": f"/api/collections/card_market_info/records/{i}"} for i in stale])

        linked = sorted({c["cardmarket_id"] for c in cards if c.get("cardmarket_id") and c["cardmarket_id"] in prices})
        hist = [{"id": f"{pid}-{price_date}", "id_product": pid, "price_date": price_date,
                 "prices": {k.replace("-", "_"): prices[pid].get(k)
                            for k in ("avg", "low", "trend", "avg30", "avg-foil", "low-foil", "trend-foil", "avg30-foil")}}
                for pid in linked]
        pb.batch([{"method": "PUT", "url": "/api/collections/cardmarket_price_history/records", "body": h} for h in hist])

        summary = {"id_game": GAME, "products_upserted": n_prod, "prices_upserted": n_price, "history_rows": len(hist),
                   "new_products": n_new, "price_date": price_date, "cards": len(infos)}
        pb.create("cardmarket_sync_log", {"ok": True, "info": summary})
        log(f"Synchro Cardmarket OK : {summary}")
    except Exception as e:
        log(f"Échec de la synchro Cardmarket : {e!r}")
        try:
            pb.create("cardmarket_sync_log", {"ok": False, "info": {"id_game": GAME, "error": str(e)[:1000]}})
        finally:
            sys.exit(1)


if __name__ == "__main__":
    main()
