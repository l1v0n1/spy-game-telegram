# Spy Game Telegram Bot

This is a Telegram bot that allows users to play a spy game where players try to identify who among them is the spy.

## Features

- Create and manage game rooms
- Join games using unique room codes
- Assign random spy roles to players
- Different locations and roles for each game
- Real-time game status updates

## Installation

1. Clone the repository:
```
git clone https://github.com/l1v0n1/spy-game-telegram.git
cd spy-game-telegram
```

2. Install dependencies:
```
npm install
```

3. Configure your Telegram bot token in a `.env` file:
```
TELEGRAM_BOT_TOKEN=your_bot_token_here
```

4. Start the bot:
```
npm start
```

## How to Play

1. Start a chat with the bot
2. Create a new game room or join an existing one
3. When enough players have joined, start the game
4. Everyone except the spy receives the same location
5. The spy receives a different message
6. Players take turns asking questions to figure out who doesn't know the location
7. Vote to identify the spy

## Tech Stack

- Node.js
- Telegraf.js (Telegram Bot API framework)
- JavaScript

## License

MIT 