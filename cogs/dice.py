import discord
from discord import app_commands
from discord.ext import commands
from utils.dice_roller import DiceRoller


class Dice(commands.Cog):
    """Dice rolling slash commands for D&D."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="roll", description="Roll dice like 1d20, 2d6+3, 4d6-1")
    @app_commands.describe(dice="Dice notation (example: 1d20, 2d6+3)")
    async def roll(self, interaction: discord.Interaction, dice: str):
        try:
            result = DiceRoller.roll(dice)
            await interaction.response.send_message(f"Rolled {dice}: {result}")
        except ValueError as e:
            await interaction.response.send_message(f"Error rolling dice: {e}", ephemeral=True)

    @app_commands.command(name="roll_adv", description="Roll with advantage")
    @app_commands.describe(dice="Dice notation, usually 1d20+modifier")
    async def roll_advantage(self, interaction: discord.Interaction, dice: str):
        try:
            result = DiceRoller.roll(dice, advantage=True)
            await interaction.response.send_message(f"Rolled {dice} with advantage: {result}")
        except ValueError as e:
            await interaction.response.send_message(f"Error: {e}", ephemeral=True)

    @app_commands.command(name="roll_dis", description="Roll with disadvantage")
    @app_commands.describe(dice="Dice notation, usually 1d20+modifier")
    async def roll_disadvantage(self, interaction: discord.Interaction, dice: str):
        try:
            result = DiceRoller.roll(dice, disadvantage=True)
            await interaction.response.send_message(f"Rolled {dice} with disadvantage: {result}")
        except ValueError as e:
            await interaction.response.send_message(f"Error: {e}", ephemeral=True)

    @app_commands.command(name="stats", description="Roll 6 ability scores (4d6 drop lowest)")
    async def stats(self, interaction: discord.Interaction):
        scores = DiceRoller.roll_stats()
        score_lines = [f"**{ability.title()}**: {value}" for ability, value in scores.items()]

        character_cog = self.bot.get_cog("Character")
        if character_cog:
            character_cog.store_rolled_stats(interaction.user.id, scores)

        embed = discord.Embed(
            title="🎲 Rolled Ability Scores",
            description="\n".join(score_lines),
            color=discord.Color.gold(),
        )
        embed.set_footer(text="Stats saved for 5 minutes. Use the button below to create a character!")

        view = CreateCharacterButton()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="d20", description="Quick d20 roll")
    async def d20(self, interaction: discord.Interaction):
        result = DiceRoller.roll("1d20")
        await interaction.response.send_message(f"🎲 Rolled 1d20: {result}")


class CreateCharacterButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.button(label="Create Character with These Stats", style=discord.ButtonStyle.green, emoji="✨")
    async def create_character(self, interaction: discord.Interaction, button: discord.ui.Button):
        character_cog = interaction.client.get_cog("Character")
        if character_cog:
            await character_cog.open_character_creation_modal(interaction)
        else:
            await interaction.response.send_message("❌ Character system not available.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Dice(bot))
    
    