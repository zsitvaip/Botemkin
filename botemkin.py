import discord
from discord.ext import commands
import logging
import sys
import traceback

import config

INTENTS = discord.Intents.default()
INTENTS.members = True
INTENTS.presences = True
INTENTS.message_content = True

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

COMMAND_PREFIX = '!'
DESCRIPTION = """
Pot but bot.
Mainly for handing out self-assignable roles (aka tags).
"""

INITIAL_EXTENSIONS = (
    'cogs.gametags',
    'cogs.fun',
    'cogs.vxtwitter',
)

class Botemkin(commands.Bot):
    """Burly bot."""

    def __init__(self):
        super().__init__(command_prefix=COMMAND_PREFIX, intents=INTENTS, description=DESCRIPTION)

    async def setup_hook(self):
        for extension in INITIAL_EXTENSIONS:
            try:
                await self.load_extension(extension)
            except Exception as e:
                log.error(f"Failed to load extension: {str(e)}")
                traceback.print_exc()
        await bot.tree.sync()

    async def on_ready(self):
        log.info(f"logged in as {self.user} with an id of {self.user.id}")

    # TODO print something helpful
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            e = discord.utils.get(ctx.guild.emojis, name='semmiertelme')
            if e:
                await ctx.message.add_reaction(e)
            await ctx.send("Command not found. Use **!help** to print commands.")
        # TODO copied from /ext/commands/bot.py could change with new versions
        print('Ignoring exception in command {}'.format(ctx.command), file=sys.stderr)
        traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)

    async def on_member_join(self, member):
        channels = member.guild.channels
        announcements = discord.utils.get(channels, name=config.ANNOUNCEMENTS_CHANNEL)
        home = discord.utils.get(channels, name=config.HOME_CHANNEL)
        welcome_msg=config.WELCOME_TEXT.format(
            new_member=member.mention,
            announcements=announcements.mention,
            home=home.mention)
        await home.send(welcome_msg)

bot = Botemkin()
bot.run(config.TOKEN, reconnect=True)
