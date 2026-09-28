#!/usr/bin/env python3
"""Définit (ou réinitialise) le mot de passe du compte de l'app Goku SS3, à lancer soi-même sur le Mac mini :

    python3 ~/Services/goku/tools/set_password.py

Le mot de passe est saisi au clavier (rien ne s'affiche) et envoyé directement à PocketBase avec le compte
superuser (~/.config/goku-pb/superuser.json). Remplace le « Mot de passe oublié » de l'ancienne version
(il n'y a pas de serveur d'e-mails sur le Mac mini).
"""
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pb import PB  # noqa: E402

pb = PB()
users = pb.list_all("users", fields="id,email")
if not users:
    sys.exit("Aucun compte dans la base.")
user = users[0]
if len(users) > 1:
    for i, u in enumerate(users):
        print(f"{i + 1}. {u['email']}")
    user = users[int(input("Numéro du compte : ")) - 1]
print(f"Compte : {user['email']}")
pw = getpass.getpass("Nouveau mot de passe (8 caractères minimum) : ")
if len(pw) < 8:
    sys.exit("Trop court (8 caractères minimum).")
if getpass.getpass("Confirmer : ") != pw:
    sys.exit("Les deux saisies ne correspondent pas.")
pb.update("users", user["id"], {"password": pw, "passwordConfirm": pw})
print("Mot de passe enregistré. Tu peux te connecter dans l'app.")
