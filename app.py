import json
import random
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

app = FastAPI()

places = {
    "J1": None,
    "J2": None
}

mains = {
    "J1": {"coeur": 0, "carreau": 0, "trefle": 0, "pique": 0},
    "J2": {"coeur": 0, "carreau": 0, "trefle": 0, "pique": 0}
}

carte_actuelle = "dos"
cartes_autorisees = ["coeur", "carreau", "trefle", "pique"]

@app.get("/")
async def afficher_page():
    with open("templates/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

def distribuer_64_cartes():
    """Crée un paquet de 64 cartes (16 de chaque), le mélange et donne 32 cartes à chaque joueur."""
    paquet = ["coeur"] * 16 + ["carreau"] * 16 + ["trefle"] * 16 + ["pique"] * 16
    random.shuffle(paquet)
    
    main_j1 = paquet[:32]
    main_j2 = paquet[32:]
    
    for role, cartes_joueur in [("J1", main_j1), ("J2", main_j2)]:
        mains[role] = {
            "coeur": cartes_joueur.count("coeur"),
            "carreau": cartes_joueur.count("carreau"),
            "trefle": cartes_joueur.count("trefle"),
            "pique": cartes_joueur.count("pique")
        }

async def envoyer_main(role: str):
    """Envoie à un joueur le nombre de cartes qu'il possède pour chaque enseigne."""
    ws = places[role]
    if ws is not None:
        try:
            await ws.send_text(json.dumps({
                "type": "maj_main",
                "main": mains[role]
            }))
        except Exception:
            pass

async def diffuser_aux_joueurs(donnees: dict):
    message = json.dumps(donnees)
    for role in ["J1", "J2"]:
        ws = places[role]
        if ws is not None:
            try:
                await ws.send_text(message)
            except Exception:
                pass

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global carte_actuelle
    await websocket.accept()

    mon_role = None
    if places["J1"] is None:
        places["J1"] = websocket
        mon_role = "J1"
    elif places["J2"] is None:
        places["J2"] = websocket
        mon_role = "J2"
    else:
        await websocket.send_text(json.dumps({
            "type": "complet",
            "message": "La partie est complète (Joueur 1 et Joueur 2 sont déjà connectés)."
        }))
        await websocket.close()
        return

    nb_joueurs = sum(1 for v in places.values() if v is not None)
    await websocket.send_text(json.dumps({
        "type": "attribution",
        "role": mon_role,
        "carte": carte_actuelle
    }))

    # Si les 2 joueurs sont arrivés, on distribue les 64 cartes aléatoirement
    if nb_joueurs == 2:
        carte_actuelle = "dos"
        distribuer_64_cartes()
        await envoyer_main("J1")
        await envoyer_main("J2")

    await diffuser_aux_joueurs({
        "type": "statut_salle",
        "nb_joueurs": nb_joueurs
    })

    try:
        while True:
            texte = await websocket.receive_text()
            data = json.loads(texte)

            if data.get("action") == "jouer_carte" and places["J1"] and places["J2"]:
                nouvelle_carte = data.get("valeur")
                # On vérifie que la carte est valide ET que le joueur en a encore en stock
                if nouvelle_carte in cartes_autorisees and mains[mon_role][nouvelle_carte] > 0:
                    mains[mon_role][nouvelle_carte] -= 1
                    carte_actuelle = nouvelle_carte
                    nom_joueur = "Joueur 1" if mon_role == "J1" else "Joueur 2"
                    
                    # On met à jour le compteur du joueur qui a joué
                    await envoyer_main(mon_role)
                    
                    # On affiche la carte au centre pour les deux joueurs
                    await diffuser_aux_joueurs({
                        "type": "carte",
                        "valeur": carte_actuelle,
                        "par": nom_joueur
                    })

    except WebSocketDisconnect:
        if places[mon_role] == websocket:
            places[mon_role] = None
            carte_actuelle = "dos"
            mains["J1"] = {"coeur": 0, "carreau": 0, "trefle": 0, "pique": 0}
            mains["J2"] = {"coeur": 0, "carreau": 0, "trefle": 0, "pique": 0}
            
            nb_restants = sum(1 for v in places.values() if v is not None)
            await diffuser_aux_joueurs({
                "type": "statut_salle",
                "nb_joueurs": nb_restants
            })
