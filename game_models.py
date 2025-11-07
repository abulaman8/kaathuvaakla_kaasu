import random
from pydantic import BaseModel, Field, computed_field
from typing import List, Dict
from collections import Counter

# --- Game Constants ---
FLIGHT_CAPACITY = 100
OVERBOOKING_PENALTY_PER_SEAT = 6000
UNDERBOOKING_PENALTY_PER_SEAT = 3000
AVG_SEAT_PRICE = 4000
CANCELLATION_PROBABILITY = 0.1

class Passenger(BaseModel):
    profession: str
    sex: str
    age_group: str
    region: str

class BookingRequest(BaseModel):
    booking_id: int
    volume: int
    price_per_seat: int
    anchor_type: str
    anchor_value: str
    passengers: List[Passenger]

    @computed_field
    @property
    def demographic_splits(self) -> Dict[str, Counter]:
        """Calculates the count of each attribute within the passenger list."""
        return {
            "Profession": Counter(p.profession for p in self.passengers),
            "Sex": Counter(p.sex for p in self.passengers),
            "Age Group": Counter(p.age_group for p in self.passengers),
            "Region": Counter(p.region for p in self.passengers),
        }

class Player(BaseModel):
    player_id: str
    name: str
    accepted_bookings: List[BookingRequest] = Field(default_factory=list)
    final_revenue: int = 0
    overbooking_penalty: int = 0
    underbooking_penalty: int = 0
    total_score: int = 0
    choice_history: Dict[int, str] = Field(default_factory=dict)
    show_up_history: Dict[int, int] = Field(default_factory=dict)

class GameRoom(BaseModel):
    """The main state container for a single game instance."""
    room_id: str
    host_id: str  # NEW: The player_id of the user who created the room
    players: Dict[str, Player] = Field(default_factory=dict)
    bookings: List[BookingRequest] = Field(default_factory=list)
    current_round: int = 0
    game_status: str = "WAITING"

    def add_player(self, player_id: str, name: str):
        if player_id not in self.players:
            self.players[player_id] = Player(player_id=player_id, name=name)

    def get_current_booking(self) -> BookingRequest | None:
        if 0 <= self.current_round < len(self.bookings):
            return self.bookings[self.current_round]
        return None

    def advance_to_next_round(self):
        """Logs rejections for undecided players, then moves to the next round."""
        current_booking = self.get_current_booking()
        if current_booking:
            for player in self.players.values():
                # If the player is not the host and hasn't made a choice for this round
                if player.player_id != self.host_id and current_booking.booking_id not in player.choice_history:
                    player.choice_history[current_booking.booking_id] = "Rejected"

        if self.current_round < len(self.bookings):
            self.current_round += 1
            if self.current_round == len(self.bookings):
                self.end_game()

    def player_accept_booking(self, player_id: str):
        """Records a player's decision to accept the current booking."""
        player = self.players.get(player_id)
        current_booking = self.get_current_booking()
        if player and current_booking:
            player.accepted_bookings.append(current_booking)
            player.choice_history[current_booking.booking_id] = "Accepted"

    def start_game(self):
        self.game_status = "IN_PROGRESS"
        self.current_round = 0

    def end_game(self):
        self.game_status = "FINISHED"
        for player in self.players.values():
            self.calculate_final_score(player)

    def calculate_final_score(self, player: Player):
        """Calculates the total revenue and penalties for a single player."""
        total_showed_up = 0
        total_revenue = 0
        
        for booking in player.accepted_bookings:
            passengers_showed_up = 0
            for passenger in booking.passengers:
                if random.random() > CANCELLATION_PROBABILITY:
                    passengers_showed_up += 1
            
            # Store the result for this booking
            player.show_up_history[booking.booking_id] = passengers_showed_up
            
            total_showed_up += passengers_showed_up
            total_revenue += passengers_showed_up * booking.price_per_seat
        
        player.final_revenue = total_revenue

        if total_showed_up > FLIGHT_CAPACITY:
            overbooked_seats = total_showed_up - FLIGHT_CAPACITY
            player.overbooking_penalty = overbooked_seats * OVERBOOKING_PENALTY_PER_SEAT
        elif total_showed_up < FLIGHT_CAPACITY:
            underbooked_seats = FLIGHT_CAPACITY - total_showed_up
            player.underbooking_penalty = underbooked_seats * UNDERBOOKING_PENALTY_PER_SEAT

        player.total_score = player.final_revenue - player.overbooking_penalty - player.underbooking_penalty
