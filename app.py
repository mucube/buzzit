from flask import Flask, render_template, request, redirect, url_for
from flask_socketio import SocketIO, emit, join_room
import eventlet
import random
import string

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app)

games = dict()  # {game_code: {'host': ..., 'buzzed': None, 'players': set()}}

def generate_game_code(length=5):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/host', methods=['GET', 'POST'])
def host():
    if request.method == 'POST':
        host_name = request.form['host_name']
        game_code = generate_game_code()
        while game_code in games:  # Ensure uniqueness
            game_code = generate_game_code()
        games[game_code] = {
            'host': host_name,
            'buzzed': None,
            'players': set(),
            'scores': dict()  # player_name: score
        }
        return redirect(url_for('game', game_code=game_code, host=1))
    return render_template('host.html')

@app.route('/join', methods=['GET', 'POST'])
def join():
    if request.method == 'POST':
        game_code = request.form['game_code'].upper().replace(' ', '')
        player_name = request.form['player_name']
        if game_code in games:
            games[game_code]['players'].add(player_name)
            return redirect(url_for('game', game_code=game_code, player=player_name))
        else:
            return render_template('join.html', error="Game not found.")
    return render_template('join.html')

@app.route('/game/<game_code>')
def game(game_code):
    host = request.args.get('host')
    player = request.args.get('player')
    return render_template('game.html', game_code=game_code, host=host, player=player)

@socketio.on('buzz')
def handle_buzz(data):
    game_code = data['game_code']
    player = data['player']
    if game_code in games:
        if games[game_code]['buzzed'] is None:
            games[game_code]['buzzed'] = player
            emit('buzzed', {'player': player}, room=game_code)
    else:
        emit('buzzed', {'player': 'Invalid game code'}, room=request.sid)

@socketio.on('join')
def on_join(data):
    game_code = data['game_code']
    player = data.get('player')
    join_room(game_code)
    if player and player.strip() and game_code in games:
        games[game_code]['players'].add(player)
        # Initialize score if not present
        if player not in games[game_code]['scores']:
            games[game_code]['scores'][player] = 0
        emit('update_players', room=game_code)

@socketio.on('get_players')
def handle_get_players(data):
    game_code = data['game_code']
    if game_code in games:
        emit('player_list', {
            'players': list(games[game_code]['players']),
            'scores': games[game_code]['scores']
        }, room=request.sid)

@socketio.on('update_score')
def handle_update_score(data):
    game_code = data['game_code']
    player = data['player']
    delta = int(data['delta'])
    if game_code in games and player in games[game_code]['scores']:
        games[game_code]['scores'][player] += delta
        # Broadcast updated scores to all clients in the game
        emit('player_list', {
            'players': list(games[game_code]['players']),
            'scores': games[game_code]['scores']
        }, room=game_code)

@socketio.on('reset')
def handle_reset(data):
    game_code = data['game_code']
    if game_code in games:
        games[game_code]['buzzed'] = None
        emit('reset', {}, room=game_code)

if __name__ == '__main__':
    socketio.run(app, debug=True)