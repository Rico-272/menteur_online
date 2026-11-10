import os
import random
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

app = FastAPI()

# Configuration des dossiers de vos images locales
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# --- CONFIGURATION EXACTE DE VOS CARTES ---
VALEURS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'jack', 'queen', 'king', 'ace']
ENSEIGNES = ['clubs', 'diamonds', 'hearts', 'spades']
PAQUET_GENERIC = [f"{v}_of_{e}" for v in VALEURS for e in ENSEIGNES]

# État global du jeu
game_state = {
    "players": {},       
    "history": []
}

# Gestionnaires de connexions WebSockets actifs
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass

manager = ConnectionManager()

@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    current_user = None
    try:
        while True:
            data = await websocket.receive_json()
            event_type = data.get("type")
            
            if event_type == "join":
                username = data.get("username")
                if username and username not in game_state["players"]:
                    current_user = username
                    # Distribue 5 cartes aléatoires uniques
                    game_state["players"][username] = {
                        "cards": random.sample(PAQUET_GENERIC, 5)
                    }
                    game_state["history"].append(f"♣️ {username} a rejoint la table de jeu.")
                    await manager.broadcast({"type": "update", "state": game_state})
                    
            elif event_type == "play_action":
                username = data.get("username")
                action = data.get("action")
                detail = data.get("detail")
                
                if action == "bet":
                    log_message = f"🎲 {username} annonce : {detail}"
                else:
                    log_message = f"🚨 {username} crie MENTEUR !"
                    
                game_state["history"].append(log_message)
                await manager.broadcast({"type": "update", "state": game_state})
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        if current_user and current_user in game_state["players"]:
            del game_state["players"][current_user]
            game_state["history"].append(f"❌ {current_user} a quitté la table.")
            await manager.broadcast({"type": "update", "state": game_state})
