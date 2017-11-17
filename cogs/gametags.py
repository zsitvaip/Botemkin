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
        everyone_role = guild.roles[0]
        available_tags = list(filter(
            lambda role: role.permissions <= everyone_role.permissions, guild.roles[1:]))

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

    def get_games_details_from_db(self, guild_id):
        game_rows = []
        try:
            conn = sqlite3.connect(self.db_path, isolation_level=None)
            conn.row_factory = sqlite3.Rows
            cursor = conn.cursor()

            cursor.execute("""
                SELECT games.id, games.name, game_details.resources
                FROM games
                LEFT OUTER JOIN game_details ON games.id = game_tags.game_id
                WHERE game_details.guild_id = ?
            """, guild_id)
            game_rows = cursor.fetchall()
        finally:
            conn.close()
        
        return game_rows

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

        for row in rows:
            print(row)

        gametags = []
        if rows:
            for tag_id, game_id, game_name in rows:
                tag = discord.utils.get(tags, id=tag_id)
                gametags.append({'tag': tag, 'game_id': game_id, 'game_name': game_name})

        return gametags

    def get_platformtags_from_db(self, tags, *, all = False):
        rows = []
        try:
            conn = sqlite3.connect(self.db_path, isolation_level=None)
            cursor = conn.cursor()

            if all:
                cursor.execute(f"""
                    SELECT platform_tags.tag_id, platforms.id, platforms.name
                    FROM platforms
                    LEFT OUTER JOIN platform_tags ON platforms.id = platform_tags.platform_id
                    ORDER BY platforms.name ASC
                """)
            else:
                cursor.execute(f"""
                    SELECT platform_tags.tag_id, platforms.id, platforms.name
                    FROM platforms
                    INNER JOIN platform_tags ON platforms.id = platform_tags.platform_id
                    WHERE platform_tags.tag_id IN (?{(len(tags) - 1) * ', ?'})
                    ORDER BY platforms.name ASC
                """, [tag.id for tag in tags])
            rows = cursor.fetchall()
        finally:
            conn.close()

        platformtags = []
        if rows:
            for tag_id, platform_id, platform_name in rows:
                tag = discord.utils.get(tags, id=tag_id)
                platformtags.append({'tag': tag, 'platform_id': platform_id, 'platform_name': platform_name})

        return platformtags

    def get_gentags_from_db(self, tags, *, all = False):
        rows = []
        try:
            conn = sqlite3.connect(self.db_path, isolation_level=None)
            cursor = conn.cursor()

            cursor.execute(f"""
                SELECT id, description
                FROM tags
                WHERE id IN (?{(len(tags) - 1) * ', ?'}) AND description NOT NULL
                ORDER BY id ASC
            """, [tag.id for tag in tags])

            rows = cursor.fetchall()
        finally:
            conn.close()

        gentags = []
        if rows:
            for tag_id, gentag_name in rows:
                tag = discord.utils.get(tags, id=tag_id)
                gentags.append({'tag': tag, 'description': gentag_name})

        return gentags

    # TODO do I need async here? probably
    async def is_admin(ctx):
        return ctx.author.guild_permissions.administrator

    @commands.group(aliases=['g'])
    async def game(self, ctx):
        """Commands for tags relating to games (aka gametags)."""

        if ctx.invoked_subcommand is None:
            await ctx.send("```Try: !help game```")

    @game.command(name='search', aliases=['s'], usage='<game_name>')
    async def game_search(self, ctx, *, game_name: str):
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

    @game.command(name='import', aliases=['i'], usage='<game_id>')
    @commands.check(is_admin)
    async def game_import(self, ctx, game_id: int):
        """Imports game from external database (IGDB) to internal. (Admin only)"""
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

    @game.group(name='list', aliases=['ls', 'l'], usage='[all|a]')
    async def game_list(self, ctx):
        """Lists all available gametags."""
        
        if ctx.invoked_subcommand.qualified_name != 'game list':
            return

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


    @game_list.command(name='all', aliases=['a'])
    async def game_list_all(self, ctx):
        """Lists all games and associated tags (if any)."""

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

    # TODO error message for required argument missing
    @game.command(name='play', aliases=['on'], usage='<gametags>')
    async def game_on(self, ctx, *tag_names):
        """Assigns you the listed gametags."""
        
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
            msg_str += f"```Unknown gametags: {', '.join(unknown_tag_names)}\nTry: !game list```"

        await ctx.send(msg_str)

    @game.command(name='drop', aliases=['off'], usage='<gametags>')
    async def game_off(self, ctx, *tag_names):
        """Removes your listed gametags."""

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
            msg_str += f"```Unknown gametags: {', '.join(unknown_tag_names)}\nTry: !game list```"

        await ctx.send(msg_str)

    @game.command(name='players', aliases=['p'], usage='<gametag>')
    async def game_players(self, ctx, role: commands.RoleConverter):
        """Lists players (and their status) with given gametag."""

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

    @game.group(name='add', aliases=['a'], invoke_without_command=True)
    @commands.check(is_admin)
    async def game_add(self, ctx): 
        """Add or update the following game attribute. (Admin only)"""

        # TODO fix so that it shows even if no subcommand is given (now it only shows on wrong subcommand)
        # invoke_without_command=True seems to have fixed this but not sure why, investigate
        if ctx.invoked_subcommand is None:
            await ctx.send("```Try: !help game add```")

    # TODO check if I need is_admin in subcommands if parent has it
    @game_add.command(name='tag', aliases=['t'], usage='<game_id> <role_name>')
    @commands.check(is_admin)
    async def game_add_tag(self, ctx, game_id: int, tag_name):
        """Associate game with given tag. (Admin only)"""

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

    def get_gtags_from_db(self, tags, *, all = False):
        rows = []
        try:
            conn = sqlite3.connect(self.db_path, isolation_level=None)
            cursor = conn.cursor()

            cursor.execute(f"""
                SELECT id, description
                FROM tags
                WHERE id IN (?{(len(tags) - 1) * ', ?'}) AND description NOT NULL
                ORDER BY id ASC
            """, [tag.id for tag in tags])

            rows = cursor.fetchall()
        finally:
            conn.close()

        gtags = []
        if rows:
            for tag_id, gtag_id, gtag_name in rows:
                tag = discord.utils.get(tags, id=tag_id)
                gtags.append({'tag': tag, 'description': gtag_name})

        return gtags
    
    '''
    @game_add.command(name='resource', aliases=['res', 'r'], usage='<game_id> <resources>')
    @commands.check(is_admin)
    async def game_add_resource(self, ctx, game_id: int, tag_name):
        """Add resources to game. (Admin only)"""
        pass
    '''

    @commands.group(aliases=['p'])
    async def platform(self, ctx):
        """Commands for tags relating to platforms (aka platformtags)."""

        if ctx.invoked_subcommand is None:
            await ctx.send("```Try: !help platform```")

    @platform.command(name='search', aliases=['s'], usage='<platform_name>')
    async def platform_search(self, ctx, *, game_name: str):
        """Search IGDB for given platform name."""
        try:
            result = self.igdb.platforms({
            'search': game_name,
            'fields': ['name', 'slug']
            })
            platforms = []
            for platform in result.body:
                platforms.append(f"#{platform['id']} {platform['name']} ({platform['slug']})")
            if platforms:
                await ctx.send(f"Search results from IGDB.com:```css\n{chr(10).join(platforms)}```")
            else:
                await ctx.send("No search results from IGDB.com.")
        except:
            await ctx.send("An error occured.")
            raise

    @platform.command(name='import', aliases=['i'], usage='<platform_id>')
    @commands.check(is_admin)
    async def platform_import(self, ctx, platform_id: int):
        """Imports platform from external database (IGDB) to internal. (Admin only)"""
        try:
            result = self.igdb.platforms({
                'ids': platform_id
            })
            
            platforms = result.body
            if platforms:
                platform = platforms[0]
                
                try:
                    conn = sqlite3.connect(self.db_path, isolation_level=None)
                    conn.execute('PRAGMA foreign_keys = ON')
                    cursor = conn.cursor()
                    
                    cursor.execute("SELECT 1 FROM platforms WHERE id = ?", [platform['id']])
                    if cursor.fetchone() is None:
                        conn.execute("INSERT INTO platforms (id, name) VALUES (?, ?)", [platform['id'], platform['name']])
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

    @platform.group(name='list', aliases=['ls', 'l'], usage='[all|a]')
    async def platform_list(self, ctx):
        """Lists all available platformtags."""
        
        if ctx.invoked_subcommand.qualified_name != 'platform list':
            return

        available_tags = self.get_available_tags(ctx.guild)

        if available_tags:
            
            platformtags = self.get_platformtags_from_db(available_tags)
            
            if platformtags:
                msg_str = ""
                for platformtag in platformtags:
                    msg_str += f"{platformtag['tag'].name} [{platformtag['platform_name']}]#{platformtag['platform_id']}\n"
                await ctx.send(f"Available platformtags:```css\n{msg_str}```")

            else:
                await ctx.send(f"```There are currently no available platformtags.```")
        else:
            await ctx.send(f"```There are currently no available tags.```")


    @platform_list.command(name='all', aliases=['a'])
    async def platform_list_all(self, ctx):
        """Lists all platforms and associated tags (if any)."""

        available_tags = self.get_available_tags(ctx.guild)

        platformtags = self.get_platformtags_from_db(available_tags, all=True)
        if platformtags:
            msg_str = ""
            for platformtag in platformtags:
                platformtag_name = "\t"
                if platformtag['tag']:
                    platformtag_name = f"{platformtag['tag'].name} "
                msg_str += f"{platformtag_name}[{platformtag['platform_name']}]#{platformtag['platform_id']}\n"
            await ctx.send(f"Imported platforms:```css\n{msg_str}```")

        else:
            await ctx.send(f"```There are currently no imported platforms.```")

    @platform.command(name='own', aliases=['buy', 'play', 'on'], usage='<platformtags>')
    async def platform_on(self, ctx, *tag_names):
        """Assigns you the listed platformtags."""
        
        selected_tags, unknown_tag_names = self.get_selected_tags(ctx.guild, tag_names)

        msg_str = ""
        if selected_tags:

            platformtags = self.get_platformtags_from_db(selected_tags)
            
            tags = []
            if platformtags:
                
                platform_names = []
                for platformtag in platformtags:
                    tags.append(platformtag['tag'])
                    platform_names.append(platformtag['platform_name'])

                # TODO handle permission denied
                await ctx.author.add_roles(*tags, reason=f"{ctx.author} requested platformtags")

                msg_str += f"{ctx.author.display_name} now plays on "
                
                if len(platform_names) > 1:
                    msg_str += f"{', '.join(platform_names[0:-1])} and {platform_names[-1]}! "
                else:
                    msg_str += f"{platform_names[0]}! "
                
                e = discord.utils.get(ctx.guild.emojis, name='quan')
                if e:
                    msg_str += len(platform_names) * f"<:{e.name}:{e.id}>"

            [unknown_tag_names.append(tag.name) for tag in selected_tags if tag not in tags]

        if unknown_tag_names:
            msg_str += f"```Unknown platformtags: {', '.join(unknown_tag_names)}\nTry: !platform list```"

        await ctx.send(msg_str)

    @platform.command(name='sell', aliases=['off'], usage='<platformtags>')
    async def platform_off(self, ctx, *tag_names):
        """Removes your listed platformtags."""

        selected_tags, unknown_tag_names = self.get_selected_tags(ctx.guild, tag_names)

        msg_str = ""
        if selected_tags:

            platformtags = self.get_platformtags_from_db(selected_tags)
            
            tags = []
            if platformtags:

                platform_names = []
                for platformtag in platformtags:
                    tags.append(platformtag['tag'])
                    platform_names.append(platformtag['platform_name'])

                await ctx.author.remove_roles(*tags, reason=f"{ctx.author} relinquished platformtags")

                msg_str += f"{ctx.author.display_name} just sold their "
                
                if len(platform_names) > 1:
                    msg_str += f"{', '.join(platform_names[0:-1])} and {platform_names[-1]}! "
                else:
                    msg_str += f"{platform_names[0]}! "
                
                e = discord.utils.get(ctx.guild.emojis, name='salt')
                if e:
                    msg_str += len(platform_names) * f"<:{e.name}:{e.id}>"

            [unknown_tag_names.append(tag.name) for tag in selected_tags if tag not in tags]

        if unknown_tag_names:
            msg_str += f"```Unknown platformtags: {', '.join(unknown_tag_names)}\nTry: !platform list```"

        await ctx.send(msg_str)

    @platform.command(name='players', aliases=['p'], usage='<platformtag>')
    async def platform_players(self, ctx, role: commands.RoleConverter):
        """Lists players (and their status) with given platformtag."""

        platform = None
        try:
            conn = sqlite3.connect(self.db_path, isolation_level=None)
            cursor = conn.cursor()

            cursor.execute(f"""
                SELECT platforms.name
                FROM platforms
                INNER JOIN platform_tags ON platforms.id = platform_tags.platform_id
                WHERE platform_tags.tag_id = ?
            """, [role.id])

            platform = cursor.fetchone()
        finally:
            conn.close()

        if platform:
            msg_str = ""
            for player in role.members:
                if player.status == discord.Status.offline:
                    msg_str += f"{player.display_name} #{player.status}\n"
                else:
                    msg_str += f"{player.display_name} [{player.status}]\n"
            if msg_str:
                await ctx.send(f"Players on {platform[0]}:```css\n{msg_str}```")
            else:
                await ctx.send("ded platform")

    @platform.group(name='add', aliases=['a'])
    @commands.check(is_admin)
    async def platform_add(self, ctx): 
        """Add or update the following platform attribute. (Admin only)"""

        if ctx.invoked_subcommand is None:
            await ctx.send("```Try: !help platform add```")

    @platform_add.command(name='tag', aliases=['t'], usage='<platform_id> <role_name>')
    @commands.check(is_admin)
    async def platform_add_tag(self, ctx, platform_id: int, tag_name):
        """Associate platform with given tag. (Admin only)"""

        available_tags = self.get_available_tags(ctx.guild)
        
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

        platforms = []
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("SELECT id, name FROM platforms WHERE id = ?", [platform_id])
            platform = cursor.fetchone()
            if platform is None:
                await ctx.send("No platform found with that ID in internal database. Try importing it first.")
            else:
                # insert or replace into tags
                cursor.execute("""
                    REPLACE INTO tags (id)
                    VALUES (?)
                """, [tag.id])
                # insert or replace into platform_tags
                cursor.execute("""
                    REPLACE INTO platform_tags (tag_id, platform_id)
                    VALUES (?, ?)
                """, [tag.id, platform['id']])

                conn.commit()
                await ctx.send(f"```'{tag.name}' is now associated with '{platform['name']}'```")
        except:
            conn.rollback()
            raise
        finally:
            conn.close()

    @commands.group(aliases='t')
    async def tag(self, ctx):
        """Commands for tags not belonging to a subcategory (aka generic tags)."""

        if ctx.invoked_subcommand is None:
            await ctx.send("```Try: !help tag```")

    @tag.group(name='list', aliases=['ls', 'l'])
    async def tag_list(self, ctx):
        """Lists all available generic tags."""
        
        available_tags = self.get_available_tags(ctx.guild)

        if available_tags:
            
            gentags = self.get_gentags_from_db(available_tags)
            
            if gentags:
                msg_str = ""
                for gentag in gentags:
                    tag = gentag['tag']
                    msg_str += f"{gentag['tag'].name} [{gentag['description']}]\n"
                await ctx.send(f"Available generic tags:```css\n{msg_str}```")

            else:
                await ctx.send(f"```There are currently no available generic tags.```")
        else:
            await ctx.send(f"```There are currently no available tags.```")

    @commands.check(is_admin)
    @tag.command(name='create', aliases=['c'], usage='<role_name> <description>')
    async def tag_create(self, ctx, tag_name: str, description: str):
        """Create a generic tag, must have a description. (Admin only)"""

        available_tags = self.get_available_tags(ctx.guild)
        
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

        try:
            conn = sqlite3.connect(self.db_path, isolation_level=None)
            cursor = conn.cursor()

            cursor.execute("SELECT 1 FROM game_tags WHERE tag_id = ?", [tag.id])
            existing_gametag = cursor.fetchone()
            cursor.execute("SELECT 1 FROM platform_tags WHERE tag_id = ?", [tag.id])
            existing_platformtag = cursor.fetchone()
            
            if existing_gametag or existing_platformtag:
                await ctx.send("This tag is already associated with an entity.")
            else:
                conn.execute("REPLACE INTO tags (id, description) VALUES (?, ?)", [tag.id, description])
                await ctx.send("Added/updated generic tag.")
        except:
            raise
        finally:
            conn.close()

    @tag.command(name='get', aliases=['on'], usage='<tag>')
    async def tag_on(self, ctx, *tag_names):
        """Assigns you the listed generic tags."""

        selected_tags, unknown_tag_names = self.get_selected_tags(ctx.guild, tag_names)

        msg_str = ""
        if selected_tags:

            gentags = self.get_gentags_from_db(selected_tags)
            
            tags = []
            if gentags:
                
                tag_names = []
                for gentag in gentags:
                    tags.append(gentag['tag'])
                    tag_names.append(gentag['tag'].name) # TODO optimize

                await ctx.author.add_roles(*tags, reason=f"{ctx.author} requested generic tags")

                msg_str += f"{ctx.author.display_name} now has tag"
                
                if len(tag_names) > 1:
                    msg_str += f"s {', '.join(tag_names[0:-1])} and {tag_names[-1]}! "
                else:
                    msg_str += f" {tag_names[0]}! "
                
                e = discord.utils.get(ctx.guild.emojis, name='quan')
                if e:
                    msg_str += len(tag_names) * f"<:{e.name}:{e.id}>"

            [unknown_tag_names.append(tag.name) for tag in selected_tags if tag not in tags]

        if unknown_tag_names:
            msg_str += f"```Unknown generic tags: {', '.join(unknown_tag_names)}\nTry: !tag list```"

        await ctx.send(msg_str)

    @tag.command(name='strip', aliases=['off'], usage='<tag>')
    async def tag_off(self, ctx, *tag_names):
        """Removes your listed generic tags."""

        selected_tags, unknown_tag_names = self.get_selected_tags(ctx.guild, tag_names)

        msg_str = ""
        if selected_tags:

            gentags = self.get_gentags_from_db(selected_tags)
            
            tags = []
            if gentags:
                
                tag_names = []
                for gentag in gentags:
                    tags.append(gentag['tag'])
                    tag_names.append(gentag['tag'].name) # TODO optimize

                await ctx.author.remove_roles(*tags, reason=f"{ctx.author} relinquished generic tags")

                msg_str += f"{ctx.author.display_name} just stripped tag"
                
                if len(tag_names) > 1:
                    msg_str += f"s {', '.join(tag_names[0:-1])} and {tag_names[-1]}! "
                else:
                    msg_str += f" {tag_names[0]}! "
                
                e = discord.utils.get(ctx.guild.emojis, name='salt')
                if e:
                    msg_str += len(tag_names) * f"<:{e.name}:{e.id}>"

            [unknown_tag_names.append(tag.name) for tag in selected_tags if tag not in tags]

        if unknown_tag_names:
            msg_str += f"```Unknown generic tags: {', '.join(unknown_tag_names)}\nTry: !tag list```"

        await ctx.send(msg_str)

    # TODO make it actually useful now that it works at all
    @tag_on.error
    @tag_off.error
    @tag_create.error
    @game_on.error
    @game_off.error
    @game_players.error
    @game_add.error
    @game_add_tag.error
    @platform_on.error
    @platform_off.error
    @platform_players.error
    @platform_add.error
    @platform_add_tag.error
    async def players_error(self, ctx, error):
        #if isinstance(error, commands.MissingRequiredArgument):
        #    await ctx.send(error)
        await ctx.send(error)

def setup(bot):
    bot.add_cog(Gametags(bot))