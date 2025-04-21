# Telegram Subscription Bot

This bot manages paid subscriptions to private Telegram channels/groups using Telegram Stars for payment.

## Features

- Automated subscription management for private Telegram channels/groups
- Payment processing using Telegram Stars
- Automatic access provision and revocation
- Multi-channel and multi-tariff support

## Setup

1. Clone this repository
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Create a `.env` file with required settings (see `.env.example`)
4. Set up your database
5. Run migrations:
   ```
   alembic upgrade head
   ```
6. Start the bot:
   ```
   python main.py
   ```

## Configuration

See `.env.example` for all required environment variables.

## Administrator Setup

1. Create a bot with @BotFather
2. Set up payments with @BotFather by enabling Telegram Stars
3. Add the bot as an administrator to your private channels/groups with these permissions:
   - Invite Users
   - Ban Users
4. Configure your channels and tariffs in the database or through the admin interface

## License

MIT 