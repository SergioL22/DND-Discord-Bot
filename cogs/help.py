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
            description="All available slash commands, organized by category:",
            color=discord.Color.blurple(),
        )

        embed.add_field(
            name="🎲 Dice Rolling",
            value=(
                "`/roll` - Roll dice using standard notation (1d20, 2d6+3)\n"
                "`/roll_adv` - Roll with advantage\n"
                "`/roll_dis` - Roll with disadvantage\n"
                "`/stats` - Roll ability scores (4d6 drop lowest)\n"
                "`/d20` - Quick d20 roll"
            ),
            inline=False,
        )

        embed.add_field(
            name="📜 Character Management",
            value=(
                "`/createchar` - Create a new character (with dropdowns for class/race)\n"
                "`/viewchar` - View a full character sheet\n"
                "`/listchars` - List all your characters\n"
                "`/deletechar` - Delete a character\n"
                "`/hp` - Adjust character HP (+heal / -damage)\n"
                "`/levelup` - Level up a character\n"
                "`/addxp` - Add experience points to a character"
            ),
            inline=False,
        )

        embed.add_field(
            name="⚔️ Combat",
            value=(
                "`/combat start` - Start combat in this channel\n"
                "`/combat join` - Join combat with one of your characters\n"
                "`/combat addnpc` - Add an NPC/monster to initiative\n"
                "`/combat status` - Show turn order and current turn\n"
                "`/combat next` - Advance to the next turn\n"
                "`/combat prev` - Move to the previous turn\n"
                "`/combat damage` - Apply damage to a participant\n"
                "`/combat heal` - Heal a participant\n"
                "`/combat addcondition` - Apply a condition (Poisoned, Stunned, etc.)\n"
                "`/combat removecondition` - Remove a condition from a participant\n"
                "`/combat deathsave` - Record a death saving throw (success or failure)\n"
                "`/combat remove` - Remove a participant from combat\n"
                "`/combat end` - End the current combat encounter"
            ),
            inline=False,
        )

        embed.add_field(
            name="🎒 Items & Resources",
            value=(
                "`/item add` - Add an item to a character's inventory\n"
                "`/item remove` - Remove an item from inventory\n"
                "`/item list` - View a character's inventory\n"
                "`/spellslots view` - View current and max spell slots\n"
                "`/spellslots set` - Set max slots for a spell level\n"
                "`/spellslots use` - Expend a spell slot\n"
                "`/spellslots restore` - Restore all spell slots to maximum\n"
                "`/spellslots setup` - Auto-populate slots from D&D 5e API by class & level\n"
                "`/rest short` - Take a short rest and recover HP\n"
                "`/rest long` - Take a long rest (full HP + all spell slots)\n"
                "`/gold view` - View a character's gold, silver, and copper\n"
                "`/gold add` - Add currency to a character\n"
                "`/gold spend` - Spend currency from a character"
            ),
            inline=False,
        )

        embed.add_field(
            name="🔍 D&D 5e Lookup",
            value=(
                "`/lookup monster` - Look up a monster's stat block (CR, HP, AC, abilities, actions)\n"
                "`/lookup spell` - Look up a spell (school, range, components, description)\n"
                "`/lookup item` - Look up a weapon or armor (damage, AC, properties)\n"
                "`/lookup class` - Look up a class (hit die, saves, proficiencies, spellcasting)\n"
                "`/lookup race` - Look up a race (speed, size, ability bonuses, traits)"
            ),
            inline=False,
        )

        embed.add_field(
            name="📚 Campaign Management",
            value=(
                "`/campaign save` - Save the current AI session as a named campaign\n"
                "`/campaign load` - Restore a saved campaign into this channel\n"
                "`/campaign status` - Show the active campaign's scene, NPCs, and events\n"
                "`/campaign list` - List all saved campaigns for this server\n"
                "`/campaign export` - Download the full session log as a text file\n"
                "`/campaign delete` - Delete a saved campaign"
            ),
            inline=False,
        )

        embed.add_field(
            name="🤖 AI Dungeon Master",
            value=(
                "`/dm start_campaign` - Initialize AI campaign context in this channel\n"
                "`/dm scene` - Generate the next story scene based on player action\n"
                "`/dm talk` - Talk to an NPC with AI-driven dialogue\n"
                "`/dm npcs` - List known NPCs and memory notes for this session\n"
                "`/dm delete_campaign` - Wipe the AI campaign data for this channel"
            ),
            inline=False,
        )

        embed.add_field(
            name="🛡️ Party",
            value=(
                "`/party add` - Add one of your characters to the party roster\n"
                "`/party remove` - Remove your character from the party\n"
                "`/party list` - Show all party members with HP bars\n"
                "`/party hp` - Apply healing or damage to the whole party\n"
                "`/party xp` - Award XP to every party member\n"
                "`/party clear` - Clear the entire party roster"
            ),
            inline=False,
        )

        embed.add_field(
            name="🎭 DM Tools",
            value=(
                "`/dmtool secret_roll` - Roll dice privately (only you see the result)\n"
                "`/dmtool note` - Save a private DM note to the current session\n"
                "`/dmtool notes` - View all your DM notes for this session\n"
                "`/dmtool npc` - Generate a quick random NPC\n"
                "`/dmtool encounter` - Roll a random encounter difficulty"
            ),
            inline=False,
        )

        embed.add_field(
            name="ℹ️ General",
            value=(
                "`/help` - Show this help message\n"
                "`/about` - About this bot"
            ),
            inline=False,
        )

        embed.set_footer(text="Tip: Start typing / to see command autocomplete!")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="about", description="Information about this D&D bot")
    async def about(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="About D&D Bot",
            description="A comprehensive Dungeons & Dragons 5e bot for managing campaigns, characters, and gameplay.",
            color=discord.Color.green(),
        )

        embed.add_field(
            name="Features",
            value=(
                "🎲 Dice rolling with advantage/disadvantage\n"
                "📜 Full character sheet management with ability scores and proficiencies\n"
                "⚔️ Combat tracking with conditions, death saves, and persistent encounters\n"
                "🎒 Inventory, spell slot, and currency management\n"
                "🔍 Live D&D 5e reference lookup (monsters, spells, items, classes, races)\n"
                "📈 XP tracking with automatic level-up notifications\n"
                "🤖 AI Dungeon Master with multi-provider support (OpenAI, Gemini, Claude)\n"
                "📚 Campaign save/load with full session history export\n"
                "🛡️ Party management with shared HP and XP commands\n"
                "🎭 DM tools for private rolls and NPC generation"
            ),
            inline=False,
        )

        embed.add_field(
            name="Getting Started",
            value=(
                "1. Roll stats with `/stats` then create a character\n"
                "2. Start a campaign with `/dm start_campaign`\n"
                "3. Use `/help` to explore all commands"
            ),
            inline=False,
        )

        embed.set_footer(text=f"Connected to {len(self.bot.guilds)} server(s)")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Help(bot))
