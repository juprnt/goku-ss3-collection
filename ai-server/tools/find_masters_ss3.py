"""Prépare la revue visuelle des cartes Son Goku de Masters (base officielle Bandai).

Contrairement à Fusion World, la plupart des cartes Masters ont la forme dans leur nom
(« SS3 Son Goku, … ») : la veille quotidienne (watch_bandai.py) les trouve seule. Ce script sert aux
autres : cartes dont le nom ne dit pas SS3 alors que l'illustration le montre (ex. BT12-031
« Son Goku, Heavy Hitter »), faces éveillées des Leaders, variantes officielles (_PR, _SPR…).

1. Recherche « Goku » sur dbs-cardgame.com/us-en (≈ 940 cartes et variantes).
2. Écarte les noms qui nomment déjà la forme (SS3 → déjà couverts ; SS, SSB, SS4, UI, Great Ape… → pas SS3).
3. Télécharge les illustrations restantes (recto et verso des Leaders) et en fait des planches
   numérotées à passer en revue à l'œil (le modèle de vision local confond SS1 et SS3).

Usage (depuis ai-server/) :
  UV_PROJECT_ENVIRONMENT=~/.local/share/goku-ai-server/venv uv run python tools/find_masters_ss3.py <dossier>
→ <dossier>/all.json (toutes les cartes Goku avec série, rareté, date), review.json, sheet_XX.jpg
Revue du 26/09/2026 : 614 illustrations, 7 cartes SS3 trouvées (voir DOCUMENTATION.md).
"""

import asyncio
import json
import re
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
import find_fw_ss3 as fw  # noqa: E402  (planches)

SEARCH = "https://www.dbs-cardgame.com/us-en/cardlist/index.php?search=true"
IMG = "https://www.dbs-cardgame.com/images/cardlist/cardimg/"
OTHER_FORM = re.compile(r"\b(SS|SS2|SS4|SSB|SSG|SSGSS|Super Saiyan( God| Blue| 2| 4)?|Ultra Instinct|UI|"
                        r"Great Ape|Oozaru|Kid|Childhood|Mastered)\b")
SS3 = re.compile(r"SS3|Super Saiyan 3|SSJ3")
clean = lambda html: re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def parse(page: str) -> list[dict]:
    out = []
    for li in re.findall(r'<li>\s*(<dl class="cardListCol.*?)</li>', page, flags=re.S):
        field = lambda pat: re.search(pat, li, flags=re.S)
        names = [clean(n) for n in re.findall(r'class="cardName"[^>]*>(.*?)</dd>', li, flags=re.S)]
        chars = [clean(c) for c in re.findall(r'characterCol">\s*<dt>Character</dt>\s*<dd>(.*?)</dd>', li, flags=re.S)]
        goku = (any("Goku" in n and not re.search(r"Goku Black|Jr\.|Gokua", n) for n in names)
                or any("Son Goku" in c and "Jr." not in c for c in chars))
        if not goku:
            continue
        s, r, d = (field(r'seriesCol">\s*<dt>Series</dt>\s*<dd>(.*?)</dd>'), field(r'rarityCol">\s*<dt>Rarity</dt>\s*<dd>(.*?)</dd>'),
                   field(r'availableDateCol">\s*<dt>[^<]*</dt>\s*<dd>(.*?)</dd>'))
        ss3 = any(SS3.search(n) for n in names)
        out.append({"no": clean(field(r'class="cardNumber"[^>]*>(.*?)</dt>').group(1)), "names": names, "chars": chars,
                    "imgs": re.findall(r'cardimg/([^"]+\.png)', li), "ss3_name": ss3,
                    "other_form": (not ss3) and all(OTHER_FORM.search(n) for n in names),
                    "series": clean(s.group(1)) if s else "", "rarity": clean(r.group(1)) if r else "",
                    "date": clean(d.group(1)) if d else ""})
    return out


async def main(out_dir: str):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(timeout=120, headers={"User-Agent": "Mozilla/5.0 goku-ss3-collection"}) as http:
        page = (await http.post(SEARCH, data={"free": "", "card": "Goku", "category_exp": "", "character": "",
                                              "btn_search": "search"})).text
        cards = parse(page)
        (out / "all.json").write_text(json.dumps(cards, ensure_ascii=False, indent=1))
        todo = [(c, i, img) for c in cards if not c["ss3_name"] and not c["other_form"] for i, img in enumerate(c["imgs"])]
        sem = asyncio.Semaphore(3)

        async def dl(img):
            if (out / img).exists():
                return
            async with sem:
                r = await fw.get(http, IMG + img)
                if r.status_code == 200:
                    (out / img).write_bytes(r.content)

        await asyncio.gather(*(dl(img) for _, _, img in todo))
    review = [{"img": img, "no": c["no"], "name": c["names"][min(i, len(c["names"]) - 1)]}
              for c, i, img in todo if (out / img).exists()]
    (out / "review.json").write_text(json.dumps(review, ensure_ascii=False, indent=1))
    fw.contact_sheets(out, review)
    print(f"{len(cards)} cartes Goku, {len(review)} illustrations à revoir → {out}/sheet_*.jpg")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "masters_goku"))
