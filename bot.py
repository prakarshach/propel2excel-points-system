import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
import db
import asyncio
import logging
import sys
from datetime import datetime
import math
import aiohttp
import json
# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
BACKEND_API_URL = os.getenv('BACKEND_API_URL', 'http://localhost:8000')  # Default backend URL

if not TOKEN:
    logger.error("❌ DISCORD_TOKEN not found in .env file!")
    sys.exit(1)

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# Global variables
cogs_loaded = False
reconnect_attempts = 0
max_reconnect_attempts = 5

async def register_user_with_backend(discord_id: str, display_name: str, username: str = None):
    """Register a new user with the backend API when they join Discord"""
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "discord_id": discord_id,
                "display_name": display_name,
                "username": username,
                "joined_at": datetime.utcnow().isoformat()
            }
            
            async with session.post(
                f"{BACKEND_API_URL}/api/users/register/",
                json=payload,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 201:
                    logger.info(f"✅ Successfully registered user {display_name} ({discord_id}) with backend")
                    return True
                elif response.status == 409:
                    logger.info(f"ℹ️ User {display_name} ({discord_id}) already exists in backend")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Failed to register user {display_name} ({discord_id}) with backend: {response.status} - {error_text}")
                    return False
                    
    except Exception as e:
        logger.error(f"❌ Error registering user {display_name} ({discord_id}) with backend: {e}")
        return False

async def update_user_points_in_backend(discord_id: str, points: int, action: str):
    """Update user points in the backend API"""
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "points": points,
                "action": action,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            async with session.post(
                f"{BACKEND_API_URL}/api/users/{discord_id}/add-points/",
                json=payload,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    logger.info(f"✅ Successfully updated points for user {discord_id} in backend")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Failed to update points for user {discord_id} in backend: {response.status} - {error_text}")
                    return False
                    
    except Exception as e:
        logger.error(f"❌ Error updating points for user {discord_id} in backend: {e}")
        return False

async def load_cogs():
    """Load all cogs with proper error handling"""
    global cogs_loaded
    if cogs_loaded:
        logger.info("Cogs already loaded, skipping...")
        return []
    
    loaded_cogs = []
    cog_files = [f for f in os.listdir('./cogs') if f.endswith('.py')]
    
    for filename in cog_files:
        cog_name = filename[:-3]
        try:
            # Check if cog is already loaded
            if cog_name in bot.cogs:
                logger.info(f"✅ Cog '{cog_name}' already loaded")
                loaded_cogs.append(cog_name)
                continue
                
            await bot.load_extension(f'cogs.{cog_name}')
            loaded_cogs.append(cog_name)
            logger.info(f"✅ Successfully loaded cog: {cog_name}")
            
        except Exception as e:
            logger.error(f"❌ Failed to load cog '{cog_name}': {e}")
            continue
    
    cogs_loaded = True
    return loaded_cogs

async def setup_database():
    """Setup database with error handling"""
    try:
        db.setup()
        db.initialize_rewards()
        logger.info("✅ Database setup completed successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Database setup failed: {e}")
        return False

@bot.event
async def on_ready():
    """Bot ready event with comprehensive setup"""
    global reconnect_attempts
    
    logger.info(f"🤖 Bot is online as {bot.user}")
    logger.info(f"🆔 Bot ID: {bot.user.id}")
    logger.info(f"📋 Connected to {len(bot.guilds)} server(s)")
    
    # Reset reconnect attempts on successful connection
    reconnect_attempts = 0
    
    # Setup database
    db_success = await setup_database()
    if not db_success:
        logger.error("❌ Failed to setup database, bot may not function properly")
    
    # Load cogs
    loaded_cogs = await load_cogs()
    logger.info(f"🎯 All cogs loaded successfully! ({len(loaded_cogs)} cogs)")
    
    # Set bot status
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=f"!help | {len(bot.guilds)} servers"
        )
    )

@bot.event
async def on_connect():
    """Bot connect event"""
    logger.info("🔗 Bot connected to Discord Gateway")

@bot.event
async def on_disconnect():
    """Bot disconnect event with reconnection logic"""
    global reconnect_attempts
    logger.warning("🔌 Bot disconnected from Discord Gateway")
    
    if reconnect_attempts < max_reconnect_attempts:
        reconnect_attempts += 1
        logger.info(f"🔄 Attempting to reconnect... (Attempt {reconnect_attempts}/{max_reconnect_attempts})")
        await asyncio.sleep(5)  # Wait 5 seconds before reconnecting
    else:
        logger.error("❌ Max reconnection attempts reached. Bot will not reconnect automatically.")

@bot.event
async def on_guild_join(guild):
    """Bot joined a new server"""
    logger.info(f"🎉 Bot joined new server: {guild.name} (ID: {guild.id})")

@bot.event
async def on_guild_remove(guild):
    """Bot left a server"""
    logger.info(f"👋 Bot left server: {guild.name} (ID: {guild.id})")

@bot.event
async def on_member_join(member):
    """Send personalized welcome DM to new members and register with backend"""
    try:
        # Register user with backend API using Discord User ID as authoritative identifier
        discord_id = str(member.id)
        display_name = member.display_name
        username = member.name if hasattr(member, 'name') else None
        
        # Register with backend (this ensures 1:1 mapping between Discord members and backend users)
        backend_success = await register_user_with_backend(discord_id, display_name, username)
        
        if not backend_success:
            logger.warning(f"⚠️ Failed to register user {display_name} ({discord_id}) with backend, but continuing with local operations")
        
        # Create personalized welcome embed
        embed = discord.Embed(
            title=f"🎉 Welcome to Propel2Excel, {member.display_name}!",
            description="You've joined an amazing community of students and professionals!",
            color=0x00ff00
        )
        
        embed.add_field(
            name="🏆 What is P2E?",
            value="Propel2Excel is a student-powered professional growth platform where you can network, learn, and grow together!",
            inline=False
        )
        
        embed.add_field(
            name="💰 Points System",
            value="Earn points for activities like:\n• Sending messages (+1 pt)\n• Reacting to posts (+2 pts)\n• Uploading resume (+20 pts)\n• Attending events (+15 pts)\n• Sharing resources (+10 pts)\n• LinkedIn updates (+5 pts)",
            inline=False
        )
        
        embed.add_field(
            name="🎯 Unlockable Incentives",
            value="**50 points** → Azure Certification\n**75 points** → Resume Review\n**100 points** → Hackathon\n\n*You'll receive a DM when you unlock each incentive!*",
            inline=False
        )
        
        embed.add_field(
            name="🚀 Getting Started",
            value="• Use `!help` to see all commands\n• Use `!points` to check your points\n• Use `!milestones` to see available incentives\n• Use `!leaderboard` to see top performers",
            inline=False
        )
        
        embed.add_field(
            name="📋 Quick Commands",
            value="`!resume` - Upload resume (+20 pts)\n`!event` - Mark attendance (+15 pts)\n`!resource <description>` - Submit resource for review (+10 pts if approved)\n`!linkedin` - Post update (+5 pts)",
            inline=False
        )
        
        embed.set_footer(text="Welcome aboard! We're excited to see you grow with us! 🚀")
        embed.set_thumbnail(url=member.display_avatar.url if member.display_avatar else None)
        
        # Send the personalized welcome DM
        await member.send(embed=embed)
        
        # Also send a simple text message as backup
        welcome_text = (
            f"Hi {member.display_name}! 👋\n\n"
            "Welcome to the Propel2Excel Discord community!\n\n"
            "**You've just joined a community where every interaction helps you grow!**\n\n"
            "Start earning points right away by:\n"
            "• Sending messages (+1 point each)\n"
            "• Reacting to posts (+2 points each)\n"
            "• Using commands like `!resume`, `!event`, `!resource`, `!linkedin`\n\n"
            "**Unlock real incentives:**\n"
            "• 50 points = Azure Certification\n"
            "• 75 points = Resume Review\n"
            "• 100 points = Hackathon\n\n"
            "Try `!help` to see all available commands!\n"
            "Welcome aboard! 🚀"
        )
        
        await member.send(welcome_text)
        
        logger.info(f"✅ Sent personalized welcome DM to {member.display_name} ({member.id}) and registered with backend")
        
    except discord.Forbidden:
        # User has DMs disabled
        logger.info(f"❌ Could not send welcome DM to {member.display_name} - DMs disabled")
    except Exception as e:
        logger.error(f"❌ Error sending welcome DM to {member.display_name}: {e}")


# Basic commands with error handling
@bot.command()
async def ping(ctx):
    """Test command to verify bot is working"""
    try:
        latency = round(bot.latency * 1000)
        embed = discord.Embed(
            title="🏓 Pong!",
            description=f"Bot is working!",
            color=0x00ff00
        )
        embed.add_field(name="Latency", value=f"{latency}ms", inline=True)
        embed.add_field(name="Status", value="✅ Online", inline=True)
        
        await ctx.send(embed=embed)
        logger.info(f"Ping command used by {ctx.author} in {ctx.guild.name}")
        
    except Exception as e:
        logger.error(f"Error in ping command: {e}")
        await ctx.send("❌ An error occurred while processing the ping command.")

@bot.command()
async def test(ctx):
    """Test command to verify points system"""
    try:
        user_id = str(ctx.author.id)
        conn = db.connect()
        c = conn.cursor()
        c.execute('SELECT points FROM users WHERE user_id = ?', (user_id,))
        data = c.fetchone()
        pts = data[0] if data else 0
        conn.close()
        
        embed = discord.Embed(
            title="🧪 Test Results",
            description="Testing bot functionality",
            color=0x00ff00
        )
        embed.add_field(name="User ID", value=user_id, inline=True)
        embed.add_field(name="Current Points", value=f"{pts} points", inline=True)
        embed.add_field(name="Bot Status", value="✅ Working", inline=True)
        embed.add_field(name="Database", value="✅ Connected", inline=True)
        
        await ctx.send(embed=embed)
        logger.info(f"Test command used by {ctx.author} in {ctx.guild.name}")
        
    except Exception as e:
        logger.error(f"Error in test command: {e}")
        await ctx.send("❌ An error occurred while processing the test command.")

@bot.command()
async def status(ctx):
    """Show bot status and loaded cogs"""
    try:
        embed = discord.Embed(
            title="🤖 Bot Status",
            description="Current bot information",
            color=0x0099ff
        )
        embed.add_field(name="Bot Name", value=bot.user.name, inline=True)
        embed.add_field(name="Latency", value=f"{round(bot.latency * 1000)}ms", inline=True)
        embed.add_field(name="Servers", value=len(bot.guilds), inline=True)
        embed.add_field(name="Loaded Cogs", value=len(bot.cogs), inline=True)
        embed.add_field(name="Commands", value=len(bot.commands), inline=True)
        embed.add_field(name="Uptime", value=f"<t:{int(bot.start_time.timestamp())}:R>", inline=True)
        
        await ctx.send(embed=embed)
        logger.info(f"Status command used by {ctx.author} in {ctx.guild.name}")
        
    except Exception as e:
        logger.error(f"Error in status command: {e}")
        await ctx.send("❌ An error occurred while processing the status command.")

@bot.command()
async def welcome(ctx):
    """Send welcome message again"""
    try:
        embed = discord.Embed(
            title=f"🎉 Welcome to Propel2Excel, {ctx.author.display_name}!",
            description="Here's your personalized welcome message!",
            color=0x00ff00
        )
        
        embed.add_field(
            name="🏆 What is P2E?",
            value="Propel2Excel is a student-powered professional growth platform where you can network, learn, and grow together!",
            inline=False
        )
        
        embed.add_field(
            name="💰 Points System",
            value="Earn points for activities like:\n• Sending messages (+1 pt)\n• Reacting to posts (+2 pts)\n• Uploading resume (+20 pts)\n• Attending events (+15 pts)\n• Sharing resources (+10 pts)\n• LinkedIn updates (+5 pts)",
            inline=False
        )
        
        embed.add_field(
            name="🎯 Unlockable Incentives",
            value="**50 points** → Azure Certification\n**75 points** → Resume Review\n**100 points** → Hackathon\n\n*You'll receive a DM when you unlock each incentive!*",
            inline=False
        )
        
        embed.add_field(
            name="🚀 Getting Started",
            value="• Use `!help` to see all commands\n• Use `!points` to check your points\n• Use `!milestones` to see available incentives\n• Use `!leaderboard` to see top performers",
            inline=False
        )
        
        embed.set_footer(text="Welcome aboard! We're excited to see you grow with us! 🚀")
        embed.set_thumbnail(url=ctx.author.display_avatar.url if ctx.author.display_avatar else None)
        
        await ctx.send(embed=embed)
        logger.info(f"Welcome command used by {ctx.author} in {ctx.guild.name}")
        
    except Exception as e:
        logger.error(f"Error in welcome command: {e}")
        await ctx.send("❌ An error occurred while processing the welcome command.")

@bot.command()
@commands.has_permissions(administrator=True)
async def sendwelcome(ctx, member: discord.Member):
    """Admin command to manually send welcome DM to a user"""
    try:
        # Create personalized welcome embed
        embed = discord.Embed(
            title=f"🎉 Welcome to Propel2Excel, {member.display_name}!",
            description="You've joined an amazing community of students and professionals!",
            color=0x00ff00
        )
        
        embed.add_field(
            name="🏆 What is P2E?",
            value="Propel2Excel is a student-powered professional growth platform where you can network, learn, and grow together!",
            inline=False
        )
        
        embed.add_field(
            name="💰 Points System",
            value="Earn points for activities like:\n• Sending messages (+1 pt)\n• Reacting to posts (+2 pts)\n• Uploading resume (+20 pts)\n• Attending events (+15 pts)\n• Sharing resources (+10 pts)\n• LinkedIn updates (+5 pts)",
            inline=False
        )
        
        embed.add_field(
            name="🎯 Unlockable Incentives",
            value="**50 points** → Azure Certification\n**75 points** → Resume Review\n**100 points** → Hackathon\n\n*You'll receive a DM when you unlock each incentive!*",
            inline=False
        )
        
        embed.add_field(
            name="🚀 Getting Started",
            value="• Use `!help` to see all commands\n• Use `!points` to check your points\n• Use `!milestones` to see available incentives\n• Use `!leaderboard` to see top performers",
            inline=False
        )
        
        embed.set_footer(text="Welcome aboard! We're excited to see you grow with us! 🚀")
        embed.set_thumbnail(url=member.display_avatar.url if member.display_avatar else None)
        
        # Send the personalized welcome DM
        await member.send(embed=embed)
        
        await ctx.send(f"✅ Sent welcome DM to {member.mention}")
        logger.info(f"Admin {ctx.author} sent welcome DM to {member.display_name}")
        
    except discord.Forbidden:
        await ctx.send(f"❌ Could not send welcome DM to {member.mention} - DMs disabled")
    except Exception as e:
        await ctx.send(f"❌ Error sending welcome DM to {member.mention}: {e}")
        logger.error(f"Error in sendwelcome command: {e}")

@bot.command()
@commands.has_permissions(administrator=True)
async def registeruser(ctx, member: discord.Member):
    """Admin command to manually register a user with the backend"""
    try:
        discord_id = str(member.id)
        display_name = member.display_name
        username = member.name if hasattr(member, 'name') else None
        
        success = await register_user_with_backend(discord_id, display_name, username)
        
        if success:
            embed = discord.Embed(
                title="✅ User Registration",
                description=f"Successfully registered {member.mention} with backend",
                color=0x00ff00
            )
            embed.add_field(name="Discord ID", value=discord_id, inline=True)
            embed.add_field(name="Display Name", value=display_name, inline=True)
            if username:
                embed.add_field(name="Username", value=username, inline=True)
            
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"❌ Failed to register {member.mention} with backend")
            
    except Exception as e:
        await ctx.send(f"❌ Error registering user: {e}")
        logger.error(f"Error in registeruser command: {e}")

@bot.command()
async def help(ctx):
    """Show available commands"""
    try:
        embed = discord.Embed(
            title="🤖 Bot Commands",
            description="Available commands for the P2E Discord Bot",
            color=0x0099ff
        )
        
        # Points commands
        embed.add_field(
            name="💰 Points Commands",
            value="`!points` - Check your points\n"
                  "`!pointshistory` - View your point history\n"
                  "`!pointvalues` - Show all ways to earn points\n"
                  "`!resume` - Claim points for resume upload\n"
                  "`!event` - Claim points for event attendance\n"
                  "`!resource` - Claim points for sharing resources\n"
                  "`!linkedin` - Claim points for LinkedIn updates",
            inline=False
        )
        
        # Shop commands
        embed.add_field(
            name="🛍️ Shop Commands",
            value="`!shop` - View available rewards\n"
                  "`!redeem <id>` - Redeem a reward",
            inline=False
        )
        
        # Admin commands
        embed.add_field(
            name="⚙️ Admin Commands",
            value="`!addpoints @user <amount>` - Add points\n"
                  "`!removepoints @user <amount>` - Remove points\n"
                  "`!stats` - View bot statistics\n"
                  "`!topusers` - Show top users",
            inline=False
        )
        
        # Utility commands
        embed.add_field(
            name="🔧 Utility Commands",
            value="`!ping` - Test bot response\n"
                  "`!test` - Test database connection\n"
                  "`!status` - Show bot status\n"
                  "`!help` - Show this help message",
            inline=False
        )
        
        embed.set_footer(text="Use ! before each command. Example: !points")
        
        await ctx.send(embed=embed)
        logger.info(f"Help command used by {ctx.author} in {ctx.guild.name}")
        
    except Exception as e:
        logger.error(f"Error in help command: {e}")
        await ctx.send("❌ An error occurred while processing the help command.")


@bot.command()
async def leaderboard(ctx, page: int = 1):
    """Show top users by points, paginated."""
    PAGE_SIZE = 10 # Number of users per page
    conn = db.connect()
    c = conn.cursor()
    c.execute("SELECT user_id, points FROM users ORDER BY points DESC")
    rows = c.fetchall()
    conn.close()
    total_users = len(rows)
    total_pages = max(1, math.ceil(total_users / PAGE_SIZE))

    page = max(1, min(page, total_pages))  # Clamp value
    start = (page - 1) * PAGE_SIZE
    end = start + PAGE_SIZE
    msg = f"**🏆 Leaderboard (Page {page}/{total_pages})**\n"
    for idx, (user_id, points) in enumerate(rows[start:end], start=start+1):
        # Try to get Discord user for nice display name
        member = ctx.guild.get_member(int(user_id)) if user_id.isdigit() else None
        name = member.display_name if member else f"User {user_id}"
        msg += f"{idx}. {name}: {points} points\n"
    if total_pages > 1:
        msg += f"\nType `!leaderboard <page>` to view other pages."
    await ctx.send(msg)


@bot.command()
async def rank(ctx, member: discord.Member = None):
    """Show user's rank and points on the leaderboard. Defaults to command caller."""
    if member is None:
        member = ctx.author

    user_id = str(member.id)

    conn = db.connect()
    c = conn.cursor()
    c.execute("SELECT user_id, points FROM users ORDER BY points DESC")
    rows = c.fetchall()
    conn.close()

    position = None
    points = 0
    for idx, (uid, pts) in enumerate(rows, start=1):
        if uid == user_id:
            position = idx
            points = pts
            break

    if position is None:
        await ctx.send(f"{member.display_name} has no points and is not on the leaderboard.")
    else:
        await ctx.send(f"🏅 {member.display_name} is ranked #{position} with {points} points.")


# Error handling
@bot.event
async def on_command_error(ctx, error):
    """Global error handler"""
    if isinstance(error, commands.CommandNotFound):
        # Ignore command not found errors to reduce spam
        return
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission to use this command.")
        logger.warning(f"Permission denied for {ctx.author} in {ctx.guild.name}")
    elif isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"⏰ Please wait {error.retry_after:.1f} seconds before using this command again.")
        logger.info(f"Cooldown triggered for {ctx.author} in {ctx.guild.name}")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Missing required argument: {error.param}")
        logger.warning(f"Missing argument for {ctx.author} in {ctx.guild.name}: {error.param}")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ Invalid argument provided.")
        logger.warning(f"Bad argument from {ctx.author} in {ctx.guild.name}")
    else:
        logger.error(f"Unhandled command error: {error}")
        await ctx.send("❌ An unexpected error occurred while processing your command.")

# Graceful shutdown
async def shutdown():
    """Graceful shutdown function"""
    logger.info("🛑 Shutting down bot...")
    await bot.close()

# Signal handlers for graceful shutdown
import signal
def signal_handler(signum, frame):
    logger.info(f"Received signal {signum}, shutting down...")
    asyncio.create_task(shutdown())

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Main execution
if __name__ == "__main__":
    try:
        logger.info("🤖 Starting Discord Bot...")
        logger.info(f"📋 Bot will use prefix: !")
        logger.info(f"🔗 Connecting to Discord...")
        
        bot.run(TOKEN, log_handler=None)  # Disable discord.py's default logging
        
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)
