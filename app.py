import json
import uuid
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

app = FastAPI()

# Structure : { id_joueur: {"ws": WebSocket, "pseudo": str, "adversaire": str | None, "carte": str} }
joueurs: dict[str, dict] = {}
cartes_autorisees = ["coeur", "carreau", "trefle", "pique", "dos"]

@app.get("/")
async def afficher_page():
    with open("templates/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

async def diffuser_lobby():
    """Envoie la liste à jour de tous les joueurs et leur statut (libre / en duel) à tout le monde."""
    liste = [
        {
            "id": j_id,
            "pseudo": infos["pseudo"],
            "en_duel": infos["adversaire"] is not None
        }
        for j_id, infos in joueurs.items()
    ]
    message = json.dumps({"type": "liste_joueurs", "joueurs": liste})
    for infos in list(joueurs.values()):
        try:
            await infos["ws"].send_text(message)
        except Exception:
            pass

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    mon_id = str(uuid.uuid4())[:8]

    try:
        while True:
            texte = await websocket.receive_text()
            data = json.loads(texte)
            action = data.get("action")

            # 1. Connexion avec pseudo
            if action == "rejoindre":
                pseudo = data.get("pseudo", "").strip() or f"Joueur-{mon_id[:4]}"
                joueurs[mon_id] = {
                    "ws": websocket,
                    "pseudo": pseudo,
                    "adversaire": None,
                    "carte": "dos"
                }
                await websocket.send_text(json.dumps({
                    "type": "bienvenue",
                    "id": mon_id,
                    "pseudo": pseudo
                }))
                await diffuser_lobby()

            # 2. Envoi d'un défi à un autre joueur
            elif action == "defier" and mon_id in joueurs:
                cible_id = data.get("cible_id")
                if cible_id in joueurs and cible_id != mon_id:
                    cible = joueurs[cible_id]
                    if cible["adversaire"] is None and joueurs[mon_id]["adversaire"] is None:
                        await cible["ws"].send_text(json.dumps({
                            "type": "defi_recu",
                            "de_id": mon_id,
                            "de_pseudo": joueurs[mon_id]["pseudo"]
                        }))

            # 3. Réponse au défi (accepter ou refuser)
            elif action == "repondre_defi" and mon_id in joueurs:
                challenger_id = data.get("de_id")
                accepte = data.get("accepte", False)

                if challenger_id in joueurs:
                    challenger = joueurs[challenger_id]
                    moi = joueurs[mon_id]

                    if accepte and challenger["adversaire"] is None and moi["adversaire"] is None:
                        # On lie les deux joueurs en duel
                        moi["adversaire"] = challenger_id
                        challenger["adversaire"] = mon_id
                        moi["carte"] = "dos"
                        challenger["carte"] = "dos"

                        # On lance l'écran de duel chez les deux joueurs
                        await moi["ws"].send_text(json.dumps({
                            "type": "debut_duel",
                            "adversaire": challenger["pseudo"]
                        }))
                        await challenger["ws"].send_text(json.dumps({
                            "type": "debut_duel",
                            "adversaire": moi["pseudo"]
                        }))
                        await diffuser_lobby()
                    else:
                        await challenger["ws"].send_text(json.dumps({
                            "type": "defi_refuse",
                            "par": moi["pseudo"]
                        }))

            # 4. Jouer une carte pendant le duel
            elif action == "jouer_carte" and mon_id in joueurs:
                adv_id = joueurs[mon_id]["adversaire"]
                carte = data.get("valeur")
                if adv_id and adv_id in joueurs and carte in cartes_autorisees:
                    joueurs[mon_id]["carte"] = carte
                    # On synchronise la carte uniquement entre les deux duellistes
                    msg = json.dumps({
                        "type": "carte_duel",
                        "valeur": carte,
                        "par": joueurs[mon_id]["pseudo"]
                    })
                    await joueurs[mon_id]["ws"].send_text(msg)
                    await joueurs[adv_id]["ws"].send_text(msg)

            # 5. Quitter le duel pour revenir au salon
            elif action == "quitter_duel" and mon_id in joueurs:
                adv_id = joueurs[mon_id]["adversaire"]
                joueurs[mon_id]["adversaire"] = None
                if adv_id and adv_id in joueurs:
                    joueurs[adv_id]["adversaire"] = None
                    await joueurs[adv_id]["ws"].send_text(json.dumps({
                        "type": "fin_duel",
                        "raison": f"{joueurs[mon_id]['pseudo']} a quitté le duel."
                    }))
                await joueurs[mon_id]["ws"].send_text(json.dumps({
                    "type": "fin_duel",
                    "raison": "Vous avez quitté le duel."
                }))
                await diffuser_lobby()

    except WebSocketDisconnect:
        if mon_id in joueurs:
            adv_id = joueurs[mon_id]["adversaire"]
            pseudo_parti = joueurs[mon_id]["pseudo"]
            del joueurs[mon_id]

            # Si le joueur était en duel, on prévient son adversaire et on le ramène au salon
            if adv_id and adv_id in joueurs:
                joueurs[adv_id]["adversaire"] = None
                await joueurs[adv_id]["ws"].send_text(json.dumps({
                    "type": "fin_duel",
                    "raison": f"{pseudo_parti} s'est déconnecté."
                }))
            await diffuser_lobby()
