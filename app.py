import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

app = FastAPI()

# Liste des joueurs actuellement connectés
clients_connectes: list[WebSocket] = []

# Mémoire de la carte actuelle sur le tapis (par défaut : dos)
carte_actuelle = "dos"
cartes_autorisees = ["coeur", "carreau", "trefle", "pique", "dos"]

@app.get("/")
async def afficher_page():
    with open("templates/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global carte_actuelle
    await websocket.accept()
    clients_connectes.append(websocket)
    
    # Dès qu'un joueur se connecte, on lui envoie la carte actuellement au centre
    await websocket.send_text(carte_actuelle)
    
    try:
        while True:
            # On attend qu'un joueur clique et envoie le nom d'une carte
            nouvelle_carte = await websocket.receive_text()
            
            if nouvelle_carte in cartes_autorisees:
                carte_actuelle = nouvelle_carte
                # On renvoie la nouvelle carte à TOUS les joueurs connectés
                for client in clients_connectes:
                    await client.send_text(carte_actuelle)
                    
    except WebSocketDisconnect:
        clients_connectes.remove(websocket)
