from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, CallbackQueryHandler
import logging
import datetime
from sqlalchemy import and_
from typing import Dict

from app.models.database import get_session, Game, GamePlayer, GameRound, Vote, User
from app.config.config import GAME_STATES, DEFAULT_VOTING_TIME
from app.utils.game_logic import calculate_votes, calculate_scores, check_game_end

logger = logging.getLogger(__name__)

# Dictionary to store votes for each round
active_votes = {}  # Format: {round_id: {user_id: target_player_id}}

def start_voting_phase(context: CallbackContext, chat_id: int, game_id: int, round_id: int) -> None:
    """
    Start the voting phase of the game.
    
    Args:
        context: Callback context
        chat_id: Chat ID of the game
        game_id: Game ID
        round_id: Current round ID
    """
    session = get_session()
    try:
        # Get game and round
        game = session.query(Game).filter(Game.id == game_id).first()
        game_round = session.query(GameRound).filter(GameRound.id == round_id).first()
        
        if not game or not game_round:
            logger.error(f"Game or round not found: game_id={game_id}, round_id={round_id}")
            return
        
        # Update game and round state
        game.state = GAME_STATES['VOTING']
        game_round.state = GAME_STATES['VOTING']
        session.commit()
        
        # Send message to group chat
        context.bot.send_message(
            chat_id=chat_id,
            text=(
                "🗳 Голосование началось!\n\n"
                f"У вас есть {DEFAULT_VOTING_TIME // 60} минут, чтобы проголосовать за игрока, "
                "которого вы считаете шпионом.\n\n"
                "Каждый игрок получит кнопки для голосования в личном сообщении."
            )
        )
        
        # Get all active players
        players = session.query(GamePlayer).filter(
            and_(
                GamePlayer.game_id == game_id,
                GamePlayer.is_active == True
            )
        ).all()
        
        # Create voting keyboard with all players
        keyboard = []
        row = []
        
        # Initialize active votes for this round
        active_votes[round_id] = {}
        
        for i, player in enumerate(players):
            user = session.query(User).filter(User.id == player.user_id).first()
            if not user:
                continue
                
            # Add player to keyboard
            button = InlineKeyboardButton(
                text=user.first_name,
                callback_data=f"vote_{round_id}_{player.id}"
            )
            
            # Create new row every 2 buttons
            if i % 2 == 0 and i > 0:
                keyboard.append(row)
                row = []
                
            row.append(button)
        
        # Add the last row if it's not empty
        if row:
            keyboard.append(row)
            
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Send voting message to each player
        for player in players:
            user = session.query(User).filter(User.id == player.user_id).first()
            if not user:
                continue
                
            try:
                context.bot.send_message(
                    chat_id=user.user_id,
                    text=(
                        "🗳 Время голосования!\n\n"
                        "Выберите игрока, которого вы считаете шпионом:"
                    ),
                    reply_markup=reply_markup
                )
            except Exception as e:
                logger.error(f"Error sending voting keyboard to user {user.user_id}: {e}")
        
        # Schedule end of voting
        context.job_queue.run_once(
            end_voting_phase,
            DEFAULT_VOTING_TIME,
            context={"chat_id": chat_id, "game_id": game_id, "round_id": round_id}
        )
        
    except Exception as e:
        logger.error(f"Error starting voting phase: {e}")
    finally:
        session.close()

def handle_vote(update: Update, context: CallbackContext) -> None:
    """
    Handle vote callback from player.
    """
    # Check if this is a valid callback query
    if not update.callback_query:
        return
        
    query = update.callback_query
    user_id = update.effective_user.id
    
    # Parse callback data
    try:
        _, round_id, target_player_id = query.data.split('_')
        round_id = int(round_id)
        target_player_id = int(target_player_id)
    except (ValueError, IndexError):
        query.answer("Неверный формат данных. Попробуйте еще раз.")
        return
    
    # Check if this round is in voting state
    if round_id not in active_votes:
        query.answer("Голосование для этого раунда уже завершено или еще не началось.")
        return
    
    session = get_session()
    try:
        # Get user
        user = session.query(User).filter(User.user_id == user_id).first()
        if not user:
            query.answer("Пользователь не найден.")
            return
        
        # Get the game round
        game_round = session.query(GameRound).filter(GameRound.id == round_id).first()
        if not game_round:
            query.answer("Раунд не найден.")
            return
        
        # Check if round is in voting state
        if game_round.state != GAME_STATES['VOTING']:
            query.answer("Голосование для этого раунда уже завершено.")
            return
        
        # Get the voter's player record
        voter = session.query(GamePlayer).filter(
            and_(
                GamePlayer.user_id == user.id,
                GamePlayer.game_id == game_round.game_id,
                GamePlayer.is_active == True
            )
        ).first()
        
        if not voter:
            query.answer("Вы не являетесь активным игроком в этой игре.")
            return
        
        # Get the target player
        target = session.query(GamePlayer).filter(
            and_(
                GamePlayer.id == target_player_id,
                GamePlayer.game_id == game_round.game_id,
                GamePlayer.is_active == True
            )
        ).first()
        
        if not target:
            query.answer("Выбранный игрок не найден или не активен.")
            return
        
        # Check if player is voting for themselves
        if voter.id == target.id:
            query.answer("Вы не можете голосовать за себя.")
            return
        
        # Check if player already voted
        existing_vote = session.query(Vote).filter(
            and_(
                Vote.round_id == round_id,
                Vote.voter_id == voter.id
            )
        ).first()
        
        if existing_vote:
            # Update existing vote
            existing_vote.target_id = target.id
            existing_vote.voted_at = datetime.datetime.utcnow()
        else:
            # Create new vote
            vote = Vote(
                round_id=round_id,
                voter_id=voter.id,
                target_id=target.id
            )
            session.add(vote)
        
        # Record vote in memory
        active_votes[round_id][voter.id] = target.id
        
        # Commit changes
        session.commit()
        
        # Get target user name
        target_user = session.query(User).filter(User.id == target.user_id).first()
        target_name = target_user.first_name if target_user else "Unknown"
        
        # Confirm vote
        query.answer(f"Ваш голос против {target_name} учтен!")
        
        # Update message
        query.edit_message_text(
            text=f"🗳 Вы проголосовали против игрока: {target_name}\n\n"
                 "Вы можете изменить свой голос до окончания голосования.",
            reply_markup=query.message.reply_markup
        )
        
    except Exception as e:
        logger.error(f"Error processing vote: {e}")
        query.answer("Произошла ошибка при обработке вашего голоса. Попробуйте еще раз.")
    finally:
        session.close()

def end_voting_phase(context: CallbackContext) -> None:
    """
    End the voting phase and calculate results.
    """
    job_data = context.job.context
    chat_id = job_data["chat_id"]
    game_id = job_data["game_id"]
    round_id = job_data["round_id"]
    
    session = get_session()
    try:
        # Get game and round
        game = session.query(Game).filter(Game.id == game_id).first()
        game_round = session.query(GameRound).filter(GameRound.id == round_id).first()
        
        if not game or not game_round:
            logger.error(f"Game or round not found: game_id={game_id}, round_id={round_id}")
            return
        
        # Update game and round state
        game.state = GAME_STATES['RESULTS']
        game_round.state = GAME_STATES['RESULTS']
        game_round.finished_at = datetime.datetime.utcnow()
        session.commit()
        
        # Get all votes for this round
        votes = session.query(Vote).filter(Vote.round_id == round_id).all()
        
        # Count votes for each player
        vote_counts: Dict[int, int] = {}
        for vote in votes:
            if vote.target_id not in vote_counts:
                vote_counts[vote.target_id] = 0
            vote_counts[vote.target_id] += 1
        
        # Find the player with the most votes
        eliminated_player_id = calculate_votes(vote_counts)
        
        if not eliminated_player_id:
            context.bot.send_message(
                chat_id=chat_id,
                text="🤔 Странно... Никто не проголосовал. Раунд продолжается без устранения."
            )
            # Start new round
            start_new_round(context, chat_id, game_id)
            return
        
        # Get the eliminated player
        eliminated_player = session.query(GamePlayer).filter(GamePlayer.id == eliminated_player_id).first()
        if not eliminated_player:
            logger.error(f"Eliminated player not found: player_id={eliminated_player_id}")
            return
        
        # Get the eliminated player's user
        eliminated_user = session.query(User).filter(User.id == eliminated_player.user_id).first()
        if not eliminated_user:
            logger.error(f"Eliminated user not found: user_id={eliminated_player.user_id}")
            return
        
        # Mark player as eliminated
        eliminated_player.is_active = False
        session.commit()
        
        # Get all active players and their roles
        active_players = session.query(GamePlayer).filter(
            and_(
                GamePlayer.game_id == game_id,
                GamePlayer.is_active == True
            )
        ).all()
        
        # Create role mapping for score calculation
        player_roles = {player.id: player.role for player in active_players}
        
        # Calculate scores
        scores = calculate_scores(eliminated_player.role, player_roles)
        
        # Update player scores
        for player_id, score in scores.items():
            player = session.query(GamePlayer).filter(GamePlayer.id == player_id).first()
            if player:
                player.score += score
        
        session.commit()
        
        # Announce elimination
        context.bot.send_message(
            chat_id=chat_id,
            text=(
                f"🚨 Агент {eliminated_user.first_name} был устранен!\n\n"
                f"Роль: *{eliminated_player.role}*\n"
                f"Количество голосов: {vote_counts.get(eliminated_player_id, 0)}"
            ),
            parse_mode='Markdown'
        )
        
        # Check if game should end
        game_over, winner_team = check_game_end(player_roles)
        
        if game_over:
            # End the game
            game.finished_at = datetime.datetime.utcnow()
            session.commit()
            
            # Get all players for final scoring
            all_players = session.query(GamePlayer).filter(GamePlayer.game_id == game_id).all()
            
            # Update user stats
            for player in all_players:
                user = session.query(User).filter(User.id == player.user_id).first()
                if user:
                    user.games_played += 1
                    if (winner_team == "loyal" and player.role in ["Лояльный агент", "Двойной агент"]) or \
                       (winner_team == "spy" and player.role == "Шпион"):
                        user.wins += 1
            
            session.commit()
            
            # Announce winner
            if winner_team == "loyal":
                context.bot.send_message(
                    chat_id=chat_id,
                    text=(
                        "🎉 Игра окончена! Победа Лояльных Агентов!\n\n"
                        "Все шпионы были успешно разоблачены. Миссия выполнена!"
                    )
                )
            else:  # spy
                context.bot.send_message(
                    chat_id=chat_id,
                    text=(
                        "🎭 Игра окончена! Победа Шпионов!\n\n"
                        "Шпионы успешно внедрились и получили численное преимущество. Миссия провалена!"
                    )
                )
            
            # Show final scores
            player_scores = []
            for player in all_players:
                user = session.query(User).filter(User.id == player.user_id).first()
                if user:
                    player_scores.append((user.first_name, player.score, player.role))
            
            # Sort by score (highest first)
            player_scores.sort(key=lambda x: x[1], reverse=True)
            
            # Format scores message
            scores_message = "📊 Финальные результаты:\n\n"
            for name, score, role in player_scores:
                scores_message += f"{name}: {score} очков - *{role}*\n"
            
            context.bot.send_message(
                chat_id=chat_id,
                text=scores_message,
                parse_mode='Markdown'
            )
            
            # Invite to play again
            context.bot.send_message(
                chat_id=chat_id,
                text=(
                    "Спасибо за игру! Для начала новой игры, "
                    "используйте команду /join и затем /startgame."
                )
            )
            
        else:
            # Start a new round
            start_new_round(context, chat_id, game_id)
        
    except Exception as e:
        logger.error(f"Error ending voting phase: {e}")
    finally:
        # Clear active votes for this round
        if round_id in active_votes:
            del active_votes[round_id]
        
        session.close()

def start_new_round(context: CallbackContext, chat_id: int, game_id: int) -> None:
    """
    Start a new round of the game.
    
    Args:
        context: Callback context
        chat_id: Chat ID of the game
        game_id: Game ID
    """
    session = get_session()
    try:
        # Get game
        game = session.query(Game).filter(Game.id == game_id).first()
        if not game:
            logger.error(f"Game not found: game_id={game_id}")
            return
        
        # Increment round
        game.current_round += 1
        session.commit()
        
        # Announce new round
        context.bot.send_message(
            chat_id=chat_id,
            text=(
                f"🔄 Начинается раунд {game.current_round}!\n\n"
                "Подготовьтесь к новому испытанию. "
                "Творческий этап начнется через минуту."
            )
        )
        
        # Create new round
        game_round = GameRound(
            game_id=game.id,
            round_number=game.current_round,
            state=GAME_STATES['PREPARATION']
        )
        session.add(game_round)
        
        # Update game state
        game.state = GAME_STATES['PREPARATION']
        session.commit()
        
        # Schedule transition to creative phase
        context.job_queue.run_once(
            lambda c: c.bot.send_message(
                chat_id=chat_id,
                text="🎨 Творческий этап начинается! Все игроки получат новые задания."
            ),
            60,  # Preparation time in seconds
            context=None
        )
        
        # This would call the creative phase handler in a real implementation
        # For now, just a placeholder
        # start_creative_phase(context, chat_id, game_id, game_round.id)
        
    except Exception as e:
        logger.error(f"Error starting new round: {e}")
    finally:
        session.close()

def register_handlers(dispatcher):
    """Register all handlers for the voting phase."""
    dispatcher.add_handler(CallbackQueryHandler(handle_vote, pattern="^vote_")) 