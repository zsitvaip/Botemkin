import discord
from discord.ext import commands
import logging
import sys
import traceback

import config

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

KOZLEMENYEK='kozlemenyek'
BOTEMKIN_PLS='botemkin_pls'

COMMAND_PREFIX = '!'
DESCRIPTION = """
Pot but bot.
Mainly for handing out self-assignable roles (aka gametags).
Gametags are case-insensitive and cannot contain whitespaces.
"""

INITIAL_EXTENSIONS = (
    'cogs.gametags',
    'cogs.fun',
)

class Botemkin(commands.Bot):
    """Burly bot."""

    def __init__(self):
        super().__init__(command_prefix=COMMAND_PREFIX, description=DESCRIPTION)

        for extension in INITIAL_EXTENSIONS:
            try:
                self.load_extension(extension)
            except Exception as e:
                log.error(f"Failed to load extension: {str(e)}")
                traceback.print_exc()

    def run(self):
        super().run(config.token, reconnect=True)

    async def on_ready(self):
        log.info(f"logged in as {self.user} with an id of {self.user.id}")

    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            e = discord.utils.get(ctx.guild.emojis, name='semmiertelme')
            if e:
                await ctx.message.add_reaction(e)
        # TODO copied from /ext/commands/bot.py could change with new versions
        print('Ignoring exception in command {}'.format(ctx.command), file=sys.stderr)
        traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)

    async def on_member_join(self, member):
        channels = member.guild.channels
        kozlemenyek = discord.utils.get(channels, name=KOZLEMENYEK)
        botemkin_pls = discord.utils.get(channels, name=BOTEMKIN_PLS)
        if kozlemenyek and botemkin_pls:
            welcome_str = f"""
{member.mention} Üdvözlünk a MAVIK discord szerverén! \
A szabályzatot a {kozlemenyek.mention} channelben találod, érdemes átolvasni. \
A {botemkin_pls.mention} channelben tudsz tageket kérni, hogy más is lássa mivel játszol. \
A !help paranccsal tudsz segítséget kérni a Botemkin használathoz. gl hf!
"""
            await botemkin_pls.send(welcome_str)
        else:
            log.error("could not find channel(s) for welcome message")

bot = Botemkin()
bot.run()