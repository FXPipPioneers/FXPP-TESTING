import discord
from discord.ext import commands
from discord import app_commands
import os
from dotenv import load_dotenv
import asyncio
from aiohttp import web
import random
import json
import time
from typing import Dict, List, Optional
import threading

# Load environment variables
load_dotenv()

# Import MetaApi for MT5 integration with comprehensive error handling
METAAPI_AVAILABLE = False
metaapi_error = None
MetaApi = None

def try_import_metaapi():
    """Try to import MetaAPI SDK with multiple fallback methods"""
    global METAAPI_AVAILABLE, metaapi_error, MetaApi
    
    # Method 1: Direct import
    try:
        from metaapi_cloud_sdk import MetaApi
        METAAPI_AVAILABLE = True
        print("MetaApi Cloud SDK loaded - MT5 integration enabled")
        return True
    except ImportError as e:
        metaapi_error = str(e)
        print(f"Direct import failed: {e}")
    except Exception as e:
        metaapi_error = str(e)
        print(f"Direct import error: {e}")
    
    # Method 2: Force install and import
    try:
        import subprocess
        import sys
        print("Attempting to install MetaAPI SDK...")
        result = subprocess.run([sys.executable, "-m", "pip", "install", "metaapi-cloud-sdk==28.0.7"], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("MetaAPI SDK installed successfully")
            from metaapi_cloud_sdk import MetaApi
            METAAPI_AVAILABLE = True
            print("MetaApi Cloud SDK loaded after installation - MT5 integration enabled")
            return True
        else:
            print(f"Installation failed: {result.stderr}")
    except Exception as e:
        print(f"Installation method failed: {e}")
    
    # Method 3: Check if module exists but import failed
    try:
        import importlib.util
        spec = importlib.util.find_spec("metaapi_cloud_sdk")
        if spec is not None:
            print("MetaAPI SDK detected in system but import failed")
            # Try to load the module directly
            import importlib
            module = importlib.import_module("metaapi_cloud_sdk")
            MetaApi = getattr(module, "MetaApi")
            METAAPI_AVAILABLE = True
            print("MetaApi Cloud SDK loaded via importlib - MT5 integration enabled")
            return True
    except Exception as e:
        print(f"Importlib method failed: {e}")
    
    return False

# Try to import MetaAPI
try_import_metaapi()

# Reconstruct tokens from split parts for enhanced security
DISCORD_TOKEN_PART1 = os.getenv("DISCORD_TOKEN_PART1", "")
DISCORD_TOKEN_PART2 = os.getenv("DISCORD_TOKEN_PART2", "")
DISCORD_TOKEN = DISCORD_TOKEN_PART1 + DISCORD_TOKEN_PART2

DISCORD_CLIENT_ID_PART1 = os.getenv("DISCORD_CLIENT_ID_PART1", "")
DISCORD_CLIENT_ID_PART2 = os.getenv("DISCORD_CLIENT_ID_PART2", "")
DISCORD_CLIENT_ID = DISCORD_CLIENT_ID_PART1 + DISCORD_CLIENT_ID_PART2

# MetaApi configuration
METAAPI_TOKEN = os.getenv("METAAPI_TOKEN", "")
MT5_ACCOUNT_ID = os.getenv("MT5_ACCOUNT_ID", "")

# MT5 credentials for connection
MT5_CREDENTIALS = {
    'login': None,
    'password': None,
    'server': None
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
        
        # Initialize MT5 connection if configured
        if METAAPI_AVAILABLE and METAAPI_TOKEN and MT5_ACCOUNT_ID:
            print("✅ MetaAPI configured - MT5 integration enabled")
            # Start market monitor
            if not market_monitor_active:
                asyncio.create_task(start_market_monitor())
        else:
            print("⚠️ MetaAPI not configured - Discord-only mode")

bot = TradingBot()

# Global storage for active signals and market monitoring
active_signals = {}  # Format: {message_id: {pair, entry_price, tp1, tp2, tp3, sl, channels, entry_type, trade_id}}
market_monitor_active = False

# Message variations for TP/SL hits
TP1_MESSAGES = [
    "@everyone TP1 has been hit. First target secured, let's keep it going. Next stop: TP2 📈🔥",
    "@everyone TP1 smashed. Secure some profits if you'd like and let's aim for TP2 🎯💪",
    "@everyone We've just hit TP1. Nice start. The current momentum is looking good for TP2 🚀📊",
    "@everyone TP1 has been hit! Keep your eyes on the next level. TP2 up next 👀💸",
    "@everyone First milestone hit. The trade is off to a clean start 📉➡️📈",
    "@everyone TP1 has been reached. Let's keep the discipline and push for TP2 💼🔁",
    "@everyone First TP level hit! TP1 is in. Stay focused as we aim for TP2 & TP3! 💹🚀",
    "@everyone TP1 locked in. Let's keep monitoring price action and go for TP2 💰📍",
    "@everyone TP1 has been reached. Trade is moving as planned. Next stop: TP2 🔄📊",
    "@everyone TP1 hit. Great entry. now let's trail it smart toward TP2 🧠📈"
]

TP2_MESSAGES = [
    "@everyone TP1 & TP2 have both been hit :rocket::rocket: move your SL to breakeven and lets get TP3 :money_with_wings:",
    "@everyone TP2 has been hit :rocket::rocket: move your SL to breakeven and lets get TP3 :money_with_wings:",
    "@everyone TP2 has been hit :rocket::rocket: move your sl to breakeven, partially close the trade and lets get tp3 :dart::dart::dart:",
    "@everyone TP2 has been hit:money_with_wings: please move your SL to breakeven, partially close the trade and lets go for TP3 :rocket:",
    "@everyone TP2 has been hit. Move your SL to breakeven and secure those profits. Let's push for TP3. we're not done yet 🚀💰",
    "@everyone TP2 has officially been smashed. Move SL to breakeven, partial close if you haven't already. TP3 is calling 📈🔥",
    "@everyone TP2 just got hit. Lock in those gains by moving your SL to breakeven. TP3 is the next target so let's stay sharp and ride this momentum 💪📊",
    "@everyone Another level cleared as TP2 has been hit. Shift SL to breakeven and lock it in. Eyes on TP3 now so let's finish strong 🧠🎯",
    "@everyone TP2 has been hit. Move your SL to breakeven immediately. This setup is moving clean and TP3 is well within reach 🚀🔒",
    "@everyone Great move traders, TP2 has been tagged. Time to shift SL to breakeven and secure the bag. TP3 is the final boss and we're coming for it 💼⚔️"
]

TP3_MESSAGES = [
    "@everyone TP3 hit. Full target smashed, perfect execution 🔥🔥🔥",
    "@everyone Huge win, TP3 reached. Congrats to everyone who followed 📊🚀",
    "@everyone TP3 just got hit. Close it out and lock in profits 💸🎯",
    "@everyone TP3 tagged. That wraps up the full setup — solid trade 💪💼",
    "@everyone TP3 locked in. Flawless setup from entry to exit 🙌📈",
    "@everyone TP3 hit. This one went exactly as expected. Great job ✅💰",
    "@everyone TP3 has been reached. Hope you secured profits all the way through 🏁📊",
    "@everyone TP3 reached. Strategy and patience paid off big time 🔍🚀",
    "@everyone Final target hit. Huge win for FX Pip Pioneers 🔥💸",
    "@everyone TP3 secured. That's the result of following the plan 💼💎"
]

SL_MESSAGES = [
    "@everyone This one hit SL. It happens. Let's stay focused and get the next one 🔄🧠",
    "@everyone SL has been hit. Risk was managed, we move on 💪📉",
    "@everyone This setup didn't go as planned and hit SL. On to the next 📊",
    "@everyone SL tagged. It's all part of the process. Stay disciplined 💼📚",
    "@everyone SL hit. Losses are part of trading. We bounce back 📈⏭️",
    "@everyone SL reached. Trust the process and prepare for the next opportunity 🔄🧠",
    "@everyone SL was hit on this one. We took the loss, now let's stay sharp 🔁💪",
    "@everyone SL hit. It's part of the game. Let's stay focused on quality 📉🎯",
    "@everyone This trade hit SL. Discipline keeps us in the game 💼🧘‍♂️",
    "@everyone SL tagged. The next setup could be the win that makes the week 🔍📊"
]

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

# MetaAPI MT5 Integration Functions
async def initialize_metaapi():
    """Initialize MetaApi connection for MT5 trading"""
    global METAAPI_AVAILABLE, MetaApi
    
    # Try to import MetaAPI if not already available
    if not METAAPI_AVAILABLE:
        if not try_import_metaapi():
            print("MetaAPI not available - skipping MT5 integration")
            return None
    
    if not METAAPI_TOKEN or not MT5_ACCOUNT_ID:
        print("MetaAPI not configured - skipping MT5 integration")
        return None
    
    try:
        print(f"Initializing MetaAPI connection...")
        api = MetaApi(METAAPI_TOKEN)
        account = await api.metatrader_account_api.get_account(MT5_ACCOUNT_ID)
        
        # Check if account is deployed
        if account.state != 'DEPLOYED':
            print("MetaAPI account not deployed - deploying...")
            await account.deploy()
            await account.wait_deployed()
        
        # Connect to account
        connection = account.get_streaming_connection()
        await connection.connect()
        await connection.wait_synchronized()
        
        print("✅ MetaAPI connected successfully")
        return connection
    except Exception as e:
        print(f"❌ MetaAPI connection failed: {e}")
        return None

async def place_mt5_trade(pair: str, entry_price: float, tp_price: float, sl_price: float, entry_type: str, lot_size: float = 0.01):
    """Place a trade on MT5 via MetaAPI"""
    try:
        connection = await initialize_metaapi()
        if not connection:
            print("MT5 trade skipped - no connection")
            return None
        
        # Determine trade direction
        is_buy = entry_type.lower().startswith('buy')
        trade_type = 'ORDER_TYPE_BUY' if is_buy else 'ORDER_TYPE_SELL'
        
        # Create trade request
        trade_request = {
            'actionType': 'ORDER_TYPE_BUY' if is_buy else 'ORDER_TYPE_SELL',
            'symbol': pair,
            'volume': lot_size,
            'type': 'MARKET',
            'stopLoss': sl_price,
            'takeProfit': tp_price,
            'comment': f'Discord Bot - {entry_type}'
        }
        
        # Execute trade
        result = await connection.create_market_order(trade_request)
        
        if result and 'positionId' in result:
            print(f"✅ MT5 trade placed: {pair} {entry_type} at {entry_price}")
            return result['positionId']
        else:
            print(f"❌ MT5 trade failed: {result}")
            return None
            
    except Exception as e:
        print(f"❌ MT5 trade error: {e}")
        return None

async def move_sl_to_breakeven(position_id: str, entry_price: float):
    """Move stop loss to breakeven (entry price)"""
    try:
        connection = await initialize_metaapi()
        if not connection or not position_id:
            return False
        
        # Get current position
        positions = await connection.get_positions()
        position = next((p for p in positions if p['id'] == position_id), None)
        
        if not position:
            print(f"Position {position_id} not found")
            return False
        
        # Modify stop loss to entry price
        result = await connection.modify_position(position_id, entry_price, position.get('takeProfit'))
        
        if result:
            print(f"✅ SL moved to breakeven at {entry_price}")
            return True
        else:
            print(f"❌ Failed to move SL to breakeven")
            return False
            
    except Exception as e:
        print(f"❌ Breakeven error: {e}")
        return False

async def get_current_price(pair: str):
    """Get current market price for a pair"""
    try:
        connection = await initialize_metaapi()
        if not connection:
            return None
        
        # Get current tick data
        tick = await connection.get_symbol_price(pair)
        
        if tick:
            # Return bid price (for selling) or ask price (for buying)
            return {
                'bid': tick.get('bid', 0),
                'ask': tick.get('ask', 0),
                'price': (tick.get('bid', 0) + tick.get('ask', 0)) / 2
            }
        return None
        
    except Exception as e:
        print(f"❌ Price fetch error for {pair}: {e}")
        return None

async def start_market_monitor():
    """Start monitoring market prices for TP/SL hits"""
    global market_monitor_active
    
    if market_monitor_active:
        return
    
    market_monitor_active = True
    print("🚀 Market monitor started")
    
    while market_monitor_active:
        try:
            if not active_signals:
                await asyncio.sleep(5)
                continue
            
            # Check each active signal
            for message_id, signal_data in list(active_signals.items()):
                await check_signal_levels(message_id, signal_data)
            
            await asyncio.sleep(2)  # Check every 2 seconds
            
        except Exception as e:
            print(f"❌ Market monitor error: {e}")
            await asyncio.sleep(10)

async def check_signal_levels(message_id: int, signal_data: dict):
    """Check if TP or SL levels have been hit for a signal"""
    try:
        pair = signal_data['pair']
        entry_type = signal_data['entry_type']
        is_buy = entry_type.lower().startswith('buy')
        
        # Get current price
        price_data = await get_current_price(pair)
        if not price_data:
            return
        
        current_price = price_data['bid'] if not is_buy else price_data['ask']
        
        # Check TP/SL levels
        tp1_hit = False
        tp2_hit = False
        tp3_hit = False
        sl_hit = False
        
        if is_buy:
            # Buy trade - price going up hits TPs, going down hits SL
            if current_price >= signal_data['tp1_raw'] and not signal_data.get('tp1_hit'):
                tp1_hit = True
            if current_price >= signal_data['tp2_raw'] and not signal_data.get('tp2_hit'):
                tp2_hit = True
            if current_price >= signal_data['tp3_raw'] and not signal_data.get('tp3_hit'):
                tp3_hit = True
            if current_price <= signal_data['sl_raw'] and not signal_data.get('sl_hit'):
                sl_hit = True
        else:
            # Sell trade - price going down hits TPs, going up hits SL
            if current_price <= signal_data['tp1_raw'] and not signal_data.get('tp1_hit'):
                tp1_hit = True
            if current_price <= signal_data['tp2_raw'] and not signal_data.get('tp2_hit'):
                tp2_hit = True
            if current_price <= signal_data['tp3_raw'] and not signal_data.get('tp3_hit'):
                tp3_hit = True
            if current_price >= signal_data['sl_raw'] and not signal_data.get('sl_hit'):
                sl_hit = True
        
        # Handle TP/SL hits
        if tp1_hit:
            await handle_tp_hit(message_id, signal_data, 'tp1')
        if tp2_hit:
            await handle_tp_hit(message_id, signal_data, 'tp2')
        if tp3_hit:
            await handle_tp_hit(message_id, signal_data, 'tp3')
        if sl_hit:
            await handle_sl_hit(message_id, signal_data)
            
    except Exception as e:
        print(f"❌ Signal check error: {e}")

async def handle_tp_hit(message_id: int, signal_data: dict, tp_level: str):
    """Handle when a TP level is hit"""
    try:
        # Mark as hit
        signal_data[f'{tp_level}_hit'] = True
        
        # Special handling for TP2 - move SL to breakeven
        if tp_level == 'tp2' and signal_data.get('trade_id'):
            await move_sl_to_breakeven(signal_data['trade_id'], signal_data['entry_raw'])
        
        # Select random message
        if tp_level == 'tp1':
            message = random.choice(TP1_MESSAGES)
        elif tp_level == 'tp2':
            message = random.choice(TP2_MESSAGES)
        elif tp_level == 'tp3':
            message = random.choice(TP3_MESSAGES)
            # Remove from active signals when TP3 is hit
            active_signals.pop(message_id, None)
        
        # Reply to original message
        await reply_to_signal_message(message_id, signal_data, message)
        
        print(f"✅ {tp_level.upper()} hit for {signal_data['pair']}")
        
    except Exception as e:
        print(f"❌ TP hit handler error: {e}")

async def handle_sl_hit(message_id: int, signal_data: dict):
    """Handle when SL is hit"""
    try:
        # Mark as hit
        signal_data['sl_hit'] = True
        
        # Select random message
        message = random.choice(SL_MESSAGES)
        
        # Reply to original message
        await reply_to_signal_message(message_id, signal_data, message)
        
        # Remove from active signals
        active_signals.pop(message_id, None)
        
        print(f"✅ SL hit for {signal_data['pair']}")
        
    except Exception as e:
        print(f"❌ SL hit handler error: {e}")

async def reply_to_signal_message(message_id: int, signal_data: dict, reply_text: str):
    """Reply to the original signal message in all channels"""
    try:
        for channel_id in signal_data.get('channels', []):
            channel = bot.get_channel(channel_id)
            if channel:
                try:
                    # Get the original message
                    original_message = await channel.fetch_message(message_id)
                    if original_message:
                        await original_message.reply(reply_text)
                except discord.NotFound:
                    print(f"Original message not found in channel {channel_id}")
                except Exception as e:
                    print(f"Error replying in channel {channel_id}: {e}")
                    
    except Exception as e:
        print(f"❌ Reply error: {e}")

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
                    await target_channel.send(signal_message)
                    sent_channels.append(target_channel.name)
                except discord.Forbidden:
                    await interaction.followup.send(f"❌ No permission to send to #{target_channel.name}", ephemeral=True)
                except Exception as e:
                    await interaction.followup.send(f"❌ Error sending to #{target_channel.name}: {str(e)}", ephemeral=True)
        
        # Execute MT5 trade if MetaAPI is configured
        trade_id = None
        if METAAPI_AVAILABLE and METAAPI_TOKEN and MT5_ACCOUNT_ID:
            try:
                trade_id = await place_mt5_trade(
                    pair=pair,
                    entry_price=levels['entry_raw'],
                    tp_price=levels['tp3_raw'],  # Always use TP3 as final target
                    sl_price=levels['sl_raw'],
                    entry_type=entry_type
                )
                if trade_id:
                    print(f"✅ MT5 trade opened: {trade_id}")
            except Exception as e:
                print(f"❌ MT5 trade failed: {e}")
        
        # Store signal for monitoring if messages were sent
        if sent_channels:
            # Get channel IDs for storage
            channel_ids = []
            for channel_identifier in channel_list:
                if channel_identifier.startswith('<#') and channel_identifier.endswith('>'):
                    channel_ids.append(int(channel_identifier[2:-1]))
                elif channel_identifier.isdigit():
                    channel_ids.append(int(channel_identifier))
                else:
                    target_channel = discord.utils.get(interaction.guild.channels, name=channel_identifier)
                    if target_channel:
                        channel_ids.append(target_channel.id)
            
            # Store the signal data for each sent message
            for channel_id in channel_ids:
                channel = bot.get_channel(channel_id)
                if channel:
                    try:
                        # Get the last message sent to this channel (our signal)
                        async for message in channel.history(limit=1):
                            if message.author == bot.user:
                                active_signals[message.id] = {
                                    'pair': pair,
                                    'entry_type': entry_type,
                                    'entry_raw': levels['entry_raw'],
                                    'tp1_raw': levels['tp1_raw'],
                                    'tp2_raw': levels['tp2_raw'],
                                    'tp3_raw': levels['tp3_raw'],
                                    'sl_raw': levels['sl_raw'],
                                    'channels': channel_ids,
                                    'trade_id': trade_id,
                                    'tp1_hit': False,
                                    'tp2_hit': False,
                                    'tp3_hit': False,
                                    'sl_hit': False
                                }
                                break
                    except Exception as e:
                        print(f"Error storing signal for channel {channel_id}: {e}")
            
            # Start market monitor if not already running
            if not market_monitor_active:
                asyncio.create_task(start_market_monitor())
            
            await interaction.response.send_message(f"✅ Signal sent to: {', '.join(sent_channels)}", ephemeral=True)
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

@bot.tree.command(name="monitoring", description="Show currently active signals and their status")
async def monitoring_command(interaction: discord.Interaction):
    """Show currently active signals and their status"""
    try:
        if not active_signals:
            await interaction.response.send_message("📊 No active signals currently being monitored.", ephemeral=True)
            return
        
        status_message = "**📊 ACTIVE SIGNALS MONITORING**\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        for message_id, signal_data in active_signals.items():
            tp1_status = "✅" if signal_data.get('tp1_hit') else "⏳"
            tp2_status = "✅" if signal_data.get('tp2_hit') else "⏳"
            tp3_status = "✅" if signal_data.get('tp3_hit') else "⏳"
            sl_status = "❌" if signal_data.get('sl_hit') else "⏳"
            
            mt5_status = "🔗 Connected" if signal_data.get('trade_id') else "💬 Discord Only"
            
            status_message += f"**{signal_data['pair']}** ({signal_data['entry_type']})\n"
            status_message += f"• TP1: {tp1_status} TP2: {tp2_status} TP3: {tp3_status} SL: {sl_status}\n"
            status_message += f"• MT5: {mt5_status}\n\n"
        
        status_message += f"**Market Monitor:** {'🟢 Active' if market_monitor_active else '🔴 Inactive'}\n"
        status_message += f"**Total Active:** {len(active_signals)} signals"
        
        await interaction.response.send_message(status_message, ephemeral=True)
        
    except Exception as e:
        await interaction.response.send_message(f"❌ Error getting monitoring status: {str(e)}", ephemeral=True)

@bot.tree.command(name="mt5status", description="Check MetaTrader 5 connection status")
async def mt5status_command(interaction: discord.Interaction):
    """Check current MT5 connection status"""
    try:
        status_msg = f"**📊 MT5 Integration Status**\n\n"
        
        # Check MetaAPI SDK availability
        if not METAAPI_AVAILABLE:
            status_msg += "❌ MetaAPI SDK not available\n"
            if metaapi_error:
                status_msg += f"Error: {metaapi_error[:100]}...\n"
            
            # Try to import it now
            status_msg += "🔄 Attempting dynamic import...\n"
            if try_import_metaapi():
                status_msg += "✅ MetaAPI SDK loaded successfully!\n"
            else:
                status_msg += "❌ Dynamic import failed\n"
                status_msg += "📦 Install command: `pip install metaapi-cloud-sdk`\n"
                
        elif not METAAPI_TOKEN:
            status_msg += "❌ MetaAPI token not configured\n"
            status_msg += "Set METAAPI_TOKEN environment variable"
        elif not MT5_ACCOUNT_ID:
            status_msg += "❌ MT5 account ID not configured\n"
            status_msg += "Set MT5_ACCOUNT_ID environment variable"
        else:
            # Test connection
            try:
                connection = await initialize_metaapi()
                if connection:
                    status_msg += "✅ MetaAPI connection active\n"
                    status_msg += f"🎯 Account ID: {MT5_ACCOUNT_ID[:8]}...\n"
                    status_msg += f"🌐 Status: Connected\n"
                    status_msg += f"📈 Auto-trading: Enabled\n"
                    status_msg += f"🔄 Market Monitor: {'Active' if market_monitor_active else 'Standby'}"
                else:
                    status_msg += "❌ MetaAPI connection failed\n"
                    status_msg += "Check account deployment and credentials"
            except Exception as e:
                status_msg += f"❌ Connection error: {str(e)[:100]}..."
        
        await interaction.response.send_message(status_msg, ephemeral=True)
        
    except Exception as e:
        await interaction.response.send_message(f"❌ Error checking MT5 status: {str(e)}", ephemeral=True)

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

async def start_bot():
    if not DISCORD_TOKEN:
        print("❌ Discord token not found. Please check your environment variables.")
        return
    
    try:
        await bot.start(DISCORD_TOKEN)
    except discord.LoginFailure:
        print("❌ Invalid Discord token. Please check your token parts in environment variables.")
    except Exception as e:
        print(f"❌ Failed to start bot: {e}")

async def main():
    # Start web server first (required for Render.com)
    print("Starting web server...")
    web_task = asyncio.create_task(start_web_server())
    
    # Wait a moment for web server to initialize
    await asyncio.sleep(1)
    
    # Start Discord bot (don't let it crash the web server)
    print("Starting Discord bot...")
    bot_task = asyncio.create_task(start_bot())
    
    # Keep both running, but prioritize web server for Render
    try:
        await asyncio.gather(web_task, bot_task, return_exceptions=True)
    except Exception as e:
        print(f"Error in main: {e}")
        # Keep web server running even if bot fails
        await web_task

# Run the bot
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped.")