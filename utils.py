import discord
from discord.ext import commands

import config as config

def superuser_only():
    async def predicate(ctx):
        SUPERUSER_ROLE = discord.utils.find(
            lambda role: role.name.casefold() == config.SUPERUSER_ROLE.casefold(), ctx.author.roles)
        if SUPERUSER_ROLE is None:
            raise commands.CheckFailure(f"This command is only available to {config.SUPERUSER_ROLE} role.")
        return True
    return commands.check(predicate)