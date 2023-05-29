import discord
from discord import app_commands
from discord.ext import commands
import logging
import asyncio
import random
from deep_translator.constants import GOOGLE_LANGUAGES_TO_CODES
from deep_translator import single_detection, GoogleTranslator
import requests

from . import config

log = logging.getLogger(__name__)

GOOGLE_CODES_TO_LANGUAGES = {v: k for k, v in GOOGLE_LANGUAGES_TO_CODES.items()}

class Fun(commands.Cog):
    """Fun module. Your mileage may vary."""

    def __init__(self, bot):
        self.bot = bot
        
        # https://github.com/Rapptz/discord.py/issues/7823
        self.ctx_menu = app_commands.ContextMenu(
            name='Translate Name',
            callback=self.translate_name_context_menu,
        )
        self.bot.tree.add_command(self.ctx_menu)

    async def cog_unload(self) -> None:
        self.bot.tree.remove_command(self.ctx_menu.name, type=self.ctx_menu.type)

    @commands.command()
    async def buster(self, ctx):
        """Busts."""
        emojis = ctx.guild.emojis
#       e1 = discord.utils.get(emojis, name='confirmed')
        e2 = discord.utils.get(emojis, name='buster')
#       if e1 and e2:
        if e2:
#           await ctx.message.add_reaction(e1)
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

#   @commands.command()
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

    @commands.command()
    async def clown(self, ctx):
        """Honk Honk"""
        await ctx.send('https://cdn.discordapp.com/attachments/706976180703854705/1005032221402484736/Akkor_bohoc.mp4')

    async def translate_name_context_menu(self, interaction: discord.Interaction, message: discord.Message) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)

        display_name = message.author.display_name
        embed = discord.Embed(title=display_name,)
        source_language_code = 'auto'
        target_languages = ['english', 'hungarian', 'japanese']
        try:
            detection = single_detection(text=display_name, api_key=config.DETECT_LANGUAGE_API_KEY, detailed=True)
            source_language = GOOGLE_CODES_TO_LANGUAGES[detection['language']]
            source_language_code = detection['language']
            if source_language in target_languages:
                target_languages.remove(source_language)
            embed.description = f"Source language: {source_language.capitalize()}\nConfidence rating: {detection['confidence']}"
        except:
            log.exception("Language detection failed")

        embed.url = f"https://translate.google.com/?sl={source_language_code}&text={requests.utils.quote(display_name)}"

        for lang in target_languages:
            try:
                translation = GoogleTranslator(source='auto', target=lang).translate(display_name)
                embed.add_field(name=lang.capitalize(), value=translation, inline=False)
            except:
                log.exception("Failed to query Google Translate")
        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Fun(bot))
