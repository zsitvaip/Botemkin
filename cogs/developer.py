from discord.ext import commands
import logging
import traceback

from utils import superuser_cog_check

log = logging.getLogger(__name__)

class Developer(commands.Cog):
    """Developer module. Uses exclusively regular (non-slash) commands."""

    async def cog_check(self, ctx):
        return await superuser_cog_check(ctx)

    def __init__(self, bot):
        self.bot = bot

    async def extension_operation(self, ctx, extension, func):
        if func not in (self.bot.reload_extension, self.bot.load_extension, self.bot.unload_extension):
            await ctx.send(f"Unknown operation.", ephemeral=True)
            return
        for x in self.bot.initial_extensions:
            if x.lower().startswith(extension.lower()):
                try:
                    await func(f'cogs.{x.lower()}')
                    await ctx.send(f"{func.__name__.split('_')[0].capitalize()}ed extension: `{x}`", ephemeral=True)
                except Exception as e:
                    traceback.print_exc()
                    await ctx.send(f"An exception occured: `{str(e)}`", ephemeral=True)
                return
        await ctx.send(f"Unrecognized extension.", ephemeral=True)

    @commands.group(aliases=['x']+['extension'[:i] for i in range(2,len('extension'))])
    async def extension(self, ctx):
        """Handle extensions."""
        if ctx.invoked_subcommand is None:
            await self.list(ctx)

    @extension.command(aliases=['ls']+['list'[:i] for i in range(2,len('list'))])
    async def list(self, ctx):
        """List available extensions."""
        await ctx.send(f"Available extensions: {', '.join([f'`{x}`' for x in self.bot.initial_extensions])}")

    @extension.command(aliases=['reload'[:i] for i in range(1,len('reload'))])
    async def reload(self, ctx, extension):
        """Reload given extension."""
        await self.extension_operation(ctx, extension, self.bot.reload_extension)

    @extension.command(aliases=['load'[:i] for i in range(1,len('load'))])
    async def load(self, ctx, extension):
        """Load given extension."""
        await self.extension_operation(ctx, extension, self.bot.load_extension)

    @extension.command(aliases=['unload'[:i] for i in range(1,len('unload'))])
    async def unload(self, ctx, extension):
        """Unload given extension."""
        await self.extension_operation(ctx, extension, self.bot.unload_extension)

async def setup(bot):
    await bot.add_cog(Developer(bot))
