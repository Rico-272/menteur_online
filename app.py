import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

app = FastAPI()

# Dictionnaire des joueurs : { websocket: "Pseudo" }
joueurs_connectes: dict[WebSocket, str] = {}

carte_actuelle = "dos"
cartes_autorisees = ["coeur", "carreau", "trefle", "pique", "dos"]

@app.get("/")
async def afficher_page():
    with open("templates/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

async def diffuser_a_tous(donnees: dict):
    """Envoie un message JSON à tous les joueurs connectés."""
    message = json.dumps(donnees)
    for client in list(joueurs_connectes.keys()):
        try:
            await client.send_text(message)
        except Exception:
            pass

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global carte_actuelle
    await websocket.accept()
    
    try:
        while True:
            texte_recu = await websocket.receive_text()
            donnees = json.loads(texte_recu)
            action = donnees.get("action")

            # 1. Un joueur entre son pseudo et rejoint la partie
            if action == "rejoindre":
                pseudo = donnees.get("pseudo", "").strip() or "Joueur Anonyme"
                joueurs_connectes[websocket] = pseudo
                
                # On lui envoie la carte actuelle sur le tapis
                await websocket.send_text(json.dumps({
                    "type": "carte",
                    "valeur": carte_actuelle
                }))
                
                # On met à jour la liste des joueurs chez tout le monde
                await diffuser_a_tous({
                    "type": "liste_joueurs",
                    "joueurs": list(joueurs_connectes.values())
                })

            # 2. Un joueur connecté clique sur une carte
            elif action == "jouer_carte" and websocket in joueurs_connectes:
                nouvelle_carte = donnees.get("valeur")
                if nouvelle_carte in cartes_autorisees:
                    carte_actuelle = nouvelle_carte
                    await diffuser_a_tous({
                        "type": "carte",
                        "valeur": carte_actuelle,
                        "par": joueurs_connectes[websocket]
                    })

    except WebSocketDisconnect:
        # Si le joueur ferme la page, on le retire et on prévient les autres
        if websocket in joueurs_connectes:
            del joueurs_connectes[websocket]
            await diffuser_a_tous({
                "type": "liste_joueurs",
                "joueurs": list(joueurs_connectes.values())
            })
