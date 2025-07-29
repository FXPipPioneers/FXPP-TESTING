import discord
from discord.ext import commands, tasks
from discord import app_commands
import os
from dotenv import load_dotenv
import asyncio
from aiohttp import web
import json
from datetime import datetime, timedelta
import re

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

# Bot setup with intents
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True  # Required for member join events

# Auto-role system storage
AUTO_ROLE_CONFIG = {
    "enabled": False,
    "role_id": None,
    "duration_hours": 24,
    "custom_message": "Your 1-day free trial has ended. Thank you for trying our service!",
    "active_members": {}  # member_id: {"role_added_time": datetime, "role_id": role_id}
}

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
        
        # Start the role removal task
        if not self.role_removal_task.is_running():
            self.role_removal_task.start()
        
        # Load auto-role config if it exists
        await self.load_auto_role_config()
        
        # Check Telegram integration
        if telegram_client:
            print("✅ Telegram integration ready")
        else:
            print("⚠️ Telegram integration not configured")

    async def on_member_join(self, member):
        """Handle new member joins and assign auto-role if enabled"""
        if not AUTO_ROLE_CONFIG["enabled"] or not AUTO_ROLE_CONFIG["role_id"]:
            return
        
        try:
            role = member.guild.get_role(AUTO_ROLE_CONFIG["role_id"])
            if not role:
                print(f"❌ Auto-role not found in guild {member.guild.name}")
                return
            
            # Add the role to the new member
            await member.add_roles(role, reason="Auto-role for new member")
            
            # Record the member for role removal tracking
            AUTO_ROLE_CONFIG["active_members"][str(member.id)] = {
                "role_added_time": datetime.now().isoformat(),
                "role_id": AUTO_ROLE_CONFIG["role_id"],
                "guild_id": member.guild.id
            }
            
            # Save the updated config
            await self.save_auto_role_config()
            
            print(f"✅ Auto-role '{role.name}' added to {member.display_name} ({member.id})")
            
        except discord.Forbidden:
            print(f"❌ No permission to assign role to {member.display_name}")
        except Exception as e:
            print(f"❌ Error assigning auto-role to {member.display_name}: {str(e)}")

    async def load_auto_role_config(self):
        """Load auto-role configuration from file if it exists"""
        try:
            if os.path.exists("auto_role_config.json"):
                with open("auto_role_config.json", "r") as f:
                    loaded_config = json.load(f)
                    AUTO_ROLE_CONFIG.update(loaded_config)
                print("✅ Auto-role configuration loaded")
        except Exception as e:
            print(f"⚠️ Error loading auto-role config: {str(e)}")

    async def save_auto_role_config(self):
        """Save auto-role configuration to file"""
        try:
            with open("auto_role_config.json", "w") as f:
                json.dump(AUTO_ROLE_CONFIG, f, indent=2)
        except Exception as e:
            print(f"❌ Error saving auto-role config: {str(e)}")

    @tasks.loop(minutes=30)  # Check every 30 minutes
    async def role_removal_task(self):
        """Background task to remove expired roles and send DMs"""
        if not AUTO_ROLE_CONFIG["enabled"] or not AUTO_ROLE_CONFIG["active_members"]:
            return
        
        current_time = datetime.now()
        expired_members = []
        
        for member_id, data in AUTO_ROLE_CONFIG["active_members"].items():
            try:
                # Parse the stored datetime
                role_added_time = datetime.fromisoformat(data["role_added_time"])
                duration = timedelta(hours=AUTO_ROLE_CONFIG["duration_hours"])
                
                if current_time >= role_added_time + duration:
                    expired_members.append(member_id)
            except Exception as e:
                print(f"❌ Error processing member {member_id}: {str(e)}")
                expired_members.append(member_id)  # Remove corrupted entries
        
        # Process expired members
        for member_id in expired_members:
            await self.remove_expired_role(member_id)
        
        # Save updated config if there were changes
        if expired_members:
            await self.save_auto_role_config()

    async def remove_expired_role(self, member_id):
        """Remove expired role from member and send DM"""
        try:
            data = AUTO_ROLE_CONFIG["active_members"].get(member_id)
            if not data:
                return
            
            # Get the guild and member
            guild = self.get_guild(data["guild_id"])
            if not guild:
                print(f"❌ Guild not found for member {member_id}")
                del AUTO_ROLE_CONFIG["active_members"][member_id]
                return
            
            member = guild.get_member(int(member_id))
            if not member:
                print(f"❌ Member {member_id} not found in guild")
                del AUTO_ROLE_CONFIG["active_members"][member_id]
                return
            
            # Get the role
            role = guild.get_role(data["role_id"])
            if role and role in member.roles:
                await member.remove_roles(role, reason="Auto-role expired")
                print(f"✅ Removed expired role '{role.name}' from {member.display_name}")
            
            # Send DM to the member
            try:
                await member.send(AUTO_ROLE_CONFIG["custom_message"])
                print(f"✅ Sent expiration DM to {member.display_name}")
            except discord.Forbidden:
                print(f"⚠️ Could not send DM to {member.display_name} (DMs disabled)")
            except Exception as e:
                print(f"❌ Error sending DM to {member.display_name}: {str(e)}")
            
            # Remove from active tracking
            del AUTO_ROLE_CONFIG["active_members"][member_id]
            
        except Exception as e:
            print(f"❌ Error removing expired role for member {member_id}: {str(e)}")
            # Clean up corrupted entry
            if member_id in AUTO_ROLE_CONFIG["active_members"]:
                del AUTO_ROLE_CONFIG["active_members"][member_id]

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
    """Parse trading signal from Telegram message text"""
    signal_data = {}
    
    # Common trading pair patterns
    pair_patterns = [
        r'(XAUUSD|GOLD|XAU)',
        r'(GBPJPY|GBP/JPY)',
        r'(EURUSD|EUR/USD)',
        r'(GBPUSD|GBP/USD)',
        r'(AUDUSD|AUD/USD)',
        r'(NZDUSD|NZD/USD)',
        r'(USDCAD|USD/CAD)',
        r'(USDCHF|USD/CHF)',
        r'(GBPCHF|GBP/CHF)',
        r'(CADCHF|CAD/CHF)',
        r'(AUDCHF|AUD/CHF)',
        r'(CHFJPY|CHF/JPY)',
        r'(CADJPY|CAD/JPY)',
        r'(AUDJPY|AUD/JPY)',
        r'(GBPCAD|GBP/CAD)',
        r'(EURCAD|EUR/CAD)',
        r'(AUDCAD|AUD/CAD)',
        r'(AUDNZD|AUD/NZD)',
        r'(US100|NASDAQ|NAS100)',
        r'(US500|S&P500|SPX500)',
        r'(GER40|DAX|GERMANY40)',
        r'(BTCUSD|BTC/USD|BITCOIN)',
        r'(USDJPY|USD/JPY)'
    ]
    
    # Try to find trading pair
    for pattern in pair_patterns:
        match = re.search(pattern, message_text.upper())
        if match:
            pair_found = match.group(1)
            # Normalize pair names
            if pair_found in ['GOLD', 'XAU']:
                signal_data['pair'] = 'XAUUSD'
            elif pair_found in ['NASDAQ', 'NAS100']:
                signal_data['pair'] = 'US100'
            elif pair_found in ['S&P500', 'SPX500']:
                signal_data['pair'] = 'US500'
            elif pair_found in ['DAX', 'GERMANY40']:
                signal_data['pair'] = 'GER40'
            elif pair_found in ['BTC/USD', 'BITCOIN']:
                signal_data['pair'] = 'BTCUSD'
            elif '/' in pair_found:
                signal_data['pair'] = pair_found.replace('/', '')
            else:
                signal_data['pair'] = pair_found
            break
    
    # Try to find entry type
    entry_patterns = [
        (r'(BUY\s*LIMIT|LONG\s*LIMIT)', 'Buy limit'),
        (r'(SELL\s*LIMIT|SHORT\s*LIMIT)', 'Sell limit'),
        (r'(BUY\s*STOP|LONG\s*STOP|BUY\s*EXECUTION)', 'Buy execution'),
        (r'(SELL\s*STOP|SHORT\s*STOP|SELL\s*EXECUTION)', 'Sell execution'),
        (r'(BUY|LONG)', 'Buy limit'),
        (r'(SELL|SHORT)', 'Sell limit')
    ]
    
    for pattern, entry_type in entry_patterns:
        if re.search(pattern, message_text.upper()):
            signal_data['entry_type'] = entry_type
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

async def forward_telegram_signal(signal_data: dict, original_message: str):
    """Forward parsed signal to Discord using the entry command logic"""
    try:
        if not TELEGRAM_DEFAULT_CHANNELS:
            print("No default channels configured for Telegram forwarding")
            return
        
        # Get default guild (first guild the bot is in)
        guild = bot.guilds[0] if bot.guilds else None
        if not guild:
            print("Bot not in any Discord servers")
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
        
        # Send to configured channels
        channel_list = [ch.strip() for ch in TELEGRAM_DEFAULT_CHANNELS.split(',')]
        sent_channels = []
        sent_messages = []
        channel_ids = []
        
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
                target_channel = discord.utils.get(guild.channels, name=channel_identifier)
            
            if target_channel and isinstance(target_channel, discord.TextChannel):
                try:
                    sent_message = await target_channel.send(signal_message)
                    sent_channels.append(target_channel.name)
                    sent_messages.append(sent_message)
                    channel_ids.append(target_channel.id)
                except Exception as e:
                    print(f"Error sending to #{target_channel.name}: {str(e)}")
        
        if sent_messages:
            print(f"✅ Telegram signal forwarded to {len(sent_channels)} channels: {', '.join(sent_channels)}")
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
        'entry': format_price(entry_price)
    }

@bot.tree.command(name="timedautorole", description="Configure timed auto-role for new members")
@app_commands.describe(
    action="Enable/disable, check status, or list active members",
    role="Role to assign to new members (required when enabling)",
    duration_hours="Duration in hours to keep the role (default: 24)",
    custom_message="Custom message to send when role expires"
)
async def timed_auto_role_command(
    interaction: discord.Interaction,
    action: str,
    role: discord.Role | None = None,
    duration_hours: int = 24,
    custom_message: str | None = None
):
    """Configure the timed auto-role system"""
    
    # Check permissions
    if not hasattr(interaction.user, 'guild_permissions') or not interaction.user.guild_permissions.manage_roles:
        await interaction.response.send_message("❌ You need 'Manage Roles' permission to use this command.", ephemeral=True)
        return
    
    try:
        if action.lower() == "enable":
            if not role:
                await interaction.response.send_message("❌ You must specify a role when enabling auto-role.", ephemeral=True)
                return
            
            # Check if bot has permission to manage the role
            if interaction.guild and interaction.guild.me and role >= interaction.guild.me.top_role:
                await interaction.response.send_message(f"❌ I cannot manage the role '{role.name}' because it's higher than my highest role.", ephemeral=True)
                return
            
            # Update configuration
            AUTO_ROLE_CONFIG["enabled"] = True
            AUTO_ROLE_CONFIG["role_id"] = role.id
            AUTO_ROLE_CONFIG["duration_hours"] = duration_hours
            if custom_message:
                AUTO_ROLE_CONFIG["custom_message"] = custom_message
            
            # Save configuration
            await bot.save_auto_role_config()
            
            await interaction.response.send_message(
                f"✅ **Auto-role system enabled!**\n"
                f"• **Role:** {role.mention}\n"
                f"• **Duration:** {duration_hours} hours\n"
                f"• **Expiration message:** {AUTO_ROLE_CONFIG['custom_message']}\n\n"
                f"New members will automatically receive this role for {duration_hours} hours.",
                ephemeral=True
            )
            
        elif action.lower() == "disable":
            AUTO_ROLE_CONFIG["enabled"] = False
            await bot.save_auto_role_config()
            
            await interaction.response.send_message("✅ Auto-role system disabled. No new roles will be assigned to new members.", ephemeral=True)
            
        elif action.lower() == "status":
            if AUTO_ROLE_CONFIG["enabled"]:
                role = interaction.guild.get_role(AUTO_ROLE_CONFIG["role_id"]) if interaction.guild and AUTO_ROLE_CONFIG["role_id"] else None
                active_count = len(AUTO_ROLE_CONFIG["active_members"])
                
                status_message = f"✅ **Auto-role system is ENABLED**\n"
                if role:
                    status_message += f"• **Role:** {role.mention}\n"
                else:
                    status_message += f"• **Role:** Not found (ID: {AUTO_ROLE_CONFIG['role_id']})\n"
                status_message += f"• **Duration:** {AUTO_ROLE_CONFIG['duration_hours']} hours\n"
                status_message += f"• **Active members:** {active_count}\n"
                status_message += f"• **Expiration message:** {AUTO_ROLE_CONFIG['custom_message']}"
            else:
                status_message = "❌ **Auto-role system is DISABLED**"
            
            await interaction.response.send_message(status_message, ephemeral=True)
            
        elif action.lower() == "list":
            if not AUTO_ROLE_CONFIG["enabled"]:
                await interaction.response.send_message("❌ Auto-role system is disabled. No active members to display.", ephemeral=True)
                return
            
            if not AUTO_ROLE_CONFIG["active_members"]:
                await interaction.response.send_message("📝 No members currently have temporary roles.", ephemeral=True)
                return
            
            # Build the list of active members with time remaining
            current_time = datetime.now()
            member_list = []
            
            for member_id, data in AUTO_ROLE_CONFIG["active_members"].items():
                try:
                    # Get member info
                    guild = interaction.guild
                    if not guild:
                        continue
                        
                    member = guild.get_member(int(member_id))
                    if not member:
                        continue
                    
                    # Calculate time remaining
                    role_added_time = datetime.fromisoformat(data["role_added_time"])
                    duration = timedelta(hours=AUTO_ROLE_CONFIG["duration_hours"])
                    expiry_time = role_added_time + duration
                    time_remaining = expiry_time - current_time
                    
                    if time_remaining.total_seconds() > 0:
                        # Format time remaining
                        hours = int(time_remaining.total_seconds() // 3600)
                        minutes = int((time_remaining.total_seconds() % 3600) // 60)
                        
                        if hours > 0:
                            time_str = f"{hours}h {minutes}m"
                        else:
                            time_str = f"{minutes}m"
                        
                        member_list.append(f"• {member.display_name} - {time_str} remaining")
                    else:
                        # Role should have expired, mark for cleanup
                        member_list.append(f"• {member.display_name} - Expired (pending removal)")
                        
                except Exception as e:
                    print(f"Error processing member {member_id}: {str(e)}")
                    continue
            
            if not member_list:
                await interaction.response.send_message("📝 No valid members found with temporary roles.", ephemeral=True)
                return
            
            # Create the response message
            role = interaction.guild.get_role(AUTO_ROLE_CONFIG["role_id"]) if interaction.guild and AUTO_ROLE_CONFIG["role_id"] else None
            role_name = role.name if role else "Unknown Role"
            
            list_message = f"📋 **Active Temporary Role Members**\n"
            list_message += f"**Role:** {role_name}\n"
            list_message += f"**Total Duration:** {AUTO_ROLE_CONFIG['duration_hours']} hours\n\n"
            list_message += "\n".join(member_list[:20])  # Limit to 20 members to avoid message length issues
            
            if len(member_list) > 20:
                list_message += f"\n\n*...and {len(member_list) - 20} more members*"
            
            await interaction.response.send_message(list_message, ephemeral=True)
            
        else:
            await interaction.response.send_message("❌ Invalid action. Use 'enable', 'disable', 'status', or 'list'.", ephemeral=True)
            
    except Exception as e:
        await interaction.response.send_message(f"❌ Error configuring auto-role: {str(e)}", ephemeral=True)

@timed_auto_role_command.autocomplete('action')
async def action_autocomplete(interaction: discord.Interaction, current: str):
    actions = ['enable', 'disable', 'status', 'list']
    return [
        app_commands.Choice(name=action, value=action)
        for action in actions if current.lower() in action.lower()
    ]

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
                    role = discord.utils.get(interaction.guild.roles, name=role_name) if interaction.guild else None
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
                target_channel = discord.utils.get(interaction.guild.channels, name=channel_identifier) if interaction.guild else None
            
            if target_channel and isinstance(target_channel, discord.TextChannel):
                try:
                    await target_channel.send(signal_message)
                    sent_channels.append(target_channel.name)
                except discord.Forbidden:
                    await interaction.followup.send(f"❌ No permission to send to #{target_channel.name}", ephemeral=True)
                except Exception as e:
                    await interaction.followup.send(f"❌ Error sending to #{target_channel.name}: {str(e)}", ephemeral=True)
        
        if sent_channels:
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
• SL Hits: **{sl_hits}** ({sl_percent})

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
                target_channel = discord.utils.get(interaction.guild.channels, name=channel_identifier) if interaction.guild else None
            
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
        if not TELEGRAM_AVAILABLE:
            status_msg += "❌ Telegram integration not installed\n"
            status_msg += "💡 Install with: pip install pyrogram tgcrypto\n\n"
        else:
            status_msg += "✅ Telegram integration installed\n\n"
        
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
        if telegram_client and TELEGRAM_API_ID and TELEGRAM_API_HASH:
            status_msg += "\n\n🎯 Status: Ready for signal forwarding"
        else:
            status_msg += "\n\n❌ Status: Not configured"
            status_msg += "\n💡 Configure environment variables to enable"
        
        await interaction.response.send_message(status_msg, ephemeral=True)
        
    except Exception as e:
        await interaction.response.send_message(f"❌ Error checking Telegram status: {str(e)}", ephemeral=True)

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

# Run the bot
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped.")