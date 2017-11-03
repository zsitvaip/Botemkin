import discord
from discord.ext import commands
from prettytable import PrettyTable

class Gametags:
    """Module for handling self-assignable roles (aka gametags)."""

    def __init__(self, bot):
        self.bot = bot

    def get_available_tags(self, guild : discord.Guild):
        everyone_role = guild.roles[0]
        available_tags = [role for role in guild.roles[1:] \
            if role.permissions <= everyone_role.permissions]
        return available_tags

    def get_selected_tags(self, guild : discord.Guild, requested_tag_names : list):
        available_tags = self.get_available_tags(guild)

        selected_tags = []
        unknown_tag_names = []
        for tag_name in requested_tag_names:
            
            requested_tag = discord.utils.find(
                lambda tag: tag.name.casefold() == tag_name.casefold(), available_tags)
            
            if requested_tag:
                selected_tags.append(requested_tag)
            else:
                unknown_tag_names.append(tag_name)

        return selected_tags, unknown_tag_names

    @commands.group()
    async def game(self, ctx):
        """Commands for handling self-assignable roles (aka gametags)."""

        if ctx.invoked_subcommand is None:
            await ctx.send("```Try: !help game```")

    @game.command(aliases=['l'])
    async def list(self, ctx):
        """Lists all available gametags."""

        available_tags = self.get_available_tags(ctx.guild)
        tag_names = [t.name for t in available_tags]

        table = PrettyTable()
        table.add_column('Available tags', tag_names)

        await ctx.send(f"```{table.get_string()}```")

    @game.command()
    async def play(self, ctx, *args):
        """Assigns you the listed gametags, usage: !game play <gametags>"""

        # TODO is there a better way to check arguments? check in doc or sample
        if not args:
            await ctx.send("```Usage: !game play <gametags>```")
            return
        
        selected_tags, unknown_tag_names = self.get_selected_tags(ctx.guild, args)
        
        msg_str = ""
        if selected_tags:
            await ctx.author.add_roles(*selected_tags, reason=f"{ctx.author} requested tags")
            tag_names = [tag.name for tag in selected_tags]
            msg_str += f"{ctx.author.name} now plays "
            
            if len(tag_names) > 1:
                msg_str += f"{', '.join(tag_names[0:-1])} and {tag_names[-1]}! "
            else:
                msg_str += f"{tag_names[0]}! "
            
            e = discord.utils.get(ctx.guild.emojis, name='quan')
            if e:
                msg_str += len(tag_names) * f"<:{e.name}:{e.id}>"

        if unknown_tag_names:
            msg_str += f"```Unknown tags: {', '.join(unknown_tag_names)}\nTry: !help list```"

        await ctx.send(msg_str)

    @game.command()
    async def drop(self, ctx, *args):
        """Removes your listed gametags, usage: !game drop <gametags>"""

        if not args:
            await ctx.send("```Usage: !game drop <gametags>```")
            return

        selected_tags, unknown_tag_names = self.get_selected_tags(ctx.guild, args)
        
        msg_str = ""
        if selected_tags:
            await ctx.author.remove_roles(*selected_tags, reason=f"{ctx.author} relinquished tags")
            tag_names = [tag.name for tag in selected_tags]
            msg_str += f"{ctx.author.name} just dropped "
            
            if len(tag_names) > 1:
                msg_str += f"{', '.join(tag_names[0:-1])} and {tag_names[-1]}! "
            else:
                msg_str += f"{tag_names[0]}! "
            
            e = discord.utils.get(ctx.guild.emojis, name='salt')
            if e:
                msg_str += len(tag_names) * f"<:{e.name}:{e.id}>"

        if unknown_tag_names:
            msg_str += f"```Unknown tags: {', '.join(unknown_tag_names)}\nTry: !help list```"

        await ctx.send(msg_str)

    @game.command(aliases=['p'])
    async def players(self, ctx, *args):
        """Lists online players with given gametag, usage: !game players <gametag>"""

        if not args:
            await ctx.send("```Usage: !game players <gametag>```")
            return

        selected_tags, unknown_tag_names = self.get_selected_tags(ctx.guild, args)

        if selected_tags:
            tagged_members = selected_tags[0].members

            table = PrettyTable()
            if tagged_members:
                for m in tagged_members:
                    table.field_names = ['Player', 'Status']
                    table.add_row([m.name, m.status.name])
                
                table.sortby = 'Status'
                table.reversesort = True

                await ctx.send(f"Players for {selected_tags[0].name}: ```{table.get_string()}```")
            else:
                await ctx.send("ded game")

        if unknown_tag_names:
            await ctx.send(f"```Unknown tags: {', '.join(unknown_tag_names)}\nTry: !help list```")

def setup(bot):
    bot.add_cog(Gametags(bot))