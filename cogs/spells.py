from typing import List, Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils.database import get_database
import utils.dnd5e_api as dnd5e


class Spells(commands.Cog):
    """Learn, prepare, and cast spells."""

    spell_group = app_commands.Group(name="spell", description="Manage and cast spells")

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = get_database()

    # ── Autocomplete helpers ──────────────────────────────────────────────────

    async def _char_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> List[app_commands.Choice[str]]:
        names = self.db.get_all_character_names(str(interaction.user.id))
        return [app_commands.Choice(name=n, value=n) for n in names if current.lower() in n.lower()][:25]

    async def _known_spell_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> List[app_commands.Choice[str]]:
        char_name = getattr(interaction.namespace, "character_name", None)
        if not char_name:
            return []
        character = self.db.get_character(str(interaction.user.id), char_name)
        if not character:
            return []
        filtered = [s for s in character.spells_known if current.lower() in s.lower()]
        return [app_commands.Choice(name=s, value=s) for s in filtered[:25]]

    async def _prepared_spell_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> List[app_commands.Choice[str]]:
        char_name = getattr(interaction.namespace, "character_name", None)
        if not char_name:
            return []
        character = self.db.get_character(str(interaction.user.id), char_name)
        if not character:
            return []
        filtered = [s for s in character.spells_prepared if current.lower() in s.lower()]
        return [app_commands.Choice(name=s, value=s) for s in filtered[:25]]

    async def _api_spell_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> List[app_commands.Choice[str]]:
        if len(current) < 2:
            return []
        try:
            results = await dnd5e.search("spells", current)
        except Exception:
            return []
        return [app_commands.Choice(name=name, value=name) for name, _ in results[:25]]

    # ── Commands ──────────────────────────────────────────────────────────────

    @spell_group.command(name="add", description="Add a spell to your character's spells known")
    @app_commands.describe(character_name="Your character", spell_name="Spell to learn")
    @app_commands.autocomplete(character_name=_char_autocomplete, spell_name=_api_spell_autocomplete)
    async def spell_add(self, interaction: discord.Interaction, character_name: str, spell_name: str):
        character = self.db.get_character(str(interaction.user.id), character_name)
        if not character:
            await interaction.response.send_message(f"❌ Character **{character_name}** not found.", ephemeral=True)
            return

        spell_name = spell_name.strip()
        if spell_name.lower() in [s.lower() for s in character.spells_known]:
            await interaction.response.send_message(
                f"⚠️ **{character.name}** already knows **{spell_name}**.", ephemeral=True
            )
            return

        character.spells_known.append(spell_name)
        self.db.save_character(character)
        await interaction.response.send_message(
            f"📖 **{character.name}** learned **{spell_name}**! ({len(character.spells_known)} spell(s) known)"
        )

    @spell_group.command(name="remove", description="Remove a spell from your character's spells known")
    @app_commands.describe(character_name="Your character", spell_name="Spell to forget")
    @app_commands.autocomplete(character_name=_char_autocomplete, spell_name=_known_spell_autocomplete)
    async def spell_remove(self, interaction: discord.Interaction, character_name: str, spell_name: str):
        character = self.db.get_character(str(interaction.user.id), character_name)
        if not character:
            await interaction.response.send_message(f"❌ Character **{character_name}** not found.", ephemeral=True)
            return

        target = spell_name.strip().lower()
        before = len(character.spells_known)
        character.spells_known = [s for s in character.spells_known if s.lower() != target]
        character.spells_prepared = [s for s in character.spells_prepared if s.lower() != target]

        if len(character.spells_known) == before:
            await interaction.response.send_message(
                f"❌ **{character.name}** doesn't know **{spell_name.strip()}**.", ephemeral=True
            )
            return

        self.db.save_character(character)
        await interaction.response.send_message(f"🗑️ **{character.name}** forgot **{spell_name.strip()}**.")

    @spell_group.command(name="prepare", description="Mark a known spell as prepared")
    @app_commands.describe(character_name="Your character", spell_name="Spell to prepare")
    @app_commands.autocomplete(character_name=_char_autocomplete, spell_name=_known_spell_autocomplete)
    async def spell_prepare(self, interaction: discord.Interaction, character_name: str, spell_name: str):
        character = self.db.get_character(str(interaction.user.id), character_name)
        if not character:
            await interaction.response.send_message(f"❌ Character **{character_name}** not found.", ephemeral=True)
            return

        spell_name = spell_name.strip()
        if spell_name.lower() not in [s.lower() for s in character.spells_known]:
            await interaction.response.send_message(
                f"❌ **{character.name}** doesn't know **{spell_name}**. Use `/spell add` first.", ephemeral=True
            )
            return

        if spell_name.lower() in [s.lower() for s in character.spells_prepared]:
            await interaction.response.send_message(f"⚠️ **{spell_name}** is already prepared.", ephemeral=True)
            return

        character.spells_prepared.append(spell_name)
        self.db.save_character(character)
        await interaction.response.send_message(
            f"✨ **{character.name}** prepared **{spell_name}**. ({len(character.spells_prepared)} prepared)"
        )

    @spell_group.command(name="unprepare", description="Remove a spell from your prepared list")
    @app_commands.describe(character_name="Your character", spell_name="Spell to unprepare")
    @app_commands.autocomplete(character_name=_char_autocomplete, spell_name=_prepared_spell_autocomplete)
    async def spell_unprepare(self, interaction: discord.Interaction, character_name: str, spell_name: str):
        character = self.db.get_character(str(interaction.user.id), character_name)
        if not character:
            await interaction.response.send_message(f"❌ Character **{character_name}** not found.", ephemeral=True)
            return

        target = spell_name.strip().lower()
        before = len(character.spells_prepared)
        character.spells_prepared = [s for s in character.spells_prepared if s.lower() != target]

        if len(character.spells_prepared) == before:
            await interaction.response.send_message(
                f"❌ **{spell_name.strip()}** is not in **{character.name}**'s prepared list.", ephemeral=True
            )
            return

        self.db.save_character(character)
        await interaction.response.send_message(f"📚 **{character.name}** unprepared **{spell_name.strip()}**.")

    @spell_group.command(name="list", description="View your character's spells known and prepared")
    @app_commands.describe(character_name="Your character")
    @app_commands.autocomplete(character_name=_char_autocomplete)
    async def spell_list(self, interaction: discord.Interaction, character_name: str):
        character = self.db.get_character(str(interaction.user.id), character_name)
        if not character:
            await interaction.response.send_message(f"❌ Character **{character_name}** not found.", ephemeral=True)
            return

        if not character.spells_known:
            await interaction.response.send_message(
                f"📖 **{character.name}** has no spells. Use `/spell add` to learn one.", ephemeral=True
            )
            return

        prepared_lower = {s.lower() for s in character.spells_prepared}
        lines = [
            f"{'✨' if s.lower() in prepared_lower else '📖'} {s}"
            for s in character.spells_known
        ]

        embed = discord.Embed(
            title=f"📖 {character.name}'s Spells",
            description="\n".join(lines)[:4000],
            color=discord.Color.purple(),
        )
        embed.set_footer(
            text=f"✨ = Prepared  📖 = Known only  |  {len(character.spells_prepared)} prepared / {len(character.spells_known)} known"
        )
        await interaction.response.send_message(embed=embed)

    @spell_group.command(name="cast", description="Cast a spell — looks up details and expends a slot if needed")
    @app_commands.describe(
        character_name="Your character",
        spell_name="Spell to cast (autocompletes from your spells known)",
        slot_level="Slot level to cast at — use to upcast. Defaults to the spell's base level.",
    )
    @app_commands.autocomplete(character_name=_char_autocomplete, spell_name=_known_spell_autocomplete)
    async def spell_cast(
        self,
        interaction: discord.Interaction,
        character_name: str,
        spell_name: str,
        slot_level: Optional[int] = None,
    ):
        character = self.db.get_character(str(interaction.user.id), character_name)
        if not character:
            await interaction.response.send_message(f"❌ Character **{character_name}** not found.", ephemeral=True)
            return

        await interaction.response.defer()

        spell_data = await dnd5e.get_spell(dnd5e.to_index(spell_name))
        if not spell_data:
            results = await dnd5e.search("spells", spell_name)
            if results:
                spell_data = await dnd5e.get_spell(results[0][1])

        spell_level = spell_data.get("level", 0) if spell_data else 0
        cast_at = slot_level if slot_level is not None else spell_level

        used_slot = False
        if cast_at > 0:
            if not character.use_spell_slot(cast_at):
                remaining = character.spell_slots.get(str(cast_at), 0)
                await interaction.followup.send(
                    f"❌ **{character.name}** has no level {cast_at} spell slots remaining ({remaining} left).",
                    ephemeral=True,
                )
                return
            self.db.save_character(character)
            used_slot = True

        embed = discord.Embed(
            title=f"🔮 {character.name} casts **{spell_name}**",
            color=discord.Color.purple(),
        )

        if spell_data:
            desc = spell_data.get("desc", [])
            desc_text = " ".join(desc)[:1000] if desc else "No description available."
            school = spell_data.get("school", {}).get("name", "Unknown")
            range_ = spell_data.get("range", "—")
            duration = spell_data.get("duration", "—")
            components = ", ".join(spell_data.get("components", []))
            conc = spell_data.get("concentration", False)
            ritual = spell_data.get("ritual", False)

            level_label = "Cantrip" if spell_level == 0 else f"Level {spell_level}"
            if cast_at != spell_level and cast_at > 0:
                level_label += f" (upcast to {cast_at})"

            embed.description = desc_text
            embed.add_field(name="School", value=school, inline=True)
            embed.add_field(name="Level", value=level_label, inline=True)
            embed.add_field(name="Range", value=range_, inline=True)
            embed.add_field(
                name="Duration",
                value=f"{duration}{' (Concentration)' if conc else ''}",
                inline=True,
            )
            embed.add_field(name="Components", value=components or "—", inline=True)
            if ritual:
                embed.add_field(name="Ritual", value="Yes", inline=True)
        else:
            embed.description = f"*(No API data found for '{spell_name}' — spell cast anyway)*"

        if used_slot:
            remaining = character.spell_slots.get(str(cast_at), 0)
            maximum = character.spell_slots_max.get(str(cast_at), 0)
            embed.set_footer(text=f"Level {cast_at} slot expended — {remaining}/{maximum} remaining")
        else:
            embed.set_footer(text="Cantrip — no slot expended")

        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Spells(bot))
