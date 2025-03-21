from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, CommandHandler, CallbackQueryHandler, Filters, MessageHandler
import logging
import datetime

from app.models.database import get_session, User, Game, GamePlayer, GameRound
from app.config.config import GAME_STATES, MIN_PLAYERS, MAX_PLAYERS, ROLES
from app.utils.game_logic import assign_roles

logger = logging.getLogger(__name__)

# Dictionary to store temporary game registration data
active_registrations = {}

def start_command(update: Update, context: CallbackContext) -> None:
    """
    Start the bot and display welcome message.
    """
    message = (
        "👋 Добро пожаловать в игру Spy Sketch!\n\n"
        "Это групповая игра-дедукция с творческими заданиями для 6-20 игроков.\n\n"
        "Используйте /join чтобы присоединиться к регистрации.\n"
        "Когда все будут готовы, используйте /startgame чтобы начать игру.\n"
        "Для получения справки используйте /help."
    )
    update.message.reply_text(message)

def help_command(update: Update, context: CallbackContext) -> None:
    """
    Display help information.
    """
    help_text = (
        "📋 Список команд:\n\n"
        "/start - Начать работу с ботом\n"
        "/join - Присоединиться к регистрации\n"
        "/startgame - Начать игру после регистрации\n"
        "/endgame - Завершить текущую игру\n"
        "/rules - Показать правила игры\n"
        "/stats - Показать вашу статистику\n"
        "/leaderboard - Показать таблицу лидеров\n\n"
        "📝 Как играть:\n"
        "1. Все желающие игроки регистрируются командой /join\n"
        "2. После регистрации всех игроков, начните игру командой /startgame\n"
        "3. Каждый игрок получит секретную роль в личном сообщении\n"
        "4. Следуйте инструкциям от бота в течение игровых этапов\n"
    )
    update.message.reply_text(help_text)

def rules_command(update: Update, context: CallbackContext) -> None:
    """
    Display game rules.
    """
    rules_text = (
        "📌 Правила игры Spy Sketch:\n\n"
        "1. Игра предназначена для 6-20 игроков.\n"
        "2. Каждый игрок получает одну из ролей:\n"
        "   - Лояльный агент: ваша цель - выявить шпионов\n"
        "   - Шпион: ваша цель - остаться незамеченным и саботировать игру\n"
        "   - Двойной агент: вы работаете на обе стороны, но побеждаете с лояльными\n\n"
        "3. Игра состоит из нескольких раундов, каждый из которых имеет этапы:\n"
        "   - Подготовка: ознакомление с ролями и заданиями\n"
        "   - Творческий этап: выполнение заданий (рисование или текст)\n"
        "   - Обсуждение: анализ результатов и поиск шпионов\n"
        "   - Голосование: выбор подозреваемого в шпионаже\n\n"
        "4. После голосования 'устраняется' один игрок, и игра продолжается.\n"
        "5. Игра заканчивается, когда все шпионы устранены (победа лояльных) или когда шпионов становится больше или столько же, сколько лояльных (победа шпионов).\n"
    )
    update.message.reply_text(rules_text)

def join_command(update: Update, context: CallbackContext) -> None:
    """
    Register a player for the game.
    """
    chat_id = update.effective_chat.id
    user = update.effective_user
    
    # Check if we're in a group chat
    if update.effective_chat.type not in ['group', 'supergroup']:
        update.message.reply_text("Эта игра доступна только в групповых чатах!")
        return
    
    # Initialize registration for this chat if it doesn't exist
    if chat_id not in active_registrations:
        active_registrations[chat_id] = []
    
    # Check if user already registered
    if any(reg_user.id == user.id for reg_user in active_registrations[chat_id]):
        update.message.reply_text(f"{user.first_name}, вы уже зарегистрированы для игры!")
        return
    
    # Check if there's a game in progress
    session = get_session()
    try:
        existing_game = session.query(Game).filter(
            Game.chat_id == chat_id,
            Game.finished_at.is_(None)
        ).first()
        
        if existing_game and existing_game.state != GAME_STATES['IDLE']:
            update.message.reply_text("В этом чате уже идет игра! Дождитесь ее завершения.")
            return
        
        # Add user to registration
        active_registrations[chat_id].append(user)
        
        # Get current player count
        player_count = len(active_registrations[chat_id])
        
        update.message.reply_text(
            f"{user.first_name} присоединился к игре! "
            f"Зарегистрировано игроков: {player_count}/{MIN_PLAYERS} мин. | {MAX_PLAYERS} макс.\n"
            f"Когда все будут готовы, введите /startgame"
        )
    finally:
        session.close()

def startgame_command(update: Update, context: CallbackContext) -> None:
    """
    Start the game after registration.
    """
    chat_id = update.effective_chat.id
    
    # Check if we're in a group chat
    if update.effective_chat.type not in ['group', 'supergroup']:
        update.message.reply_text("Эта игра доступна только в групповых чатах!")
        return
    
    # Check if there's an active registration
    if chat_id not in active_registrations or not active_registrations[chat_id]:
        update.message.reply_text("Сначала игроки должны зарегистрироваться с помощью команды /join!")
        return
    
    # Check if we have enough players
    player_count = len(active_registrations[chat_id])
    if player_count < MIN_PLAYERS:
        update.message.reply_text(
            f"Недостаточно игроков! Требуется минимум {MIN_PLAYERS}, "
            f"сейчас зарегистрировано {player_count}."
        )
        return
    
    # Check if we have too many players
    if player_count > MAX_PLAYERS:
        update.message.reply_text(
            f"Слишком много игроков! Максимум {MAX_PLAYERS}, "
            f"сейчас зарегистрировано {player_count}."
        )
        return
    
    session = get_session()
    try:
        # Check if there's a game in progress
        existing_game = session.query(Game).filter(
            Game.chat_id == chat_id,
            Game.finished_at.is_(None)
        ).first()
        
        if existing_game and existing_game.state != GAME_STATES['IDLE']:
            update.message.reply_text("В этом чате уже идет игра! Дождитесь ее завершения.")
            return
        
        # Create new game or reuse existing one
        if not existing_game:
            game = Game(chat_id=chat_id, state=GAME_STATES['REGISTRATION'])
            session.add(game)
            session.commit()
        else:
            game = existing_game
            game.state = GAME_STATES['REGISTRATION']
            game.started_at = datetime.datetime.utcnow()
            game.finished_at = None
        
        # Generate roles
        roles = assign_roles(player_count)
        
        # Register all players and send them their roles
        update.message.reply_text("🎮 Игра начинается! Каждый игрок получит свою роль в личном сообщении.")
        
        for i, telegram_user in enumerate(active_registrations[chat_id]):
            # Get or create user in database
            user = session.query(User).filter(User.user_id == telegram_user.id).first()
            if not user:
                user = User(
                    user_id=telegram_user.id,
                    username=telegram_user.username,
                    first_name=telegram_user.first_name,
                    last_name=telegram_user.last_name
                )
                session.add(user)
                session.commit()
            
            # Create game player
            game_player = GamePlayer(
                game_id=game.id,
                user_id=user.id,
                role=roles[i]
            )
            session.add(game_player)
            
            # Send role information to player
            role_info = get_role_description(roles[i])
            try:
                context.bot.send_message(
                    chat_id=telegram_user.id,
                    text=f"🔒 Ваша роль в игре Spy Sketch: *{roles[i]}*\n\n{role_info}",
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Error sending role to user {telegram_user.id}: {e}")
                update.message.reply_text(
                    f"⚠️ Не удалось отправить роль игроку {telegram_user.first_name}. "
                    f"Убедитесь, что бот не заблокирован и вы начали с ним диалог."
                )
        
        # Create first round
        game_round = GameRound(
            game_id=game.id,
            round_number=1,
            state=GAME_STATES['PREPARATION']
        )
        session.add(game_round)
        
        # Update game state
        game.state = GAME_STATES['PREPARATION']
        session.commit()
        
        # Clear active registrations for this chat
        active_registrations[chat_id] = []
        
        # Move to preparation stage
        update.message.reply_text(
            "🔍 Фаза подготовки началась!\n\n"
            "Все игроки получили свои роли. У вас есть время, чтобы ознакомиться с ними.\n"
            "Скоро начнется творческий этап игры!"
        )
        
        # Schedule transition to creative phase
        context.job_queue.run_once(
            transition_to_creative_phase,
            60,  # Preparation time in seconds
            context={"chat_id": chat_id, "game_id": game.id, "round_id": game_round.id}
        )
        
    except Exception as e:
        logger.error(f"Error starting game: {e}")
        update.message.reply_text("Произошла ошибка при запуске игры. Пожалуйста, попробуйте еще раз.")
        session.rollback()
    finally:
        session.close()

def get_role_description(role: str) -> str:
    """
    Get detailed description for a role.
    """
    if role == ROLES['LOYAL']:
        return (
            "Вы - лояльный агент! Ваша задача - выявить шпионов среди игроков.\n\n"
            "• Внимательно анализируйте творческие задания других игроков\n"
            "• Ищите странные или неуместные ответы, которые могут выдать шпиона\n"
            "• В своих заданиях старайтесь дать подсказки другим лояльным агентам\n"
            "• Будьте осторожны - шпионы попытаются вас запутать"
        )
    elif role == ROLES['SPY']:
        return (
            "Вы - шпион! Ваша задача - оставаться незамеченным и саботировать игру.\n\n"
            "• Притворяйтесь лояльным агентом\n"
            "• В творческих заданиях старайтесь быть неоднозначным, но не слишком явно\n"
            "• Пытайтесь обвинить лояльных агентов, чтобы отвести подозрения от себя\n"
            "• Координируйтесь с другими шпионами, если вы заметите их"
        )
    elif role == ROLES['DOUBLE']:
        return (
            "Вы - двойной агент! Ваша задача - помочь лояльным агентам, но при этом не раскрыть себя шпионам.\n\n"
            "• Вы знаете, кто шпионы, но должны быть очень осторожны\n"
            "• В творческих заданиях оставляйте тонкие намеки лояльным агентам\n"
            "• Не раскрывайте себя слишком рано, иначе шпионы вычислят вас\n"
            "• Вы побеждаете вместе с лояльными агентами"
        )
    else:
        return "Неизвестная роль. Пожалуйста, сообщите об этой ошибке администратору."

def transition_to_creative_phase(context: CallbackContext) -> None:
    """
    Transition from preparation to creative phase.
    """
    job_data = context.job.context
    chat_id = job_data["chat_id"]
    game_id = job_data["game_id"]
    round_id = job_data["round_id"]
    
    # This function will be implemented in creative.py handler
    # It will update the game state and start the creative phase
    # For now, we'll just announce the transition
    context.bot.send_message(
        chat_id=chat_id,
        text="🎨 Творческий этап начинается!\n\nВсе игроки получат задания в личных сообщениях."
    )
    
    # Here we would call a function from the creative phase handler
    # For example: start_creative_phase(context, chat_id, game_id, round_id)

def welcome_bot(update: Update, context: CallbackContext) -> None:
    """
    Welcome message when bot is added to a group chat.
    """
    # Check if this is a new chat member event and it's about the bot
    if not update.message or not update.message.new_chat_members:
        return
    
    bot_user = context.bot.get_me()
    for member in update.message.new_chat_members:
        if member.id == bot_user.id:
            # Bot was added to a group chat, send welcome message
            update.message.reply_text(
                "👋 Привет всем! Я бот для игры Spy Sketch!\n\n"
                "Это групповая игра-дедукция с творческими заданиями.\n\n"
                "Используйте следующие команды:\n"
                "/start - Начать работу с ботом\n"
                "/join - Присоединиться к регистрации\n"
                "/startgame - Начать игру после регистрации\n"
                "/rules - Показать правила игры\n"
                "/help - Показать все доступные команды"
            )
            break

def register_handlers(dispatcher):
    """Register all handlers for the registration phase."""
    dispatcher.add_handler(CommandHandler("start", start_command))
    dispatcher.add_handler(CommandHandler("help", help_command))
    dispatcher.add_handler(CommandHandler("rules", rules_command))
    dispatcher.add_handler(CommandHandler("join", join_command))
    dispatcher.add_handler(CommandHandler("startgame", startgame_command))
    dispatcher.add_handler(MessageHandler(Filters.status_update.new_chat_members, welcome_bot)) 