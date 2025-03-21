import os
import logging
from telegram.ext import Updater

from app.config.config import TOKEN
from app.models.database import init_db
from app.handlers.registration import register_handlers as register_registration_handlers
from app.handlers.creative import register_handlers as register_creative_handlers
from app.handlers.voting import register_handlers as register_voting_handlers
from app.handlers.stats import register_handlers as register_stats_handlers

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def main():
    """Main function to start the bot."""
    
    # Initialize database
    logger.info("Initializing database...")
    init_db()
    
    # Create updater and pass it bot token
    logger.info("Starting bot...")
    updater = Updater(TOKEN)
    
    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher
    
    # Register all handlers
    register_registration_handlers(dispatcher)
    register_creative_handlers(dispatcher)
    register_voting_handlers(dispatcher)
    register_stats_handlers(dispatcher)
    
    # Start the Bot
    updater.start_polling()
    
    # Run the bot until you press Ctrl-C or the process is stopped
    updater.idle()
    
    logger.info("Bot stopped")

if __name__ == '__main__':
    main() 