import os, random, secrets
from threading import RLock
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))
socketio = SocketIO(app, async_mode='threading')
players, games, invitations = {}, {}, {}
lock = RLock()
TYPES = ['Coeur', 'Carreau', 'Trefle', 'Pique']

@app.route('/')
def index():
    return render_template('index.html')

def lobby():
    socketio.emit('lobby', [{'id': sid, 'name': p['name'], 'busy': bool(p.get('game'))} for sid, p in players.items()])

def state(gid):
    g = games.get(gid)
    if not g: return
    for sid in g['players']:
        other = next(x for x in g['players'] if x != sid)
        socketio.emit('game', {'hand': g['hands'][sid], 'opponent': players.get(other, {}).get('name', 'Adversaire'), 'opponentCount': len(g['hands'][other]), 'pile': len(g['pile']), 'claim': g['claim'], 'turn': g['turn'] == sid, 'canCall': bool(g['last']) and g['last']['by'] != sid, 'message': g['message']}, to=sid)

def finish(gid, winner):
    g = games.pop(gid, None)
    if not g: return
    for sid in g['players']:
        if sid in players: players[sid]['game'] = None
        socketio.emit('finished', {'message': 'Tu as gagné !' if sid == winner else 'Ton adversaire a gagné.'}, to=sid)
    lobby()

@socketio.on('join')
def join(data):
    with lock:
        name = str((data or {}).get('name', '')).strip()[:20]
        if not name: return emit('notice', 'Choisis un pseudo.')
        if request.sid in players: return
        if len(players) >= 100: return emit('notice', 'Le salon est complet.')
        if any(p['name'].casefold() == name.casefold() for p in players.values()): return emit('notice', 'Ce pseudo est déjà utilisé.')
        players[request.sid] = {'name': name, 'game': None}
        emit('joined', {'id': request.sid})
        lobby()

@socketio.on('challenge')
def challenge(data):
    with lock:
        sid, target = request.sid, str((data or {}).get('id', ''))
        if sid not in players or target not in players or sid == target: return
        if players[sid]['game'] or players[target]['game']: return emit('notice', 'Ce joueur est déjà en duel.')
        invitations[target] = sid
        socketio.emit('invitation', {'id': sid, 'name': players[sid]['name']}, to=target)
        emit('notice', 'Défi envoyé : attends sa réponse.')

@socketio.on('answer')
def answer(data):
    with lock:
        sid = request.sid
        challenger = invitations.pop(sid, None)
        if sid not in players or challenger not in players: return
        if not (data or {}).get('accept'): return socketio.emit('notice', 'Défi refusé.', to=challenger)
        if players[sid]['game'] or players[challenger]['game']: return
        gid = secrets.token_hex(12)
        deck = TYPES * 8
        random.shuffle(deck)
        games[gid] = {'players': [challenger, sid], 'hands': {challenger: deck[:16], sid: deck[16:]}, 'pile': [], 'last': None, 'claim': None, 'turn': challenger, 'message': 'Le premier joueur choisit le type annoncé.'}
        for p in [sid, challenger]: players[p]['game'] = gid
        state(gid)
        lobby()

@socketio.on('play')
def play(data):
    with lock:
        sid = request.sid
        gid = players.get(sid, {}).get('game')
        g = games.get(gid)
        if not g or g['turn'] != sid: return
        data = data or {}
        indices, claim = data.get('indices'), data.get('claim')
        if not isinstance(indices, list) or not 1 <= len(indices) <= 3: return
        if any(type(i) is not int for i in indices) or len(set(indices)) != len(indices): return
        if any(i < 0 or i >= len(g['hands'][sid]) for i in indices): return
        if g['claim'] and claim != g['claim']: return
        if claim not in TYPES: return
        if g['last'] and not g['hands'][g['last']['by']]: return finish(gid, g['last']['by'])
        cards = [g['hands'][sid][i] for i in indices]
        for i in sorted(indices, reverse=True): g['hands'][sid].pop(i)
        g['pile'].extend(cards)
        g['last'] = {'by': sid, 'cards': cards}
        g['claim'] = claim
        g['turn'] = next(p for p in g['players'] if p != sid)
        g['message'] = f"{players[sid]['name']} annonce {len(cards)} carte(s) de type {claim}. Menteur ou continuer ?"
        state(gid)

@socketio.on('call')
def call():
    with lock:
        sid = request.sid
        gid = players.get(sid, {}).get('game')
        g = games.get(gid)
        if not g or not g['last'] or g['last']['by'] == sid or g['turn'] != sid: return
        author = g['last']['by']
        lied = any(c != g['claim'] for c in g['last']['cards'])
        loser = author if lied else sid
        revealed = ', '.join(g['last']['cards'])
        g['hands'][loser].extend(g['pile'])
        g['message'] = f"Cartes révélées : {revealed}. {players[loser]['name']} ramasse la pile."
        g.update(pile=[], last=None, claim=None, turn=loser)
        if not g['hands'][author]: return finish(gid, author)
        state(gid)

@socketio.on('leave')
def leave():
    with lock:
        gid = players.get(request.sid, {}).get('game')
        if gid in games:
            winner = next(p for p in games[gid]['players'] if p != request.sid)
            finish(gid, winner)

@socketio.on('disconnect')
def disconnect():
    with lock:
        sid = request.sid
        gid = players.get(sid, {}).get('game')
        if gid in games: finish(gid, next(p for p in games[gid]['players'] if p != sid))
        players.pop(sid, None)
        invitations.pop(sid, None)
        for target, challenger in list(invitations.items()):
            if challenger == sid: invitations.pop(target, None)
        lobby()

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), allow_unsafe_werkzeug=True)
