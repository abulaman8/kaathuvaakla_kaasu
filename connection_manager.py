from fastapi import WebSocket
from typing import Dict, List, Tuple

class ConnectionManager:
    def __init__(self):
        # Store a tuple of (player_id, websocket)
        self.active_connections: Dict[str, List[Tuple[str, WebSocket]]] = {}

    async def connect(self, websocket: WebSocket, room_id: str, player_id: str):
        """Accepts a connection, storing the websocket and player ID."""
        await websocket.accept()
        if room_id not in self.active_connections:
            self.active_connections[room_id] = []
        self.active_connections[room_id].append((player_id, websocket))

    def disconnect(self, websocket: WebSocket, room_id: str, player_id: str):
        """Removes a connection from the room's list."""
        if room_id in self.active_connections:
            connection_to_remove = next((conn for conn in self.active_connections[room_id] if conn[1] is websocket), None)
            if connection_to_remove:
                self.active_connections[room_id].remove(connection_to_remove)

    async def broadcast_html(self, room_id: str, html_content: str):
        """
        Broadcasts a message to all clients in a specific room.
        If a connection is closed, it will be skipped instead of crashing.
        """
        if room_id in self.active_connections:
            # We iterate over a copy of the list [:] in case a disconnect
            # modifies the list during the broadcast.
            for player_id, connection in self.active_connections[room_id][:]:
                try:
                    await connection.send_text(html_content)
                except RuntimeError as e:
                    # This error occurs if the socket is closed.
                    # We can safely ignore it and continue broadcasting to others.
                    print(f"Could not send to closed socket for player {player_id}: {e}")


    def get_connections_in_room(self, room_id: str) -> List[Tuple[str, WebSocket]]:
        """Generator to yield all connections in a room."""
        return self.active_connections.get(room_id, [])
