/// <reference path="../pb_data/types.d.ts" />
// Schéma Goku SS3 Collection sur PocketBase (remplace Supabase, 27/09/2026).
// - Les identifiants Supabase (UUID) sont conservés : le champ `id` accepte 1 à 36 caractères [a-z0-9-].
//   Pour les jeux, l'id est le slug (« dbscg-masters »…).
// - Les dates « métier » (sortie, acquisition) sont en texte AAAA-MM-JJ, comme avant côté app.
// - Catalogue partagé : lecture et modification pour tout compte connecté (comme les règles RLS Supabase).
//   Données personnelles (collection, photos, cartes masquées) : uniquement les siennes.
// - Prix Cardmarket : une ligne par carte (`card_market_info`, champ JSON `info`), écrite chaque nuit
//   par tools/cardmarket_sync.py avec le compte superuser ; lecture seule pour l'app.

const CONNECTE = '@request.auth.id != ""';
const PROPRIO = "user_id = @request.auth.id";

function idLibre(c, min) {
  const f = c.fields.getByName("id");
  f.min = min || 1;
  f.max = 36;
  f.pattern = "^[a-z0-9-]+$";
}

function base(app, name, fields, rules, indexes) {
  // Créée avec { type } seulement puis complétée (piège JSVM : champs / règles perdus sinon).
  const c = new Collection({ type: "base" });
  c.name = name;
  idLibre(c);
  for (const f of fields) c.fields.add(f);
  c.listRule = rules.list;
  c.viewRule = rules.view === undefined ? rules.list : rules.view;
  c.createRule = rules.create;
  c.updateRule = rules.update;
  c.deleteRule = rules.delete;
  if (indexes) c.indexes = indexes;
  app.save(c);
  return c;
}

const txt = (name, max) => new TextField({ name, max: max || 5000 });
const num = (name) => new NumberField({ name });
const creeLe = (name) => new AutodateField({ name: name || "created_at", onCreate: true, onUpdate: false });
const majLe = () => new AutodateField({ name: "updated_at", onCreate: true, onUpdate: true });

migrate((app) => {
  // ---- Comptes : un seul compte (le propriétaire), pas d'inscription publique -----------------
  const users = app.findCollectionByNameOrId("users");
  idLibre(users);
  users.listRule = "id = @request.auth.id";
  users.viewRule = "id = @request.auth.id";
  users.createRule = null;   // comptes créés par le superuser (pas de formulaire d'inscription)
  users.updateRule = "id = @request.auth.id";
  users.deleteRule = null;
  app.save(users);

  const lectureCatalogue = { list: CONNECTE, create: CONNECTE, update: CONNECTE, delete: CONNECTE };

  base(app, "games", [
    txt("slug"), txt("name"), txt("subtitle"), txt("logo_url", 200000), txt("color"), num("sort_order"),
  ], { list: CONNECTE, create: null, update: null, delete: null });

  base(app, "game_sets", [
    txt("game_slug"), txt("set_name"), txt("display_name"), txt("logo_url", 200000), num("sort_order"),
    txt("release_date"), txt("release_precision"),
  ], { list: CONNECTE, create: null, update: null, delete: null },
  ["CREATE UNIQUE INDEX idx_game_sets_slug_name ON game_sets (game_slug, set_name)"]);

  const cards = base(app, "cards", [
    txt("game"), txt("game_slug"), txt("set_name"), txt("set_code"), txt("card_number"), txt("card_name"),
    txt("rarity"), txt("card_type"), txt("color"), txt("language"), txt("release_date"),
    txt("official_image_url", 2000),
    new FileField({ name: "image", maxSelect: 1, maxSize: 10485760,
      mimeTypes: ["image/png", "image/jpeg", "image/webp", "image/gif"] }),
    txt("source_url", 2000), txt("notes", 20000), txt("review_status"), txt("review_source"),
    num("cardmarket_id"), txt("cardmarket_match"), creeLe(), majLe(),
  ], lectureCatalogue, [
    "CREATE INDEX idx_cards_status ON cards (review_status)",
    "CREATE UNIQUE INDEX idx_cards_unique ON cards (game, set_code, card_number, language)",
  ]);

  const perso = { list: PROPRIO, create: `${CONNECTE} && @request.body.user_id = @request.auth.id`, update: PROPRIO, delete: PROPRIO };

  const items = base(app, "collection_items", [
    new RelationField({ name: "user_id", collectionId: users.id, maxSelect: 1, required: true, cascadeDelete: true }),
    new RelationField({ name: "card_id", collectionId: cards.id, maxSelect: 1 }),
    txt("custom_name"), txt("status"), num("quantity"), txt("condition"), txt("language_override"),
    txt("grading_company"), num("grading_score"), num("price_paid"), num("estimated_value"), txt("currency"),
    txt("acquired_date"), txt("notes", 20000), creeLe(), majLe(),
  ], perso);

  base(app, "card_photos", [
    new RelationField({ name: "collection_item_id", collectionId: items.id, maxSelect: 1, required: true, cascadeDelete: true }),
    new RelationField({ name: "user_id", collectionId: users.id, maxSelect: 1, required: true, cascadeDelete: true }),
    new FileField({ name: "photo", maxSelect: 1, maxSize: 20971520, protected: true,
      mimeTypes: ["image/png", "image/jpeg", "image/webp", "image/heic", "image/heif"] }),
    txt("side"), creeLe(),
  ], perso);

  base(app, "hidden_cards", [
    new RelationField({ name: "user_id", collectionId: users.id, maxSelect: 1, required: true, cascadeDelete: true }),
    new RelationField({ name: "card_id", collectionId: cards.id, maxSelect: 1, required: true, cascadeDelete: true }),
    creeLe("hidden_at"),
  ], perso, ["CREATE UNIQUE INDEX idx_hidden_user_card ON hidden_cards (user_id, card_id)"]);

  // ---- Cardmarket (écrit par le superuser) -----------------------------------------------------
  const lectureSeule = { list: CONNECTE, create: null, update: null, delete: null };
  base(app, "card_market_info", [txt("card_id"), new JSONField({ name: "info" }), majLe()], lectureSeule,
    ["CREATE UNIQUE INDEX idx_market_card ON card_market_info (card_id)"]);
  base(app, "cardmarket_price_history", [num("id_product"), txt("price_date"), new JSONField({ name: "prices" })], lectureSeule,
    ["CREATE UNIQUE INDEX idx_history_product_date ON cardmarket_price_history (id_product, price_date)"]);
  base(app, "cardmarket_sync_log", [new BoolField({ name: "ok" }), new JSONField({ name: "info" }), creeLe("run_at")],
    { list: null, create: null, update: null, delete: null });

  // ---- Réglages : nom, requêtes groupées (import / synchro), limitation des connexions ----------
  const s = app.settings();
  s.meta.appName = "Goku SS3 Collection";
  s.batch.enabled = true;
  s.batch.maxRequests = 200;
  s.rateLimits.enabled = true;
  const rules = s.rateLimits.rules.filter((r) => r.label !== "*:authWithPassword");
  rules.push({ label: "*:authWithPassword", audience: "", duration: 60, maxRequests: 10 });
  s.rateLimits.rules = rules;
  app.save(s);
}, (app) => {
  for (const n of ["cardmarket_sync_log", "cardmarket_price_history", "card_market_info", "hidden_cards",
                   "card_photos", "collection_items", "cards", "game_sets", "games"]) {
    try { app.delete(app.findCollectionByNameOrId(n)); } catch (e) {}
  }
});
