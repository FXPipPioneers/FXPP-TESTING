# Discord Trading Bot

## Overview

This is a professional Discord bot designed for trading signal distribution with automatic TP/SL calculations and comprehensive statistics tracking. The bot provides a complete solution for forex and commodity trading communities to share and track trading signals across multiple Discord channels.

## System Architecture

### Core Technologies
- **Runtime**: Python 3.11
- **Framework**: Discord.py 2.5.2 (async/await architecture)
- **Environment Management**: python-dotenv for configuration
- **Web Framework**: aiohttp for web server functionality
- **Deployment**: Multi-platform support (Render.com, Heroku, Replit)

### Security Architecture
- **Split Token System**: Discord bot tokens are split into two environment variables for enhanced security
- **Environment-based Configuration**: All sensitive data stored in environment variables
- **Secure Deployment**: No hardcoded credentials in source code

## Key Components

### Bot Commands
1. **`/entry` Command**: Creates and distributes trading signals
   - Entry types: Buy limit, Sell limit, Buy execution, Sell execution
   - Supported pairs: XAUUSD, GBPJPY, USDJPY, GBPUSD, EURUSD, AUDUSD, NZDUSD, US100, US500, custom pairs
   - Automatic TP/SL calculation based on pip values
   - Multi-channel distribution
   - Role tagging functionality
   - Broker warning for BTCUSD, US100, GER40 pairs

2. **`/stats` Command**: Displays trading performance statistics
   - Customizable date ranges
   - TP hit tracking (TP1, TP2, TP3)
   - SL hit tracking
   - Win rate calculations
   - Multi-channel distribution

3. **`/telegram` Command**: Check Telegram integration status
   - Configuration validation
   - Connection status
   - Setup guidance

### Trading Logic
- **Pip Calculation Engine**: Instrument-specific pip value calculations
- **Price Formatting**: Decimal precision based on trading pair requirements
- **Automatic TP/SL Generation**: 
  - TP1: 20 pips from entry
  - TP2: 50 pips from entry  
  - TP3: 100 pips from entry
  - SL: 70 pips from entry (opposite direction)

### Message Distribution
- **Multi-channel Broadcasting**: Send signals to multiple channels simultaneously
- **Role Tagging System**: Configurable role mentions at message bottom
- **Immediate Delivery**: Real-time signal distribution without delays

### Telegram Integration
- **Automatic Signal Forwarding**: Monitors Telegram groups for trading signals
- **Intelligent Signal Parsing**: Recognizes trading pairs, entry types, and prices
- **Instant Relay**: Forwards signals to Discord without delays
- **Broker Warnings**: Adds specific warnings for volatile pairs (BTCUSD, US100, GER40)
- **Configurable Monitoring**: Can monitor specific chat IDs or all accessible chats

### Timed Auto-Role System
- **Automatic Role Assignment**: Assigns specified roles to new members upon joining
- **Configurable Duration**: Set custom expiration time (default 24 hours)
- **Automatic Role Removal**: Removes expired roles via background monitoring task
- **Custom DM Notifications**: Sends personalized messages when roles expire
- **Persistent Storage**: Maintains member tracking across bot restarts
- **Admin Controls**: `/timedautorole` command for enable/disable/status management

## Data Flow

1. **Command Input**: User executes `/entry` or `/stats` slash command
2. **Parameter Validation**: Bot validates trading pair, price format, and channels
3. **Calculation Engine**: Automatic TP/SL calculation based on pair configuration
4. **Message Generation**: Professional formatting with proper decimal places
5. **Multi-channel Distribution**: Simultaneous broadcasting to selected channels
6. **Role Notification**: Tag specified roles at message bottom

### Trading Pair Configuration
```python
PAIR_CONFIG = {
    'XAUUSD': {'decimals': 2, 'pip_value': 0.1},
    'GBPJPY': {'decimals': 3, 'pip_value': 0.01},
    'USDJPY': {'decimals': 3, 'pip_value': 0.01},
    'GBPUSD': {'decimals': 4, 'pip_value': 0.0001},
    'EURUSD': {'decimals': 4, 'pip_value': 0.0001},
    'AUDUSD': {'decimals': 5, 'pip_value': 0.0001},
    'NZDUSD': {'decimals': 5, 'pip_value': 0.0001},
    'US100': {'decimals': 0, 'pip_value': 1.0},
    'US500': {'decimals': 2, 'pip_value': 0.1}
}
```

## External Dependencies

### Required Packages
- `discord.py==2.5.2`: Discord API interaction
- `python-dotenv==1.1.0`: Environment variable management
- `aiohttp==3.12.13`: Web server functionality
- `pyrogram==2.0.106`: Telegram integration
- `tgcrypto==1.2.5`: Telegram encryption support

### Discord API Requirements
- Bot token with appropriate permissions:
  - Send Messages
  - Use Slash Commands
  - Mention Everyone (for role tagging)
  - Read Message History

### Environment Variables
- `DISCORD_TOKEN_PART1`: First half of Discord bot token
- `DISCORD_TOKEN_PART2`: Second half of Discord bot token  
- `DISCORD_CLIENT_ID_PART1`: First half of Discord client ID
- `DISCORD_CLIENT_ID_PART2`: Second half of Discord client ID

### Discord Bot Permissions
For the auto-role system to work, the bot needs:
- **Manage Roles**: To assign and remove roles from members
- **Send Messages**: To send notifications and confirmations
- **Use Slash Commands**: For the `/timedautorole` command
- **View Members**: To detect new member joins

### Telegram Integration Variables
- `TELEGRAM_API_ID`: Telegram API ID from my.telegram.org
- `TELEGRAM_API_HASH`: Telegram API hash from my.telegram.org
- `TELEGRAM_PHONE_NUMBER`: Phone number associated with Telegram account
- `TELEGRAM_SOURCE_CHAT_ID`: Chat ID of the source trading group (optional)
- `TELEGRAM_DEFAULT_CHANNELS`: Default Discord channels for forwarding (comma-separated)
- `TELEGRAM_DEFAULT_ROLES`: Default roles to mention (comma-separated)

## Deployment Strategy

### Multi-platform Support
1. **Render.com**: Web service deployment with automatic scaling
2. **Heroku**: Worker dyno configuration via Procfile
3. **Replit**: Development and testing environment

### Deployment Configuration
- **Build Command**: `pip install discord.py python-dotenv aiohttp`
- **Start Command**: `python main.py`
- **Runtime**: Python 3.11.0
- **Service Type**: Web service (keeps bot alive 24/7)

### Security Considerations
- Split token system prevents complete token exposure
- Environment-based configuration
- No sensitive data in version control
- Secure deployment practices across platforms

## User Preferences

Preferred communication style: Simple, everyday language.

## Recent Changes

- July 29, 2025: Merged Telegram signal forwarding with timed auto-role system:
  - Added complete Telegram integration for automatic signal parsing and forwarding
  - Implemented intelligent signal parsing for all trading pairs
  - Added broker warnings for volatile pairs (BTCUSD, US100, GER40)
  - Created /telegram command for integration status checking
  - Enhanced entry command with broker warnings
  - Maintained all auto-role functionality (assignment, removal, monitoring, listing)
  - Combined both systems in single unified bot
- January 10, 2025: Added Telegram integration for automatic signal forwarding
- January 10, 2025: Added broker warning messages for BTCUSD, US100, and GER40 pairs
- January 10, 2025: Implemented intelligent signal parsing from Telegram messages
- January 10, 2025: Added /telegram command for integration status checking
- July 10, 2025: Cleaned up codebase by removing all failed trading integration attempts (MetaAPI, OANDA, MT5)
- July 10, 2025: Simplified bot to focus on core signal distribution functionality
- July 10, 2025: Updated deployment files to include Telegram dependencies

## Changelog

Changelog:
- June 24, 2025. Initial setup