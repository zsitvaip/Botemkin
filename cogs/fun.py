import discord
from discord.ext import commands
import logging
import asyncio
import random

log = logging.getLogger(__name__)

class Fun:
    """Fun module. Your mileage may vary."""

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def buster(self, ctx):
        """Busts."""
        emojis = ctx.guild.emojis
        e1 = discord.utils.get(emojis, name='confirmed')
        e2 = discord.utils.get(emojis, name='buster')
        if e1 and e2:
            await ctx.message.add_reaction(e1)
            msg = await ctx.send("４８の必殺技！")
            await asyncio.sleep(2)
            await msg.edit(content="ボチョムキン……！！")
            await asyncio.sleep(2)
            await msg.edit(content=f"バスターァ！！！！ <:{e2.name}:{e2.id}>")
        else:
            log.warning("!buster called but missing emoji")

    @commands.command()
    async def waifu(self, ctx):
        """???"""
        emojis = ctx.guild.emojis
        e = discord.utils.get(emojis, name='igenytelenseg')
        if e:
            await ctx.message.add_reaction(e)
        e1 = discord.utils.get(emojis, name='destr')
        e2 = discord.utils.get(emojis, name='royed')
        if e1 and e2:
            await ctx.send(f"{ctx.author.mention} <:{e1.name}:{e1.id}><:{e2.name}:{e2.id}> your laifu!")
        else:
            await ctx.send(f"{ctx.author.mention} Get a laifu!")
            log.warning("!waifu called but missing emoji")

    @commands.command()
    async def clash(self, ctx):
        """This hardly ever happens, really."""
        if random.randint(1, 10) > 3:
            return
        emojis = ctx.guild.emojis
        e1 = discord.utils.get(emojis, name='danger')
        e2 = discord.utils.get(emojis, name='time')
        msg = await ctx.send('3')
        await asyncio.sleep(1)
        await msg.edit(content='2')
        await asyncio.sleep(1)
        await msg.edit(content='1')
        await asyncio.sleep(1)
        if e1 and e2:
            await msg.edit(content=f"<:{e1.name}:{e1.id}><:{e2.name}:{e2.id}>")
        else:
            log.warning("!clash called but missing emoji")

def setup(bot):
    bot.add_cog(Fun(bot))