from collections import namedtuple
from enum import Enum
import logging
import pathlib
import sqlite3

import discord
from discord.ext import commands

# for IGDB wrapper
import requests
import json

from . import config

log = logging.getLogger(__name__)

class ItemType(Enum):
    game = 1
    platform = 2

    def __str__(self):
        return self.name

    # TODO really this should be a lookup in a list/dict
    def pre(self):
        if self.value is 1:
            return ''
        if self.value is 2:
            return 'on '

# TODO python 3.7: consider changing these to dataclasses, setting defaults is also simpler
Item = namedtuple('Item', 'type id name slug')
Item.__new__.__defaults__ = (None,) * len(Item._fields)

Itemtag = namedtuple('Itemtag', 'item tag')

class Gametags(commands.Cog):
    """Module for handling self-assignable roles (aka tags)."""

    def __init__(self, bot):
        self.bot = bot
        self.repository = ItemtagRepository()
        self.repository.setup()
        self.igdb_wrapper = IgdbWrapper(config.igdb_key)

    async def is_developer(ctx):
        dev_role = discord.utils.find(
                lambda role: role.name.casefold() == 'botemkin developer'.casefold(), ctx.author.roles)
        return dev_role is not None

    # TODO make async?
    def _get_available_tags(self, guild : discord.Guild):
        everyone_role = discord.utils.find(
            lambda role: role.id == guild.id, guild.roles)

        # TODO this doesn't seem to actually filter out roles by permission
        available_tags = list(filter(
            lambda role: role.id != everyone_role.id and role.permissions <= everyone_role.permissions, guild.roles))

        return available_tags

    # TODO make async?
    def _get_selected_tags(self, guild : discord.Guild, requested_tag_names: list):
        # TODO use sets and the intersection/difference functions
        available_tags = self._get_available_tags(guild)

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

    async def _search_IGDB_item(self, ctx, item_type, item_name):
        try:
            items = await self.igdb_wrapper.find_items_by_name(item_type, item_name)
            table_rows = []
            for item in items:
                table_rows.append(f"#{item.id} {item.name} ({item.slug})")
            if table_rows:
                await ctx.send(f"Search results from the *Internet Game Database* (<https://www.igdb.com>):```css\n{chr(10).join(table_rows)}```")
            else:
                await ctx.send("No search results from the *Internet Game Database* (<https://www.igdb.com>).")
        except:
            await ctx.send("An error occured while accessing the *Internet Game Database* (<https://www.igdb.com>).")
            raise

    @commands.command(name='search_game', aliases=['search', 'sg', 's'], usage='<game_name>')
    @commands.check(is_developer)
    async def search_IGDB_game(self, ctx, *, game_name):
        """Search IGDB for given game name. (dev-only)

        Use to get the game id to be used with the !tag_game command.

        Usage examples:

        !search puyo tetris
        !s dong never die
        """
        await self._search_IGDB_item(ctx, ItemType.game, game_name)

    @commands.command(name='search_platform', aliases=['search_plat', 'sp'], usage='<platform_name>')
    @commands.check(is_developer)
    async def search_IGDB_platform(self, ctx, *, platform_name):
        """Search IGDB for given platform name. (dev-only)

        Use to get the platform id to be used with the !tag_platform command.

        Usage examples:

        !search_plat plebstation
        !sp pc masterrace
        """
        await self._search_IGDB_item(ctx, ItemType.platform, platform_name)

    async def _print_itemtags(self, item_type, tags):
        itemtags = await self.repository.find_itemtags_by_tags(item_type, tags)
        msg_str = ""
        if itemtags:
            for itemtag in itemtags:
                msg_str += f"{itemtag.tag.name} [{itemtag.item.name}]#{itemtag.item.id}\n"
        return msg_str

    async def _print_all_itemtags(self, item_type, tags):
        itemtags = await self.repository.find_itemtags_by_tags(item_type, tags, all=True)
        msg_str = ""
        if itemtags:
            for itemtag in itemtags:
                itemtag_name = "\t"
                if itemtag.tag:
                    itemtag_name = f"{itemtag.tag.name} "
                msg_str += f"{itemtag_name}[{itemtag.item.name}]#{itemtag.item.id}\n"
        return msg_str

    async def _list_available_tags(self, ctx):
        available_tags = self._get_available_tags(ctx.guild)
        msg_str = ""
        if available_tags:
            for item_type in ItemType:
                ret_str = await self._print_itemtags(item_type, available_tags)
                if ret_str:
                    msg_str += f"Available {item_type}tags:```css\n{ret_str}```"
                else:
                    msg_str += f"```There are currently no available {item_type}tags.```"
        else:
            msg_str = f"```There are currently no available tags.```"
        await ctx.send(msg_str)

    async def _list_all_tags(self, ctx):
        available_tags = self._get_available_tags(ctx.guild)
        msg_str = ""
        for item_type in ItemType:
            ret_str = await self._print_all_itemtags(item_type, available_tags)
            if ret_str:
                msg_str += f"Imported {item_type}s:```css\n{ret_str}```"
            else:
                msg_str += f"```There are currently no imported {item_type}s.```"
        await ctx.send(msg_str)

    @commands.command(name='list', aliases=['ls', 'l'], usage='[all]')
    async def list_available_tags(self, ctx, arg=None):
        """Lists available tags.

        Use with 'all' to show all games/platforms imported from IGDB including ones without tags associated with them.

        Usage examples:

        !list
        !ls all
        !l a
        """

        if arg in ['a', 'al', 'all']:
            await self._list_all_tags(ctx)
        else:
            await self._list_available_tags(ctx)

    async def _assign_tags_by_name(self, ctx, item_type, tag_names):
        selected_tags, unknown_tag_names = self._get_selected_tags(ctx.guild, tag_names)
        msg_str = ""
        if selected_tags:

            itemtags = await self.repository.find_itemtags_by_tags(item_type, selected_tags)
            tags = []
            if itemtags:

                item_names = []
                for itemtag in itemtags:
                    tags.append(itemtag.tag)
                    item_names.append(itemtag.item.name)

                # TODO handle permission denied
                await ctx.author.add_roles(*tags, reason=f"{ctx.author} requested {item_type}tags")

                msg_str += f"{ctx.author.display_name} now plays {item_type.pre()}"

                if len(item_names) > 1:
                    msg_str += f"*{', '.join(item_names[0:-1])}* and *{item_names[-1]}*! "
                else:
                    msg_str += f"*{item_names[0]}*! "

                e = discord.utils.get(ctx.guild.emojis, name='quan')
                if e:
                    msg_str += len(item_names) * f"<:{e.name}:{e.id}>"

            [unknown_tag_names.append(tag.name) for tag in selected_tags if tag not in tags]

        if unknown_tag_names:
            msg_str += f"```Unknown {item_type}tags: {', '.join(unknown_tag_names)}```Use **!list** to print available {item_type}tags."

        await ctx.send(msg_str)


    @commands.command(name='play', aliases=['p'], usage='<gametags>')
    async def play_game(self, ctx, *tag_names):
        """Assigns you the listed gametags.

        Usage examples:

        !play T7
        !p GG Melty UNIST
        """

        # required because *tag_names being empty does not trigger a MissingRequiredArgument
        if not tag_names:
            return await ctx.send_help(ctx.command)
        await self._assign_tags_by_name(ctx, ItemType.game, tag_names)

    @commands.command(name='platform', aliases=['plat'], usage='<platformtags>')
    async def play_on_platform(self, ctx, *tag_names):
        """Assigns you the listed platformtags.

        Usage examples:

        !platform PC
        !plat PS4 XBONE
        """

        # required because *tag_names being empty does not trigger a MissingRequiredArgument
        if not tag_names:
            return await ctx.send_help(ctx.command)
        await self._assign_tags_by_name(ctx, ItemType.platform, tag_names)

    async def _remove_any_tags_by_name(self, ctx, tag_names):
        selected_tags, unknown_tag_names = self._get_selected_tags(ctx.guild, tag_names)
        msg_str = ""
        if selected_tags:

            gametags = await self.repository.find_itemtags_by_tags(ItemType.game, selected_tags)
            platformtags = await self.repository.find_itemtags_by_tags(ItemType.platform, selected_tags)
            itemtags = gametags + platformtags
            tags = []
            if itemtags:

                item_names = []
                for itemtag in itemtags:
                    tags.append(itemtag.tag)
                    item_names.append(itemtag.item.name)

                await ctx.author.remove_roles(*tags, reason=f"{ctx.author} relinquished tags")

                msg_str += f"{ctx.author.display_name} just dropped "

                if len(item_names) > 1:
                    msg_str += f"*{', '.join(item_names[0:-1])}* and *{item_names[-1]}*! "
                else:
                    msg_str += f"*{item_names[0]}*! "

                e = discord.utils.get(ctx.guild.emojis, name='salt')
                if e:
                    msg_str += len(item_names) * f"<:{e.name}:{e.id}>"

            [unknown_tag_names.append(tag.name) for tag in selected_tags if tag not in tags]

        if unknown_tag_names:
            msg_str += f"```Unknown tags: {', '.join(unknown_tag_names)}```Use **!list** to print available tags."

        await ctx.send(msg_str)

    @commands.command(name='drop', aliases=['d'], usage='<tags>')
    async def drop(self, ctx, *tag_names):
        """Removes your listed tags.

        Usage examples:

        !drop IJ2
        !d DBFZ BBTag
        """

        # required because *tag_names being empty does not trigger a MissingRequiredArgument
        if not tag_names:
            return await ctx.send_help(ctx.command)
        await self._remove_any_tags_by_name(ctx, tag_names)

    # TODO perhaps only display offline members if an extra parameter (such as 'all') is given
    @commands.command(name='players', aliases=['ps'], usage='<tags>')
    async def show_players(self, ctx, *role_names):
        """Shows players (and their status) with given tags. When given mutiple tags only show players who match all of them.

        Usage examples:

        !players SFV
        !ps PS4
        !ps GG BBCF PC
        """

        # required because *tag_names being empty does not trigger a MissingRequiredArgument
        if not role_names:
            return await ctx.send_help(ctx.command)
        if len(role_names) > 1:
            await self._intersect_players(ctx, role_names)
        else:
            await self._show_players_for_single_role(ctx, role_names[0])

    async def _show_players_for_single_role(self, ctx, role_name):
        role = discord.utils.find(
            lambda role: role.name.casefold() == role_name.casefold(), ctx.guild.roles)

        if not role:
            await ctx.send(f"```Unknown tag: {role_name}```Use **!list** to print available tags.")
            return

        item = await self.repository.find_any_item_by_tag(role)
        if item:
            msg_str = ""
            for player in role.members:
                if player.status == discord.Status.offline:
                    msg_str += f"{player.display_name} #{player.status}\n"
                else:
                    msg_str += f"{player.display_name} [{player.status}]\n"
            if msg_str:
                num = len(role.members)
                msg_str = (f"*{item.name}* has {num} player{'s' if num else ''}:```css\n{msg_str}```")
            else:
                msg_str = f"*{role.name}* is a **DEAD** {item.type}"
                e = discord.utils.get(ctx.guild.emojis, name='rip')
                if e:
                    msg_str = f"<:{e.name}:{e.id}> {msg_str} <:{e.name}:{e.id}>"
        else:
            msg_str = f"```Not a tag: {role.name}```Use **!list** to print available tags."

        await ctx.send(msg_str)

    async def _intersect_players(self, ctx, role_names):
        selected_tags, unknown_tag_names = self._get_selected_tags(ctx.guild, role_names)
        if not selected_tags:
            return await ctx.send("No matching tags found.")

        valid_role_names = [role.name for role in selected_tags]

        players = set(selected_tags[0].members)
        for role in selected_tags[1:]:
            players &= set(role.members)
        if not players:
            return await ctx.send(f"No players who match all of the following tags: *{'*, *'.join(valid_role_names)}*.")

        msg_str = ""
        for player in players:
            if player.status == discord.Status.offline:
                msg_str += f"{player.display_name} #{player.status}\n"
            else:
                msg_str += f"{player.display_name} [{player.status}]\n"

        num = len(players)
        msg_str =  f"The following tags are matched by {num} player{'s' if num else ''}: *{'*, *'.join(valid_role_names)}*.```css\n{msg_str}```"
        if unknown_tag_names:
            msg_str += f"```Unknown tags: {', '.join(unknown_tag_names)}```Use **!list** to print available tags."

        await ctx.send(msg_str)

    async def _tag_item(self, ctx, item_type, item_id, tag_name):
        item = await self.igdb_wrapper.find_item_by_id(item_type, item_id)
        if item:
            ret = await self.repository.add_item(item)
            if ret:
                await ctx.send(f"Added *{item.name}* to internal database.")
            else:
                await ctx.send(f"Found *{item.name}* in internal database.")
        else:
            await ctx.send(f"Could not find {item_type} in external database.")
            return

        available_tags = self._get_available_tags(ctx.guild)

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

        itemtag = Itemtag(item, tag)
        try:
            await self.repository.add_itemtag(itemtag)
        except:
            await ctx.send(f"Failed to add {item_type}tag to internal database.")
            raise
        await ctx.send(f"The {item_type}tag {tag.mention} is now associated with *{item.name}*.")

    @commands.command(name='tag_game', aliases=['tag', 'tg', 't'], usage='<game_id> <role_name>')
    @commands.check(is_developer)
    async def tag_game(self, ctx, game_id: int, tag_name: str):
        """Associate game with given tag. (dev-only)

        To find the game id use the !search_game command.

        Usage examples:

        !tag 80207 ABK
        !t 76885 SCVI
        """
        await self._tag_item(ctx, ItemType.game, game_id, tag_name)

    @commands.command(name='tag_platform', aliases=['tag_plat', 'tp'], usage='<platform_id> <role_name>')
    @commands.check(is_developer)
    async def tag_platform(self, ctx, platform_id: int, tag_name: str):
        """Associate platform with given tag. (dev-only)

        To find the platform id use the !search_platform command.

        Usage examples:

        !tag_platform 6 PC
        !tag_plat 48 PS4
        """
        await self._tag_item(ctx, ItemType.platform, platform_id, tag_name)

    # non dev-only commands print their !help when not enough arguments are given
    # @play_game.error
    @play_on_platform.error
    @drop.error
    @show_players.error
    async def _missing_required_argument_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send_help(ctx.command)
        raise error

    # dev-only commands print !help like regular ones but also print other errors
    @search_IGDB_game.error
    @search_IGDB_platform.error
    @tag_game.error
    @tag_platform.error
    async def _verbose_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send_help(ctx.command)
        else:
            await ctx.send(f"```{error}```")
        raise error

def setup(bot):
    bot.add_cog(Gametags(bot))

class ItemtagRepository:

    def __init__(self):
        self.data_dir = 'data/'
        self.db_path = f'{self.data_dir}gametag.db'

    def setup(self):
        pathlib.Path(self.data_dir).mkdir(parents=True, exist_ok=True)
        try:
            conn = sqlite3.connect(self.db_path, isolation_level=None)
            cursor = conn.cursor()
            cursor.execute('PRAGMA journal_mode = wal')
            cursor.execute('PRAGMA foreign_keys = ON')

            cursor.execute('BEGIN')
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tags (
                    id INTEGER PRIMARY KEY,
                    description TEXT
                )"""
            )
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS games (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL
                )"""
            )
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS platforms (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL
                )"""
            )
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS game_tags (
                    tag_id INTEGER,
                    game_id INTEGER NOT NULL UNIQUE,
                    PRIMARY KEY (tag_id),
                    FOREIGN KEY (tag_id) REFERENCES tags(id),
                    FOREIGN KEY (game_id) REFERENCES games(id)
                )"""
            )
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS platform_tags (
                    tag_id INTEGER,
                    platform_id INTEGER NOT NULL UNIQUE,
                    PRIMARY KEY (tag_id),
                    FOREIGN KEY (tag_id) REFERENCES tags(id),
                    FOREIGN KEY (platform_id) REFERENCES platforms(id)
                )"""
            )
            conn.commit()
        except:
            conn.rollback()
            raise
        finally:
            conn.close()

    async def add_item(self, item):
        try:
            conn = sqlite3.connect(self.db_path, isolation_level=None)
            cursor = conn.cursor()
            cursor.execute(f"INSERT INTO {item.type}s (id, name) VALUES (?, ?)", [item.id, item.name])
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()

    async def add_itemtag(self, itemtag):
        item = itemtag.item
        tag = itemtag.tag

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # insert or replace into tags
            cursor.execute("""
                REPLACE INTO tags (id)
                VALUES (?)
            """, [tag.id])
            # insert or replace into <item_type>_tags
            cursor.execute(f"""
                REPLACE INTO {item.type}_tags (tag_id, {item.type}_id)
                VALUES (?, ?)
            """, [tag.id, item.id])

            conn.commit()
        except:
            conn.rollback()
            raise
        finally:
            conn.close()

    async def find_item_by_tag(self, item_type, tag):
        item = None
        try:
            conn = sqlite3.connect(self.db_path, isolation_level=None)
            cursor = conn.cursor()

            cursor.execute(f"""
                SELECT {item_type}s.id, {item_type}s.name
                FROM {item_type}s
                INNER JOIN {item_type}_tags ON {item_type}s.id = {item_type}_tags.{item_type}_id
                WHERE {item_type}_tags.tag_id = ?
            """, [tag.id])

            row = cursor.fetchone()
            if (row):
                item = Item(item_type, row[0], row[1])
        finally:
            conn.close()
        return item

    async def find_any_item_by_tag(self, tag):
        item = None
        for item_type in ItemType:
            item = await self.find_item_by_tag(item_type, tag)
            if item:
                break
        return item

    async def find_itemtags_by_tags(self, item_type, tags, *, all = False):
        rows = []
        try:
            conn = sqlite3.connect(self.db_path, isolation_level=None)
            cursor = conn.cursor()

            if all:
                cursor.execute(f"""
                    SELECT {item_type}_tags.tag_id, {item_type}s.id, {item_type}s.name
                    FROM {item_type}s
                    LEFT OUTER JOIN {item_type}_tags ON {item_type}s.id = {item_type}_tags.{item_type}_id
                    ORDER BY {item_type}s.name ASC
                """)
            else:
                cursor.execute(f"""
                    SELECT {item_type}_tags.tag_id, {item_type}s.id, {item_type}s.name
                    FROM {item_type}s
                    INNER JOIN {item_type}_tags ON {item_type}s.id = {item_type}_tags.{item_type}_id
                    WHERE {item_type}_tags.tag_id IN (?{(len(tags) - 1) * ', ?'})
                    ORDER BY {item_type}s.name ASC
                """, [tag.id for tag in tags])
            rows = cursor.fetchall()
        finally:
            conn.close()

        itemtags = []
        if rows:
            for tag_id, item_id, item_name in rows:
                item = Item(item_type, item_id, item_name)
                tag = discord.utils.get(tags, id=tag_id)
                itemtags.append(Itemtag(item, tag))
        return itemtags

class IgdbWrapper:

    def __init__(self, igdb_key):
        self.__api_key = igdb_key
        self.__api_url = "https://api-v3.igdb.com/"

    async def find_item_by_id(self, item_type, item_id):
        url = self.__api_url + f"{item_type}s/"
        data = f"fields id,name; where id = {item_id};"
        headers = {
            "user-key": self.__api_key,
            'Accept': 'application/json',
        }
        result = requests.get(url, data=data, headers=headers)
        try:
            result.raise_for_status()
        except:
            print("data: " + data)
            print("result: "+ result.text)
            raise

        result.body = json.loads(result.text)
        elem = result.body[0] if result.body else None
        item = None
        if elem:
            item = Item(item_type, elem['id'], elem['name'])
        return item

    async def find_items_by_name(self, item_type, item_name):
        url = self.__api_url + f"{item_type}s/"
        data = f"fields id,name,slug; sort first_release_date desc; limit 20; where name ~ *\"{item_name}\"*;"
        headers = {
            "user-key": self.__api_key,
            'Accept': 'application/json',
        }
        result = requests.get(url, data=data, headers=headers)
        try:
            result.raise_for_status()
        except:
            print("data: " + data)
            print("result: "+ result.text)
            raise

        result.body = json.loads(result.text)
        items = []
        for elem in result.body:
            items.append(Item(item_type, elem['id'], elem['name'], elem['slug']))
        return items
