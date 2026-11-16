import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

app = FastAPI()

# Les deux seules places disponibles
places = {
    "J1": None,
    "J2": None
}

carte_actuelle = "dos"
cartes_autorisees = ["coeur", "carreau", "trefle", "pique", "dos"]

@app.get("/")
async def afficher_page():
    with open("templates/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

async def diffuser_aux_joueurs(donnees: dict):
    """Envoie les informations uniquement au Joueur 1 et au Joueur 2."""
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

    # Attribution automatique des places
    mon_role = None
    if places["J1"] is None:
        places["J1"] = websocket
        mon_role = "J1"
    elif places["J2"] is None:
        places["J2"] = websocket
        mon_role = "J2"
    else:
        # 3e personne ou plus : on bloque l'accès
        await websocket.send_text(json.dumps({
            "type": "complet",
            "message": "La partie est complète (Joueur 1 et Joueur 2 sont déjà connectés)."
        }))
        await websocket.close()
        return

    # On informe le joueur de son numéro et de l'état de la salle
    nb_joueurs = sum(1 for v in places.values() if v is not None)
    await websocket.send_text(json.dumps({
        "type": "attribution",
        "role": mon_role,
        "carte": carte_actuelle
    }))

    await diffuser_aux_joueurs({
        "type": "statut_salle",
        "nb_joueurs": nb_joueurs
    })

    try:
        while True:
            texte = await websocket.receive_text()
            data = json.loads(texte)

            # Le duel ne fonctionne que si les 2 joueurs sont là
            if data.get("action") == "jouer_carte" and places["J1"] and places["J2"]:
                nouvelle_carte = data.get("valeur")
                if nouvelle_carte in cartes_autorisees:
                    carte_actuelle = nouvelle_carte
                    nom_joueur = "Joueur 1" if mon_role == "J1" else "Joueur 2"
                    await diffuser_aux_joueurs({
                        "type": "carte",
                        "valeur": carte_actuelle,
                        "par": nom_joueur
                    })

    except WebSocketDisconnect:
        # Libération de la place quand un joueur ferme la page
        if places[mon_role] == websocket:
            places[mon_role] = None
            carte_actuelle = "dos"
            nb_restants = sum(1 for v in places.values() if v is not None)
            await diffuser_aux_joueurs({
                "type": "statut_salle",
                "nb_joueurs": nb_restants
            })
