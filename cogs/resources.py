from typing import List

import discord
from discord import app_commands
from discord.ext import commands

from utils.database import get_database


SPELL_LEVEL_CHOICES = [app_commands.Choice(name=f"Level {i}", value=i) for i in range(1, 10)]


class Resources(commands.Cog):
    """Inventory, spell slots, rest, and currency management."""

    item_group = app_commands.Group(name="item", description="Manage character inventory")
    spellslots_group = app_commands.Group(name="spellslots", description="Track and use spell slots")
    rest_group = app_commands.Group(name="rest", description="Take a short or long rest")
    gold_group = app_commands.Group(name="gold", description="Manage character currency")

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = get_database()

    async def _char_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> List[app_commands.Choice[str]]:
        owner_id = str(interaction.user.id)
        names = self.db.get_all_character_names(owner_id)
        filtered = [name for name in names if current.lower() in name.lower()]
        return [app_commands.Choice(name=n, value=n) for n in filtered[:25]]

    # ── Items ─────────────────────────────────────────────────────────────────

    @item_group.command(name="add", description="Add an item to a character's inventory")
    @app_commands.describe(character_name="Your character", item="Item to add")
    @app_commands.autocomplete(character_name=_char_autocomplete)
    async def item_add(self, interaction: discord.Interaction, character_name: str, item: str):
        owner_id = str(interaction.user.id)
        character = self.db.get_character(owner_id, character_name)
        if not character:
            await interaction.response.send_message(f"❌ Character **{character_name}** not found.", ephemeral=True)
            return

        character.add_item(item)
        self.db.save_character(character)
        await interaction.response.send_message(
            f"🎒 Added **{item.strip()}** to **{character.name}**'s inventory. "
            f"({len(character.inventory)} item(s) total)"
        )

    @item_group.command(name="remove", description="Remove an item from a character's inventory")
    @app_commands.describe(character_name="Your character", item="Item to remove")
    @app_commands.autocomplete(character_name=_char_autocomplete)
    async def item_remove(self, interaction: discord.Interaction, character_name: str, item: str):
        owner_id = str(interaction.user.id)
        character = self.db.get_character(owner_id, character_name)
        if not character:
            await interaction.response.send_message(f"❌ Character **{character_name}** not found.", ephemeral=True)
            return

        if not character.remove_item(item):
            await interaction.response.send_message(
                f"❌ **{item.strip()}** not found in **{character.name}**'s inventory.", ephemeral=True
            )
            return

        self.db.save_character(character)
        await interaction.response.send_message(
            f"🗑️ Removed **{item.strip()}** from **{character.name}**'s inventory."
        )

    @item_group.command(name="list", description="View a character's inventory")
    @app_commands.describe(character_name="Your character")
    @app_commands.autocomplete(character_name=_char_autocomplete)
    async def item_list(self, interaction: discord.Interaction, character_name: str):
        owner_id = str(interaction.user.id)
        character = self.db.get_character(owner_id, character_name)
        if not character:
            await interaction.response.send_message(f"❌ Character **{character_name}** not found.", ephemeral=True)
            return

        if not character.inventory:
            await interaction.response.send_message(
                f"🎒 **{character.name}**'s inventory is empty.", ephemeral=True
            )
            return

        items_text = "\n".join(f"• {it}" for it in character.inventory)
        embed = discord.Embed(
            title=f"🎒 {character.name}'s Inventory",
            description=items_text[:4000],
            color=discord.Color.blurple(),
        )
        embed.set_footer(
            text=f"{len(character.inventory)} item(s)  |  "
                 f"💰 {character.gold}gp {character.silver}sp {character.copper}cp"
        )
        await interaction.response.send_message(embed=embed)

    # ── Spell Slots ───────────────────────────────────────────────────────────

    @spellslots_group.command(name="view", description="View a character's current spell slots")
    @app_commands.describe(character_name="Your character")
    @app_commands.autocomplete(character_name=_char_autocomplete)
    async def spellslots_view(self, interaction: discord.Interaction, character_name: str):
        owner_id = str(interaction.user.id)
        character = self.db.get_character(owner_id, character_name)
        if not character:
            await interaction.response.send_message(f"❌ Character **{character_name}** not found.", ephemeral=True)
            return

        if not character.spell_slots_max and not character.spell_slots:
            await interaction.response.send_message(
                f"ℹ️ **{character.name}** has no spell slots configured.\n"
                f"Use `/spellslots set` to set them up.",
                ephemeral=True,
            )
            return

        all_levels = sorted(
            {int(k) for k in list(character.spell_slots) + list(character.spell_slots_max)}
        )
        embed = discord.Embed(title=f"🔮 {character.name}'s Spell Slots", color=discord.Color.purple())
        for level in all_levels:
            current = character.spell_slots.get(str(level), 0)
            maximum = character.spell_slots_max.get(str(level), 0)
            bar = "🟣" * current + "⬛" * max(0, maximum - current)
            embed.add_field(name=f"Level {level}", value=f"{bar} {current}/{maximum}", inline=True)
        embed.set_footer(text="Use /spellslots use to expend  •  /spellslots restore to recover all")
        await interaction.response.send_message(embed=embed)

    @spellslots_group.command(name="set", description="Set the max slots for a spell level")
    @app_commands.describe(
        character_name="Your character",
        level="Spell level (1–9)",
        count="Number of maximum slots at this level",
    )
    @app_commands.autocomplete(character_name=_char_autocomplete)
    @app_commands.choices(level=SPELL_LEVEL_CHOICES)
    async def spellslots_set(
        self,
        interaction: discord.Interaction,
        character_name: str,
        level: app_commands.Choice[int],
        count: int,
    ):
        if count < 0:
            await interaction.response.send_message("❌ Slot count cannot be negative.", ephemeral=True)
            return

        owner_id = str(interaction.user.id)
        character = self.db.get_character(owner_id, character_name)
        if not character:
            await interaction.response.send_message(f"❌ Character **{character_name}** not found.", ephemeral=True)
            return

        character.set_max_spell_slots(level.value, count)
        self.db.save_character(character)
        await interaction.response.send_message(
            f"🔮 **{character.name}** level {level.value} spell slots set to **{count}/{count}**."
        )

    @spellslots_group.command(name="use", description="Expend one spell slot")
    @app_commands.describe(character_name="Your character", level="Spell slot level to use (1–9)")
    @app_commands.autocomplete(character_name=_char_autocomplete)
    @app_commands.choices(level=SPELL_LEVEL_CHOICES)
    async def spellslots_use(
        self,
        interaction: discord.Interaction,
        character_name: str,
        level: app_commands.Choice[int],
    ):
        owner_id = str(interaction.user.id)
        character = self.db.get_character(owner_id, character_name)
        if not character:
            await interaction.response.send_message(f"❌ Character **{character_name}** not found.", ephemeral=True)
            return

        if not character.use_spell_slot(level.value):
            current = character.spell_slots.get(str(level.value), 0)
            await interaction.response.send_message(
                f"❌ **{character.name}** has no level {level.value} slots remaining (current: {current}).",
                ephemeral=True,
            )
            return

        self.db.save_character(character)
        remaining = character.spell_slots.get(str(level.value), 0)
        maximum = character.spell_slots_max.get(str(level.value), 0)
        await interaction.response.send_message(
            f"🔮 **{character.name}** used a level **{level.value}** spell slot. "
            f"({remaining}/{maximum} remaining)"
        )

    @spellslots_group.command(name="restore", description="Restore all spell slots to maximum")
    @app_commands.describe(character_name="Your character")
    @app_commands.autocomplete(character_name=_char_autocomplete)
    async def spellslots_restore(self, interaction: discord.Interaction, character_name: str):
        owner_id = str(interaction.user.id)
        character = self.db.get_character(owner_id, character_name)
        if not character:
            await interaction.response.send_message(f"❌ Character **{character_name}** not found.", ephemeral=True)
            return

        character.restore_spell_slots()
        self.db.save_character(character)
        await interaction.response.send_message(
            f"✨ **{character.name}**'s spell slots fully restored."
        )

    @spellslots_group.command(
        name="setup",
        description="Auto-fill spell slot maximums from the D&D 5e API based on class and level",
    )
    @app_commands.describe(character_name="Your character")
    @app_commands.autocomplete(character_name=_char_autocomplete)
    async def spellslots_setup(self, interaction: discord.Interaction, character_name: str):
        owner_id = str(interaction.user.id)
        character = self.db.get_character(owner_id, character_name)
        if not character:
            await interaction.response.send_message(f"❌ Character **{character_name}** not found.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        from utils import dnd5e_api as dnd5e

        try:
            level_data = await dnd5e.get_class_level(character.character_class, character.level)
        except RuntimeError as e:
            await interaction.followup.send(f"❌ API error: {e}", ephemeral=True)
            return

        if not level_data:
            await interaction.followup.send(
                f"❌ No data found for **{character.character_class}** level {character.level}. "
                f"Check that the class name is spelled correctly.",
                ephemeral=True,
            )
            return

        spellcasting = level_data.get("spellcasting", {})
        if not spellcasting:
            await interaction.followup.send(
                f"ℹ️ **{character.character_class}** does not have standard spell slots at level {character.level}.\n"
                f"Use `/spellslots set` to configure slots manually (e.g. for Warlock Pact Magic).",
                ephemeral=True,
            )
            return

        SLOT_KEYS = {
            1: "spell_slots_level_1", 2: "spell_slots_level_2", 3: "spell_slots_level_3",
            4: "spell_slots_level_4", 5: "spell_slots_level_5", 6: "spell_slots_level_6",
            7: "spell_slots_level_7", 8: "spell_slots_level_8", 9: "spell_slots_level_9",
        }

        set_slots = {}
        for lvl, key in SLOT_KEYS.items():
            count = spellcasting.get(key, 0)
            if count > 0:
                character.set_max_spell_slots(lvl, count)
                set_slots[lvl] = count

        if not set_slots:
            await interaction.followup.send(
                f"ℹ️ No spell slots found for **{character.character_class}** level {character.level}.",
                ephemeral=True,
            )
            return

        self.db.save_character(character)
        summary = "  ".join(f"L{lvl}: {count}" for lvl, count in sorted(set_slots.items()))
        await interaction.followup.send(
            f"✅ **{character.name}**'s spell slots auto-configured for "
            f"{character.character_class} level {character.level}:\n`{summary}`",
            ephemeral=True,
        )

    # ── Rest ──────────────────────────────────────────────────────────────────

    @rest_group.command(name="short", description="Short rest — recover HP by spending hit dice")
    @app_commands.describe(
        character_name="Your character",
        hp_recovered="HP recovered from your hit dice rolls (calculate manually)",
    )
    @app_commands.autocomplete(character_name=_char_autocomplete)
    async def rest_short(self, interaction: discord.Interaction, character_name: str, hp_recovered: int):
        if hp_recovered < 0:
            await interaction.response.send_message("❌ HP recovered cannot be negative.", ephemeral=True)
            return

        owner_id = str(interaction.user.id)
        character = self.db.get_character(owner_id, character_name)
        if not character:
            await interaction.response.send_message(f"❌ Character **{character_name}** not found.", ephemeral=True)
            return

        old_hp = character.current_hp
        character.adjust_hp(hp_recovered)
        self.db.save_character(character)

        embed = discord.Embed(
            title=f"⏱️ {character.name} — Short Rest",
            color=discord.Color.blue(),
        )
        embed.add_field(
            name="HP",
            value=f"{old_hp} → {character.current_hp}/{character.max_hp} (+{hp_recovered})",
            inline=True,
        )
        embed.add_field(name="Hit Dice", value=character.hit_dice, inline=True)
        embed.set_footer(text="Spell slots are NOT restored on a short rest.")
        await interaction.response.send_message(embed=embed)

    @rest_group.command(name="long", description="Long rest — restores HP to max and all spell slots")
    @app_commands.describe(character_name="Your character")
    @app_commands.autocomplete(character_name=_char_autocomplete)
    async def rest_long(self, interaction: discord.Interaction, character_name: str):
        owner_id = str(interaction.user.id)
        character = self.db.get_character(owner_id, character_name)
        if not character:
            await interaction.response.send_message(f"❌ Character **{character_name}** not found.", ephemeral=True)
            return

        old_hp = character.current_hp
        character.adjust_hp(character.max_hp - character.current_hp)
        character.restore_spell_slots()
        self.db.save_character(character)

        embed = discord.Embed(
            title=f"🌙 {character.name} — Long Rest",
            color=discord.Color.dark_blue(),
        )
        embed.add_field(
            name="HP Restored",
            value=f"{old_hp} → {character.max_hp}/{character.max_hp}",
            inline=True,
        )
        if character.spell_slots:
            slots_text = "  ".join(
                f"L{lvl}: {count}"
                for lvl, count in sorted(character.spell_slots.items(), key=lambda x: int(x[0]))
            )
            embed.add_field(name="Spell Slots", value=slots_text, inline=False)
        await interaction.response.send_message(embed=embed)

    # ── Currency ──────────────────────────────────────────────────────────────

    @gold_group.command(name="view", description="View a character's currency")
    @app_commands.describe(character_name="Your character")
    @app_commands.autocomplete(character_name=_char_autocomplete)
    async def gold_view(self, interaction: discord.Interaction, character_name: str):
        owner_id = str(interaction.user.id)
        character = self.db.get_character(owner_id, character_name)
        if not character:
            await interaction.response.send_message(f"❌ Character **{character_name}** not found.", ephemeral=True)
            return

        total_cp = character.gold * 100 + character.silver * 10 + character.copper
        embed = discord.Embed(title=f"💰 {character.name}'s Currency", color=discord.Color.gold())
        embed.add_field(name="Gold (gp)", value=str(character.gold), inline=True)
        embed.add_field(name="Silver (sp)", value=str(character.silver), inline=True)
        embed.add_field(name="Copper (cp)", value=str(character.copper), inline=True)
        embed.set_footer(text=f"Total: {total_cp} cp")
        await interaction.response.send_message(embed=embed)

    @gold_group.command(name="add", description="Add currency to a character")
    @app_commands.describe(
        character_name="Your character",
        gp="Gold pieces to add",
        sp="Silver pieces to add",
        cp="Copper pieces to add",
    )
    @app_commands.autocomplete(character_name=_char_autocomplete)
    async def gold_add(
        self,
        interaction: discord.Interaction,
        character_name: str,
        gp: int = 0,
        sp: int = 0,
        cp: int = 0,
    ):
        if gp == 0 and sp == 0 and cp == 0:
            await interaction.response.send_message("❌ Specify at least one currency amount.", ephemeral=True)
            return
        if gp < 0 or sp < 0 or cp < 0:
            await interaction.response.send_message(
                "❌ Amounts must be non-negative. Use `/gold spend` to subtract.", ephemeral=True
            )
            return

        owner_id = str(interaction.user.id)
        character = self.db.get_character(owner_id, character_name)
        if not character:
            await interaction.response.send_message(f"❌ Character **{character_name}** not found.", ephemeral=True)
            return

        character.adjust_currency(gp=gp, sp=sp, cp=cp)
        self.db.save_character(character)

        parts = [f"{gp}gp" if gp else "", f"{sp}sp" if sp else "", f"{cp}cp" if cp else ""]
        gained = " ".join(p for p in parts if p)
        await interaction.response.send_message(
            f"💰 **{character.name}** gained **{gained}**.\n"
            f"Now has: {character.gold}gp {character.silver}sp {character.copper}cp"
        )

    @gold_group.command(name="spend", description="Spend currency from a character")
    @app_commands.describe(
        character_name="Your character",
        gp="Gold pieces to spend",
        sp="Silver pieces to spend",
        cp="Copper pieces to spend",
    )
    @app_commands.autocomplete(character_name=_char_autocomplete)
    async def gold_spend(
        self,
        interaction: discord.Interaction,
        character_name: str,
        gp: int = 0,
        sp: int = 0,
        cp: int = 0,
    ):
        if gp == 0 and sp == 0 and cp == 0:
            await interaction.response.send_message("❌ Specify at least one currency amount.", ephemeral=True)
            return
        if gp < 0 or sp < 0 or cp < 0:
            await interaction.response.send_message("❌ Amounts must be non-negative.", ephemeral=True)
            return

        owner_id = str(interaction.user.id)
        character = self.db.get_character(owner_id, character_name)
        if not character:
            await interaction.response.send_message(f"❌ Character **{character_name}** not found.", ephemeral=True)
            return

        try:
            character.adjust_currency(gp=-gp, sp=-sp, cp=-cp)
        except ValueError:
            await interaction.response.send_message(
                f"❌ **{character.name}** doesn't have enough currency.\n"
                f"Has: {character.gold}gp {character.silver}sp {character.copper}cp",
                ephemeral=True,
            )
            return

        self.db.save_character(character)
        parts = [f"{gp}gp" if gp else "", f"{sp}sp" if sp else "", f"{cp}cp" if cp else ""]
        spent = " ".join(p for p in parts if p)
        await interaction.response.send_message(
            f"💸 **{character.name}** spent **{spent}**.\n"
            f"Remaining: {character.gold}gp {character.silver}sp {character.copper}cp"
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Resources(bot))
