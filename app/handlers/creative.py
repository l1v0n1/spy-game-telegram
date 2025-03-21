from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, MessageHandler, Filters, CallbackQueryHandler
import logging
import datetime
from sqlalchemy import and_

from app.models.database import get_session, Game, GamePlayer, GameRound, CreativeSubmission, User
from app.config.config import GAME_STATES, DEFAULT_CREATIVE_TIME
from app.utils.game_logic import generate_task

logger = logging.getLogger(__name__)

# Dictionary to store temporary submission data
pending_submissions = {}

def start_creative_phase(context: CallbackContext, chat_id: int, game_id: int, round_id: int) -> None:
    """
    Start the creative phase of the game.
    
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
        game.state = GAME_STATES['CREATIVE']
        game_round.state = GAME_STATES['CREATIVE']
        session.commit()
        
        # Send message to group chat
        context.bot.send_message(
            chat_id=chat_id,
            text=(
                "🎨 Творческий этап начался!\n\n"
                "Все игроки получают задания в личных сообщениях. "
                f"У вас есть {DEFAULT_CREATIVE_TIME // 60} минут на выполнение задания.\n\n"
                "Внимательно следуйте инструкциям и будьте креативны!"
            )
        )
        
        # Get all active players
        players = session.query(GamePlayer).filter(
            and_(
                GamePlayer.game_id == game_id,
                GamePlayer.is_active == True
            )
        ).all()
        
        # Send tasks to each player
        for player in players:
            user = session.query(User).filter(User.id == player.user_id).first()
            if not user:
                continue
            
            # Generate task
            task_type, task_text = generate_task()
            
            # Create submission record
            submission = CreativeSubmission(
                round_id=round_id,
                player_id=player.id,
                task=task_text,
                submission_type=task_type,
                content=None  # Will be filled when player submits
            )
            session.add(submission)
            session.commit()
            
            # Store pending submission
            if user.user_id not in pending_submissions:
                pending_submissions[user.user_id] = {}
            
            pending_submissions[user.user_id] = {
                "submission_id": submission.id,
                "task_type": task_type,
                "task_text": task_text
            }
            
            # Send task to player
            message_text = f"🎯 Ваше задание для раунда {game_round.round_number}:\n\n*{task_text}*\n\n"
            
            if task_type == 'DRAWING':
                message_text += (
                    "Пожалуйста, нарисуйте и отправьте изображение в ответ на это сообщение.\n"
                    "Вы можете использовать любой графический редактор или нарисовать от руки и сфотографировать."
                )
            else:  # TEXT
                message_text += "Пожалуйста, напишите и отправьте ваш ответ в ответ на это сообщение."
            
            try:
                context.bot.send_message(
                    chat_id=user.user_id,
                    text=message_text,
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Error sending task to user {user.user_id}: {e}")
        
        # Schedule transition to discussion phase
        context.job_queue.run_once(
            transition_to_discussion_phase,
            DEFAULT_CREATIVE_TIME,
            context={"chat_id": chat_id, "game_id": game_id, "round_id": round_id}
        )
        
    except Exception as e:
        logger.error(f"Error starting creative phase: {e}")
    finally:
        session.close()

def handle_text_submission(update: Update, context: CallbackContext) -> None:
    """
    Handle text submission from player.
    """
    # Check if this is a valid message update
    if not update.message or not hasattr(update.message, 'text'):
        return
        
    user_id = update.effective_user.id
    text = update.message.text
    
    # Only process text submissions in private chats
    if update.effective_chat.type != 'private':
        return
    
    # Check if this user has a pending submission
    if user_id not in pending_submissions:
        update.message.reply_text("У вас нет активного задания или время вышло.")
        return
    
    # Check if the submission is a text task
    if pending_submissions[user_id]["task_type"] != "TEXT":
        update.message.reply_text(
            "Это задание требует изображение. Пожалуйста, отправьте фото или рисунок."
        )
        return
    
    # Process text submission
    submission_id = pending_submissions[user_id]["submission_id"]
    
    session = get_session()
    try:
        submission = session.query(CreativeSubmission).filter(
            CreativeSubmission.id == submission_id
        ).first()
        
        if not submission:
            update.message.reply_text("Произошла ошибка. Попробуйте еще раз.")
            return
        
        # Update submission
        submission.content = text
        session.commit()
        
        # Remove from pending submissions
        del pending_submissions[user_id]
        
        update.message.reply_text(
            "✅ Ваш ответ принят! Ожидайте начала обсуждения."
        )
        
    except Exception as e:
        logger.error(f"Error processing text submission: {e}")
        update.message.reply_text("Произошла ошибка при обработке вашего ответа. Попробуйте еще раз.")
    finally:
        session.close()

def handle_photo_submission(update: Update, context: CallbackContext) -> None:
    """
    Handle photo submission from player.
    """
    # Check if this is a valid photo update
    if not update.message or not update.message.photo:
        return
        
    user_id = update.effective_user.id
    photo = update.message.photo[-1]  # Get the largest photo
    
    # Only process photo submissions in private chats
    if update.effective_chat.type != 'private':
        return
    
    # Check if this user has a pending submission
    if user_id not in pending_submissions:
        update.message.reply_text("У вас нет активного задания или время вышло.")
        return
    
    # Check if the submission is a drawing task
    if pending_submissions[user_id]["task_type"] != "DRAWING":
        update.message.reply_text(
            "Это задание требует текстовый ответ. Пожалуйста, отправьте сообщение."
        )
        return
    
    # Process photo submission
    submission_id = pending_submissions[user_id]["submission_id"]
    
    session = get_session()
    try:
        submission = session.query(CreativeSubmission).filter(
            CreativeSubmission.id == submission_id
        ).first()
        
        if not submission:
            update.message.reply_text("Произошла ошибка. Попробуйте еще раз.")
            return
        
        # Update submission with file_id
        submission.content = photo.file_id
        session.commit()
        
        # Remove from pending submissions
        del pending_submissions[user_id]
        
        update.message.reply_text(
            "✅ Ваш рисунок принят! Ожидайте начала обсуждения."
        )
        
    except Exception as e:
        logger.error(f"Error processing photo submission: {e}")
        update.message.reply_text("Произошла ошибка при обработке вашего рисунка. Попробуйте еще раз.")
    finally:
        session.close()

def remind_players(context: CallbackContext) -> None:
    """
    Send reminders to players who haven't submitted yet.
    """
    if not pending_submissions:
        return
    
    for user_id, data in pending_submissions.items():
        try:
            context.bot.send_message(
                chat_id=user_id,
                text=(
                    "⏰ Напоминание: у вас осталось мало времени для выполнения задания! "
                    "Пожалуйста, отправьте ваш ответ как можно скорее."
                )
            )
        except Exception as e:
            logger.error(f"Error sending reminder to user {user_id}: {e}")

def transition_to_discussion_phase(context: CallbackContext) -> None:
    """
    Transition from creative to discussion phase.
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
        game.state = GAME_STATES['DISCUSSION']
        game_round.state = GAME_STATES['DISCUSSION']
        session.commit()
        
        # Get all submissions for this round
        submissions = session.query(CreativeSubmission).filter(
            CreativeSubmission.round_id == round_id
        ).all()
        
        # Send message to group chat
        context.bot.send_message(
            chat_id=chat_id,
            text=(
                "🔎 Обсуждение начинается!\n\n"
                "Ниже будут показаны анонимные результаты творческого этапа. "
                "Внимательно анализируйте их, чтобы выявить шпионов!"
            )
        )
        
        # Display all submissions anonymously
        for i, submission in enumerate(submissions, 1):
            if not submission.content:
                continue  # Skip empty submissions
                
            player = session.query(GamePlayer).filter(GamePlayer.id == submission.player_id).first()
            if not player:
                continue
                
            # Send anonymized submission
            if submission.submission_type == 'DRAWING':
                caption = f"🖼 Рисунок #A{i}: *{submission.task}*"
                context.bot.send_photo(
                    chat_id=chat_id,
                    photo=submission.content,
                    caption=caption,
                    parse_mode='Markdown'
                )
            else:  # TEXT
                context.bot.send_message(
                    chat_id=chat_id,
                    text=(
                        f"📝 Описание #A{i}:\n"
                        f"Задание: *{submission.task}*\n\n"
                        f"Ответ: \"{submission.content}\""
                    ),
                    parse_mode='Markdown'
                )
        
        # Send final discussion message
        context.bot.send_message(
            chat_id=chat_id,
            text=(
                "Обсудите представленные материалы и попытайтесь определить, кто может быть шпионом.\n"
                "Голосование начнется через несколько минут."
            )
        )
        
        # Schedule transition to voting phase
        # This will be implemented in discussion.py handler
        # For now, we'll just announce that voting will start soon
        context.job_queue.run_once(
            lambda c: c.bot.send_message(
                chat_id=chat_id,
                text="🗳 Голосование скоро начнется! Приготовьтесь сделать свой выбор."
            ),
            240,  # Discussion time in seconds
            context=None
        )
        
    except Exception as e:
        logger.error(f"Error transitioning to discussion phase: {e}")
    finally:
        session.close()

def register_handlers(dispatcher):
    """Register all handlers for the creative phase."""
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_text_submission))
    dispatcher.add_handler(MessageHandler(Filters.photo, handle_photo_submission)) 