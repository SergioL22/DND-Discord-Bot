import logging
import random

import discord
from discord import app_commands
from discord.ext import commands

from utils import schema as db
from utils.dice_roller import DiceRoller

logger = logging.getLogger(__name__)


class DMTools(commands.Cog):
    """Private DM utilities: secret rolls, session notes, and quick tables."""

    dm_tools_group = app_commands.Group(name="dmtool", description="DM-only utility commands")

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @dm_tools_group.command(name="secret_roll", description="Roll dice privately — only you see the result")
    @app_commands.describe(dice="Dice notation, e.g. 1d20+5 or 2d6")
    async def secret_roll(self, interaction: discord.Interaction, dice: str):
        try:
            result = DiceRoller.roll(dice.strip())
        except Exception:
            await interaction.response.send_message(
                "❌ Invalid dice notation. Use standard notation like `1d20`, `2d6+3`.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title=f"🎲 Secret Roll: {dice.strip()}",
            description=str(result),
            color=discord.Color.dark_grey(),
        )
        embed.set_footer(text="Only you can see this roll.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @dm_tools_group.command(name="note", description="Add a private DM note to the current session")
    @app_commands.describe(text="The note to save")
    async def add_note(self, interaction: discord.Interaction, text: str):
        if not interaction.channel_id:
            await interaction.response.send_message("❌ Must be used in a server channel.", ephemeral=True)
            return

        session = db.session_get(interaction.channel_id)
        if not session:
            await interaction.response.send_message(
                "❌ No active campaign in this channel. Start one with `/dm start_campaign`.",
                ephemeral=True,
            )
            return

        notes = session.setdefault("dm_notes", [])
        notes.append(text.strip())
        session["dm_notes"] = notes[-20:]  # keep last 20
        db.session_save(interaction.channel_id, session)

        await interaction.response.send_message(
            f"📝 Note saved ({len(session['dm_notes'])} total).", ephemeral=True
        )

    @dm_tools_group.command(name="notes", description="View all DM notes for the current session")
    async def view_notes(self, interaction: discord.Interaction):
        if not interaction.channel_id:
            await interaction.response.send_message("❌ Must be used in a server channel.", ephemeral=True)
            return

        session = db.session_get(interaction.channel_id)
        notes = session.get("dm_notes", []) if session else []

        if not notes:
            await interaction.response.send_message("ℹ️ No DM notes saved for this session.", ephemeral=True)
            return

        embed = discord.Embed(title="📝 DM Notes", color=discord.Color.dark_gold())
        for i, note in enumerate(notes, 1):
            embed.add_field(name=f"#{i}", value=note[:1024], inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @dm_tools_group.command(name="npc", description="Generate a quick random NPC")
    async def random_npc(self, interaction: discord.Interaction):
        races = ["Human", "Elf", "Dwarf", "Halfling", "Gnome", "Half-Elf", "Tiefling", "Dragonborn"]
        traits = [
            "nervous and fidgety", "boastful and loud", "quiet and suspicious",
            "warm and generous", "greedy and cunning", "haunted by the past",
            "cheerful despite hardship", "blunt and honest to a fault",
            "obsessed with a strange hobby", "speaks in riddles",
        ]
        jobs = [
            "merchant", "blacksmith", "innkeeper", "guard", "farmer",
            "wandering bard", "former soldier", "healer", "scholar", "thief",
        ]
        male_names = ["Aldric", "Bram", "Caius", "Dorin", "Edran", "Fynn", "Gareth", "Holt"]
        female_names = ["Aela", "Brynn", "Calla", "Dara", "Elara", "Fiona", "Gwen", "Hilde"]
        names = male_names + female_names

        name = random.choice(names)
        race = random.choice(races)
        job = random.choice(jobs)
        trait = random.choice(traits)
        secret = random.choice([
            "owes a dangerous debt", "is hiding from someone",
            "knows more than they let on", "is not who they claim to be",
            "desperately needs the party's help", "has a connection to the main plot",
        ])

        embed = discord.Embed(
            title=f"👤 {name} the {job.title()}",
            color=discord.Color.teal(),
        )
        embed.add_field(name="Race", value=race, inline=True)
        embed.add_field(name="Occupation", value=job.title(), inline=True)
        embed.add_field(name="Personality", value=trait.capitalize(), inline=False)
        embed.add_field(name="Hidden secret", value=secret.capitalize(), inline=False)
        embed.set_footer(text="Roll again for a different NPC")
        await interaction.response.send_message(embed=embed)

    @dm_tools_group.command(name="encounter", description="Roll a random encounter difficulty for the party")
    @app_commands.describe(party_level="Average party level (1–20)", party_size="Number of players")
    async def random_encounter(self, interaction: discord.Interaction, party_level: int, party_size: int):
        if not 1 <= party_level <= 20:
            await interaction.response.send_message("❌ Party level must be between 1 and 20.", ephemeral=True)
            return
        if not 1 <= party_size <= 10:
            await interaction.response.send_message("❌ Party size must be between 1 and 10.", ephemeral=True)
            return

        difficulties = ["Easy", "Medium", "Hard", "Deadly"]
        weights = [25, 35, 25, 15]
        difficulty = random.choices(difficulties, weights=weights)[0]

        monster_count = random.randint(1, max(1, party_size))
        cr_map = {
            "Easy": max(1, party_level // 4),
            "Medium": max(1, party_level // 2),
            "Hard": party_level,
            "Deadly": min(20, party_level + random.randint(1, 4)),
        }
        cr = cr_map[difficulty]

        color_map = {
            "Easy": discord.Color.green(),
            "Medium": discord.Color.yellow(),
            "Hard": discord.Color.orange(),
            "Deadly": discord.Color.red(),
        }

        terrain = random.choice([
            "dense forest", "abandoned ruins", "narrow cave tunnel",
            "open road", "foggy swamp", "mountain pass", "tavern backroom",
        ])

        embed = discord.Embed(
            title=f"⚔️ {difficulty} Encounter",
            color=color_map[difficulty],
        )
        embed.add_field(name="Suggested CR", value=str(cr), inline=True)
        embed.add_field(name="Monster Count", value=str(monster_count), inline=True)
        embed.add_field(name="Setting", value=terrain.capitalize(), inline=True)
        embed.set_footer(text=f"Party: {party_size} players · Level {party_level}")
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(DMTools(bot))
