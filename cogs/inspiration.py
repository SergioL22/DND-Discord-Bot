from typing import List

import discord
from discord import app_commands
from discord.ext import commands

from utils.database import get_database


class Inspiration(commands.Cog):
    """Award, spend, and check D&D inspiration."""

    inspiration_group = app_commands.Group(name="inspiration", description="Give, use, and check inspiration")

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = get_database()

    async def _char_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> List[app_commands.Choice[str]]:
        names = self.db.get_all_character_names(str(interaction.user.id))
        return [app_commands.Choice(name=n, value=n) for n in names if current.lower() in n.lower()][:25]

    # ── Commands ──────────────────────────────────────────────────────────────

    @inspiration_group.command(name="give", description="Award inspiration to one of your characters (DM use)")
    @app_commands.describe(character_name="Character to receive inspiration")
    @app_commands.autocomplete(character_name=_char_autocomplete)
    async def inspiration_give(self, interaction: discord.Interaction, character_name: str):
        character = self.db.get_character(str(interaction.user.id), character_name)
        if not character:
            await interaction.response.send_message(f"❌ Character **{character_name}** not found.", ephemeral=True)
            return

        if character.inspiration:
            await interaction.response.send_message(
                f"⚠️ **{character.name}** already has inspiration.", ephemeral=True
            )
            return

        character.inspiration = True
        self.db.save_character(character)
        await interaction.response.send_message(
            f"⭐ **{character.name}** now has **inspiration**!\n"
            f"Use `/inspiration use` to spend it for advantage on any roll."
        )

    @inspiration_group.command(name="use", description="Spend your inspiration to declare advantage on your next roll")
    @app_commands.describe(character_name="Your character")
    @app_commands.autocomplete(character_name=_char_autocomplete)
    async def inspiration_use(self, interaction: discord.Interaction, character_name: str):
        character = self.db.get_character(str(interaction.user.id), character_name)
        if not character:
            await interaction.response.send_message(f"❌ Character **{character_name}** not found.", ephemeral=True)
            return

        if not character.inspiration:
            await interaction.response.send_message(
                f"❌ **{character.name}** doesn't have inspiration. Ask your DM to award it with `/inspiration give`.",
                ephemeral=True,
            )
            return

        character.inspiration = False
        self.db.save_character(character)
        await interaction.response.send_message(
            f"🌟 **{character.name}** spent their inspiration! Roll your next check with **advantage**."
        )

    @inspiration_group.command(name="status", description="Check whether a character currently has inspiration")
    @app_commands.describe(character_name="Your character")
    @app_commands.autocomplete(character_name=_char_autocomplete)
    async def inspiration_status(self, interaction: discord.Interaction, character_name: str):
        character = self.db.get_character(str(interaction.user.id), character_name)
        if not character:
            await interaction.response.send_message(f"❌ Character **{character_name}** not found.", ephemeral=True)
            return

        if character.inspiration:
            await interaction.response.send_message(f"⭐ **{character.name}** has **inspiration**.")
        else:
            await interaction.response.send_message(f"✨ **{character.name}** does not have inspiration.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Inspiration(bot))
