import discord
from discord.ext import commands

from config import SUPERUSER_ROLE

def superuser_only():
    async def predicate(ctx):
        su_role = discord.utils.find(
            lambda role: role.name.casefold() == SUPERUSER_ROLE.casefold(), ctx.author.roles)
        if su_role is None:
            raise commands.CheckFailure(f"This command is only available to {SUPERUSER_ROLE} role.")
        return True
    return commands.check(predicate)

async def superuser_cog_check(ctx):
    su_role = discord.utils.find(
        lambda role: role.name.casefold() == SUPERUSER_ROLE.casefold(), ctx.author.roles)
    if su_role is None:
        return False
    return True