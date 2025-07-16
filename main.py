import discord
from discord.ext import commands
from discord import app_commands
import os
from dotenv import load_dotenv
import asyncio
from aiohttp import web
import re
from datetime import datetime, timedelta
import json

# Telegram integration
try:
    from pyrogram import Client, filters
    from pyrogram.types import Message
    TELEGRAM_AVAILABLE = True
    print("Pyrogram loaded - Telegram integration enabled")
except ImportError:
    TELEGRAM_AVAILABLE = False
    print("Pyrogram not available - Install with: pip install pyrogram tgcrypto")

# Load environment variables
load_dotenv()

# Reconstruct tokens from split parts for enhanced security
DISCORD_TOKEN_PART1 = os.getenv("DISCORD_TOKEN_PART1", "")
DISCORD_TOKEN_PART2 = os.getenv("DISCORD_TOKEN_PART2", "")
DISCORD_TOKEN = DISCORD_TOKEN_PART1 + DISCORD_TOKEN_PART2

DISCORD_CLIENT_ID_PART1 = os.getenv("DISCORD_CLIENT_ID_PART1", "")
DISCORD_CLIENT_ID_PART2 = os.getenv("DISCORD_CLIENT_ID_PART2", "")
DISCORD_CLIENT_ID = DISCORD_CLIENT_ID_PART1 + DISCORD_CLIENT_ID_PART2



# Telegram configuration for signal forwarding
TELEGRAM_API_ID = os.getenv("TELEGRAM_API_ID", "")
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH", "")
TELEGRAM_PHONE_NUMBER = os.getenv("TELEGRAM_PHONE_NUMBER", "")
TELEGRAM_SOURCE_CHAT_ID = os.getenv("TELEGRAM_SOURCE_CHAT_ID", "")  # The chat ID of the source trading group
TELEGRAM_DEFAULT_CHANNELS = os.getenv("TELEGRAM_DEFAULT_CHANNELS", "")  # Default Discord channels for forwarding
TELEGRAM_DEFAULT_ROLES = os.getenv("TELEGRAM_DEFAULT_ROLES", "")  # Default roles to mention

# Channel tracking configuration
TRACKING_CONFIG = {
    "xauusd_daily": {
        "enabled": True,
        "sent_today": False,
        "last_reset": datetime.now().date(),
        "channels": ["free", "vip", "premium"]
    },
    "vip_signals": {
        "enabled": True,
        "channels": ["vip", "premium"],
        "daily_limit": 4,
        "sent_today": 0
    },
    "premium_signals": {
        "enabled": True,
        "channels": ["premium"],
        "daily_limit": 10,
        "sent_today": 0
    }
}

# Channel mapping - these should match your actual Discord channel names or IDs
CHANNEL_MAPPING = {
    "free": os.getenv("FREE_SIGNALS_CHANNEL", ""),
    "vip": os.getenv("VIP_SIGNALS_CHANNEL", ""),
    "premium": os.getenv("PREMIUM_SIGNALS_CHANNEL", "")
}

# Bot setup with intents
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

class TradingBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=intents)

    async def setup_hook(self):
        # Sync slash commands
        try:
            synced = await self.tree.sync()
            print(f"Synced {len(synced)} command(s)")
        except Exception as e:
            print(f"Failed to sync commands: {e}")

    async def on_ready(self):
        print(f'{self.user} has landed!')
        if self.user:
            print(f'Bot ID: {self.user.id}')
        
        # Check Telegram integration
        if telegram_client:
            print("✅ Telegram integration ready")
        else:
            print("⚠️ Telegram integration not configured")

bot = TradingBot()

# Initialize Telegram client if available
telegram_client = None
if TELEGRAM_AVAILABLE and TELEGRAM_API_ID and TELEGRAM_API_HASH:
    telegram_client = Client(
        "trading_bot_session",
        api_id=TELEGRAM_API_ID,
        api_hash=TELEGRAM_API_HASH,
        phone_number=TELEGRAM_PHONE_NUMBER
    )
    print("Telegram client initialized")
else:
    print("Telegram integration not configured")

# Trading pair configurations

# Trading pair configurations
PAIR_CONFIG = {
    'XAUUSD': {'decimals': 2, 'pip_value': 0.1},
    'GBPJPY': {'decimals': 3, 'pip_value': 0.01},
    'GBPUSD': {'decimals': 4, 'pip_value': 0.0001},
    'EURUSD': {'decimals': 4, 'pip_value': 0.0001},
    'AUDUSD': {'decimals': 5, 'pip_value': 0.00001},
    'NZDUSD': {'decimals': 5, 'pip_value': 0.00001},
    'US100': {'decimals': 1, 'pip_value': 1.0},
    'US500': {'decimals': 2, 'pip_value': 0.1},
    'GER40': {'decimals': 1, 'pip_value': 1.0},  # Same as US100
    'BTCUSD': {'decimals': 1, 'pip_value': 1.0},  # Same as US100 and GER40
    'GBPCHF': {'decimals': 4, 'pip_value': 0.0001},  # Same as GBPUSD
    'USDCHF': {'decimals': 4, 'pip_value': 0.0001},  # Same as GBPUSD
    'CADCHF': {'decimals': 4, 'pip_value': 0.0001},  # Same as GBPUSD
    'AUDCHF': {'decimals': 4, 'pip_value': 0.0001},  # Same as GBPUSD
    'CHFJPY': {'decimals': 3, 'pip_value': 0.01},  # Same as GBPJPY
    'CADJPY': {'decimals': 3, 'pip_value': 0.01},  # Same as GBPJPY
    'AUDJPY': {'decimals': 3, 'pip_value': 0.01},  # Same as GBPJPY
    'USDCAD': {'decimals': 4, 'pip_value': 0.0001},  # Same as GBPUSD
    'GBPCAD': {'decimals': 4, 'pip_value': 0.0001},  # Same as GBPUSD
    'EURCAD': {'decimals': 4, 'pip_value': 0.0001},  # Same as GBPUSD
    'AUDCAD': {'decimals': 4, 'pip_value': 0.0001},  # Same as GBPUSD
    'AUDNZD': {'decimals': 4, 'pip_value': 0.0001}   # Same as GBPUSD
}

# Telegram Signal Parsing Functions
def parse_telegram_signal(message_text: str) -> dict:
    """Parse trading signal from Telegram message text with enhanced filtering"""
    signal_data = {}
    
    # Check for required keywords first
    required_keywords = ['ENTRY', 'TAKE PROFIT', 'STOP LOSS']
    message_upper = message_text.upper()
    
    if not all(keyword in message_upper for keyword in required_keywords):
        return signal_data  # Return empty dict if keywords not found
    
    # Find entry type and pair together (Buy XAUUSD, Sell GBPJPY pattern)
    entry_pair_patterns = [
        (r'(BUY|SELL)\s+(XAUUSD|GOLD|XAU)', 'XAUUSD'),
        (r'(BUY|SELL)\s+(GBPJPY|GBP/JPY)', 'GBPJPY'),
        (r'(BUY|SELL)\s+(EURUSD|EUR/USD)', 'EURUSD'),
        (r'(BUY|SELL)\s+(GBPUSD|GBP/USD)', 'GBPUSD'),
        (r'(BUY|SELL)\s+(AUDUSD|AUD/USD)', 'AUDUSD'),
        (r'(BUY|SELL)\s+(NZDUSD|NZD/USD)', 'NZDUSD'),
        (r'(BUY|SELL)\s+(USDCAD|USD/CAD)', 'USDCAD'),
        (r'(BUY|SELL)\s+(USDCHF|USD/CHF)', 'USDCHF'),
        (r'(BUY|SELL)\s+(GBPCHF|GBP/CHF)', 'GBPCHF'),
        (r'(BUY|SELL)\s+(CADCHF|CAD/CHF)', 'CADCHF'),
        (r'(BUY|SELL)\s+(AUDCHF|AUD/CHF)', 'AUDCHF'),
        (r'(BUY|SELL)\s+(CHFJPY|CHF/JPY)', 'CHFJPY'),
        (r'(BUY|SELL)\s+(CADJPY|CAD/JPY)', 'CADJPY'),
        (r'(BUY|SELL)\s+(AUDJPY|AUD/JPY)', 'AUDJPY'),
        (r'(BUY|SELL)\s+(GBPCAD|GBP/CAD)', 'GBPCAD'),
        (r'(BUY|SELL)\s+(EURCAD|EUR/CAD)', 'EURCAD'),
        (r'(BUY|SELL)\s+(AUDCAD|AUD/CAD)', 'AUDCAD'),
        (r'(BUY|SELL)\s+(AUDNZD|AUD/NZD)', 'AUDNZD'),
        (r'(BUY|SELL)\s+(US100|NASDAQ|NAS100)', 'US100'),
        (r'(BUY|SELL)\s+(US500|S&P500|SPX500)', 'US500'),
        (r'(BUY|SELL)\s+(GER40|DAX|GERMANY40)', 'GER40'),
        (r'(BUY|SELL)\s+(BTCUSD|BTC/USD|BITCOIN)', 'BTCUSD'),
        (r'(BUY|SELL)\s+(USDJPY|USD/JPY)', 'USDJPY')
    ]
    
    # Try to find entry type and pair together
    for pattern, normalized_pair in entry_pair_patterns:
        match = re.search(pattern, message_upper)
        if match:
            entry_action = match.group(1)
            signal_data['pair'] = normalized_pair
            
            # Set entry type based on action
            if entry_action == 'BUY':
                signal_data['entry_type'] = 'Buy execution'
            else:  # SELL
                signal_data['entry_type'] = 'Sell execution'
            break
    
    # Try to find entry price
    price_patterns = [
        r'(?:ENTRY|PRICE|@)\s*:?\s*([0-9]+\.?[0-9]*)',
        r'([0-9]+\.[0-9]+)',
        r'([0-9]+)',
    ]
    
    for pattern in price_patterns:
        matches = re.findall(pattern, message_text)
        if matches:
            try:
                signal_data['entry_price'] = float(matches[0])
                break
            except ValueError:
                continue
    
    return signal_data

def is_valid_signal(signal_data: dict) -> bool:
    """Check if parsed signal has required fields"""
    required_fields = ['pair', 'entry_type', 'entry_price']
    return all(field in signal_data for field in required_fields)

def reset_daily_counters():
    """Reset daily tracking counters if it's a new day"""
    today = datetime.now().date()
    
    # Reset XAUUSD daily tracking
    if TRACKING_CONFIG["xauusd_daily"]["last_reset"] != today:
        TRACKING_CONFIG["xauusd_daily"]["sent_today"] = False
        TRACKING_CONFIG["xauusd_daily"]["last_reset"] = today
    
    # Reset VIP and Premium signal counters
    if TRACKING_CONFIG["vip_signals"].get("last_reset", today) != today:
        TRACKING_CONFIG["vip_signals"]["sent_today"] = 0
        TRACKING_CONFIG["vip_signals"]["last_reset"] = today
    
    if TRACKING_CONFIG["premium_signals"].get("last_reset", today) != today:
        TRACKING_CONFIG["premium_signals"]["sent_today"] = 0
        TRACKING_CONFIG["premium_signals"]["last_reset"] = today

def determine_target_channels(pair: str) -> list:
    """Determine which channels should receive the signal based on pair and limits"""
    reset_daily_counters()
    target_channels = []
    
    if pair == "XAUUSD":
        # XAUUSD only goes to free, and only once per day
        if (TRACKING_CONFIG["xauusd_daily"]["enabled"] and 
            not TRACKING_CONFIG["xauusd_daily"]["sent_today"]):
            target_channels = ["free", "vip", "premium"]
            TRACKING_CONFIG["xauusd_daily"]["sent_today"] = True
        else:
            return []  # No channels if already sent or disabled
    else:
        # Other pairs go to VIP and Premium based on limits
        vip_config = TRACKING_CONFIG["vip_signals"]
        premium_config = TRACKING_CONFIG["premium_signals"]
        
        # Check VIP limit (includes VIP and Premium)
        if (vip_config["enabled"] and 
            vip_config["sent_today"] < vip_config["daily_limit"]):
            target_channels.extend(["vip", "premium"])
            vip_config["sent_today"] += 1
        
        # Check Premium limit (Premium only, additional signals)
        elif (premium_config["enabled"] and 
              premium_config["sent_today"] < premium_config["daily_limit"]):
            target_channels.append("premium")
            premium_config["sent_today"] += 1
    
    return target_channels

async def forward_telegram_signal(signal_data: dict, original_message: str):
    """Forward parsed signal to Discord using smart routing logic"""
    try:
        # Get default guild (first guild the bot is in)
        guild = bot.guilds[0] if bot.guilds else None
        if not guild:
            print("Bot not in any Discord servers")
            return
        
        # Determine target channels based on pair and limits
        target_channels = determine_target_channels(signal_data['pair'])
        
        if not target_channels:
            print(f"🚫 Signal blocked: {signal_data['pair']} - daily limits reached or tracking disabled")
            return
        
        # Calculate TP and SL levels
        levels = calculate_levels(signal_data['entry_price'], signal_data['pair'], signal_data['entry_type'])
        
        # Create the signal message (same format as /entry command)
        signal_message = f"""**Trade Signal For: {signal_data['pair']}**
Entry Type: {signal_data['entry_type']}
Entry Price: {levels['entry']}

**Take Profit Levels:**
TP1: {levels['tp1']}
TP2: {levels['tp2']}
TP3: {levels['tp3']}

Stop Loss: {levels['sl']}

*🔄 Auto-forwarded from Telegram*"""

        # Add broker warning for specific pairs
        if signal_data['pair'].upper() in ['BTCUSD', 'US100', 'GER40']:
            signal_message += "\n\n**Please note that prices on BTC, US100 & GER40 vary a lot from broker to broker, so it is possible that the current price in our signal is different than the current price with your broker. Execute this signal within a 5 minute window of this trade being sent and please manually recalculate the pip value for TP1/2/3 & SL depending on your broker's current price.**"
        
        # Add role mentions if configured
        if TELEGRAM_DEFAULT_ROLES:
            role_mentions = []
            role_names = [role.strip() for role in TELEGRAM_DEFAULT_ROLES.split(',')]
            for role_name in role_names:
                if role_name.lower() == "@everyone" or role_name.lower() == "everyone":
                    role_mentions.append("@everyone")
                else:
                    role = discord.utils.get(guild.roles, name=role_name)
                    if role:
                        role_mentions.append(role.mention)
                    else:
                        role_mentions.append(f"{role_name}")
            
            if role_mentions:
                signal_message += f"\n\n{' '.join(role_mentions)}"
        
        # Send to target channels
        sent_channels = []
        sent_messages = []
        
        for channel_type in target_channels:
            channel_id = CHANNEL_MAPPING.get(channel_type)
            if not channel_id:
                print(f"⚠️ Channel mapping not found for {channel_type}")
                continue
                
            target_channel = None
            
            # Try to parse as channel mention
            if channel_id.startswith('<#') and channel_id.endswith('>'):
                channel_id = int(channel_id[2:-1])
                target_channel = bot.get_channel(channel_id)
            # Try to parse as channel ID
            elif channel_id.isdigit():
                target_channel = bot.get_channel(int(channel_id))
            # Try to find by name
            else:
                target_channel = discord.utils.get(guild.channels, name=channel_id)
            
            if target_channel and isinstance(target_channel, discord.TextChannel):
                try:
                    sent_message = await target_channel.send(signal_message)
                    sent_channels.append(f"{channel_type}({target_channel.name})")
                    sent_messages.append(sent_message)
                except Exception as e:
                    print(f"Error sending to #{target_channel.name}: {str(e)}")
        
        if sent_messages:
            print(f"✅ {signal_data['pair']} signal forwarded to {len(sent_channels)} channels: {', '.join(sent_channels)}")
        else:
            print("❌ No messages sent - check channel configuration")
            
    except Exception as e:
        print(f"❌ Error forwarding Telegram signal: {str(e)}")

# Telegram message handler
if telegram_client:
    @telegram_client.on_message(filters.chat(TELEGRAM_SOURCE_CHAT_ID) if TELEGRAM_SOURCE_CHAT_ID else filters.all)
    async def handle_telegram_message(client, message: Message):
        """Handle incoming Telegram messages from the specified chat"""
        try:
            # Only process messages from the configured source chat
            if TELEGRAM_SOURCE_CHAT_ID and str(message.chat.id) != TELEGRAM_SOURCE_CHAT_ID:
                return
            
            # Skip if no text content
            if not message.text:
                return
            
            print(f"📱 Received Telegram message: {message.text[:100]}...")
            
            # Parse the signal
            signal_data = parse_telegram_signal(message.text)
            
            if is_valid_signal(signal_data):
                print(f"🎯 Valid signal parsed: {signal_data}")
                await forward_telegram_signal(signal_data, message.text)
            else:
                print(f"⚠️ Invalid signal format, skipping...")
                
        except Exception as e:
            print(f"❌ Error processing Telegram message: {str(e)}")

def calculate_levels(entry_price: float, pair: str, entry_type: str):
    """Calculate TP and SL levels based on pair configuration"""
    if pair in PAIR_CONFIG:
        pip_value = PAIR_CONFIG[pair]['pip_value']
        decimals = PAIR_CONFIG[pair]['decimals']
    else:
        # Default values for unknown pairs
        pip_value = 0.0001  
        decimals = 4
    
    # Calculate pip amounts
    tp1_pips = 20 * pip_value
    tp2_pips = 50 * pip_value
    tp3_pips = 100 * pip_value
    sl_pips = 70 * pip_value
    
    # Determine direction based on entry type
    is_buy = entry_type.lower().startswith('buy')
    
    if is_buy:
        tp1 = entry_price + tp1_pips
        tp2 = entry_price + tp2_pips
        tp3 = entry_price + tp3_pips
        sl = entry_price - sl_pips
    else:  # Sell
        tp1 = entry_price - tp1_pips
        tp2 = entry_price - tp2_pips
        tp3 = entry_price - tp3_pips
        sl = entry_price + sl_pips
    
    # Format prices with correct decimals
    if pair == 'XAUUSD' or pair == 'US500':
        currency_symbol = '$'
    elif pair == 'US100':
        currency_symbol = '$'
    else:
        currency_symbol = '$'
    
    def format_price(price):
        return f"{currency_symbol}{price:.{decimals}f}"
    
    return {
        'tp1': format_price(tp1),
        'tp2': format_price(tp2),
        'tp3': format_price(tp3),
        'sl': format_price(sl),
        'entry': format_price(entry_price),
        'tp1_raw': tp1,
        'tp2_raw': tp2,
        'tp3_raw': tp3,
        'sl_raw': sl,
        'entry_raw': entry_price
    }

@bot.tree.command(name="entry", description="Create a trading signal entry")
@app_commands.describe(
    entry_type="Type of entry (Long, Short, Long Swing, Short Swing)",
    pair="Trading pair",
    price="Entry price",
    channels="Select channels to send the signal to (comma-separated channel mentions or names)",
    roles="Roles to mention (comma-separated, required)"
)
async def entry_command(
    interaction: discord.Interaction,
    entry_type: str,
    pair: str,
    price: float,
    channels: str,
    roles: str
):
    """Create and send a trading signal to specified channels"""
    
    try:
        # Calculate TP and SL levels
        levels = calculate_levels(price, pair, entry_type)
        
        # Create the signal message
        signal_message = f"""**Trade Signal For: {pair}**
Entry Type: {entry_type}
Entry Price: {levels['entry']}

**Take Profit Levels:**
TP1: {levels['tp1']}
TP2: {levels['tp2']}
TP3: {levels['tp3']}

Stop Loss: {levels['sl']}"""

        # Add broker warning for specific pairs
        if pair.upper() in ['BTCUSD', 'US100', 'GER40']:
            signal_message += "\n\n**Please note that prices on BTC, US100 & GER40 vary a lot from broker to broker, so it is possible that the current price in our signal is different than the current price with your broker. Execute this signal within a 5 minute window of this trade being sent and please manually recalculate the pip value for TP1/2/3 & SL depending on your broker's current price.**"
        
        # Add role mentions at the bottom if provided
        if roles.strip():
            role_mentions = []
            role_names = [role.strip() for role in roles.split(',')]
            for role_name in role_names:
                # Handle @everyone specifically to avoid double @
                if role_name.lower() == "@everyone" or role_name.lower() == "everyone":
                    role_mentions.append("@everyone")
                else:
                    # Find role by name in the guild
                    role = discord.utils.get(interaction.guild.roles, name=role_name)
                    if role:
                        role_mentions.append(role.mention)
                    else:
                        role_mentions.append(f"{role_name}")
            
            if role_mentions:
                signal_message += f"\n\n{' '.join(role_mentions)}"
        
        # Parse and send to multiple channels - using channel IDs to avoid name conflicts
        channel_list = [ch.strip() for ch in channels.split(',')]
        sent_channels = []
        sent_messages = []
        channel_ids = []
        
        for channel_identifier in channel_list:
            target_channel = None
            
            # Priority 1: Try to parse as channel mention (most reliable)
            if channel_identifier.startswith('<#') and channel_identifier.endswith('>'):
                channel_id = int(channel_identifier[2:-1])
                target_channel = bot.get_channel(channel_id)
            # Priority 2: Try to parse as channel ID
            elif channel_identifier.isdigit():
                target_channel = bot.get_channel(int(channel_identifier))
            # Priority 3: Find by name (will get first match - this is the issue you mentioned)
            else:
                target_channel = discord.utils.get(interaction.guild.channels, name=channel_identifier)
            
            if target_channel and isinstance(target_channel, discord.TextChannel):
                try:
                    sent_message = await target_channel.send(signal_message)
                    sent_channels.append(target_channel.name)
                    sent_messages.append(sent_message)
                    channel_ids.append(target_channel.id)
                except discord.Forbidden:
                    await interaction.followup.send(f"❌ No permission to send to #{target_channel.name}", ephemeral=True)
                except Exception as e:
                    await interaction.followup.send(f"❌ Error sending to #{target_channel.name}: {str(e)}", ephemeral=True)
        
        if sent_channels:
            success_msg = f"✅ Signal sent to: {', '.join(sent_channels)}"
            await interaction.response.send_message(success_msg, ephemeral=True)
        else:
            await interaction.response.send_message("❌ No valid channels found or no messages sent.", ephemeral=True)
            
    except Exception as e:
        await interaction.response.send_message(f"❌ Error creating signal: {str(e)}", ephemeral=True)

@entry_command.autocomplete('entry_type')
async def entry_type_autocomplete(interaction: discord.Interaction, current: str):
    types = ['Buy limit', 'Sell limit', 'Buy execution', 'Sell execution']
    return [
        app_commands.Choice(name=entry_type, value=entry_type)
        for entry_type in types if current.lower() in entry_type.lower()
    ]

@entry_command.autocomplete('pair')
async def pair_autocomplete(interaction: discord.Interaction, current: str):
    # Organized pairs by currency groups for easier navigation
    pairs = [
        # USD pairs
        'EURUSD', 'GBPUSD', 'AUDUSD', 'NZDUSD', 'USDCAD', 'USDCHF', 'XAUUSD', 'BTCUSD',
        # JPY pairs  
        'GBPJPY', 'CHFJPY', 'CADJPY', 'AUDJPY',
        # CHF pairs
        'GBPCHF', 'CADCHF', 'AUDCHF',
        # CAD pairs
        'GBPCAD', 'EURCAD', 'AUDCAD',
        # Cross pairs
        'AUDNZD',
        # Indices
        'US100', 'US500', 'GER40'
    ]
    return [
        app_commands.Choice(name=pair, value=pair)
        for pair in pairs if current.lower() in pair.lower()
    ]

@bot.tree.command(name="stats", description="Send trading statistics summary")
@app_commands.describe(
    date_range="Date range for the statistics",
    total_signals="Total number of signals sent",
    tp1_hits="Number of TP1 hits",
    tp2_hits="Number of TP2 hits", 
    tp3_hits="Number of TP3 hits",
    sl_hits="Number of SL hits",
    channels="Select channels to send the stats to (comma-separated channel mentions or names)",
    currently_open="Number of currently open trades",
    total_closed="Total closed trades (auto-calculated if not provided)"
)
async def stats_command(
    interaction: discord.Interaction,
    date_range: str,
    total_signals: int,
    tp1_hits: int,
    tp2_hits: int,
    tp3_hits: int,
    sl_hits: int,
    channels: str,
    currently_open: str = "0",
    total_closed: int = None
):
    """Send formatted trading statistics to specified channels"""
    
    try:
        # Calculate total closed if not provided
        if total_closed is None:
            total_closed = tp1_hits + sl_hits
        
        # Calculate percentages
        def calc_percentage(hits, total):
            if total == 0:
                return "0%"
            return f"{(hits/total)*100:.0f}%"
        
        tp1_percent = calc_percentage(tp1_hits, total_closed) if total_closed > 0 else "0%"
        tp2_percent = calc_percentage(tp2_hits, total_closed) if total_closed > 0 else "0%"
        tp3_percent = calc_percentage(tp3_hits, total_closed) if total_closed > 0 else "0%"
        sl_percent = calc_percentage(sl_hits, total_closed) if total_closed > 0 else "0%"
        
        # Create the stats message
        stats_message = f"""**:bar_chart: TRADING SIGNAL STATISTICS**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**:date: Period:** {date_range}

**:chart_with_upwards_trend: SIGNAL OVERVIEW**
• Total Signals Sent: **{total_signals}**
• Total Closed Positions: **{total_closed}**
• Currently Open: **{currently_open}**

**:dart: TAKE PROFIT PERFORMANCE**
• TP1 Hits: **{tp1_hits}**
• TP2 Hits: **{tp2_hits}**
• TP3 Hits: **{tp3_hits}**

**:octagonal_sign: STOP LOSS**
• SL Hits: **{sl_hits}**

**:bar_chart: PERFORMANCE SUMMARY**
• **Win Rate:** {tp1_percent}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""
        
        # Parse and send to multiple channels
        channel_list = [ch.strip() for ch in channels.split(',')]
        sent_channels = []
        
        for channel_identifier in channel_list:
            target_channel = None
            
            # Try to parse as channel mention
            if channel_identifier.startswith('<#') and channel_identifier.endswith('>'):
                channel_id = int(channel_identifier[2:-1])
                target_channel = bot.get_channel(channel_id)
            # Try to parse as channel ID
            elif channel_identifier.isdigit():
                target_channel = bot.get_channel(int(channel_identifier))
            # Try to find by name
            else:
                target_channel = discord.utils.get(interaction.guild.channels, name=channel_identifier)
            
            if target_channel and isinstance(target_channel, discord.TextChannel):
                try:
                    await target_channel.send(stats_message)
                    sent_channels.append(target_channel.name)
                except discord.Forbidden:
                    await interaction.followup.send(f"❌ No permission to send to #{target_channel.name}", ephemeral=True)
                except Exception as e:
                    await interaction.followup.send(f"❌ Error sending to #{target_channel.name}: {str(e)}", ephemeral=True)
        
        if sent_channels:
            await interaction.response.send_message(f"✅ Stats sent to: {', '.join(sent_channels)}", ephemeral=True)
        else:
            await interaction.response.send_message("❌ No valid channels found or no messages sent.", ephemeral=True)
            
    except Exception as e:
        await interaction.response.send_message(f"❌ Error sending statistics: {str(e)}", ephemeral=True)



@bot.tree.command(name="telegram", description="Check Telegram integration status")
async def telegram_command(interaction: discord.Interaction):
    """Check Telegram integration status and configuration"""
    try:
        status_msg = f"**📱 Telegram Integration Status**\n\n"
        
        # Check if Telegram is available
        if TELEGRAM_AVAILABLE:
            status_msg += "✅ Telegram integration installed\n\n"
        else:
            status_msg += "❌ Telegram integration not installed\n"
            status_msg += "💡 Install with: pip install pyrogram tgcrypto\n\n"
        
        # Check configuration
        config_status = []
        if TELEGRAM_API_ID:
            config_status.append("✅ API ID configured")
        else:
            config_status.append("❌ API ID missing")
            
        if TELEGRAM_API_HASH:
            config_status.append("✅ API Hash configured")
        else:
            config_status.append("❌ API Hash missing")
            
        if TELEGRAM_PHONE_NUMBER:
            config_status.append("✅ Phone number configured")
        else:
            config_status.append("❌ Phone number missing")
            
        if TELEGRAM_SOURCE_CHAT_ID:
            config_status.append(f"✅ Source chat ID: {TELEGRAM_SOURCE_CHAT_ID}")
        else:
            config_status.append("⚠️ No specific source chat configured (monitoring all)")
            
        if TELEGRAM_DEFAULT_CHANNELS:
            config_status.append(f"✅ Default channels: {TELEGRAM_DEFAULT_CHANNELS}")
        else:
            config_status.append("❌ No default Discord channels configured")
            
        if TELEGRAM_DEFAULT_ROLES:
            config_status.append(f"✅ Default roles: {TELEGRAM_DEFAULT_ROLES}")
        else:
            config_status.append("⚠️ No default roles configured")
        
        status_msg += "\n".join(config_status)
        
        # Overall status
        if TELEGRAM_AVAILABLE and TELEGRAM_API_ID and TELEGRAM_API_HASH and TELEGRAM_PHONE_NUMBER:
            status_msg += "\n\n🎯 Status: Ready for signal forwarding"
        else:
            status_msg += "\n\n❌ Status: Not configured"
            status_msg += "\n💡 Configure environment variables to enable"
        
        await interaction.response.send_message(status_msg, ephemeral=True)
        
    except Exception as e:
        await interaction.response.send_message(f"❌ Error checking Telegram status: {str(e)}", ephemeral=True)

@bot.tree.command(name="tracking", description="Manage signal tracking settings")
@app_commands.describe(
    action="Action to perform",
    target="What to control (xauusd, vip, premium, all)",
    channel_type="Channel type for sleep mode (free, vip, premium, all)"
)
async def tracking_command(
    interaction: discord.Interaction,
    action: str,
    target: str = "all",
    channel_type: str = "all"
):
    """Manage signal tracking settings - sleep mode, resume, and status"""
    
    try:
        if action == "sleep":
            # Put tracking into sleep mode
            if target == "xauusd":
                if channel_type == "all":
                    TRACKING_CONFIG["xauusd_daily"]["enabled"] = False
                    await interaction.response.send_message("🛌 XAUUSD tracking disabled for all channels (free, vip, premium) until manually resumed.", ephemeral=True)
                else:
                    await interaction.response.send_message("⚠️ XAUUSD tracking affects all channels. Use target='xauusd' and channel_type='all'.", ephemeral=True)
            elif target == "vip":
                TRACKING_CONFIG["vip_signals"]["enabled"] = False
                await interaction.response.send_message("🛌 VIP signals tracking disabled (affects vip and premium channels) until manually resumed.", ephemeral=True)
            elif target == "premium":
                TRACKING_CONFIG["premium_signals"]["enabled"] = False
                await interaction.response.send_message("🛌 Premium signals tracking disabled until manually resumed.", ephemeral=True)
            elif target == "all":
                TRACKING_CONFIG["xauusd_daily"]["enabled"] = False
                TRACKING_CONFIG["vip_signals"]["enabled"] = False
                TRACKING_CONFIG["premium_signals"]["enabled"] = False
                await interaction.response.send_message("🛌 All signal tracking disabled until manually resumed.", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Invalid target. Use: xauusd, vip, premium, or all", ephemeral=True)
        
        elif action == "resume":
            # Resume tracking
            if target == "xauusd":
                TRACKING_CONFIG["xauusd_daily"]["enabled"] = True
                await interaction.response.send_message("✅ XAUUSD tracking resumed for all channels.", ephemeral=True)
            elif target == "vip":
                TRACKING_CONFIG["vip_signals"]["enabled"] = True
                await interaction.response.send_message("✅ VIP signals tracking resumed.", ephemeral=True)
            elif target == "premium":
                TRACKING_CONFIG["premium_signals"]["enabled"] = True
                await interaction.response.send_message("✅ Premium signals tracking resumed.", ephemeral=True)
            elif target == "all":
                TRACKING_CONFIG["xauusd_daily"]["enabled"] = True
                TRACKING_CONFIG["vip_signals"]["enabled"] = True
                TRACKING_CONFIG["premium_signals"]["enabled"] = True
                await interaction.response.send_message("✅ All signal tracking resumed.", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Invalid target. Use: xauusd, vip, premium, or all", ephemeral=True)
        
        elif action == "status":
            # Show current tracking status
            reset_daily_counters()  # Ensure counters are up to date
            
            status_msg = "**🎯 Signal Tracking Status**\n\n"
            
            # XAUUSD Status
            xauusd_config = TRACKING_CONFIG["xauusd_daily"]
            xauusd_status = "✅ Active" if xauusd_config["enabled"] else "🛌 Sleeping"
            xauusd_sent = "✅ Sent today" if xauusd_config["sent_today"] else "⏳ Not sent yet"
            status_msg += f"**XAUUSD Daily Signal (Free, VIP, Premium):**\n"
            status_msg += f"• Status: {xauusd_status}\n"
            status_msg += f"• Today: {xauusd_sent}\n\n"
            
            # VIP Status
            vip_config = TRACKING_CONFIG["vip_signals"]
            vip_status = "✅ Active" if vip_config["enabled"] else "🛌 Sleeping"
            vip_count = f"{vip_config['sent_today']}/{vip_config['daily_limit']}"
            status_msg += f"**VIP Signals (VIP, Premium channels):**\n"
            status_msg += f"• Status: {vip_status}\n"
            status_msg += f"• Today: {vip_count} signals\n\n"
            
            # Premium Status
            premium_config = TRACKING_CONFIG["premium_signals"]
            premium_status = "✅ Active" if premium_config["enabled"] else "🛌 Sleeping"
            premium_count = f"{premium_config['sent_today']}/{premium_config['daily_limit']}"
            status_msg += f"**Premium Signals (Premium channel only):**\n"
            status_msg += f"• Status: {premium_status}\n"
            status_msg += f"• Today: {premium_count} signals\n\n"
            
            # Channel mapping info
            status_msg += "**📋 Channel Configuration:**\n"
            status_msg += f"• Free: {CHANNEL_MAPPING.get('free', 'Not configured')}\n"
            status_msg += f"• VIP: {CHANNEL_MAPPING.get('vip', 'Not configured')}\n"
            status_msg += f"• Premium: {CHANNEL_MAPPING.get('premium', 'Not configured')}\n"
            
            await interaction.response.send_message(status_msg, ephemeral=True)
        
        else:
            await interaction.response.send_message("❌ Invalid action. Use: sleep, resume, or status", ephemeral=True)
            
    except Exception as e:
        await interaction.response.send_message(f"❌ Error managing tracking: {str(e)}", ephemeral=True)

@tracking_command.autocomplete('action')
async def tracking_action_autocomplete(interaction: discord.Interaction, current: str):
    actions = ['sleep', 'resume', 'status']
    return [
        app_commands.Choice(name=action, value=action)
        for action in actions if current.lower() in action.lower()
    ]

@tracking_command.autocomplete('target')
async def tracking_target_autocomplete(interaction: discord.Interaction, current: str):
    targets = ['xauusd', 'vip', 'premium', 'all']
    return [
        app_commands.Choice(name=target, value=target)
        for target in targets if current.lower() in target.lower()
    ]

@tracking_command.autocomplete('channel_type')
async def tracking_channel_type_autocomplete(interaction: discord.Interaction, current: str):
    channel_types = ['free', 'vip', 'premium', 'all']
    return [
        app_commands.Choice(name=channel_type, value=channel_type)
        for channel_type in channel_types if current.lower() in channel_type.lower()
    ]

# Error handling
@bot.event
async def on_command_error(ctx, error):
    print(f"Command error: {error}")

@bot.event
async def on_application_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if not interaction.response.is_done():
        await interaction.response.send_message(f"❌ An error occurred: {str(error)}", ephemeral=True)
    print(f"Application command error: {error}")

# Simple web server for Render.com health checks
async def health_check(request):
    return web.Response(text="Discord Trading Bot is running!", status=200)

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', health_check)
    app.router.add_get('/health', health_check)
    
    # Use PORT environment variable or default to 5000
    port = int(os.getenv('PORT', 5000))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"Web server started on port {port}")
    return site

async def start_bot():
    """Start the Discord bot"""
    if not DISCORD_TOKEN:
        print("Error: DISCORD_TOKEN not found in environment variables")
        return
    
    await bot.start(DISCORD_TOKEN)

async def start_telegram_client():
    """Start the Telegram client"""
    if not telegram_client:
        print("Telegram client not configured")
        return
    
    try:
        await telegram_client.start()
        print("✅ Telegram client started successfully")
        
        # Print configuration status
        if TELEGRAM_SOURCE_CHAT_ID:
            print(f"📱 Monitoring Telegram chat: {TELEGRAM_SOURCE_CHAT_ID}")
        else:
            print("⚠️ No specific chat ID configured - monitoring all chats")
            
        if TELEGRAM_DEFAULT_CHANNELS:
            print(f"🎯 Default Discord channels: {TELEGRAM_DEFAULT_CHANNELS}")
        else:
            print("⚠️ No default Discord channels configured")
            
        # Keep running
        await telegram_client.idle()
        
    except Exception as e:
        print(f"❌ Error starting Telegram client: {str(e)}")

async def main():
    """Main function to run web server, Discord bot, and Telegram client"""
    print("Starting web server...")
    await start_web_server()
    
    # Start both Discord bot and Telegram client concurrently
    tasks = []
    
    print("Starting Discord bot...")
    tasks.append(asyncio.create_task(start_bot()))
    
    if telegram_client:
        print("Starting Telegram client...")
        tasks.append(asyncio.create_task(start_telegram_client()))
    
    # Wait for all tasks to complete
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())