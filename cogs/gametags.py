import discord
from discord.ext import commands
import logging
import pathlib
import sqlite3
from igdb_api_python.igdb import igdb as igdb

from . import config

log = logging.getLogger(__name__)

class Gametags:
    """Module for handling self-assignable roles (aka tags)."""

    def __init__(self, bot):
        self.bot = bot

        self.gametag_dict = {}
        self.data_dir = 'data/'
        self.db_path = f'{self.data_dir}gametag.db'
        self.setup_db()

        self.igdb = igdb(config.igdb_key)

    # TODO rethink DB scheme
    def setup_db(self):
        pathlib.Path(self.data_dir).mkdir(parents=True, exist_ok=True)
        try:
            conn = sqlite3.connect(self.db_path, isolation_level=None)
            conn.execute('PRAGMA journal_mode = wal')
            conn.execute('PRAGMA foreign_keys = ON')

            conn.execute('BEGIN')
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tags (
                    id INTEGER PRIMARY KEY,
                    description TEXT
                )"""
            )
            conn.execute("""
                CREATE TABLE IF NOT EXISTS games (
                    id INTEGER PRIMARY KEY,
                    name TEXT
                )"""
            )
            conn.execute("""
                CREATE TABLE IF NOT EXISTS platforms (
                    id INTEGER PRIMARY KEY,
                    name TEXT
                )"""
            )
            conn.execute("""
                CREATE TABLE IF NOT EXISTS game_tags (
                    tag_id INTEGER,
                    game_id INTEGER,
                    PRIMARY KEY (tag_id, game_id),
                    FOREIGN KEY (tag_id) REFERENCES tags(id),
                    FOREIGN KEY (game_id) REFERENCES games(id)
                )"""
            )
            conn.execute("""
                CREATE TABLE IF NOT EXISTS platform_tags (
                    tag_id INTEGER,
                    platform_id INTEGER,
                    PRIMARY KEY (tag_id, platform_id),
                    FOREIGN KEY (tag_id) REFERENCES tags(id),
                    FOREIGN KEY (platform_id) REFERENCES platforms(id)
                )"""
            )
            conn.execute("""
                CREATE TABLE IF NOT EXISTS game_details (
                    game_id INTEGER,
                    guild_id INTEGER,
                    resources TEXT,
                    PRIMARY KEY (game_id, guild_id),
                    FOREIGN KEY (game_id) REFERENCES games(id)
                )"""
            )
            conn.commit()
        except:
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_available_tags(self, guild : discord.Guild):
        everyone_role = discord.utils.find(
            lambda role: role.id == guild.id, guild.roles)

        available_tags = list(filter(
            lambda role: role.id != everyone_role.id and role.permissions <= everyone_role.permissions, guild.roles))

        return available_tags

    def get_selected_tags(self, guild : discord.Guild, requested_tag_names: list):
        # TODO use sets and the intersection/difference functions
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

    def get_gametags_from_db(self, tags, *, all = False):
        rows = []
        try:
            conn = sqlite3.connect(self.db_path, isolation_level=None)
            cursor = conn.cursor()

            if all:
                cursor.execute(f"""
                    SELECT game_tags.tag_id, games.id, games.name
                    FROM games
                    LEFT OUTER JOIN game_tags ON games.id = game_tags.game_id
                    ORDER BY games.name ASC
                """)
            else:
                cursor.execute(f"""
                    SELECT game_tags.tag_id, games.id, games.name
                    FROM games
                    INNER JOIN game_tags ON games.id = game_tags.game_id
                    WHERE game_tags.tag_id IN (?{(len(tags) - 1) * ', ?'})
                    ORDER BY games.name ASC
                """, [tag.id for tag in tags])
            rows = cursor.fetchall()
        finally:
            conn.close()

        # TODO remove, this was just for debugging
        # for row in rows:
        #     print(row)

        gametags = []
        if rows:
            for tag_id, game_id, game_name in rows:
                tag = discord.utils.get(tags, id=tag_id)
                gametags.append({'tag': tag, 'game_id': game_id, 'game_name': game_name})

        return gametags

    async def is_admin(ctx):
        return ctx.author.guild_permissions.administrator

    # TODO fix, was broken by some recent IGDB update it seems
    # TODO add examples to help message like for other commands
    @commands.command(name='search', aliases=['s'], usage='<game_name>')
    @commands.check(is_admin)
    async def search_IGDB(self, ctx, *, game_name: str):
        """Search IGDB for given game name."""
        try:
            result = self.igdb.games({
            'search': game_name,
            'fields': ['name', 'slug']
            })
            games = []
            for game in result.body:
                games.append(f"#{game['id']} {game['name']} ({game['slug']})")
            if games:
                await ctx.send(f"Search results from IGDB.com:```css\n{chr(10).join(games)}```")
            else:
                await ctx.send("No search results from IGDB.com.")
        except:
            await ctx.send("An error occured.")
            raise

    @commands.command(name='import', aliases=['i'], usage='<game_id>')
    @commands.check(is_admin)
    async def import_game(self, ctx, game_id: int):
        """Imports game from external database (IGDB) to internal."""
        try:
            result = self.igdb.games({
                'ids': game_id
            })

            games = result.body
            if games:
                game = games[0]

                try:
                    conn = sqlite3.connect(self.db_path, isolation_level=None)
                    conn.execute('PRAGMA foreign_keys = ON')
                    cursor = conn.cursor()

                    cursor.execute("SELECT 1 FROM games WHERE id = ?", [game['id']])
                    if cursor.fetchone() is None:
                        conn.execute("INSERT INTO games (id, name) VALUES (?, ?)", [game['id'], game['name']])
                        await ctx.send("Game added to internal database.")
                    else:
                        await ctx.send("Game already in internal database.")
                except:
                    raise
                finally:
                    conn.close()

            else:
                await ctx.send("Game not found in external database.")
        except:
            await ctx.send("An error occured.")
            raise

    async def _list_games(self, ctx):
        available_tags = self.get_available_tags(ctx.guild)

        if available_tags:

            gametags = self.get_gametags_from_db(available_tags)

            if gametags:
                msg_str = ""
                for gametag in gametags:
                    msg_str += f"{gametag['tag'].name} [{gametag['game_name']}]#{gametag['game_id']}\n"
                await ctx.send(f"Available gametags:```css\n{msg_str}```")
            else:
                await ctx.send(f"```There are currently no available gametags.```")
        else:
            await ctx.send(f"```There are currently no available tags.```")

    async def _list_all_games(self, ctx):
        available_tags = self.get_available_tags(ctx.guild)

        gametags = self.get_gametags_from_db(available_tags, all=True)
        if gametags:
            msg_str = ""
            for gametag in gametags:
                gametag_name = "\t"
                if gametag['tag']:
                    gametag_name = f"{gametag['tag'].name} "
                msg_str += f"{gametag_name}[{gametag['game_name']}]#{gametag['game_id']}\n"
            await ctx.send(f"Imported games:```css\n{msg_str}```")
        else:
            await ctx.send(f"```There are currently no imported games.```")

    @commands.command(name='list', aliases=['ls', 'l'], usage='[all]')
    async def list_games(self, ctx, arg=None):
        """Lists available gametags.

        Use with 'all' to show all games imported from IGDB including ones without gametags associated with them.

        Usage examples:
        !list
        !ls all
        !l a
        """

        if arg in ['a', 'al', 'all']:
            await self._list_all_games(ctx)
        else:
            await self._list_games(ctx)

    @commands.command(name='play', aliases=['p'], usage='<gametags>')
    async def play_game(self, ctx, *tag_names):
        """Assigns you the listed gametags.

        Usage examples:

        !play T7
        !p GG Melty UNIST
        """

        # required because *tag_names being empty does not trigger a MissingRequiredArgument
        if not tag_names:
            await self.send_help(ctx)
            return

        selected_tags, unknown_tag_names = self.get_selected_tags(ctx.guild, tag_names)

        msg_str = ""
        if selected_tags:

            gametags = self.get_gametags_from_db(selected_tags)

            tags = []
            if gametags:

                game_names = []
                for gametag in gametags:
                    tags.append(gametag['tag'])
                    game_names.append(gametag['game_name'])

                # TODO handle permission denied
                await ctx.author.add_roles(*tags, reason=f"{ctx.author} requested gametags")

                msg_str += f"{ctx.author.display_name} now plays "

                if len(game_names) > 1:
                    msg_str += f"{', '.join(game_names[0:-1])} and {game_names[-1]}! "
                else:
                    msg_str += f"{game_names[0]}! "

                e = discord.utils.get(ctx.guild.emojis, name='quan')
                if e:
                    msg_str += len(game_names) * f"<:{e.name}:{e.id}>"

            [unknown_tag_names.append(tag.name) for tag in selected_tags if tag not in tags]

        if unknown_tag_names:
            msg_str += f"```Unknown gametags: {', '.join(unknown_tag_names)}\nTry: !list```"

        await ctx.send(msg_str)

    @commands.command(name='drop', aliases=['d'], usage='<gametags>')
    async def drop_game(self, ctx, *tag_names):
        """Removes your listed gametags.

        Usage examples:

        !drop IJ2
        !d DBFZ BBTag
        """

        # required because *tag_names being empty does not trigger a MissingRequiredArgument
        if not tag_names:
            await self.send_help(ctx)
            return

        selected_tags, unknown_tag_names = self.get_selected_tags(ctx.guild, tag_names)

        msg_str = ""
        if selected_tags:

            gametags = self.get_gametags_from_db(selected_tags)

            tags = []
            if gametags:

                game_names = []
                for gametag in gametags:
                    tags.append(gametag['tag'])
                    game_names.append(gametag['game_name'])

                await ctx.author.remove_roles(*tags, reason=f"{ctx.author} relinquished gametags")

                msg_str += f"{ctx.author.display_name} just dropped "

                if len(game_names) > 1:
                    msg_str += f"{', '.join(game_names[0:-1])} and {game_names[-1]}! "
                else:
                    msg_str += f"{game_names[0]}! "

                e = discord.utils.get(ctx.guild.emojis, name='salt')
                if e:
                    msg_str += len(game_names) * f"<:{e.name}:{e.id}>"

            [unknown_tag_names.append(tag.name) for tag in selected_tags if tag not in tags]

        if unknown_tag_names:
            msg_str += f"```Unknown gametags: {', '.join(unknown_tag_names)}\nTry: !list```"

        await ctx.send(msg_str)

    # TODO make case insensitive
    @commands.command(name='players', aliases=['ps'], usage='<gametag>')
    async def list_players(self, ctx, role: commands.RoleConverter):
        """Lists players (and their status) with given gametag.

        Usage examples:

        !players SFV
        !ps BB
        """

        game = None
        try:
            conn = sqlite3.connect(self.db_path, isolation_level=None)
            cursor = conn.cursor()

            cursor.execute(f"""
                SELECT games.name
                FROM games
                INNER JOIN game_tags ON games.id = game_tags.game_id
                WHERE game_tags.tag_id = ?
            """, [role.id])

            game = cursor.fetchone()
        finally:
            conn.close()

        if game:
            msg_str = ""
            for player in role.members:
                if player.status == discord.Status.offline:
                    msg_str += f"{player.display_name} #{player.status}\n"
                else:
                    msg_str += f"{player.display_name} [{player.status}]\n"
            if msg_str:
                await ctx.send(f"Players for {game[0]}:```css\n{msg_str}```")
            else:
                await ctx.send("ded game")

    # TODO do not create discord role if id not found
    @commands.command(name='tag', aliases=['t'], usage='<game_id> <role_name>')
    @commands.check(is_admin)
    async def tag_game(self, ctx, game_id: int, tag_name):
        """Associate game with given tag. (Admin only.)

        Requires first importing the game via !import.

        Usage example:
        !tag 80207 ABK
        !t 76885 SCVI
        """

        available_tags = self.get_available_tags(ctx.guild)

        #tag = discord.utils.get(available_tags, name=tag_name)
        tag = discord.utils.find(
            lambda tag: tag.name.casefold() == tag_name.casefold(), available_tags)

        if tag is None:
            msg = await ctx.send("No existing tag found by that name, creating now.")
            try:
                tag = await ctx.guild.create_role(
                    name=tag_name,
                    mentionable=True,
                    reason=f"{ctx.author} requested role creation through {ctx.command.name}"
                    )
            except:
                await msg.edit(content="Failed to create Discord role.")
                raise
            else:
                await msg.edit(content="Discord role created.")

        games = []
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("SELECT id, name FROM games WHERE id = ?", [game_id])
            game = cursor.fetchone()
            if game is None:
                await ctx.send("No game found with that ID in internal database. Try importing it first.")
            else:
                # insert or replace into tags
                cursor.execute("""
                    REPLACE INTO tags (id)
                    VALUES (?)
                """, [tag.id])
                # insert or replace into game_tags
                cursor.execute("""
                    REPLACE INTO game_tags (tag_id, game_id)
                    VALUES (?, ?)
                """, [tag.id, game['id']])

                conn.commit()
                await ctx.send(f"```'{tag.name}' is now associated with '{game['name']}'```")
        except:
            conn.rollback()
            raise
        finally:
            conn.close()

    # non admin-only commands print their !help when not enough arguments are given
    @list_games.error
    @play_game.error
    @drop_game.error
    @list_players.error
    async def missing_required_argument_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await self.send_help(ctx)
        raise error

    # admin-only commands print !help like regular ones but also print other errors
    @search_IGDB.error
    @import_game.error
    @tag_game.error
    async def _error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await self.send_help(ctx)
        else:
            await ctx.send(error)
        raise error

    def send_help(self, ctx):
        return ctx.invoke(self.bot.get_command('help'), ctx.command.name)

def setup(bot):
    bot.add_cog(Gametags(bot))
