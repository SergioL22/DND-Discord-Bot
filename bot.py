import discord
from discord.ext import commands 
import os
import sys
from config import Config


class DNDBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True 
        
        super().__init__(
            command_prefix = Config.COMMAND_PREFIX,
            intents = intents,
            description = "A Dungeons and Dragons 5e bot for managing campaigns and gameplay"
        )
        
    async def setup_hook(self):
        print("Setting up bot ...")
        await self.load_cogs()
        synced = await self.tree.sync()
        print(f'Synced {len(synced)} global command(s) to Discord.')

        test_guild_id = os.getenv("TEST_GUILD_ID")
        if test_guild_id:
            try:
                guild = discord.Object(id=int(test_guild_id))
                self.tree.copy_global_to(guild=guild)
                guild_synced = await self.tree.sync(guild=guild)
                print(f'Synced {len(guild_synced)} guild command(s) to TEST_GUILD_ID={test_guild_id}.')
            except ValueError:
                print("Invalid TEST_GUILD_ID in environment. Must be a numeric guild ID.")
        
    async def load_cogs(self):
        cogs_dir = 'cogs'
        
        if not os.path.exists(cogs_dir):
            print(f"Warning: {cogs_dir} directory does not exist.")
            return
        
        for filename in os.listdir(cogs_dir):
            if filename.endswith('.py') and not filename.startswith('_'):
                cog_name = f'cogs.{filename[:-3]}'
                try:
                    await self.load_extension(cog_name)
                    print(f'Loaded cog: {cog_name}')
                except Exception as e:
                    print(f'Failed to load cog: {cog_name}. Error: {e}')
    async def on_ready(self):
        print(f'\n{"="*50}')
        print(f'Bot is ready!')                
        print(f'Logged in as: {self.user.name}')
        print(f'Connected to {len(self.guilds)} server(s)')
        print(f'{"="*50}\n')
        
        #Bot status
        await self.change_presence(
            activity = discord.Game(name = Config.BOT_STATUS)
        )
        
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            await ctx.send(f"Command not found. Use '!help' to see the list of available commands.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"Missing argument: {error.param.name}")
        else:
            print(f"An error occurred: {error}")
            await ctx.send(f'An error occurred: {error}')
            
def main():
    try:
        
        Config.validate()
        
        bot = DNDBot()
        
        print("Starting Discord DND Bot...")
        bot.run(Config.BOT_TOKEN)
        
    except ValueError as e:
        print(f"Configuration Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f'An unexpected error occurred: {e}')
        sys.exit(1)
        
if __name__ == "__main__":
    main()