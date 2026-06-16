import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, List, Dict
import time

from utils.character_sheet import CharacterSheet
from utils.database import get_database


RACE_SPEEDS = {
    "Dragonborn": 30,
    "Dwarf": 25,
    "Elf": 30,
    "Gnome": 25,
    "Half-Elf": 30,
    "Half-Orc": 30,
    "Halfling": 25,
    "Human": 30,
    "Tiefling": 30,
}

XP_THRESHOLDS = [
    0, 300, 900, 2700, 6500, 14000, 23000, 34000, 48000, 64000,
    85000, 100000, 120000, 140000, 165000, 195000, 225000, 265000, 305000, 355000,
]


def _build_character_embed(character: "CharacterSheet") -> discord.Embed:
    embed = discord.Embed(
        title="✨ Character Created",
        description=f"**{character.name}** is ready for adventure.",
        color=discord.Color.green(),
    )
    embed.add_field(name="Class", value=character.character_class, inline=True)
    embed.add_field(name="Race", value=character.race, inline=True)
    embed.add_field(name="Level", value=str(character.level), inline=True)
    embed.add_field(name="HP", value=f"{character.current_hp}/{character.max_hp}", inline=True)
    embed.add_field(name="AC", value=str(character.effective_ac()), inline=True)
    embed.add_field(name="Speed", value=f"{character.speed} ft", inline=True)
    ability_text = "\n".join(
        f"**{a.title()}**: {s} ({'+' if CharacterSheet.ability_modifier(s) >= 0 else ''}{CharacterSheet.ability_modifier(s)})"
        for a, s in character.abilities.items()
    )
    embed.add_field(name="Ability Scores", value=ability_text, inline=False)
    return embed


class Character(commands.Cog):
    """Character management slash commands for D&D."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = get_database()
        self.rolled_stats: Dict[int, tuple[Dict[str, int], float]] = {}  # user_id -> (stats, timestamp)

    async def _character_name_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> List[app_commands.Choice[str]]:
        owner_id = str(interaction.user.id)
        names = self.db.get_all_character_names(owner_id)
        filtered = [name for name in names if current.lower() in name.lower()]
        return [app_commands.Choice(name=n, value=n) for n in filtered[:25]]
    
    def store_rolled_stats(self, user_id: int, stats: Dict[str, int]) -> None:
        """Store rolled stats for a user with 5-minute expiry."""
        self.rolled_stats[user_id] = (stats, time.time())
    
    def get_rolled_stats(self, user_id: int) -> Optional[Dict[str, int]]:
        """Retrieve rolled stats if they exist and haven't expired (5 minutes)."""
        if user_id not in self.rolled_stats:
            return None
        
        stats, timestamp = self.rolled_stats[user_id]
        if time.time() - timestamp > 300:  # 5 minutes
            del self.rolled_stats[user_id]
            return None
        
        return stats
    
    async def open_character_creation_modal(self, interaction: discord.Interaction) -> None:
        """Open the character creation flow with dropdowns for class/race."""
        stats = self.get_rolled_stats(interaction.user.id)
        if not stats:
            await interaction.response.send_message(
                "❌ Your rolled stats have expired. Use `/stats` again to roll new ones.",
                ephemeral=True
            )
            return
        
        view = ClassSelectionView(stats, self.db)
        await interaction.response.send_message(
            "**Step 1/3:** Select your character's class:",
            view=view,
            ephemeral=True
        )

    @app_commands.command(name="viewchar", description="View one of your characters")
    @app_commands.describe(character_name="Character to view")
    @app_commands.autocomplete(character_name=_character_name_autocomplete)
    async def view_character(self, interaction: discord.Interaction, character_name: str):
        owner_id = str(interaction.user.id)
        character = self.db.get_character(owner_id, character_name)

        if not character:
            await interaction.response.send_message(
                f"❌ Character **{character_name}** not found.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title=f"📜 {character.name}",
            description=f"Level {character.level} {character.race} {character.character_class}",
            color=discord.Color.blurple(),
        )

        if character.background:
            embed.add_field(name="Background", value=character.background, inline=True)
        if character.alignment:
            embed.add_field(name="Alignment", value=character.alignment, inline=True)
        embed.add_field(name="XP", value=str(character.exp), inline=True)

        combat = character.combat_snapshot()
        combat_text = (
            f"**HP:** {combat['hp']}\n"
            f"**Temp HP:** {combat['temp_hp']}\n"
            f"**AC:** {combat['ac']}\n"
            f"**Initiative:** {'+' if combat['initiative'] >= 0 else ''}{combat['initiative']}\n"
            f"**Speed:** {combat['speed']} ft\n"
            f"**Passive Perception:** {combat['passive_perception']}"
        )
        embed.add_field(name="⚔️ Combat", value=combat_text, inline=False)

        ability_text = ""
        for ability, score in character.abilities.items():
            mod = character.get_modifier(ability)
            ability_text += f"**{ability.title()}**: {score} ({'+' if mod >= 0 else ''}{mod})\n"
        embed.add_field(name="📊 Abilities", value=ability_text, inline=True)

        prof_text = f"**Proficiency Bonus:** +{character.proficiency_bonus()}\n"
        if character.saving_throw_proficiencies:
            prof_text += f"**Saves:** {', '.join(s.title() for s in character.saving_throw_proficiencies)}\n"
        if character.skill_proficiencies:
            prof_text += f"**Skills:** {', '.join(s.replace('_', ' ').title() for s in character.skill_proficiencies)}"
        embed.add_field(name="✨ Proficiencies", value=prof_text, inline=True)

        embed.add_field(
            name="Currency",
            value=f"💰 {character.gold}gp {character.silver}sp {character.copper}cp",
            inline=False,
        )

        if character.inventory:
            inv = ", ".join(character.inventory[:10])
            if len(character.inventory) > 10:
                inv += f" ... (+{len(character.inventory) - 10} more)"
            embed.add_field(name="🎒 Inventory", value=inv, inline=False)

        if character.spellcasting_ability:
            spell_text = (
                f"**Ability:** {character.spellcasting_ability.title()}\n"
                f"**Spell Save DC:** {character.spell_save_dc}\n"
                f"**Spell Attack:** +{character.spell_attack_bonus}"
            )
            embed.add_field(name="🔮 Spellcasting", value=spell_text, inline=False)

        embed.set_footer(text=f"Owner: {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="listchars", description="List all of your characters")
    async def list_characters(self, interaction: discord.Interaction):
        owner_id = str(interaction.user.id)
        characters = self.db.get_all_characters(owner_id)

        if not characters:
            await interaction.response.send_message(
                "❌ You don’t have any characters yet. Use `/stats` and click **Create Character** to get started.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title=f"📚 {interaction.user.display_name}'s Characters",
            color=discord.Color.gold(),
        )

        for char in characters:
            info = (
                f"**Level {char.level}** {char.race} {char.character_class}\n"
                f"HP: {char.current_hp}/{char.max_hp} | AC: {char.effective_ac()} | XP: {char.exp}"
            )
            embed.add_field(name=char.name, value=info, inline=False)

        embed.set_footer(text=f"Total: {len(characters)} character(s)")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="deletechar", description="Delete one of your characters")
    @app_commands.describe(character_name="Character to delete")
    @app_commands.autocomplete(character_name=_character_name_autocomplete)
    async def delete_character(self, interaction: discord.Interaction, character_name: str):
        owner_id = str(interaction.user.id)

        if not self.db.character_exists(owner_id, character_name):
            await interaction.response.send_message(
                f"❌ Character **{character_name}** not found.",
                ephemeral=True,
            )
            return

        self.db.delete_character(owner_id, character_name)
        await interaction.response.send_message(f"✅ Deleted **{character_name}**.")

    @app_commands.command(name="hp", description="Adjust HP for one of your characters")
    @app_commands.describe(
        character_name="Character to modify",
        amount="Use positive to heal, negative to damage (example: -7 or 5)",
    )
    @app_commands.autocomplete(character_name=_character_name_autocomplete)
    async def adjust_hp(self, interaction: discord.Interaction, character_name: str, amount: int):
        owner_id = str(interaction.user.id)
        character = self.db.get_character(owner_id, character_name)

        if not character:
            await interaction.response.send_message(
                f"❌ Character **{character_name}** not found.",
                ephemeral=True,
            )
            return

        old_hp = character.current_hp
        character.adjust_hp(amount)
        self.db.save_character(character)

        await interaction.response.send_message(
            f"💚 **{character.name}** HP: {old_hp} → {character.current_hp}/{character.max_hp} "
            f"({'+' if amount > 0 else ''}{amount})"
        )

    @app_commands.command(name="levelup", description="Level up one of your characters")
    @app_commands.describe(character_name="Character to level up")
    @app_commands.autocomplete(character_name=_character_name_autocomplete)
    async def level_up(self, interaction: discord.Interaction, character_name: str):
        owner_id = str(interaction.user.id)
        character = self.db.get_character(owner_id, character_name)

        if not character:
            await interaction.response.send_message(
                f"❌ Character **{character_name}** not found.",
                ephemeral=True,
            )
            return

        if character.level >= 20:
            await interaction.response.send_message(
                f"❌ **{character.name}** is already level 20.",
                ephemeral=True,
            )
            return

        old_level = character.level
        character.level_up()
        self.db.save_character(character)

        await interaction.response.send_message(
            f"🎉 **{character.name}** leveled up: {old_level} → {character.level}\n"
            f"Proficiency Bonus: +{character.proficiency_bonus()}"
        )

    @app_commands.command(name="addxp", description="Add XP to one of your characters")
    @app_commands.describe(character_name="Character to award XP to", amount="XP amount to add")
    @app_commands.autocomplete(character_name=_character_name_autocomplete)
    async def add_xp(self, interaction: discord.Interaction, character_name: str, amount: int):
        owner_id = str(interaction.user.id)
        character = self.db.get_character(owner_id, character_name)

        if not character:
            await interaction.response.send_message(
                f"❌ Character **{character_name}** not found.",
                ephemeral=True,
            )
            return

        try:
            old_xp = character.exp
            character.add_xp(amount)
            self.db.save_character(character)

            levelup_note = ""
            next_level = character.level + 1
            if next_level <= 20 and character.exp >= XP_THRESHOLDS[next_level - 1]:
                levelup_note = f"\n🎉 **Ready to level up to level {next_level}!** Use `/levelup` to advance."

            await interaction.response.send_message(
                f"✨ **{character.name}** gained {amount} XP.\n"
                f"XP: {old_xp} → {character.exp}"
                f"{levelup_note}"
            )
        except ValueError as e:
            await interaction.response.send_message(f"❌ {e}", ephemeral=True)


class ClassSelectionView(discord.ui.View):
    """View with dropdown for selecting character class."""
    
    def __init__(self, stats: Dict[str, int], db):
        super().__init__(timeout=300)
        self.stats = stats
        self.db = db
    
    @discord.ui.select(
        placeholder="Choose a class",
        options=[
            discord.SelectOption(label="Barbarian", value="Barbarian"),
            discord.SelectOption(label="Bard", value="Bard"),
            discord.SelectOption(label="Cleric", value="Cleric"),
            discord.SelectOption(label="Druid", value="Druid"),
            discord.SelectOption(label="Fighter", value="Fighter"),
            discord.SelectOption(label="Monk", value="Monk"),
            discord.SelectOption(label="Paladin", value="Paladin"),
            discord.SelectOption(label="Ranger", value="Ranger"),
            discord.SelectOption(label="Rogue", value="Rogue"),
            discord.SelectOption(label="Sorcerer", value="Sorcerer"),
            discord.SelectOption(label="Warlock", value="Warlock"),
            discord.SelectOption(label="Wizard", value="Wizard"),
        ]
    )
    async def class_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        selected_class = select.values[0]
        view = RaceSelectionView(self.stats, self.db, selected_class)
        await interaction.response.edit_message(
            content=f"**Step 2/3:** You chose **{selected_class}**. Now select your race:",
            view=view
        )


class RaceSelectionView(discord.ui.View):
    """View with dropdown for selecting character race."""
    
    def __init__(self, stats: Dict[str, int], db, character_class: str):
        super().__init__(timeout=300)
        self.stats = stats
        self.db = db
        self.character_class = character_class
    
    @discord.ui.select(
        placeholder="Choose a race",
        options=[
            discord.SelectOption(label="Dragonborn", value="Dragonborn"),
            discord.SelectOption(label="Dwarf", value="Dwarf"),
            discord.SelectOption(label="Elf", value="Elf"),
            discord.SelectOption(label="Gnome", value="Gnome"),
            discord.SelectOption(label="Half-Elf", value="Half-Elf"),
            discord.SelectOption(label="Half-Orc", value="Half-Orc"),
            discord.SelectOption(label="Halfling", value="Halfling"),
            discord.SelectOption(label="Human", value="Human"),
            discord.SelectOption(label="Tiefling", value="Tiefling"),
        ]
    )
    async def race_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        selected_race = select.values[0]
        modal = NameInputModal(self.stats, self.db, self.character_class, selected_race)
        await interaction.response.send_modal(modal)


class NameInputModal(discord.ui.Modal, title="Character Name"):
    """Final step: enter character name."""
    
    def __init__(self, stats: Dict[str, int], db, character_class: str, race: str):
        super().__init__()
        self.stats = stats
        self.db = db
        self.character_class = character_class
        self.race = race
    
    name = discord.ui.TextInput(
        label="Enter your character's name",
        placeholder="Gandalf, Frodo, Aragorn...",
        required=True,
        max_length=50
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        owner_id = str(interaction.user.id)
        
        if self.db.character_exists(owner_id, self.name.value):
            await interaction.response.send_message(
                f"❌ You already have a character named **{self.name.value}**.",
                ephemeral=True
            )
            return
        
        try:
            abilities = {k.lower(): v for k, v in self.stats.items()}
            
            con_mod = CharacterSheet.ability_modifier(abilities["constitution"])
            starting_hp = max(1, 10 + con_mod)
            
            character = CharacterSheet(
                owner_id=owner_id,
                name=self.name.value,
                character_class=self.character_class,
                race=self.race,
                abilities=abilities,
                max_hp=starting_hp,
                current_hp=starting_hp,
                speed=RACE_SPEEDS.get(self.race, 30),
            )
            self.db.save_character(character)
            
            await interaction.response.send_message(embed=_build_character_embed(character))
        except ValueError as e:
            await interaction.response.send_message(f"❌ Error creating character: {e}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Character(bot))