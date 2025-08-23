from dataclasses import dataclass
import discord
from discord import Role, Member, TextChannel, Message, app_commands, Interaction
from discord.ext import commands
from typing import List

import config as config
import logging

log = logging.getLogger(__name__)

kok_moderation_channel_name = "kok-moderation" if not hasattr(config, "KOK_MOD_CHANNEL") else config.KOK_MOD_CHANNEL
kok_log_channel_name = "kok-log" if not hasattr(config, "KOK_LOG_CHANNEL") else config.KOK_LOG_CHANNEL
kok_games = ["SF", "TEKKEN", "BazBlue", "FatalFury", "GG", "GB"] if not hasattr(config, "KOK_GAMES") else config.KOK_GAMES

def get_role_for_game(ctx: Interaction, game: str) -> Role:
    role_name = f"King of {game}"
    return discord.utils.get(ctx.guild.roles, name=role_name)
 
@dataclass
class KoKResult:
    game: str
    winner: Member
    loser: Member
    winner_rounds: int
    loser_rounds: int
    
    def __init__(self, game: str, reporter: Member, opponent: Member, rounds_won: int, rounds_lost: int):
        self.game = game
        self.winner = reporter if rounds_won > rounds_lost else opponent
        self.loser = reporter if rounds_lost > rounds_won else opponent
        self.winner_rounds = max([rounds_won, rounds_lost])
        self.loser_rounds = min([rounds_won, rounds_lost])
    def free(self) -> bool:
        return self.loser_rounds == 0

class KokApproveButton(discord.ui.View):
    def __init__(self,result_msg: str, result: KoKResult):
        super().__init__()
        self.result = result
        self.result_msg = result_msg

    @discord.ui.button(label="💯Real🗣️📢📠", style=discord.ButtonStyle.primary, custom_id="approve_button")
    async def button_callback(self, interaction: Interaction, button: discord.ui.Button):
        # Respond we must
        await interaction.response.send_message(f"Approved!", ephemeral=True, delete_after=3)
        # Edit message, Delete button
        await interaction.message.edit(content=f"{self.result_msg} ✅ - approved by {interaction.user}", view=None)
        # Post to log channel
        kok_log_channel = discord.utils.get(interaction.guild.channels, name=kok_log_channel_name)
        log_msg: Message = await kok_log_channel.send(self.result_msg)
        # Hehe :^)
        if self.result.free():
            await log_msg.add_reaction("🆓")
        # Steal Role
        role = get_role_for_game(interaction, self.result.game)
        await self.result.loser.remove_roles(role, reason=f"Lost to {self.result.winner}")
        await self.result.winner.add_roles(role, reason=f"Won against {self.result.loser}")

class KokCog(commands.Cog):
    
    def __init__(self, bot):
        self.bot = bot
        
    async def games_autocomplete(self, i: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        return [
            app_commands.Choice(name=choice, value=choice)
            for choice in kok_games if current.lower() in choice.lower()
	    ]
    
    @app_commands.command(name="kok-report")
    @app_commands.describe(
        game="Name of the game",
        opponent="Your opponent",
        rounds_won="Matches you won 👑",
        rounds_lost="Matches you lost 👎"
    )
    @app_commands.autocomplete(game=games_autocomplete)
    async def report_kok_result(self, interaction: Interaction, 
                             game: str, opponent: Member, 
                             rounds_won: int, rounds_lost: int):
        result: KoKResult = KoKResult(game=game, reporter=interaction.user, opponent=opponent, rounds_won=rounds_won, rounds_lost=rounds_lost)
        # Confirm report
        await interaction.response.send_message(content="KoK submited, awaiting approval", ephemeral=True, delete_after=3)
        # Notify moderators for approval
        kok_mod_channel: TextChannel = discord.utils.get(interaction.guild.channels, name=kok_moderation_channel_name)
        role = get_role_for_game(interaction, game)
        result_msg = f"[{role.mention}]: {result.winner.mention} {result.winner_rounds} - {result.loser_rounds} {result.loser.mention}"
        await kok_mod_channel.send(result_msg, view=KokApproveButton(result_msg, result))
    
    @app_commands.command(name="kok-challenge")
    @app_commands.describe(game="Name of the game")
    @app_commands.autocomplete(game=games_autocomplete)
    async def challenge_kok(self, interaction: Interaction, game: str):
        role = get_role_for_game(interaction, game)
        if role:
            members_with_role = [member for member in interaction.guild.members if role in member.roles]
            if len(members_with_role) > 0:
                await interaction.response.send_message(content=f"[{role.mention}]: New Challenger! {members_with_role[0].mention}. You have 48 hours to play the set, or else...!")
            else:
                await interaction.response.send_message(content="No one has the role yet, congrats!", ephemeral=True, delete_after=5)
                await interaction.user.add_roles(role, reason=f"No Contest")
                kok_log_channel = discord.utils.get(interaction.guild.channels, name=kok_log_channel_name)
                await kok_log_channel.send(f"[{role.mention}] - {interaction.user.mention} claimed the title.")
        else:
            log.warning(f"Role not found for game {game}")
        
async def setup(bot):
    await bot.add_cog(KokCog(bot))