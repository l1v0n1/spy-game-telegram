from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Boolean, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import datetime

from app.config.config import DATABASE_URL

Base = declarative_base()
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, unique=True)
    username = Column(String, nullable=True)
    first_name = Column(String)
    last_name = Column(String, nullable=True)
    games_played = Column(Integer, default=0)
    wins = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    game_players = relationship("GamePlayer", back_populates="user")
    
    def __repr__(self):
        return f"<User(id={self.id}, username={self.username})>"
    
class Game(Base):
    __tablename__ = 'games'
    
    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer)
    state = Column(Integer, default=0)  # Using GAME_STATES from config
    current_round = Column(Integer, default=1)
    max_rounds = Column(Integer, default=3)
    started_at = Column(DateTime, default=datetime.datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    
    players = relationship("GamePlayer", back_populates="game")
    rounds = relationship("GameRound", back_populates="game")
    
    def __repr__(self):
        return f"<Game(id={self.id}, chat_id={self.chat_id}, state={self.state})>"

class GamePlayer(Base):
    __tablename__ = 'game_players'
    
    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey('games.id'))
    user_id = Column(Integer, ForeignKey('users.id'))
    role = Column(String)  # LOYAL, SPY, DOUBLE
    is_active = Column(Boolean, default=True)
    score = Column(Integer, default=0)
    
    game = relationship("Game", back_populates="players")
    user = relationship("User", back_populates="game_players")
    submissions = relationship("CreativeSubmission", back_populates="player")
    votes = relationship("Vote", foreign_keys="[Vote.voter_id]", back_populates="voter")
    votes_received = relationship("Vote", foreign_keys="[Vote.target_id]", back_populates="target")
    
    def __repr__(self):
        return f"<GamePlayer(id={self.id}, game_id={self.game_id}, role={self.role})>"

class GameRound(Base):
    __tablename__ = 'game_rounds'
    
    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey('games.id'))
    round_number = Column(Integer)
    state = Column(Integer)
    started_at = Column(DateTime, default=datetime.datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    
    game = relationship("Game", back_populates="rounds")
    submissions = relationship("CreativeSubmission", back_populates="round")
    votes = relationship("Vote", back_populates="round")
    
    def __repr__(self):
        return f"<GameRound(id={self.id}, game_id={self.game_id}, round_number={self.round_number})>"

class CreativeSubmission(Base):
    __tablename__ = 'creative_submissions'
    
    id = Column(Integer, primary_key=True)
    round_id = Column(Integer, ForeignKey('game_rounds.id'))
    player_id = Column(Integer, ForeignKey('game_players.id'))
    task = Column(Text)
    submission_type = Column(String)  # DRAWING or TEXT
    content = Column(Text)  # File ID for images, or text content
    submitted_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    round = relationship("GameRound", back_populates="submissions")
    player = relationship("GamePlayer", back_populates="submissions")
    
    def __repr__(self):
        return f"<CreativeSubmission(id={self.id}, player_id={self.player_id}, type={self.submission_type})>"

class Vote(Base):
    __tablename__ = 'votes'
    
    id = Column(Integer, primary_key=True)
    round_id = Column(Integer, ForeignKey('game_rounds.id'))
    voter_id = Column(Integer, ForeignKey('game_players.id'))
    target_id = Column(Integer, ForeignKey('game_players.id'))
    voted_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    round = relationship("GameRound", back_populates="votes")
    voter = relationship("GamePlayer", foreign_keys=[voter_id], back_populates="votes")
    target = relationship("GamePlayer", foreign_keys=[target_id], back_populates="votes_received")
    
    def __repr__(self):
        return f"<Vote(id={self.id}, voter_id={self.voter_id}, target_id={self.target_id})>"

def init_db():
    """Initialize the database by creating all tables."""
    Base.metadata.create_all(engine)

def get_session():
    """Get a new database session."""
    return Session() 