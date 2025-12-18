import discord
from discord.ext import commands
import asyncio
from datetime import datetime, timedelta
from collections import defaultdict
from flask import Flask
from threading import Thread
import os

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)

channel_creation_tracker = defaultdict(list)
message_spam_tracker = defaultdict(list)
join_tracker = defaultdict(list)
raid_mode = False
emergency_channel_ids = set()

# Flask for health check (prevents Render spin-down)
app = Flask(__name__)

@app.route('/ping')
def ping():
    return "PONG! Anti-Raid Bot is alive."

@app.route('/health')
def health():
    return "OK"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", 8080)))

@bot.event
async def on_ready():
    print(f'🛡️ ANTI-RAID BOT ONLINE: {bot.user}')
    Thread(target=run_flask).start()  # Start Flask to keep Render awake

@bot.event
async def on_guild_channel_create(channel):
    guild = channel.guild
    now = datetime.now()

    if channel.id in emergency_channel_ids:
        return

    channel_creation_tracker[guild.id].append(now)
    channel_creation_tracker[guild.id] = [
        time for time in channel_creation_tracker[guild.id]
        if now - time < timedelta(seconds=3)
    ]

    raid_keywords = ['raid', 'spam', 'nuked', 'hacked', 'rip', 'lol', 'get', 'raided', 'bot', 'link', 'http', 'discord.gg', '.gg', 'invite', 'join', 'www', '.com', '.net', '.org']

    if any(keyword in channel.name.lower() for keyword in raid_keywords):
        try:
            await channel.delete()
            print(f"Deleted suspicious channel: {channel.name}")
        except:
            pass
        await instant_lockdown(guild, "Suspicious channel detected")
        return

    if len(channel_creation_tracker[guild.id]) >= 2:
        try:
            await channel.delete()
        except:
            pass
        await instant_lockdown(guild, "Mass channel creation detected")

@bot.event
async def on_member_join(member):
    guild = member.guild
    now = datetime.now()

    if member.bot:
        join_tracker[guild.id].append(now)
        join_tracker[guild.id] = [
            time for time in join_tracker[guild.id]
            if now - time < timedelta(seconds=10)
        ]

        if len(join_tracker[guild.id]) >= 2:
            try:
                await member.ban(reason="Auto-ban: Multiple bots joining rapidly")
            except:
                pass
            await instant_lockdown(guild, "Multiple bots joining detected")

@bot.event
async def on_message(message):
    if message.author.bot and message.author.id != bot.user.id:
        guild = message.guild
        if not guild:
            await bot.process_commands(message)
            return

        now = datetime.now()
        bot_id = message.author.id

        if bot_id not in message_spam_tracker:
            message_spam_tracker[bot_id] = []

        message_spam_tracker[bot_id].append(now)
        message_spam_tracker[bot_id] = [
            time for time in message_spam_tracker[bot_id]
            if now - time < timedelta(seconds=2)
        ]

        if len(message_spam_tracker[bot_id]) >= 3:
            try:
                await message.author.ban(reason="Bot spam detected - instant ban")
            except:
                pass
            await instant_lockdown(guild, "Bot spam detected")

        await bot.process_commands(message)
        return

    if not message.author.bot:
        guild = message.guild
        if not guild:
            return

        now = datetime.now()
        user_id = message.author.id

        if user_id not in message_spam_tracker:
            message_spam_tracker[user_id] = []

        message_spam_tracker[user_id].append(now)
        message_spam_tracker[user_id] = [
            time for time in message_spam_tracker[user_id]
            if now - time < timedelta(seconds=3)
        ]

        if len(message_spam_tracker[user_id]) >= 5:
            try:
                await message.author.timeout(timedelta(hours=1), reason="Spam detected")
            except:
                pass

        if '@everyone' in message.content or '@here' in message.content:
            if not message.author.guild_permissions.mention_everyone:
                try:
                    await message.delete()
                    await message.author.ban(reason="Unauthorized @everyone spam")
                except:
                    pass

    await bot.process_commands(message)

# FIXED EMERGENCY CHANNEL CREATION
async def create_emergency_channels(guild):
    global emergency_channel_ids
    emergency_channel_ids.clear()

    print("🛡️ Starting emergency lockdown...")

    channels = list(guild.channels)
    print(f"Deleting {len(channels)} channels...")

    for channel in channels:
        try:
            await channel.delete()
            print(f"Deleted channel: {channel.name}")
        except discord.NotFound:
            pass
        except discord.Forbidden:
            print(f"No permission to delete {channel.name}")
        except Exception as e:
            print(f"Failed to delete {channel.name}: {e}")

    print("✅ All channels deleted successfully")
    print("Waiting 10 seconds for Discord to finish processing...")
    await asyncio.sleep(10)

    try:
        being_fixed = await guild.create_text_channel("being-fixed")
        await being_fixed.set_permissions(
            guild.default_role,
            view_channel=True,
            send_messages=False,
            read_messages=True
        )
        emergency_channel_ids.add(being_fixed.id)
        print(f"✅ Created #being-fixed: {being_fixed.id}")

        await asyncio.sleep(3)

        temp = await guild.create_text_channel("only-temporary")
        await temp.set_permissions(
            guild.default_role,
            view_channel=True,
            send_messages=True,
            read_messages=True
        )
        emergency_channel_ids.add(temp.id)
        print(f"✅ Created #only-temporary: {temp.id}")

        await asyncio.sleep(2)

        # Comforting message in being-fixed
        explanation_embed = discord.Embed(
            title="🛡️ RAID ATTACK STOPPED",
            description="Our security system detected and stopped a raid attack on this server.",
            color=discord.Color.red()
        )
        explanation_embed.add_field(
            name="⚠️ What Happened:",
            value="• Malicious bots joined the server\n• They attempted to spam channels\n• They tried to create hundreds of fake channels\n• Our anti-raid system detected this instantly",
            inline=False
        )
        explanation_embed.add_field(
            name="✅ How We Fixed It:",
            value="• **Banned all raid bots** within seconds\n• **Deleted all compromised channels**\n• **Removed all malicious webhooks**\n• **Created these temporary channels** for communication\n• **Protected your data** - nothing was lost",
            inline=False
        )
        explanation_embed.add_field(
            name="📢 What's Next:",
            value="• Admins will restore the server shortly\n• Use #only-temporary to chat in the meantime\n• **Please don't leave!** Everything is under control\n• Your roles and permissions are safe",
            inline=False
        )
        explanation_embed.add_field(
            name="💙 Thank You!",
            value="Thank you for your patience and for staying with us. We take server security seriously and will have everything back to normal very soon!",
            inline=False
        )
        explanation_embed.set_footer(text=f"Security Team • {guild.name}")
        explanation_embed.timestamp = datetime.utcnow()

        await being_fixed.send(content="@everyone **PLEASE READ**", embed=explanation_embed)
        print("✅ Sent raid explanation message to #being-fixed")

        # Welcome in only-temporary
        temp_embed = discord.Embed(
            title="💬 Temporary Chat Room",
            description="Welcome! You can chat here while we restore the server.",
            color=discord.Color.green()
        )
        temp_embed.add_field(
            name="ℹ️ About This Channel:",
            value="This is a temporary channel for everyone to communicate while admins restore the server. Check #being-fixed for updates on what happened and the fix progress!",
            inline=False
        )
        temp_embed.add_field(
            name="📋 Rules:",
            value="• Be respectful\n• No spam\n• Stay calm - everything is under control\n• Ask questions if you need clarification",
            inline=False
        )
        await temp.send(content="@everyone", embed=temp_embed)
        print("✅ Sent welcome message to #only-temporary")

        print("✅ Emergency channels fully created and messages sent successfully!")
        return being_fixed, temp

    except discord.Forbidden:
        print("❌ Bot does NOT have MANAGE_CHANNELS permission! Fix this first.")
        return None, None
    except discord.HTTPException as e:
        print(f"❌ Discord error during creation: {e}")
        return None, None
    except Exception as e:
        print(f"Unexpected error: {e}")
        return None, None

async def instant_lockdown(guild, reason):
    global raid_mode

    if raid_mode:
        return

    raid_mode = True
    print(f"🚨 RAID MODE ACTIVATED: {reason}")

    ban_tasks = []
    now = datetime.now()
    for member in guild.members:
        if member.bot and member.id != bot.user.id:
            try:
                if (now - member.joined_at.replace(tzinfo=None)) < timedelta(minutes=10):
                    ban_tasks.append(member.ban(reason="Anti-raid: Suspicious bot"))
            except:
                pass

    await asyncio.gather(*ban_tasks, return_exceptions=True)
    print("✅ Raid bots banned")

    webhook_tasks = []
    for channel in guild.text_channels:
        try:
            webhooks = await channel.webhooks()
            for webhook in webhooks:
                webhook_tasks.append(webhook.delete())
        except:
            pass

    await asyncio.gather(*webhook_tasks, return_exceptions=True)
    print("✅ Webhooks deleted")

    being_fixed, temp = await create_emergency_channels(guild)
    if not being_fixed or not temp:
        print("❌ Failed to create emergency channels!")
        return

    print(f"✅ Lockdown complete. Emergency channels: {being_fixed.name} & {temp.name}")

# Admin commands
@bot.command()
@commands.has_permissions(administrator=True)
async def lockdown(ctx):
    await instant_lockdown(ctx.guild, "Manual lockdown by admin")

@bot.command()
@commands.has_permissions(administrator=True)
async def unlock(ctx):
    global raid_mode
    raid_mode = False
    await ctx.send('🔓 Raid mode deactivated. You can now restore your server manually.')

@bot.command()
@commands.has_permissions(administrator=True)
async def emergency_channels(ctx):
    await ctx.send('🚨 Creating emergency channels...')
    await create_emergency_channels(ctx.guild)

@bot.command()
@commands.has_permissions(administrator=True)
async def ban_all_bots(ctx):
    tasks = []
    for member in ctx.guild.members:
        if member.bot and member.id != bot.user.id:
            tasks.append(member.ban(reason="Manual bot purge"))
    results = await asyncio.gather(*tasks, return_exceptions=True)
    banned = sum(1 for r in results if not isinstance(r, Exception))
    await ctx.send(f'✅ Banned {banned} bots!')

@bot.command()
@commands.has_permissions(administrator=True)
async def backup(ctx):
    guild = ctx.guild
    await ctx.send("📦 Starting server backup...")

    # Collect data
    backup_data = {
        "name": guild.name,
        "roles": [],
        "channels": [],
        "categories": [],
        "emojis": []
    }

    # Roles (name, color, permissions, hoist, mentionable)
    for role in guild.roles:
        if role.managed or role.is_default():  # Skip @everyone and managed
            continue
        backup_data["roles"].append({
            "name": role.name,
            "color": role.color.value,
            "permissions": role.permissions.value,
            "hoist": role.hoist,
            "mentionable": role.mentionable
        })

    # Channels (text/voice, permissions, position)
    for channel in guild.channels:
        perms = []
        for overwrite in channel.overwrites:
            perms.append({
                "id": overwrite.id,
                "type": "role" if isinstance(overwrite, discord.Role) else "member",
                "allow": overwrite.allow.value,
                "deny": overwrite.deny.value
            })
        backup_data["channels"].append({
            "name": channel.name,
            "type": str(channel.type),
            "position": channel.position,
            "permissions": perms,
            "category_id": channel.category_id if channel.category else None
        })

    # Emojis
    for emoji in guild.emojis:
        backup_data["emojis"].append({
            "name": emoji.name,
            "url": str(emoji.url)
        })

    # Save to JSON file
    import json
    import os
    backup_folder = "backups"
    if not os.path.exists(backup_folder):
        os.makedirs(backup_folder)
    filename = f"{backup_folder}/backup_{guild.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w') as f:
        json.dump(backup_data, f, indent=4)

    await ctx.send(f"✅ Backup complete! Saved to `{filename}` on the server.")
    print(f"Backup saved: {filename}")

@bot.command()
@commands.has_permissions(administrator=True)
async def restore(ctx):
    guild = ctx.guild
    await ctx.send("⚠️ **WARNING**: This will OVERWRITE your server! Type 'confirm' in 30 seconds to proceed.")

    def check(m):
        return m.author == ctx.author and m.content.lower() == 'confirm'

    try:
        msg = await bot.wait_for('message', check=check, timeout=30.0)
    except asyncio.TimeoutError:
        await ctx.send("Restore cancelled.")
        return

    await ctx.send("🔄 Restoring server...")

    # Find latest backup
    import glob
    backups = glob.glob("backups/backup_*.json")
    if not backups:
        await ctx.send("No backups found!")
        return
    latest = max(backups, key=os.path.getctime)
    with open(latest, 'r') as f:
        data = json.load(f)

    # Restore roles
    for role_data in data["roles"]:
        try:
            await guild.create_role(
                name=role_data["name"],
                color=discord.Color(role_data["color"]),
                permissions=discord.Permissions(role_data["permissions"]),
                hoist=role_data["hoist"],
                mentionable=role_data["mentionable"]
            )
            print(f"Restored role: {role_data['name']}")
        except:
            pass

    # Restore channels (simplified - creates text/voice)
    for ch_data in data["channels"]:
        try:
            if ch_data["type"] == "text":
                await guild.create_text_channel(ch_data["name"], position=ch_data["position"])
            elif ch_data["type"] == "voice":
                await guild.create_voice_channel(ch_data["name"], position=ch_data["position"])
            print(f"Restored channel: {ch_data['name']}")
        except:
            pass

    # Emojis
    for emoji_data in data["emojis"]:
        try:
            response = requests.get(emoji_data["url"])
            await guild.create_custom_emoji(name=emoji_data["name"], image=response.content)
        except:
            pass

    await ctx.send("✅ Server restore complete! Check everything.")

import json
import os
import asyncio
import datetime

# Auto-backup every 3 weeks (21 days = 1,814,400 seconds)
AUTO_BACKUP_INTERVAL = 21 * 24 * 60 * 60  # 3 weeks in seconds

async def create_backup(guild):
    print("📦 Starting automatic server backup...")

    backup_data = {
        "name": guild.name,
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "roles": [],
        "channels": [],
        "emojis": []
    }

    # Roles
    for role in guild.roles:
        if role.managed or role.is_default():
            continue
        backup_data["roles"].append({
            "name": role.name,
            "color": role.color.value,
            "permissions": role.permissions.value,
            "hoist": role.hoist,
            "mentionable": role.mentionable
        })

    # Channels
    for channel in guild.channels:
        perms = []
        for overwrite in channel.overwrites:
            perms.append({
                "id": overwrite.id,
                "type": "role" if isinstance(overwrite, discord.Role) else "member",
                "allow": overwrite.allow.value,
                "deny": overwrite.deny.value
            })
        backup_data["channels"].append({
            "name": channel.name,
            "type": str(channel.type),
            "position": channel.position,
            "permissions": perms,
            "category_id": channel.category_id if channel.category else None
        })

    # Emojis
    for emoji in guild.emojis:
        backup_data["emojis"].append({
            "name": emoji.name,
            "url": str(emoji.url)
        })

    # Save to file
    backup_folder = "backups"
    if not os.path.exists(backup_folder):
        os.makedirs(backup_folder)
    filename = f"{backup_folder}/auto_backup_{guild.id}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w') as f:
        json.dump(backup_data, f, indent=4)

    print(f"✅ Automatic backup saved: {filename}")

@bot.event
async def on_ready():
    print(f'🛡️ ANTI-RAID BOT ONLINE: {bot.user}')
    Thread(target=run_flask).start()  # Your existing Flask keep-alive

    # Start auto-backup loop
    async def auto_backup_loop():
        while True:
            try:
                # Backup all guilds the bot is in (in case it's in multiple servers)
                for guild in bot.guilds:
                    await create_backup(guild)
            except Exception as e:
                print(f"Auto-backup error: {e}")
            await asyncio.sleep(AUTO_BACKUP_INTERVAL)  # Wait 3 weeks

    bot.loop.create_task(auto_backup_loop())

# Start the bot using environment variable
bot.run(os.getenv("DISCORD_TOKEN"))

