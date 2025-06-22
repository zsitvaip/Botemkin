﻿from collections import namedtuple
from enum import Enum
import logging
import pathlib
import sqlite3
from contextlib import closing

import discord
from discord.ext import commands

# for IGDB wrapper
import requests

from . import cog_config
from utils import superuser_only

log = logging.getLogger(__name__)

class ItemType(Enum):
    game = 1
    # platform = 2

    def __str__(self):
        return self.name

    # TODO really this should be a lookup in a list/dict
    def pre(self):
        if self.value == 1:
            return ''
        if self.value == 2:
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
        self.igdb_wrapper = IgdbWrapper(cog_config.IGDB_CLIENT_ID, cog_config.IGDB_CLIENT_SECRET)

    # TODO make async?
    def _get_available_tags(self, guild : discord.Guild):
        everyone_role = discord.utils.find(
            lambda role: role.id == guild.id, guild.roles)

        # TODO this doesn't seem to actually filter out roles by permission
        available_tags = list(filter(
            lambda role: role.id != everyone_role.id and role.permissions <= everyone_role.permissions, guild.roles))  # type: ignore

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
                paginator = commands.Paginator(prefix='```css', suffix='```', linesep='\n')
                paginator.add_line(f"Search results from the *Internet Game Database* (<https://www.igdb.com>):{paginator.prefix}")
                for row in table_rows:
                    paginator.add_line(row)

                pages = [paginator.pages[0][len(paginator.prefix):]] + paginator.pages[1:]  # type: ignore
                for page in pages:
                    await ctx.send(page)
            else:
                await ctx.send("No search results from the *Internet Game Database* (<https://www.igdb.com>).")
        except:
            await ctx.send("An error occured while accessing the *Internet Game Database* (<https://www.igdb.com>).")
            raise

    @commands.command(name='search_game', aliases=['search', 'sg', 's'], usage='<game_name>')
    @superuser_only()
    async def search_IGDB_game(self, ctx, *, game_name):
        """Search IGDB for given game name. (superuser-only)

        Use to get the game id to be used with the !tag_game command.

        Usage examples:

        !search puyo tetris
        !s dong never die
        """
        await self._search_IGDB_item(ctx, ItemType.game, game_name)

    async def _get_pages_for_available_itemtags(self, item_type, tags):
        itemtags = await self.repository.find_itemtags_by_tags(item_type, tags)
        pages = None
        if itemtags:
            paginator = commands.Paginator(prefix='```css', suffix='```', linesep='\n')
            paginator.add_line(f"Available {item_type}tags:{paginator.prefix}")
            for itemtag in itemtags:
                paginator.add_line(f"{itemtag.tag.name} [{itemtag.item.name}]#{itemtag.item.id}")
            pages = [paginator.pages[0][len(paginator.prefix):]] + paginator.pages[1:]  # type: ignore
        return pages

    async def _get_pages_for_all_itemtags(self, item_type, tags):
        itemtags = await self.repository.find_itemtags_by_tags(item_type, tags, all=True)
        pages = None
        if itemtags:
            paginator = commands.Paginator(prefix='```css', suffix='```', linesep='\n')
            paginator.add_line(f"Imported {item_type}s:{paginator.prefix}")
            for itemtag in itemtags:
                itemtag_name = "\t"
                if itemtag.tag:
                    itemtag_name = f"{itemtag.tag.name} "
                paginator.add_line(f"{itemtag_name}[{itemtag.item.name}]#{itemtag.item.id}")
            pages = [paginator.pages[0][len(paginator.prefix):]] + paginator.pages[1:]  # type: ignore
        return pages

    async def _list_available_tags(self, ctx):
        available_tags = self._get_available_tags(ctx.guild)
        if available_tags:
            for item_type in ItemType:
                pages = await self._get_pages_for_available_itemtags(item_type, available_tags)
                if pages:
                    for page in pages:
                        await ctx.send(page)
                else:
                    await ctx.send(f"```There are currently no available {item_type}tags.```")
        else:
            await ctx.send(f"```There are currently no available tags.```")

    async def _list_all_tags(self, ctx):
        available_tags = self._get_available_tags(ctx.guild)
        for item_type in ItemType:
            pages = await self._get_pages_for_all_itemtags(item_type, available_tags)
            if pages:
                for page in pages:
                    await ctx.send(page)
            else:
                await ctx.send(f"```There are currently no imported {item_type}s.```")

    @commands.command(name='list', aliases=['ls', 'l'], usage='[all]')
    async def list_available_tags(self, ctx, arg=None):
        """Lists available tags.

        Use with 'all' to show all games imported from IGDB including ones without tags associated with them.

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

    async def _remove_any_tags_by_name(self, ctx, tag_names):
        selected_tags, unknown_tag_names = self._get_selected_tags(ctx.guild, tag_names)
        msg_str = ""
        if selected_tags:

            gametags = await self.repository.find_itemtags_by_tags(ItemType.game, selected_tags)
            tags = []
            if gametags:

                item_names = []
                for itemtag in gametags:
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
        """Shows players with given tags. When given multiple tags only show players who match all of them.

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
            await self._show_players_for_single_role(ctx, role_names[0])  # type: ignore

    async def _show_players_for_single_role(self, ctx, role_name):
        role = discord.utils.find(
            lambda role: role.name.casefold() == role_name.casefold(), ctx.guild.roles)

        if not role:
            await ctx.send(f"```Unknown tag: {role_name}```Use **!list** to print available tags.")
            return

        paginator = commands.Paginator(prefix='', suffix='', linesep='\n')
        item = await self.repository.find_any_item_by_tag(role)
        if item:
            num = len(role.members)
            if num > 0:
                paginator.add_line(f"*{item.name}* has {num} player{'s' if num != 1 else ''}:")
                for player in role.members:
                    paginator.add_line(f"{player.mention} ({discord.utils.escape_markdown(player.name)})")
            else:
                msg_str = f"*{role.name}* is a **DEAD** {item.type}"
                e = discord.utils.get(ctx.guild.emojis, name='rip')
                if e:
                    msg_str = f"<:{e.name}:{e.id}> {msg_str} <:{e.name}:{e.id}>"
                paginator.add_line(msg_str)
        else:
            paginator.add_line(f"```Not a tag: {role.name}```Use **!list** to print available tags.")

        for page in paginator.pages:
            await ctx.send(page, allowed_mentions = discord.AllowedMentions.none())

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
            msg_str += f"{player.mention} ({discord.utils.escape_markdown(player.name)})\n"

        num = len(players)
        msg_str =  f"The following tags are matched by {num} player{'s' if num != 1 else ''}: *{'*, *'.join(valid_role_names)}*.\n{msg_str}"
        if unknown_tag_names:
            msg_str += f"```Unknown tags: {', '.join(unknown_tag_names)}```Use **!list** to print available tags."

        await ctx.send(msg_str, allowed_mentions = discord.AllowedMentions.none())

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
    @superuser_only()
    async def tag_game(self, ctx, game_id: int, tag_name: str):
        """Associate game with given tag. (superuser-only)

        To find the game id use the !search_game command.

        Usage examples:

        !tag 80207 ABK
        !t 76885 SCVI
        """
        await self._tag_item(ctx, ItemType.game, game_id, tag_name)

    # superuser-only commands print !help as well as print other errors
    @search_IGDB_game.error
    @tag_game.error
    async def _verbose_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send_help(ctx.command)
        else:
            await ctx.send(f"```{error}```")
        raise error

async def setup(bot):
    await bot.add_cog(Gametags(bot))

class ItemtagRepository:

    def __init__(self):
        self.data_dir = 'data/'
        self.db_path = f'{self.data_dir}gametag.db'

    def setup(self):
        pathlib.Path(self.data_dir).mkdir(parents=True, exist_ok=True)

        # TODO use closing context manager instead of try/except once sqlite3 autocommit parameter becomes available for connect (python>=3.12)
            # - all DB connections should turn off autocommit and manually commit changes for clarity
            # - conn.commit() will need to be called for all DB changes
            # - conn.rollback() and conn.close() will be handled by the closing context manager (i.e. less boilerplate)
            # - cursor.execute('BEGIN') will be handled by first cursor.execute() that implicitly triggers a transaction as needed (e.g. INSERT)
                # so remove explicit call
            # Example: with closing(sqlite3.connect(self.db_path, autocommit=False)) as conn:
        conn = sqlite3.connect(self.db_path)
        try:
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
            # cursor.execute("""
            #     CREATE TABLE IF NOT EXISTS platforms (
            #         id INTEGER PRIMARY KEY,
            #         name TEXT NOT NULL
            #     )"""
            # )
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS game_tags (
                    tag_id INTEGER,
                    game_id INTEGER NOT NULL UNIQUE,
                    PRIMARY KEY (tag_id),
                    FOREIGN KEY (tag_id) REFERENCES tags(id),
                    FOREIGN KEY (game_id) REFERENCES games(id)
                )"""
            )
            # cursor.execute("""
            #     CREATE TABLE IF NOT EXISTS platform_tags (
            #         tag_id INTEGER,
            #         platform_id INTEGER NOT NULL UNIQUE,
            #         PRIMARY KEY (tag_id),
            #         FOREIGN KEY (tag_id) REFERENCES tags(id),
            #         FOREIGN KEY (platform_id) REFERENCES platforms(id)
            #     )"""
            # )
            conn.commit()
        except:
            conn.rollback()
            raise
        finally:
            conn.close()

    async def add_item(self, item):
        conn = sqlite3.connect(self.db_path)
        try:
            # TODO see note on autocommit
            with closing(sqlite3.connect(self.db_path)) as conn:
                cursor = conn.cursor()
                cursor.execute(f"INSERT INTO {item.type}s (id, name) VALUES (?, ?)", [item.id, item.name])
                conn.commit()  # not sure why this is needed with the expected autocommit behaviour but it is
            return True
        except sqlite3.IntegrityError:
            return False

    async def add_itemtag(self, itemtag):
        item = itemtag.item
        tag = itemtag.tag

        # TODO see note on autocommit
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute('BEGIN')

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
        with closing(sqlite3.connect(self.db_path)) as conn:
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
        with closing(sqlite3.connect(self.db_path)) as conn:
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

        itemtags = []
        if rows:
            for tag_id, item_id, item_name in rows:
                item = Item(item_type, item_id, item_name)
                tag = discord.utils.get(tags, id=tag_id)
                itemtags.append(Itemtag(item, tag))
        return itemtags

class IgdbWrapper:

    def __init__(self, igdb_client_id, igdb_client_secret):
        self.__igdb_url = "https://api.igdb.com/v4/"
        self.__twitch_url = "https://id.twitch.tv/oauth2/token"
        self.__IGDB_CLIENT_ID = igdb_client_id
        self.__IGDB_CLIENT_SECRET = igdb_client_secret
        self.__access_token = None

    async def __renew_access_token(self):
        log.info('Renewing IGDB access token')
        payload = {'client_id': self.__IGDB_CLIENT_ID, 'client_secret': self.__IGDB_CLIENT_SECRET, 'grant_type': 'client_credentials'}
        result = requests.post(self.__twitch_url, params=payload)
        result.raise_for_status()
        self.__access_token = result.json()['access_token']

    async def __post_request(self, url, data):
        for i in range(2):
            headers = {
                'Client-ID': self.__IGDB_CLIENT_ID,
                'Authorization': f"Bearer {self.__access_token}",
                'Accept': 'application/json',
            }
            try:
                result = requests.post(url, data=data, headers=headers)
                result.raise_for_status()
            except requests.exceptions.HTTPError as err:
                if err.response.status_code == 401:
                    log.info(err)
                    await self.__renew_access_token()
                    continue
                log.error(err)
        return result

    async def find_item_by_id(self, item_type, item_id):
        url = self.__igdb_url + f"{item_type}s/"
        # TODO validate/sanitize
        data = f"fields id,name; where id = {item_id};"

        result = await self.__post_request(url, data)
        result.body = result.json()  # type: ignore
        elem = result.body[0] if result.body else None  # type: ignore
        item = None
        if elem:
            item = Item(item_type, elem['id'], elem['name'])
        return item

    async def find_items_by_name(self, item_type, item_name):
        url = self.__igdb_url + f"{item_type}s/"
        # TODO validate/sanitize
        data = f"fields id,name,slug; sort first_release_date desc; limit 20; where name ~ *\"{item_name}\"*;"

        result = await self.__post_request(url, data)
        items = []
        for elem in result.json():
            items.append(Item(item_type, elem['id'], elem['name'], elem['slug']))
        return items
