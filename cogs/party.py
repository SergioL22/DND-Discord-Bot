import logging

import discord
from discord import app_commands
from discord.ext import commands

from utils import db
from utils.character_sheet import CharacterSheet
from utils.database import get_database

logger = logging.getLogger(__name__)


class Party(commands.Cog):
    """Party roster and group management commands."""

    party_group = app_commands.Group(name="party", description="Manage the adventuring party")

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.char_db = get_database()

    @party_group.command(name="add", description="Add one of your characters to the party")
    @app_commands.describe(character_name="Your character to add to the party")
    async def party_add(self, interaction: discord.Interaction, character_name: str):
        if not interaction.guild_id:
            await interaction.response.send_message("❌ This command must be used in a server.", ephemeral=True)
            return

        owner_id = str(interaction.user.id)
        character = self.char_db.get_character(owner_id, character_name)
        if not character:
            await interaction.response.send_message(
                f"❌ Character **{character_name}** not found. Create one with `/createchar`.",
                ephemeral=True,
            )
            return

        added = db.party_add(interaction.guild_id, owner_id, character.name)
        if not added:
            await interaction.response.send_message(
                f"❌ **{character.name}** is already in the party.", ephemeral=True
            )
            return

        await interaction.response.send_message(
            f"✅ **{character.name}** ({character.race} {character.character_class} Lv{character.level}) joined the party!"
        )

    @party_group.command(name="remove", description="Remove one of your characters from the party")
    @app_commands.describe(character_name="Your character to remove from the party")
    async def party_remove(self, interaction: discord.Interaction, character_name: str):
        if not interaction.guild_id:
            await interaction.response.send_message("❌ This command must be used in a server.", ephemeral=True)
            return

        removed = db.party_remove(interaction.guild_id, str(interaction.user.id), character_name)
        if not removed:
            await interaction.response.send_message(
                f"❌ **{character_name}** is not in the party.", ephemeral=True
            )
            return

        await interaction.response.send_message(f"🗑️ **{character_name}** removed from the party.")

    @party_group.command(name="list", description="Show all party members and their current HP")
    async def party_list(self, interaction: discord.Interaction):
        if not interaction.guild_id:
            await interaction.response.send_message("❌ This command must be used in a server.", ephemeral=True)
            return

        members = db.party_list(interaction.guild_id)
        if not members:
            await interaction.response.send_message(
                "ℹ️ The party is empty. Use `/party add` to add characters.", ephemeral=True
            )
            return

        embed = discord.Embed(title="⚔️ Party Roster", color=discord.Color.gold())
        total_members = 0

        for m in members:
            char = self.char_db.get_character(m["owner_id"], m["name_key"])
            if char is None:
                continue
            hp_bar = _hp_bar(char.current_hp, char.max_hp)
            value = (
                f"Lv {char.level} {char.race} {char.character_class}\n"
                f"HP: {char.current_hp}/{char.max_hp} {hp_bar}\n"
                f"AC: {char.armor_class} | <@{m['owner_id']}>"
            )
            embed.add_field(name=char.name, value=value, inline=True)
            total_members += 1

        embed.set_footer(text=f"{total_members} member(s)")
        await interaction.response.send_message(embed=embed)

    @party_group.command(name="hp", description="Apply healing or damage to every party member")
    @app_commands.describe(amount="Positive to heal, negative to damage (e.g. 10 or -7)")
    async def party_hp(self, interaction: discord.Interaction, amount: int):
        if not interaction.guild_id:
            await interaction.response.send_message("❌ This command must be used in a server.", ephemeral=True)
            return

        members = db.party_list(interaction.guild_id)
        if not members:
            await interaction.response.send_message("ℹ️ The party is empty.", ephemeral=True)
            return

        action = "healed" if amount > 0 else "took damage"
        lines = []
        for m in members:
            char = self.char_db.get_character(m["owner_id"], m["name_key"])
            if char is None:
                continue
            old_hp = char.current_hp
            char.adjust_hp(amount)
            self.char_db.save_character(char)
            lines.append(f"**{char.name}**: {old_hp} → {char.current_hp}/{char.max_hp}")

        if not lines:
            await interaction.response.send_message("❌ No valid party members found.", ephemeral=True)
            return

        verb = "healed" if amount > 0 else "damaged"
        embed = discord.Embed(
            title=f"{'💚' if amount > 0 else '💥'} Party {verb.title()} ({'+' if amount > 0 else ''}{amount} HP)",
            description="\n".join(lines),
            color=discord.Color.green() if amount > 0 else discord.Color.red(),
        )
        await interaction.response.send_message(embed=embed)

    @party_group.command(name="xp", description="Award XP to every party member")
    @app_commands.describe(amount="XP to award to each party member")
    async def party_xp(self, interaction: discord.Interaction, amount: int):
        if not interaction.guild_id:
            await interaction.response.send_message("❌ This command must be used in a server.", ephemeral=True)
            return

        if amount <= 0:
            await interaction.response.send_message("❌ XP amount must be greater than 0.", ephemeral=True)
            return

        members = db.party_list(interaction.guild_id)
        if not members:
            await interaction.response.send_message("ℹ️ The party is empty.", ephemeral=True)
            return

        lines = []
        for m in members:
            char = self.char_db.get_character(m["owner_id"], m["name_key"])
            if char is None:
                continue
            old_xp = char.exp
            char.add_xp(amount)
            self.char_db.save_character(char)
            lines.append(f"**{char.name}**: {old_xp} → {char.exp} XP")

        if not lines:
            await interaction.response.send_message("❌ No valid party members found.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"✨ Party awarded {amount} XP each",
            description="\n".join(lines),
            color=discord.Color.blurple(),
        )
        await interaction.response.send_message(embed=embed)

    @party_group.command(name="clear", description="Remove all members from the party roster")
    @app_commands.describe(confirm="Set to true to confirm clearing the roster")
    async def party_clear(self, interaction: discord.Interaction, confirm: bool):
        if not interaction.guild_id:
            await interaction.response.send_message("❌ This command must be used in a server.", ephemeral=True)
            return

        if not confirm:
            await interaction.response.send_message(
                "⚠️ Re-run with `confirm: true` to clear the entire party roster.", ephemeral=True
            )
            return

        removed = db.party_clear(interaction.guild_id)
        await interaction.response.send_message(f"🗑️ Cleared {removed} member(s) from the party roster.")


def _hp_bar(current: int, maximum: int, length: int = 8) -> str:
    if maximum <= 0:
        return ""
    filled = round(length * current / maximum)
    return "█" * filled + "░" * (length - filled)


async def setup(bot: commands.Bot):
    await bot.add_cog(Party(bot))
