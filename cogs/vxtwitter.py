import discord
from discord.ext import commands
import logging
import re

log = logging.getLogger(__name__)

UNDO_EMOJI_NAME = '\u21a9\ufe0f'  # :leftwards_arrow_with_hook:

class Vxtwitter(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or message.type not in (discord.MessageType.default, discord.MessageType.reply):
            return
        links = self.generate_vxtwitter_links(message.content)
        if not links:
            return
        reply = await message.reply(links, mention_author=False)
        await reply.add_reaction(UNDO_EMOJI_NAME)
        await message.edit(suppress=True)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.emoji.name != UNDO_EMOJI_NAME or payload.user_id == self.bot.user.id:
            return
        channel = self.bot.get_channel(payload.channel_id)
        msg = await channel.fetch_message(payload.message_id)
        if msg.author != self.bot.user:
            # if it ain't mine then why are we still here?
            return
        ref = msg.reference.resolved  # this will raise AttributeError if no ref but that's fine
        if not ref:
            # temporarily couldn't fetch ref, user should retry later
            return
        if not isinstance(ref, discord.DeletedReferencedMessage):
            if ref.author.id != payload.user_id and not payload.member.guild_permissions.manage_messages:
                return
            try:
                await ref.edit(suppress=False)
            except discord.HTTPException as e:
                log.exception(e)
                return
        # if the original messages was deleted anyone can revert
        await msg.delete()

    def generate_vxtwitter_links(self, text):
        # NOTE this pattern is a bit more forgiving than Discord's
        pattern = re.compile(r'https://(mobile.|vx)?(twitter|x).com/([\w]{4,15}/status/[0-9]+)')
        matches = pattern.finditer(text)
        prefixes = set()
        links = dict()  # wanted to use ordered set but apparently this is the closest thing
        for m in matches:
            prefixes.add(m.group(1))
            links[f"https://vxtwitter.com/{m.group(3)}"] = None
        if not links or prefixes == {"vx"}:
            # if there are no matches (or it's all vxtwitter links) then our work here is done
            return
        return ' '.join(links.keys())

async def setup(bot):
    await bot.add_cog(Vxtwitter(bot))