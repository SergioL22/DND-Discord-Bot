import random
from typing import List, Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils.character_sheet import ABILITY_NAMES, SKILL_TO_ABILITY
from utils.database import get_database


SKILL_CHOICES = [app_commands.Choice(name=s, value=s) for s in sorted(SKILL_TO_ABILITY.keys())]
ABILITY_CHOICES = [app_commands.Choice(name=a, value=a) for a in ABILITY_NAMES]


class Checks(commands.Cog):
    """Skill checks and saving throws."""

    check_group = app_commands.Group(name="check", description="Roll skill checks and saving throws")

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = get_database()

    async def _char_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> List[app_commands.Choice[str]]:
        names = self.db.get_all_character_names(str(interaction.user.id))
        return [app_commands.Choice(name=n, value=n) for n in names if current.lower() in n.lower()][:25]

    # ── Commands ──────────────────────────────────────────────────────────────

    @check_group.command(name="skill", description="Roll a skill check for your character")
    @app_commands.describe(
        character_name="Your character",
        skill="Skill to roll",
        dc="Optional DC — shows pass/fail if provided",
    )
    @app_commands.autocomplete(character_name=_char_autocomplete)
    @app_commands.choices(skill=SKILL_CHOICES)
    async def check_skill(
        self,
        interaction: discord.Interaction,
        character_name: str,
        skill: app_commands.Choice[str],
        dc: Optional[int] = None,
    ):
        character = self.db.get_character(str(interaction.user.id), character_name)
        if not character:
            await interaction.response.send_message(f"❌ Character **{character_name}** not found.", ephemeral=True)
            return

        bonus = character.skill_bonus(skill.value)
        roll = random.randint(1, 20)
        total = roll + bonus
        bonus_str = f"+{bonus}" if bonus >= 0 else str(bonus)
        proficient = skill.value.lower() in character.skill_proficiencies
        ability = SKILL_TO_ABILITY[skill.value]

        embed = discord.Embed(
            title=f"🎲 {character.name} — {skill.value} Check",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Roll", value=f"d20: **{roll}** {bonus_str} = **{total}**", inline=False)
        footer = f"{ability} | {'Proficient' if proficient else 'Not proficient'}"
        if character.inspiration:
            footer += " | ⭐ Has inspiration — use `/inspiration use` to roll with advantage"

        if dc is not None:
            passed = total >= dc
            embed.add_field(name=f"DC {dc}", value="✅ Pass" if passed else "❌ Fail", inline=False)
            embed.color = discord.Color.green() if passed else discord.Color.red()

        embed.set_footer(text=footer)
        await interaction.response.send_message(embed=embed)

    @check_group.command(name="save", description="Roll a saving throw for your character")
    @app_commands.describe(
        character_name="Your character",
        ability="Ability for the saving throw",
        dc="Optional DC — shows pass/fail if provided",
    )
    @app_commands.autocomplete(character_name=_char_autocomplete)
    @app_commands.choices(ability=ABILITY_CHOICES)
    async def check_save(
        self,
        interaction: discord.Interaction,
        character_name: str,
        ability: app_commands.Choice[str],
        dc: Optional[int] = None,
    ):
        character = self.db.get_character(str(interaction.user.id), character_name)
        if not character:
            await interaction.response.send_message(f"❌ Character **{character_name}** not found.", ephemeral=True)
            return

        bonus = character.saving_throw_bonus(ability.value)
        roll = random.randint(1, 20)
        total = roll + bonus
        bonus_str = f"+{bonus}" if bonus >= 0 else str(bonus)
        proficient = ability.value.lower() in character.saving_throw_proficiencies

        embed = discord.Embed(
            title=f"🛡️ {character.name} — {ability.value} Saving Throw",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Roll", value=f"d20: **{roll}** {bonus_str} = **{total}**", inline=False)

        if dc is not None:
            passed = total >= dc
            embed.add_field(name=f"DC {dc}", value="✅ Pass" if passed else "❌ Fail", inline=False)
            embed.color = discord.Color.green() if passed else discord.Color.red()

        embed.set_footer(text=f"{'Proficient' if proficient else 'Not proficient'} in {ability.value} saves")
        await interaction.response.send_message(embed=embed)

    @check_group.command(name="ability", description="Roll a raw ability check")
    @app_commands.describe(
        character_name="Your character",
        ability="Ability to check",
        dc="Optional DC — shows pass/fail if provided",
    )
    @app_commands.autocomplete(character_name=_char_autocomplete)
    @app_commands.choices(ability=ABILITY_CHOICES)
    async def check_ability(
        self,
        interaction: discord.Interaction,
        character_name: str,
        ability: app_commands.Choice[str],
        dc: Optional[int] = None,
    ):
        character = self.db.get_character(str(interaction.user.id), character_name)
        if not character:
            await interaction.response.send_message(f"❌ Character **{character_name}** not found.", ephemeral=True)
            return

        mod = character.get_modifier(ability.value)
        roll = random.randint(1, 20)
        total = roll + mod
        mod_str = f"+{mod}" if mod >= 0 else str(mod)

        embed = discord.Embed(
            title=f"💪 {character.name} — {ability.value} Check",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Roll", value=f"d20: **{roll}** {mod_str} = **{total}**", inline=False)

        if dc is not None:
            passed = total >= dc
            embed.add_field(name=f"DC {dc}", value="✅ Pass" if passed else "❌ Fail", inline=False)
            embed.color = discord.Color.green() if passed else discord.Color.red()

        score = character.abilities[ability.value.lower()]
        embed.set_footer(text=f"{ability.value} {score} (modifier {mod_str})")
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Checks(bot))
