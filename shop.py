from discord.ext import commands
import db

class Shop(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def shop(self, ctx):
        conn = db.connect()
        c = conn.cursor()
        c.execute('SELECT id, name, cost FROM rewards ORDER BY cost')
        rewards = c.fetchall()
        if not rewards:
            await ctx.send("The shop is currently empty!")
            return
        msg = "**Available Rewards:**\n"
        for r_id, name, cost in rewards:
            msg += f"{r_id}. {name} — {cost} points\n"
        msg += "\nUse `!redeem <reward id>` to redeem a reward."
        await ctx.send(msg)

    @commands.command()
    async def redeem(self, ctx, reward_id: int):
        user_id = str(ctx.author.id)
        conn = db.connect()
        c = conn.cursor()

        # Check reward existence
        c.execute('SELECT name, cost FROM rewards WHERE id = ?', (reward_id,))
        reward = c.fetchone()
        if not reward:
            await ctx.send(f"Reward ID `{reward_id}` does not exist.")
            return
        reward_name, cost = reward

        # Check user points
        c.execute('SELECT points FROM users WHERE user_id = ?', (user_id,))
        data = c.fetchone()
        points = data[0] if data else 0

        if points < cost:
            await ctx.send(f"Sorry {ctx.author.mention}, you don't have enough points to redeem **{reward_name}**. You have {points} points.")
            return

        # Deduct points and log redemption
        c.execute('UPDATE users SET points = points - ? WHERE user_id = ?', (cost, user_id))
        c.execute('INSERT INTO redemptions(user_id, reward_id) VALUES (?, ?)', (user_id, reward_id))
        conn.commit()
        conn.close()

        await ctx.send(f"{ctx.author.mention}, you have successfully redeemed **{reward_name}**! Our team will contact you shortly.")

async def setup(bot):
    await bot.add_cog(Shop(bot))
