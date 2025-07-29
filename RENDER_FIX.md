# Render Deployment Fix for Telegram Integration

## Problem
Render is not installing pyrogram and tgcrypto packages correctly, causing the Telegram integration to fail.

## Solution 1: Manual Build Command
Update your Render service build command to:
```
pip install --upgrade pip && pip install discord.py==2.5.2 python-dotenv==1.1.0 aiohttp==3.12.13 requests pyrogram==2.0.106 tgcrypto==1.2.5
```

## Solution 2: Alternative Package Installation
If the above doesn't work, try this build command:
```
pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir discord.py python-dotenv aiohttp requests && pip install --no-cache-dir pyrogram tgcrypto
```

## Solution 3: Force Reinstall
If packages are cached incorrectly, use:
```
pip install --upgrade pip --force-reinstall && pip install --force-reinstall pyrogram==2.0.106 tgcrypto==1.2.5 discord.py==2.5.2 python-dotenv==1.1.0 aiohttp==3.12.13 requests
```

## Verification
After deployment, check the build logs to ensure you see:
- "Successfully installed pyrogram-2.0.106"
- "Successfully installed tgcrypto-1.2.5"

## Environment Variables Required
Make sure all these are set in Render:
```
DISCORD_TOKEN_PART1
DISCORD_TOKEN_PART2
DISCORD_CLIENT_ID_PART1
DISCORD_CLIENT_ID_PART2
TELEGRAM_API_ID
TELEGRAM_API_HASH
TELEGRAM_PHONE_NUMBER
TELEGRAM_SOURCE_CHAT_ID
TELEGRAM_DEFAULT_CHANNELS
TELEGRAM_DEFAULT_ROLES
```

## Test Command
After deployment, use `/telegram` command in Discord to verify integration status.