import random
import math
from typing import List, Dict, Tuple
import logging

from app.config.config import SPY_RATIO, DOUBLE_AGENT_ENABLED, DOUBLE_AGENT_PROBABILITY
from app.config.config import DRAWING_TASKS, TEXT_TASKS, ROLES

logger = logging.getLogger(__name__)

def assign_roles(player_count: int) -> List[str]:
    """
    Assign roles to players based on the player count and predefined ratios.
    
    Args:
        player_count: Number of players in the game
        
    Returns:
        A list of roles (LOYAL, SPY, DOUBLE)
    """
    spy_count = max(1, math.floor(player_count * SPY_RATIO))
    
    # Initialize all players as loyal
    roles = [ROLES['LOYAL']] * player_count
    
    # Assign spy roles
    for i in range(spy_count):
        roles[i] = ROLES['SPY']
    
    # Possibly assign a double agent if enabled
    if DOUBLE_AGENT_ENABLED and random.random() < DOUBLE_AGENT_PROBABILITY:
        # Ensure we don't replace a spy with a double agent
        loyal_indices = [i for i, role in enumerate(roles) if role == ROLES['LOYAL']]
        if loyal_indices:
            double_agent_index = random.choice(loyal_indices)
            roles[double_agent_index] = ROLES['DOUBLE']
    
    # Shuffle the roles to randomize assignments
    random.shuffle(roles)
    
    return roles

def generate_task(task_type: str = None) -> Tuple[str, str]:
    """
    Generate a creative task for a player.
    
    Args:
        task_type: Optional type of task ('DRAWING' or 'TEXT'). If None, randomly chosen.
        
    Returns:
        Tuple containing (task_type, task_description)
    """
    if not task_type:
        task_type = random.choice(['DRAWING', 'TEXT'])
    
    if task_type == 'DRAWING':
        task = random.choice(DRAWING_TASKS)
    else:  # TEXT
        task = random.choice(TEXT_TASKS)
    
    return task_type, task

def calculate_votes(votes: Dict[int, int]) -> int:
    """
    Calculate the player with the most votes.
    
    Args:
        votes: Dictionary mapping player_id to vote count
        
    Returns:
        player_id of the most voted player, or None if tie
    """
    if not votes:
        return None
    
    max_votes = max(votes.values())
    most_voted = [player_id for player_id, vote_count in votes.items() if vote_count == max_votes]
    
    # If there's a tie, randomly select one of the most voted players
    if len(most_voted) > 1:
        logger.info(f"Tie between players: {most_voted} with {max_votes} votes each")
        return random.choice(most_voted)
    
    return most_voted[0]

def calculate_scores(eliminated_player_role: str, player_roles: Dict[int, str]) -> Dict[int, int]:
    """
    Calculate scores for players based on the eliminated player's role.
    
    Args:
        eliminated_player_role: Role of the eliminated player
        player_roles: Dictionary mapping player_id to player role
        
    Returns:
        Dictionary mapping player_id to points earned this round
    """
    scores = {player_id: 0 for player_id in player_roles.keys()}
    
    # If spy was eliminated, loyal agents get points
    if eliminated_player_role == ROLES['SPY']:
        for player_id, role in player_roles.items():
            if role == ROLES['LOYAL']:
                scores[player_id] = 2
            elif role == ROLES['DOUBLE']:
                scores[player_id] = 1
    
    # If loyal agent was eliminated, spies get points
    elif eliminated_player_role == ROLES['LOYAL']:
        for player_id, role in player_roles.items():
            if role == ROLES['SPY']:
                scores[player_id] = 1
    
    # If double agent was eliminated, spies get points
    elif eliminated_player_role == ROLES['DOUBLE']:
        for player_id, role in player_roles.items():
            if role == ROLES['SPY']:
                scores[player_id] = 1
    
    return scores

def check_game_end(player_roles: Dict[int, str]) -> Tuple[bool, str]:
    """
    Check if the game should end based on the current roles.
    
    Args:
        player_roles: Dictionary mapping player_id to player role
        
    Returns:
        Tuple of (is_game_over, winner_team)
    """
    active_roles = list(player_roles.values())
    
    # Count active spies and loyal agents
    spy_count = active_roles.count(ROLES['SPY'])
    loyal_count = active_roles.count(ROLES['LOYAL']) + active_roles.count(ROLES['DOUBLE'])
    
    # Game ends if all spies are eliminated
    if spy_count == 0:
        return True, "loyal"
    
    # Game ends if spies have numerical advantage or equal numbers
    if spy_count >= loyal_count:
        return True, "spy"
    
    # Game continues
    return False, None 