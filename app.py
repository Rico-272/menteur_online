import os
from flask import Flask, render_template
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret_menteur_key'
# Gunicorn utilise eventlet ou gevent sur Render
socketio = SocketIO(app, cors_allowed_origins="*")

# Stockage temporaire des joueurs (En production, préférez une base de données ou Redis)
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
    player_id = request.sid if hasattr(request, 'sid') else None # identifiant unique de session socket
    
    if username:
        game_state["players"][username] = {"id": player_id, "cards_count": 5}
        emit('update_game', game_state, broadcast=True)

@socketio.on('play_action')
def handle_action(data):
    # data contient l'action du joueur : "parier" ou "mentir"
    username = data.get('username')
    action = data.get('action')
    detail = data.get('detail') # ex: "3 Rois"
    
    log_message = f"{username} a dit : {detail}" if action == "bet" else f"{username} a crié MENTEUR !"
    game_state["history"].append(log_message)
    
    emit('update_game', game_state, broadcast=True)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port)
