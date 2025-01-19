import discord
from discord.ext import commands
import logging
import sys
import traceback
from datetime import datetime, timezone
import asyncio

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

    def __init__(self, debug = False):
        super().__init__(command_prefix=COMMAND_PREFIX, intents=INTENTS, description=DESCRIPTION)
        self.onboarding_enabled_date = datetime.strptime(config.ONBOARDING_ENABLED_DATE, '%Y-%m-%d').replace(tzinfo=timezone.utc)
        self.debug = debug

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

    async def on_member_update(self, before, after):
        if before.flags.completed_onboarding == True or after.flags.completed_onboarding == False:
            return
        elif (before.joined_at < self.onboarding_enabled_date):
            mod_channel = discord.utils.get(channels, name=config.MOD_CHANNEL)
            await mod_channel.send(f"Onboarded member who joined before its introduction, name: {after.mention}")
            return
        channels = after.guild.channels
        home_channel = discord.utils.get(channels, name=config.HOME_CHANNEL)
        restricted_role = discord.utils.find(
            lambda role: role.name.casefold() == config.RESTRICTED_ROLE.casefold(), after.roles)
        if restricted_role:
            # new member is most likely a bot as they did not accept the terms of service
            # if after.flags.did_rejoin == False:
                # TODO if first time joiner send a DM requesting them to retry
            await after.kick(reason="Did not accept terms of service during onboarding, likely a bot.")
            mod_channel = discord.utils.get(channels, name=config.MOD_CHANNEL)
            await mod_channel.send(f"Kicked newly onboarded member that picked {restricted_role.mention} role, username: {after.name}")
            # wait a bit for Discord to post the built-in welcome message and then delete it
            await asyncio.sleep(1)
            async for message in home_channel.history(limit=200):
                if message.author == after:
                    await message.delete()
                    break
        else:
            announcements_channel = discord.utils.get(channels, name=config.ANNOUNCEMENTS_CHANNEL)
            general_channel = discord.utils.get(channels, name=config.GENERAL_CHANNEL)
            matchmaking_channel = discord.utils.get(channels, name=config.MATCHMAKING_CHANNEL)
            welcome_msg=config.WELCOME_TEXT.format(
                new_member=after.mention,
                announcements=announcements_channel.mention,
                home=home_channel.mention,
                general=general_channel.mention,
                matchmaking=matchmaking_channel.mention,
                botemkin=self.user.mention)
            await home_channel.send(welcome_msg)

bot = Botemkin()
bot.run(config.TOKEN, reconnect=True)
