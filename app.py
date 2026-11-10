import os
import random
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret_menteur_key'
# Support optimal pour le déploiement en temps réel
socketio = SocketIO(app, cors_allowed_origins="*")

# --- CONFIGURATION EXACTE DE VOS CARTES ---
VALEURS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'jack', 'queen', 'king', 'ace']
ENSEIGNES = ['clubs', 'diamonds', 'hearts', 'spades']

# Génère la liste des 52 noms de fichiers sans extension (ex: "2_of_clubs")
PAQUET_GENERIC = [f"{v}_of_{e}" for v in VALEURS for e in ENSEIGNES]

game_state = {
    "players": {},       
    "current_turn": None,
    "history": []
}

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('join')
def handle_join(data):
    username = data.get('username')
    player_id = request.sid if hasattr(request, 'sid') else None
    
    if username and username not in game_state["players"]:
        # Distribution de 5 cartes aléatoires uniques
        main_du_joueur = random.sample(PAQUET_GENERIC, 5)
        
        game_state["players"][username] = {
            "id": player_id, 
            "cards": main_du_joueur
        }
        
        game_state["history"].append(f"♣️ {username} a rejoint la table de jeu.")
        emit('update_game', game_state, broadcast=True)

@socketio.on('play_action')
def handle_action(data):
    username = data.get('username')
    action = data.get('action')
    detail = data.get('detail')
    
    if action == "bet":
        log_message = f"🎲 {username} annonce : {detail}"
    else:
        log_message = f"🚨 {username} crie MENTEUR !"
        
    game_state["history"].append(log_message)
    emit('update_game', game_state, broadcast=True)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port)
