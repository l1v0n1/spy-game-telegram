import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Bot Configuration
TOKEN = os.getenv('TELEGRAM_TOKEN')
if not TOKEN:
    raise ValueError("No TELEGRAM_TOKEN found in environment variables")

# Game Settings
MIN_PLAYERS = 3  # Changed from 6 to 3 for easier testing
MAX_PLAYERS = 20
DEFAULT_ROUND_TIME = 180  # seconds
DEFAULT_DISCUSSION_TIME = 240  # seconds
DEFAULT_VOTING_TIME = 60  # seconds
DEFAULT_PREPARATION_TIME = 60  # seconds
DEFAULT_CREATIVE_TIME = 120  # seconds

# Role Distribution
SPY_RATIO = 0.25  # Percentage of players who will be spies
DOUBLE_AGENT_ENABLED = True  # Whether to include double agent role
DOUBLE_AGENT_PROBABILITY = 0.15  # Chance of having a double agent if enabled

# Database
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///spy_sketch.db')

# Game States
GAME_STATES = {
    'IDLE': 0,
    'REGISTRATION': 1,
    'PREPARATION': 2,
    'CREATIVE': 3,
    'DISCUSSION': 4,
    'VOTING': 5,
    'RESULTS': 6
}

# Roles
ROLES = {
    'LOYAL': 'Лояльный агент',
    'SPY': 'Шпион',
    'DOUBLE': 'Двойной агент'
}

# Creative tasks templates
DRAWING_TASKS = [
    "Нарисуй секретный объект, который поможет твоей команде",
    "Нарисуй место, где может быть спрятан важный документ",
    "Нарисуй замаскированное оружие шпиона",
    "Изобрази устройство для подслушивания",
    "Нарисуй шифр, который поможет твоей команде",
    "Нарисуй карту секретного объекта"
]

TEXT_TASKS = [
    "Опиши предмет, который может указывать на двойного агента",
    "Опиши место встречи агентов",
    "Напиши кодовую фразу для опознавания друг друга",
    "Опиши странное поведение, которое может выдать шпиона",
    "Создай легенду для тайного агента",
    "Придумай название операции, которое что-то значит для твоей команды"
] 