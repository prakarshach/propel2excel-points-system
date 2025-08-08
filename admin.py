from discord.ext import commands
import db
import discord
from datetime import datetime, timedelta

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def add_points(self, user_id, pts):
        conn = db.connect()
        c = conn.cursor()
        c.execute('INSERT OR IGNORE INTO users (user_id, points) VALUES (?, ?)', (user_id, 0))
        c.execute('UPDATE users SET points = points + ? WHERE user_id = ?', (pts, user_id))
        conn.commit()
        conn.close()

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def addpoints(self, ctx, member: commands.MemberConverter, amount: int):
        self.add_points(str(member.id), amount)
        embed = discord.Embed(
            title="✅ Points Added",
            description=f"Added {amount} points to {member.mention}",
            color=0x00ff00
        )
        await ctx.send(embed=embed)

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def removepoints(self, ctx, member: commands.MemberConverter, amount: int):
        self.add_points(str(member.id), -amount)
        embed = discord.Embed(
            title="❌ Points Removed",
            description=f"Removed {amount} points from {member.mention}",
            color=0xff0000
        )
        await ctx.send(embed=embed)

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def resetpoints(self, ctx, member: commands.MemberConverter):
        conn = db.connect()
        c = conn.cursor()
        c.execute('UPDATE users SET points = 0 WHERE user_id = ?', (str(member.id),))
        conn.commit()
        conn.close()
        embed = discord.Embed(
            title="🔄 Points Reset",
            description=f"Reset points for {member.mention}",
            color=0xffaa00
        )
        await ctx.send(embed=embed)

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def stats(self, ctx):
        """Show bot statistics and activity"""
        conn = db.connect()
        c = conn.cursor()
        
        # Get total users
        c.execute('SELECT COUNT(*) FROM users')
        total_users = c.fetchone()[0]
        
        # Get total points distributed
        c.execute('SELECT SUM(points) FROM points_log WHERE points > 0')
        total_points = c.fetchone()[0] or 0
        
        # Get today's activity
        today = datetime.now().strftime('%Y-%m-%d')
        c.execute('SELECT COUNT(*) FROM points_log WHERE DATE(timestamp) = ?', (today,))
        today_activity = c.fetchone()[0]
        
        # Get suspicious activity count
        c.execute('SELECT COUNT(*) FROM suspicious_activity')
        suspicious_count = c.fetchone()[0]
        
        # Get recent suspicious activity
        c.execute('SELECT COUNT(*) FROM suspicious_activity WHERE DATE(timestamp) = ?', (today,))
        today_suspicious = c.fetchone()[0]
        
        conn.close()
        
        embed = discord.Embed(
            title="📊 Bot Statistics",
            description="Current bot activity and metrics",
            color=0x0099ff
        )
        embed.add_field(name="Total Users", value=f"{total_users}", inline=True)
        embed.add_field(name="Total Points Distributed", value=f"{total_points:,}", inline=True)
        embed.add_field(name="Today's Activities", value=f"{today_activity}", inline=True)
        embed.add_field(name="Total Suspicious Activities", value=f"{suspicious_count}", inline=True)
        embed.add_field(name="Today's Suspicious Activities", value=f"{today_suspicious}", inline=True)
        embed.add_field(name="Bot Uptime", value=f"<t:{int(self.bot.start_time.timestamp())}:R>", inline=True)
        
        await ctx.send(embed=embed)

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def topusers(self, ctx, limit: int = 10):
        """Show top users by points"""
        conn = db.connect()
        c = conn.cursor()
        c.execute('SELECT user_id, points FROM users ORDER BY points DESC LIMIT ?', (limit,))
        rows = c.fetchall()
        conn.close()
        
        if not rows:
            await ctx.send("No users found.")
            return
        
        embed = discord.Embed(
            title="🏆 Top Users by Points",
            description=f"Top {limit} users with the most points",
            color=0xffd700
        )
        
        for i, (user_id, points) in enumerate(rows, 1):
            try:
                user = await self.bot.fetch_user(int(user_id))
                username = user.display_name
            except:
                username = f"User {user_id}"
            
            embed.add_field(
                name=f"#{i} {username}",
                value=f"{points:,} points",
                inline=True
            )
        
        await ctx.send(embed=embed)

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def clearwarnings(self, ctx, member: commands.MemberConverter):
        """Clear warnings for a user"""
        conn = db.connect()
        c = conn.cursor()
        c.execute('UPDATE user_status SET warnings = 0 WHERE user_id = ?', (str(member.id),))
        conn.commit()
        conn.close()
        
        embed = discord.Embed(
            title="✅ Warnings Cleared",
            description=f"Cleared all warnings for {member.mention}",
            color=0x00ff00
        )
        await ctx.send(embed=embed)

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def suspenduser(self, ctx, member: commands.MemberConverter, duration_minutes: int):
        """Suspend a user's ability to earn points"""
        conn = db.connect()
        c = conn.cursor()
        suspension_end = datetime.now() + timedelta(minutes=duration_minutes)
        c.execute('''INSERT OR REPLACE INTO user_status 
                     (user_id, warnings, points_suspended, suspension_end) 
                     VALUES (?, 0, TRUE, ?)''', (str(member.id), suspension_end))
        conn.commit()
        conn.close()
        
        embed = discord.Embed(
            title="⏸️ User Suspended",
            description=f"{member.mention} is suspended from earning points for {duration_minutes} minutes",
            color=0xffaa00
        )
        embed.add_field(name="Suspension Ends", value=f"<t:{int(suspension_end.timestamp())}:R>", inline=True)
        await ctx.send(embed=embed)

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def unsuspenduser(self, ctx, member: commands.MemberConverter):
        """Remove suspension from a user"""
        conn = db.connect()
        c = conn.cursor()
        c.execute('UPDATE user_status SET points_suspended = FALSE WHERE user_id = ?', (str(member.id),))
        conn.commit()
        conn.close()
        
        embed = discord.Embed(
            title="✅ User Unsuspended",
            description=f"{member.mention} can now earn points again",
            color=0x00ff00
        )
        await ctx.send(embed=embed)

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def activitylog(self, ctx, hours: int = 24):
        """Show recent activity log"""
        conn = db.connect()
        c = conn.cursor()
        time_threshold = datetime.now() - timedelta(hours=hours)
        c.execute('''SELECT user_id, action, points, timestamp 
                     FROM points_log 
                     WHERE timestamp > ? 
                     ORDER BY timestamp DESC 
                     LIMIT 20''', (time_threshold,))
        rows = c.fetchall()
        conn.close()
        
        if not rows:
            await ctx.send(f"No activity in the last {hours} hours.")
            return
        
        embed = discord.Embed(
            title=f"📝 Activity Log (Last {hours}h)",
            description="Recent point-earning activities",
            color=0x0099ff
        )
        
        for user_id, action, points, timestamp in rows:
            try:
                user = await self.bot.fetch_user(int(user_id))
                username = user.display_name
            except:
                username = f"User {user_id}"
            
            embed.add_field(
                name=f"{timestamp[:19]} - {username}",
                value=f"{action} (+{points} pts)",
                inline=False
            )
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Admin(bot))
