import uuid
import secrets
import json
import asyncio
from fastapi import FastAPI, Request, Form, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from typing import Dict, List

from game_models import GameRoom, Player
from game_logic import generate_bookings
from connection_manager import ConnectionManager

# --- Application State & Managers ---
game_manager: Dict[str, GameRoom] = {}
connection_manager = ConnectionManager()
templates = Jinja2Templates(directory="templates")

# Initialize the FastAPI application
app = FastAPI()

# --- Helper Functions ---

def get_unique_name(base_name: str, players: List[Player]) -> str:
    """Appends a number to a name if it's already taken."""
    if not any(p.name == base_name for p in players):
        return base_name
    counter = 2
    while True:
        new_name = f"{base_name}#{counter}"
        if not any(p.name == new_name for p in players):
            return new_name
        counter += 1

# --- Game Logic Functions ---

async def start_new_round(room_id: str):
    """
    Initiates a new round by sending the correct view to the host and players,
    or ends the game and broadcasts the final results if no rounds are left.
    """
    game_room = game_manager.get(room_id)
    if not game_room:
        return

    current_booking = game_room.get_current_booking()
    
    if current_booking:
        # --- GAME IS IN PROGRESS ---
        
        # 1. Differentiate between host and players
        host_id = game_room.host_id
        
        # 2. Render the two different views
        player_html = templates.get_template("_booking_request.html").render({
            "room": game_room, "booking": current_booking
        })
        
        host_html = templates.get_template("_host_view.html").render({
            "room": game_room, "booking": current_booking
        })

        # 3. Broadcast the correct view to each person
        for player_id, connection in connection_manager.get_connections_in_room(room_id):
            if player_id == host_id:
                await connection.send_text(host_html)
            else:
                await connection.send_text(player_html)
        
        # 4. Start the backend timer for the round
        asyncio.create_task(round_timer(room_id, game_room.current_round))
    
    else:
        # --- GAME HAS ENDED ---
        
        # 1. Calculate final scores for all players
        game_room.end_game()
        
        host_player_id = game_room.host_id

        # 2. Create a list of actual players for the results (excluding the host)
        actual_players = [p for p in game_room.players.values() if p.player_id != host_player_id]

        # 3. Broadcast the final results, sending a custom view to the host
        for player_id, connection in connection_manager.get_connections_in_room(room_id):
             is_player_host = player_id == host_player_id
             
             html_content = templates.get_template("_results.html").render({
                "players": actual_players,
                "is_host": is_player_host,
                "host_name": game_room.players[host_player_id].name,
                "current_player_id": player_id,
                "game_room": game_room
            })
             await connection.send_text(html_content)

async def round_timer(room_id: str, round_number: int):
    """Waits for a set time, then advances the game."""
    await asyncio.sleep(5) # 60-second timer
    
    game_room = game_manager.get(room_id)
    if game_room and game_room.current_round == round_number:
        game_room.advance_to_next_round()
        await start_new_round(room_id)

# --- HTTP Endpoints ---

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/host")
async def host_game(player_name: str = Form(...)):
    """Creates a game room and sets the host."""
    room_id = secrets.token_hex(3)
    host_id = str(uuid.uuid4()) # Generate a unique ID for the host
    
    # Create the room and immediately add the host as the first "player"
    new_game_room = GameRoom(room_id=room_id, host_id=host_id)
    new_game_room.add_player(host_id, name=f"{player_name} (Host)")
    new_game_room.bookings = generate_bookings() # Generate bookings for the game
    
    game_manager[room_id] = new_game_room
    
    # The host joins the game room URL, but we will also pass their unique ID
    response = RedirectResponse(url=f"/game/{room_id}?name={player_name}", status_code=303)
    # The host's ID is set in their cookie, just like a regular player
    response.set_cookie(key="player_id", value=host_id, httponly=True)
    return response

@app.post("/join")
async def join_game(room_id: str = Form(...), player_name: str = Form(...)):
    """Redirects a player to a game room."""
    if room_id in game_manager:
        return RedirectResponse(url=f"/game/{room_id}?name={player_name}", status_code=303)
    else:
        return RedirectResponse(url="/", status_code=303)

@app.get("/game/{room_id}", response_class=HTMLResponse)
async def get_game_room(request: Request, room_id: str, name: str = "Player"):
    """The main endpoint for the game room/lobby."""
    game_room = game_manager.get(room_id)
    if not game_room:
        return RedirectResponse(url="/")

    # --- REFACTORED LOGIC ---

    # 1. Get the ID from the cookie
    cookie_player_id = request.cookies.get("player_id")
    
    # 2. Check if a player with this ID is already in THIS room
    player = game_room.players.get(cookie_player_id) if cookie_player_id else None

    # 3. Handle the player's state
    if player:
        # Case A: Player is returning. Their cookie is valid for this room.
        # We will use their existing ID.
        response_player_id = cookie_player_id
    else:
        # Case B: New player. They have no cookie, or their cookie is from an old game.
        # We MUST create a new identity for them for this room.
        new_player_id = str(uuid.uuid4())
        unique_name = get_unique_name(name, list(game_room.players.values()))
        game_room.add_player(new_player_id, unique_name)
        
        # Get the newly created player object
        player = game_room.players[new_player_id]
        # The ID for the response and the new cookie is the one we just created.
        response_player_id = new_player_id

    # 4. Render the response and set the correct cookie
    response = templates.TemplateResponse(
        "game_room.html",
        {"request": request, "room": game_room, "player": player}
    )
    response.set_cookie(key="player_id", value=response_player_id, httponly=True)
    return response

# --- WebSocket Endpoint ---

@app.websocket("/ws/{room_id}/{player_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str, player_id: str):
    await connection_manager.connect(websocket, room_id, player_id)
    game_room = game_manager.get(room_id)
    
    if game_room:
        html_content = templates.get_template("_lobby_updater.html").render({
            "players": game_room.players.values(), "current_player_id": player_id
        })
        await connection_manager.broadcast_html(room_id, html_content)

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            action = message.get("action")

            if game_room and action == "start_game":
                game_room.start_game()
                await start_new_round(room_id)
            
            if game_room and action == "accept_booking":
                game_room.player_accept_booking(player_id)
                html_confirm = templates.get_template("_waiting_for_decision.html").render({"decision": "Accepted"})
                await websocket.send_text(html_confirm)

            if game_room and action == "reject_booking":
                html_confirm = templates.get_template("_waiting_for_decision.html").render({"decision": "Rejected"})
                await websocket.send_text(html_confirm)

    except WebSocketDisconnect:
        connection_manager.disconnect(websocket, room_id, player_id)
        if game_room:
            html_content = templates.get_template("_lobby_updater.html").render({
                "players": game_room.players.values(), "current_player_id": None
            })
            await connection_manager.broadcast_html(room_id, html_content)
