from telegram import Update
from telegram.ext import CallbackContext, CommandHandler
import logging
import datetime
from sqlalchemy import desc, func

from app.models.database import get_session, User, GamePlayer, Game
from app.config.config import GAME_STATES

logger = logging.getLogger(__name__)

def stats_command(update: Update, context: CallbackContext) -> None:
    """
    Display user statistics.
    """
    user_id = update.effective_user.id
    
    session = get_session()
    try:
        # Get user
        user = session.query(User).filter(User.user_id == user_id).first()
        
        if not user:
            update.message.reply_text(
                "У вас пока нет статистики. Сыграйте свою первую игру!"
            )
            return
        
        # Calculate win rate
        win_rate = 0
        if user.games_played > 0:
            win_rate = (user.wins / user.games_played) * 100
        
        # Get roles played
        roles_played = session.query(GamePlayer.role, func.count(GamePlayer.role).label('count')) \
            .join(User, User.id == GamePlayer.user_id) \
            .filter(User.user_id == user_id) \
            .group_by(GamePlayer.role) \
            .all()
        
        # Format roles statistics
        roles_stats = ""
        for role, count in roles_played:
            roles_stats += f"• {role}: {count} раз\n"
        
        if not roles_stats:
            roles_stats = "Нет данных"
        
        # Send statistics message
        update.message.reply_text(
            f"📊 Статистика игрока {user.first_name}:\n\n"
            f"Игр сыграно: {user.games_played}\n"
            f"Побед: {user.wins}\n"
            f"Процент побед: {win_rate:.1f}%\n\n"
            f"Роли:\n{roles_stats}"
        )
        
    except Exception as e:
        logger.error(f"Error getting user stats: {e}")
        update.message.reply_text("Произошла ошибка при получении статистики.")
    finally:
        session.close()

def leaderboard_command(update: Update, context: CallbackContext) -> None:
    """
    Display the leaderboard.
    """
    session = get_session()
    try:
        # Get top 10 users by win rate (minimum 3 games)
        top_users = session.query(
            User,
            (User.wins * 100 / User.games_played).label('win_rate')
        ).filter(
            User.games_played >= 3
        ).order_by(
            desc('win_rate'),
            desc(User.wins)
        ).limit(10).all()
        
        if not top_users:
            update.message.reply_text(
                "В таблице лидеров пока никого нет. Сыграйте несколько игр!"
            )
            return
        
        # Format leaderboard message
        leaderboard_text = "🏆 Таблица лидеров (мин. 3 игры):\n\n"
        
        for i, (user, win_rate) in enumerate(top_users, 1):
            leaderboard_text += (
                f"{i}. {user.first_name} - "
                f"{win_rate:.1f}% побед ({user.wins}/{user.games_played} игр)\n"
            )
        
        update.message.reply_text(leaderboard_text)
        
    except Exception as e:
        logger.error(f"Error getting leaderboard: {e}")
        update.message.reply_text("Произошла ошибка при получении таблицы лидеров.")
    finally:
        session.close()

def endgame_command(update: Update, context: CallbackContext) -> None:
    """
    Force end the current game.
    """
    chat_id = update.effective_chat.id
    
    # Check if we're in a group chat
    if update.effective_chat.type not in ['group', 'supergroup']:
        update.message.reply_text("Эта команда доступна только в групповых чатах!")
        return
    
    session = get_session()
    try:
        # Check if there's a game in progress
        game = session.query(Game).filter(
            Game.chat_id == chat_id,
            Game.finished_at.is_(None)
        ).first()
        
        if not game:
            update.message.reply_text("В этом чате нет активной игры.")
            return
        
        # End the game
        game.finished_at = datetime.datetime.utcnow()
        game.state = GAME_STATES['IDLE']
        session.commit()
        
        update.message.reply_text(
            "Игра была принудительно завершена. Для начала новой игры используйте /join."
        )
        
    except Exception as e:
        logger.error(f"Error ending game: {e}")
        update.message.reply_text("Произошла ошибка при завершении игры.")
    finally:
        session.close()

def register_handlers(dispatcher):
    """Register all handlers for stats."""
    dispatcher.add_handler(CommandHandler("stats", stats_command))
    dispatcher.add_handler(CommandHandler("leaderboard", leaderboard_command))
    dispatcher.add_handler(CommandHandler("endgame", endgame_command)) 