import logging
import os
import sys

import discord
from discord.ext import commands

from config import Config

logger = logging.getLogger(__name__)


class DNDBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True

        super().__init__(
            command_prefix=Config.COMMAND_PREFIX,
            intents=intents,
            description="A Dungeons and Dragons 5e bot for managing campaigns and gameplay",
        )

    async def setup_hook(self):
        logger.info("Setting up bot ...")
        await self.load_cogs()
        synced = await self.tree.sync()
        logger.info("Synced %d global command(s) to Discord.", len(synced))

        test_guild_id = os.getenv("TEST_GUILD_ID")
        if test_guild_id:
            try:
                guild = discord.Object(id=int(test_guild_id))
                self.tree.copy_global_to(guild=guild)
                guild_synced = await self.tree.sync(guild=guild)
                logger.info(
                    "Synced %d guild command(s) to TEST_GUILD_ID=%s.",
                    len(guild_synced),
                    test_guild_id,
                )
            except ValueError:
                logger.warning("Invalid TEST_GUILD_ID in environment. Must be a numeric guild ID.")

    async def load_cogs(self):
        cogs_dir = "cogs"

        if not os.path.exists(cogs_dir):
            logger.warning("Cogs directory '%s' does not exist.", cogs_dir)
            return

        for filename in os.listdir(cogs_dir):
            if filename.endswith(".py") and not filename.startswith("_"):
                cog_name = f"cogs.{filename[:-3]}"
                try:
                    await self.load_extension(cog_name)
                    logger.info("Loaded cog: %s", cog_name)
                except Exception as e:
                    logger.error("Failed to load cog %s: %s", cog_name, e)

    async def on_ready(self):
        logger.info("Bot is ready! Logged in as %s, connected to %d server(s).", self.user.name, len(self.guilds))

        await self.change_presence(activity=discord.Game(name=Config.BOT_STATUS))

    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            await ctx.send("Command not found. Use '!help' to see the list of available commands.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"Missing argument: {error.param.name}")
        else:
            logger.error("Command error: %s", error)
            await ctx.send(f"An error occurred: {error}")


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    try:
        Config.validate()

        bot = DNDBot()

        logger.info("Starting Discord DND Bot...")
        bot.run(Config.BOT_TOKEN)

    except ValueError as e:
        logger.critical("Configuration error: %s", e)
        sys.exit(1)
    except Exception as e:
        logger.critical("Unexpected error: %s", e)
        sys.exit(1)
        
if __name__ == "__main__":
    main()