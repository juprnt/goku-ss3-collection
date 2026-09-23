"""Serveur IA local pour Goku SS3 Collection.

Tourne sur le Mac mini, à côté d'Ollama. L'app (web ou Android) l'appelle avec le
jeton Supabase de l'utilisateur connecté ; le serveur lit Supabase *avec ce jeton*,
donc les policies RLS s'appliquent exactement comme dans l'app.

Endpoints :
  GET  /health    — état d'Ollama et du modèle
  POST /identify  — photo d'une carte -> infos lues + cartes du catalogue candidates
  POST /identify/base64 — idem, photo en base64 dans un JSON (app Android)
  POST /search    — question en langage naturel -> filtres + résultats
"""

import base64
import difflib
import hashlib
import io
import json
import os
import re
import time
import unicodedata
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from PIL import Image, ImageOps
from pydantic import BaseModel

load_dotenv(Path(__file__).parent / ".env")

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3.6:35b-mlx")
SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]

GAMES = {
    "carddass": "Carddass (Bandai, cartes rétro DB/DBZ/GT, années 90)",
    "dbh": "Dragon Ball Heroes (cartes arcade)",
    "dbscg-masters": "Dragon Ball Super Card Game — Masters (numéros type BT3-083, SD5-02, P-045)",
    "dbscg-fusion": "Dragon Ball Super Card Game — Fusion World (numéros type FB01-001, FS03-05)",
}
CONDITIONS = ["Mint", "Near Mint", "Excellent", "Good", "Played", "Poor", "Gradée"]
MAX_IMAGE_SIDE = 1280
USER_CACHE_TTL = 300
CATALOGUE_CACHE_TTL = 600

app = FastAPI(title="Goku SS3 — serveur IA", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
    # Chrome (Private Network Access) : autorise un site public à appeler l'adresse Tailscale privée.
    allow_private_network=True,
)

http = httpx.AsyncClient(timeout=httpx.Timeout(300, connect=10))


# ---------------------------------------------------------------- Auth / Supabase

_user_cache: dict[str, tuple[float, dict]] = {}


async def current_user(authorization: str = Header(default="")) -> dict:
    """Valide le jeton Supabase auprès de Supabase Auth (résultat mis en cache 5 min)."""
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(401, "Jeton Supabase manquant (en-tête Authorization: Bearer ...)")
    key = hashlib.sha256(token.encode()).hexdigest()
    cached = _user_cache.get(key)
    if cached and cached[0] > time.time():
        return cached[1]
    try:
        r = await http.get(
            f"{SUPABASE_URL}/auth/v1/user",
            headers={"apikey": SUPABASE_ANON_KEY, "Authorization": f"Bearer {token}"},
        )
    except httpx.HTTPError as e:
        raise HTTPException(503, f"Supabase injoignable : {e}")
    if r.status_code != 200:
        raise HTTPException(401, "Jeton Supabase invalide ou expiré")
    user = {**r.json(), "_token": token}
    _user_cache[key] = (time.time() + USER_CACHE_TTL, user)
    return user


async def sb_select(token: str, table: str, params: dict) -> list[dict]:
    r = await http.get(
        f"{SUPABASE_URL}/rest/v1/{table}",
        params=params,
        headers={"apikey": SUPABASE_ANON_KEY, "Authorization": f"Bearer {token}"},
    )
    if r.status_code != 200:
        raise HTTPException(502, f"Erreur Supabase ({table}) : {r.text[:300]}")
    return r.json()


_catalogue_cache: tuple[float, list[dict]] = (0.0, [])


async def load_catalogue(token: str) -> list[dict]:
    """Catalogue confirmé, partagé entre utilisateurs -> un seul cache global."""
    global _catalogue_cache
    if _catalogue_cache[0] > time.time():
        return _catalogue_cache[1]
    cards = await sb_select(token, "cards", {"select": "*", "review_status": "eq.confirmed"})
    _catalogue_cache = (time.time() + CATALOGUE_CACHE_TTL, cards)
    return cards


async def load_collection(token: str) -> list[dict]:
    return await sb_select(token, "collection_items", {"select": "*,cards(*)"})


# ---------------------------------------------------------------- Ollama

# Les modèles servis via MLX ne gèrent pas la sortie structurée ("format") d'Ollama :
# on bascule alors sur un schéma décrit dans le prompt + extraction du JSON de la réponse.
_structured_output = True


def extract_json(content: str) -> dict:
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.S)
    start, end = content.find("{"), content.rfind("}")
    if start == -1 or end == -1:
        raise HTTPException(502, f"Réponse Ollama non JSON : {content[:300]}")
    try:
        return json.loads(content[start:end + 1])
    except json.JSONDecodeError:
        raise HTTPException(502, f"Réponse Ollama non JSON : {content[:300]}")


async def ollama_json(system: str, user: str, schema: dict, images: list[str] | None = None) -> dict:
    """Appel à Ollama avec sortie JSON conforme à `schema`."""
    global _structured_output
    msg = {"role": "user", "content": user}
    if images:
        msg["images"] = images
    payload = {
        "model": OLLAMA_MODEL,
        "stream": False,
        "think": False,
        "keep_alive": "30m",
        "options": {"temperature": 0},
    }
    for _ in range(2):
        if _structured_output:
            payload |= {"messages": [{"role": "system", "content": system}, msg], "format": schema}
        else:
            payload.pop("format", None)
            prompt_system = (f"{system}\n\nRéponds UNIQUEMENT par un objet JSON valide, sans texte autour, "
                             f"conforme à ce schéma JSON :\n{json.dumps(schema, ensure_ascii=False)}")
            payload["messages"] = [{"role": "system", "content": prompt_system}, msg]
        try:
            r = await http.post(f"{OLLAMA_URL}/api/chat", json=payload)
        except httpx.HTTPError as e:
            raise HTTPException(503, f"Ollama injoignable : {e}")
        if r.status_code != 200 and _structured_output and "structured output" in r.text:
            _structured_output = False
            continue
        if r.status_code != 200:
            raise HTTPException(502, f"Erreur Ollama : {r.text[:300]}")
        data = extract_json(r.json()["message"]["content"])
        return {k: data.get(k) for k in schema["properties"]}
    raise HTTPException(502, "Ollama : sortie structurée indisponible")


def prepare_image(raw: bytes) -> str:
    """Redresse (EXIF), réduit et ré-encode en JPEG base64 pour accélérer le modèle."""
    try:
        img = Image.open(io.BytesIO(raw))
        img = ImageOps.exif_transpose(img).convert("RGB")
    except Exception:
        raise HTTPException(400, "Image illisible")
    img.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=88)
    return base64.b64encode(buf.getvalue()).decode()


# ---------------------------------------------------------------- Helpers

def norm(s: str | None) -> str:
    """Minuscules, sans accents ni ponctuation : 'BT3-083 ' -> 'bt3083'."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", s.lower())


def similarity(a: str | None, b: str | None) -> float:
    a, b = norm(a), norm(b)
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def owned_index(collection: list[dict]) -> dict[str, dict]:
    idx: dict[str, dict] = {}
    for item in collection:
        cid = item.get("card_id")
        if not cid:
            continue
        entry = idx.setdefault(cid, {"owned_qty": 0, "wishlist": False, "item_ids": []})
        entry["item_ids"].append(item["id"])
        if item.get("status") == "owned":
            entry["owned_qty"] += item.get("quantity") or 1
        elif item.get("status") == "wishlist":
            entry["wishlist"] = True
    return idx


# ---------------------------------------------------------------- Routes

@app.get("/health")
async def health():
    try:
        r = await http.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        models = [m["name"] for m in r.json().get("models", [])]
    except httpx.HTTPError as e:
        return {"ok": False, "ollama": f"injoignable : {e}"}
    return {"ok": OLLAMA_MODEL in models, "model": OLLAMA_MODEL, "models": models}


@app.get("/")
async def test_page():
    return FileResponse(Path(__file__).parent / "static" / "test.html")


IDENTIFY_SCHEMA = {
    "type": "object",
    "properties": {
        "is_card": {"type": "boolean"},
        "game": {"type": "string", "enum": [*GAMES, "unknown"]},
        "card_number": {"type": ["string", "null"]},
        "set_code": {"type": ["string", "null"]},
        "card_name": {"type": ["string", "null"]},
        "rarity": {"type": ["string", "null"]},
        "language": {"type": ["string", "null"]},
        "is_goku_ss3": {"type": "boolean"},
        "visible_text": {"type": "string"},
        "confidence": {"type": "number"},
    },
    "required": ["is_card", "game", "card_number", "set_code", "card_name", "rarity",
                 "language", "is_goku_ss3", "visible_text", "confidence"],
}

IDENTIFY_SYSTEM = f"""Tu es un expert des cartes à collectionner Dragon Ball.
On te montre la photo d'une carte (souvent Son Goku Super Saiyan 3). Lis-la attentivement
et renvoie uniquement ce que tu vois réellement, sans inventer.

Jeux possibles :
{chr(10).join(f"- {k} : {v}" for k, v in GAMES.items())}

- card_number : le numéro imprimé tel quel (ex. "BT3-083", "FB05-012", "P-045", "123").
- set_code : le code d'extension s'il est lisible séparément (ex. "BT3", "FB05").
- card_name : le nom imprimé de la carte.
- rarity : la rareté si imprimée (C, UC, R, SR, SPR, SCR, L...).
- language : langue du texte de la carte (fr, en, ja...).
- visible_text : les principaux textes lisibles, en une ligne.
- confidence : ta confiance globale entre 0 et 1.
Si une information n'est pas lisible, mets null."""


def score_card(card: dict, ex: dict) -> float:
    score = 0.0
    num = norm(ex.get("card_number"))
    card_num = norm(card.get("card_number"))
    card_full = norm((card.get("set_code") or "") + (card.get("card_number") or ""))
    if num and card_num:
        if num in (card_num, card_full):
            score += 60
        elif len(card_num) >= 3 and num.endswith(card_num):
            score += 30
    if ex.get("set_code") and norm(ex["set_code"]) == norm(card.get("set_code")):
        score += 15
    if ex.get("game") and ex["game"] == card.get("game_slug"):
        score += 10
    score += 20 * similarity(ex.get("card_name"), card.get("card_name"))
    if ex.get("rarity") and norm(ex["rarity"]) == norm(card.get("rarity")):
        score += 5
    return round(score, 1)


@app.post("/identify")
async def identify(photo: UploadFile = File(...), user: dict = Depends(current_user)):
    return await identify_image(await photo.read(), user)


class IdentifyBase64Request(BaseModel):
    photo_base64: str


@app.post("/identify/base64")
async def identify_base64(req: IdentifyBase64Request, user: dict = Depends(current_user)):
    """Variante JSON pour l'app Android (le client HTTP natif n'envoie pas de multipart)."""
    try:
        raw = base64.b64decode(req.photo_base64.split(",")[-1])
    except ValueError:
        raise HTTPException(400, "Image base64 invalide")
    return await identify_image(raw, user)


async def identify_image(raw: bytes, user: dict) -> dict:
    image_b64 = prepare_image(raw)
    t0 = time.time()
    extracted = await ollama_json(IDENTIFY_SYSTEM, "Identifie cette carte.", IDENTIFY_SCHEMA, [image_b64])
    llm_seconds = round(time.time() - t0, 1)

    token = user["_token"]
    catalogue = await load_catalogue(token)
    owned = owned_index(await load_collection(token))

    scored = sorted(((score_card(c, extracted), c) for c in catalogue), key=lambda t: -t[0])
    candidates = [
        {"score": s, "card": c, **owned.get(c["id"], {"owned_qty": 0, "wishlist": False, "item_ids": []})}
        for s, c in scored[:5] if s >= 20
    ]
    # Correspondance "sûre" : numéro reconnu et nette avance sur le 2e.
    best = None
    if candidates and candidates[0]["score"] >= 60:
        second = candidates[1]["score"] if len(candidates) > 1 else 0
        if candidates[0]["score"] - second >= 15:
            best = candidates[0]["card"]["id"]

    return {"extracted": extracted, "candidates": candidates, "best_match_id": best, "llm_seconds": llm_seconds}


class SearchRequest(BaseModel):
    query: str


SEARCH_SCHEMA = {
    "type": "object",
    "properties": {
        "scope": {"type": "string", "enum": ["collection", "wishlist", "catalogue", "missing"]},
        "games": {"type": "array", "items": {"type": "string", "enum": list(GAMES)}},
        "text": {"type": ["string", "null"]},
        "conditions": {"type": "array", "items": {"type": "string", "enum": CONDITIONS}},
        "graded": {"type": ["boolean", "null"]},
        "min_value": {"type": ["number", "null"]},
        "max_value": {"type": ["number", "null"]},
        "sort": {"type": "string", "enum": ["default", "value_desc", "value_asc", "recent", "name"]},
        "limit": {"type": ["integer", "null"]},
    },
    "required": ["scope", "games", "text", "conditions", "graded", "min_value", "max_value", "sort", "limit"],
}

SEARCH_SYSTEM = f"""Tu traduis une question d'un collectionneur de cartes Dragon Ball (Goku SS3)
en filtres JSON. Ne réponds que par les filtres.

- scope : "collection" (cartes possédées, par défaut), "wishlist", "catalogue" (toutes les
  cartes connues), "missing" (cartes du catalogue que l'utilisateur ne possède pas).
- games : liste de jeux parmi {json.dumps(GAMES, ensure_ascii=False)} ; vide = tous.
- text : mots-clés à chercher dans le nom, le numéro, l'extension ou les notes (null si aucun).
  N'y mets pas "Goku" ni "SS3" : toutes les cartes le sont.
- conditions : états parmi {CONDITIONS} ; vide = tous. "mauvais état" = Played, Poor.
- graded : true pour cartes gradées (PSA, BGS...), false pour non gradées, null sinon.
- min_value / max_value : bornes de valeur estimée en euros.
- sort : "value_desc" pour "les plus chères", "recent" pour "dernières ajoutées", etc.
- limit : nombre de résultats demandé ("mes 5 plus chères" -> 5), sinon null."""


def item_value(item: dict) -> float:
    return float(item.get("estimated_value") or 0)


def item_text(item: dict) -> str:
    c = item.get("cards") or item
    return " ".join(str(x) for x in [
        c.get("card_name"), c.get("card_number"), c.get("set_code"), c.get("set_name"),
        c.get("rarity"), item.get("custom_name"), item.get("notes"),
    ] if x)


def clean_filters(f: dict) -> dict:
    """Ramène la réponse du modèle dans les valeurs autorisées (utile sans sortie structurée)."""
    def number(v):
        return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None

    props = SEARCH_SCHEMA["properties"]
    return {
        "scope": f.get("scope") if f.get("scope") in props["scope"]["enum"] else "collection",
        "games": [g for g in (f.get("games") or []) if g in GAMES],
        "text": f.get("text") if isinstance(f.get("text"), str) and f["text"].strip() else None,
        "conditions": [c for c in (f.get("conditions") or []) if c in CONDITIONS],
        "graded": f.get("graded") if isinstance(f.get("graded"), bool) else None,
        "min_value": number(f.get("min_value")),
        "max_value": number(f.get("max_value")),
        "sort": f.get("sort") if f.get("sort") in props["sort"]["enum"] else "default",
        "limit": int(f["limit"]) if number(f.get("limit")) and f["limit"] > 0 else None,
    }


@app.post("/search")
async def search(req: SearchRequest, user: dict = Depends(current_user)):
    if not req.query.strip():
        raise HTTPException(400, "Question vide")
    f = clean_filters(await ollama_json(SEARCH_SYSTEM, req.query.strip(), SEARCH_SCHEMA))

    token = user["_token"]
    scope = f["scope"]
    if scope in ("catalogue", "missing"):
        items = await load_catalogue(token)
        if scope == "missing":
            owned = owned_index(await load_collection(token))
            items = [c for c in items if owned.get(c["id"], {}).get("owned_qty", 0) == 0]
        game_of = lambda it: it.get("game_slug")
    else:
        status = "owned" if scope == "collection" else "wishlist"
        items = [i for i in await load_collection(token) if i.get("status") == status]
        game_of = lambda it: (it.get("cards") or {}).get("game_slug")

    if f["games"]:
        items = [i for i in items if game_of(i) in f["games"]]
    if f["text"]:
        words = [norm(w) for w in f["text"].split() if norm(w)]
        items = [i for i in items if all(w in norm(item_text(i)) for w in words)]
    if scope in ("collection", "wishlist"):
        if f["conditions"]:
            items = [i for i in items if i.get("condition") in f["conditions"]]
        if f["graded"] is not None:
            items = [i for i in items if bool(i.get("grading_company")) == f["graded"]]
        if f["min_value"] is not None:
            items = [i for i in items if item_value(i) >= f["min_value"]]
        if f["max_value"] is not None:
            items = [i for i in items if item_value(i) <= f["max_value"]]
        if f["sort"] == "value_desc":
            items.sort(key=item_value, reverse=True)
        elif f["sort"] == "value_asc":
            items.sort(key=item_value)
        elif f["sort"] == "recent":
            items.sort(key=lambda i: i.get("created_at") or "", reverse=True)
    if f["sort"] == "name":
        items.sort(key=lambda i: norm((i.get("cards") or i).get("card_name") or i.get("custom_name")))

    limit = min(f["limit"] or 100, 100)
    return {"filters": f, "count": len(items), "results": items[:limit]}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8787")))
