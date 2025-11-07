import random
from typing import List
from game_models import BookingRequest, Passenger

# --- Predefined Demographic Data (Indian Context) ---
PROFESSIONS = ["Engineer", "Doctor", "Artist", "Farmer", "Teacher", "Lawyer", "Student", "Politician"]
SEXES = ["Male", "Female"]
AGE_GROUPS = ["18-25", "26-40", "41-60", "60+"]
INDIAN_STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa", "Gujarat", 
    "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh", 
    "Maharashtra", "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab", 
    "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh", 
    "Uttarakhand", "West Bengal", "Delhi", "Puducherry"
]
TOTAL_BOOKINGS_PER_GAME = 15

def generate_bookings() -> List[BookingRequest]:
    """
    Generates a list of randomized booking requests for a new game.
    """
    bookings = []
    
    for i in range(TOTAL_BOOKINGS_PER_GAME):
        volume = random.randint(5, 15)
        price_per_seat = int(4000 * random.uniform(0.75, 1.5))
        anchor_type = random.choice(['profession', 'sex', 'age_group', 'region'])
        
        # --- NEW LOGIC: Limit region diversity per booking ---
        # Pre-select a small number of states for this specific booking
        max_regions = 3
        selected_regions = random.sample(INDIAN_STATES, k=min(len(INDIAN_STATES), max_regions))

        if anchor_type == 'profession':
            anchor_value = random.choice(PROFESSIONS)
        elif anchor_type == 'sex':
            anchor_value = random.choice(SEXES)
        elif anchor_type == 'age_group':
            anchor_value = random.choice(AGE_GROUPS)
        else: # region
            anchor_value = random.choice(INDIAN_STATES)
            
        passengers = []
        for _ in range(volume):
            passenger_profile = {
                'profession': anchor_value if anchor_type == 'profession' else random.choice(PROFESSIONS),
                'sex': anchor_value if anchor_type == 'sex' else random.choice(SEXES),
                'age_group': anchor_value if anchor_type == 'age_group' else random.choice(AGE_GROUPS),
                # UPDATED: Choose from the small pre-selected list of regions
                'region': anchor_value if anchor_type == 'region' else random.choice(selected_regions),
            }
            passengers.append(Passenger(**passenger_profile))

        bookings.append(BookingRequest(
            booking_id=i,
            volume=volume,
            price_per_seat=price_per_seat,
            anchor_type=anchor_type.replace('_', ' ').title(),
            anchor_value=anchor_value,
            passengers=passengers
        ))
        
    return bookings
