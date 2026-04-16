import discord
from discord import app_commands
from discord.ext import commands


class Help(commands.Cog):
    """Help and information commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="help", description="Show all available commands organized by category")
    async def help_command(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🎲 D&D Bot Commands",
            description="Here are all available slash commands, organized by category:",
            color=discord.Color.blurple()
        )

        # Dice Rolling Commands
        dice_commands = [
            "`/roll` - Roll dice using standard notation (1d20, 2d6+3)",
            "`/roll_adv` - Roll with advantage",
            "`/roll_dis` - Roll with disadvantage",
            "`/stats` - Roll ability scores (4d6 drop lowest)",
            "`/d20` - Quick d20 roll"
        ]
        embed.add_field(
            name="🎲 Dice Rolling",
            value="\n".join(dice_commands),
            inline=False
        )

        # Character Management Commands
        character_commands = [
            "`/createchar` - Create a new character (with dropdowns for class/race)",
            "`/viewchar` - View a character sheet",
            "`/listchars` - List all your characters",
            "`/deletechar` - Delete a character",
            "`/hp` - Adjust character HP (+heal / -damage)",
            "`/levelup` - Level up a character",
            "`/addxp` - Add experience points to a character"
        ]
        embed.add_field(
            name="📜 Character Management",
            value="\n".join(character_commands),
            inline=False
        )

        # Combat Commands
        combat_commands = [
            "`/combat start` - Start combat in this channel",
            "`/combat join` - Join combat with one of your characters",
            "`/combat addnpc` - Add an NPC/monster to initiative",
            "`/combat status` - Show turn order and current turn",
            "`/combat next` - Advance to the next turn",
            "`/combat prev` - Move to the previous turn",
            "`/combat damage` - Apply damage to a participant",
            "`/combat heal` - Heal a participant",
            "`/combat remove` - Remove a participant",
            "`/combat end` - End the current combat encounter"
        ]
        embed.add_field(
            name="⚔️ Combat",
            value="\n".join(combat_commands),
            inline=False
        )

        # AI Dungeon Master Commands
        ai_dm_commands = [
            "`/dm start_campaign` - Initialize AI campaign context in this channel",
            "`/dm scene` - Generate the next story scene based on player action",
            "`/dm talk` - Talk to an NPC with AI-driven dialogue"
        ]
        embed.add_field(
            name="🤖 AI Dungeon Master",
            value="\n".join(ai_dm_commands),
            inline=False
        )

        # General Commands
        general_commands = [
            "`/help` - Show this help message",
            "`/about` - About this bot"
        ]
        embed.add_field(
            name="ℹ️ General",
            value="\n".join(general_commands),
            inline=False
        )

        embed.set_footer(text="Tip: Start typing / to see command autocomplete!")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="about", description="Information about this D&D bot")
    async def about(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="About D&D Bot",
            description="A comprehensive Dungeons & Dragons 5e bot for managing campaigns, characters, and gameplay.",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="Features",
            value=(
                "✨ Dice rolling with advantage/disadvantage\n"
                "📊 Full character sheet management\n"
                "⚔️ Combat tracking and HP management\n"
                "🎯 Ability score rolling and modifiers\n"
                "📈 Experience and leveling system"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Getting Started",
            value="Use `/help` to see all commands, or `/createchar` to make your first character!",
            inline=False
        )
        
        embed.set_footer(text=f"Connected to {len(self.bot.guilds)} server(s)")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Help(bot))
