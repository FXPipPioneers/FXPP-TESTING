# Telegram Integration Setup Guide

This guide will walk you through getting all the Telegram API credentials and configuration needed for your Discord trading bot.

## Step 1: Get Telegram API Credentials

### 1.1 Create Telegram API Application
1. Open your web browser and go to **https://my.telegram.org**
2. Enter your phone number (including country code, e.g., +1234567890)
3. Click "Next"
4. You'll receive a confirmation code via Telegram on your phone
5. Enter the confirmation code
6. If prompted, enter your 2FA password

### 1.2 Create New Application
1. Once logged in, click **"API Development Tools"**
2. Fill out the form:
   - **App title**: "Discord Trading Bot" (or any name you prefer)
   - **Short name**: "discord-bot" (or any short name)
   - **URL**: Leave blank or enter your website
   - **Platform**: Select "Other"
   - **Description**: "Bot for forwarding trading signals"
3. Click **"Create Application"**

### 1.3 Copy Your API Credentials
After creating the application, you'll see:
- **API ID**: A number like `12345678` - Copy this
- **API Hash**: A string like `abcdef1234567890abcdef1234567890` - Copy this

**Save these values - you'll need them for your environment variables:**
- `TELEGRAM_API_ID` = Your API ID number
- `TELEGRAM_API_HASH` = Your API Hash string

## Step 2: Get Your Phone Number

Simply use your phone number in international format:
- **Format**: +[country code][phone number]
- **Example**: +1234567890
- **Save as**: `TELEGRAM_PHONE_NUMBER`

## Step 3: Find Channel IDs and Chat IDs

### 3.1 Find Discord Channel IDs
1. Open Discord and go to your server
2. Right-click on any channel name
3. Select "Copy Channel ID" (you may need to enable Developer Mode first)
4. **To enable Developer Mode:**
   - Click the gear icon (User Settings) in Discord
   - Go to "Advanced" in the left sidebar
   - Toggle "Developer Mode" ON

**Example Discord Channel IDs:**
- `987654321098765432` (for #signals channel)
- `123456789012345678` (for #trading-room channel)

### 3.2 Find Telegram Chat IDs

#### Option A: Use a Telegram Bot to Get Chat ID
1. Search for **@userinfobot** on Telegram
2. Start a conversation with it
3. Forward a message from the trading group you want to monitor
4. The bot will show you the chat ID (it will be a negative number for groups)

#### Option B: Use @RawDataBot
1. Search for **@RawDataBot** on Telegram
2. Start a conversation with it
3. Forward a message from your trading group
4. Look for the "chat" section in the response - the "id" field is your chat ID

#### Option C: Manual Method
1. Add your bot to the trading group (after you create it)
2. Send a test message in the group
3. Check the logs - the chat ID will appear in the console

**Example Chat IDs:**
- `-1001234567890` (for group chats, always negative)
- `1234567890` (for private chats, always positive)

## Step 4: Environment Variables Summary

Here's what you'll set in your Render.com dashboard:

### Required Telegram Variables:
```
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=abcdef1234567890abcdef1234567890
TELEGRAM_PHONE_NUMBER=+1234567890
```

### Optional Configuration:
```
TELEGRAM_SOURCE_CHAT_ID=-1001234567890
TELEGRAM_DEFAULT_CHANNELS=987654321098765432,123456789012345678
TELEGRAM_DEFAULT_ROLES=traders,vip-members
```

### NEW: Channel Mapping Variables (Required for Smart Routing):
```
FREE_SIGNALS_CHANNEL=987654321098765432
VIP_SIGNALS_CHANNEL=123456789012345678
PREMIUM_SIGNALS_CHANNEL=456789012345678901
```

**Note:** The channel mapping variables are required for the new smart routing feature that automatically sends:
- XAUUSD signals to Free + VIP + Premium channels (once per day)
- Other signals to VIP + Premium channels (4 per day)
- Additional signals to Premium channel only (6-8 more per day)

## Step 5: Setting Up on Render.com

1. Go to your Render.com dashboard
2. Click on your Discord bot service
3. Go to "Environment" tab
4. Click "Add Environment Variable"
5. Add each variable one by one:

**Required Variables:**
- **Key**: `TELEGRAM_API_ID` **Value**: `12345678`
- **Key**: `TELEGRAM_API_HASH` **Value**: `abcdef1234567890abcdef1234567890`
- **Key**: `TELEGRAM_PHONE_NUMBER` **Value**: `+1234567890`

**Channel Mapping Variables (Required for Smart Routing):**
- **Key**: `FREE_SIGNALS_CHANNEL` **Value**: `987654321098765432`
- **Key**: `VIP_SIGNALS_CHANNEL` **Value**: `123456789012345678`
- **Key**: `PREMIUM_SIGNALS_CHANNEL` **Value**: `456789012345678901`

**Optional Variables:**
- **Key**: `TELEGRAM_SOURCE_CHAT_ID` **Value**: `-1001234567890`
- **Key**: `TELEGRAM_DEFAULT_CHANNELS` **Value**: `987654321098765432,123456789012345678`
- **Key**: `TELEGRAM_DEFAULT_ROLES` **Value**: `traders,vip-members`

6. Click "Save Changes"
7. Your service will automatically redeploy

## Step 6: Testing the Integration

1. After deployment, go to your Discord server
2. Use the `/telegram` command to check integration status
3. If everything is configured correctly, you should see:
   - ✅ Telegram integration installed
   - ✅ API ID configured
   - ✅ API Hash configured
   - ✅ Phone number configured
   - 🎯 Status: Ready for signal forwarding

## Step 7: New Smart Routing Features

### Signal Filtering
The bot now only forwards messages that contain ALL three keywords:
- **ENTRY**
- **TAKE PROFIT**
- **STOP LOSS**

### Smart Channel Routing
- **XAUUSD signals**: Automatically sent to Free + VIP + Premium channels (once per day)
- **Other pairs**: Sent to VIP + Premium channels (up to 4 per day)
- **Additional signals**: Sent to Premium channel only (up to 6-8 more per day)

### Management Commands
Use `/tracking` command to:
- **Sleep mode**: `/tracking sleep xauusd` - Disable XAUUSD tracking
- **Resume tracking**: `/tracking resume xauusd` - Re-enable XAUUSD tracking  
- **Check status**: `/tracking status` - See what's being tracked
- **Control all**: `/tracking sleep all` - Disable all tracking

## Configuration Options Explained

### TELEGRAM_SOURCE_CHAT_ID (Optional)
- If set: Only monitors the specific chat ID
- If not set: Monitors all accessible chats
- **Recommendation**: Set this to avoid unwanted message forwarding

### TELEGRAM_DEFAULT_CHANNELS (Optional)
- Discord channel IDs where Telegram signals will be forwarded
- Use comma-separated channel IDs (not names)
- **Example**: `987654321098765432,123456789012345678`

### TELEGRAM_DEFAULT_ROLES (Optional)
- Discord roles to mention when forwarding signals
- Use comma-separated role names
- **Example**: `traders,vip-members,everyone`

## Troubleshooting

### Common Issues:

1. **"Invalid phone number"**
   - Make sure to include country code with + symbol
   - Example: +1234567890 (not 1234567890)

2. **"API credentials invalid"**
   - Double-check API ID and Hash from my.telegram.org
   - Make sure there are no extra spaces

3. **"Chat not found"**
   - Make sure the chat ID is correct
   - For groups, the ID should be negative (start with -)
   - For private chats, the ID should be positive

4. **"No messages being forwarded"**
   - Check that TELEGRAM_SOURCE_CHAT_ID matches your trading group
   - Verify the bot account has access to the group
   - Check Discord channel IDs are correct

### Getting Help:
- Use `/telegram` command in Discord to check configuration status
- Check Render.com logs for detailed error messages
- Verify all environment variables are set correctly

---

**Security Note**: Never share your API credentials publicly. These should only be stored in your secure Render.com environment variables.