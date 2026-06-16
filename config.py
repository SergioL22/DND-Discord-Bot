import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
    COMMAND_PREFIX = os.getenv("COMMAND_PREFIX", "!")

    BOT_STATUS = os.getenv("BOT_STATUS", "D&D 5e | !help")

    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    AI_MAX_TOKENS_SCENE = int(os.getenv("AI_MAX_TOKENS_SCENE", "2000"))
    AI_MAX_TOKENS_TALK = int(os.getenv("AI_MAX_TOKENS_TALK", "1000"))

    COLOR_PRIMARY = 0x7289DA  # Discord Blurple
    COLOR_SUCCESS = 0x43B581  # Green
    COLOR_ERROR = 0xF04747    # Red
    COLOR_WARNING = 0xFAA61A  # Yellow

    MAX_DICE = 100
    MAX_SIDES = 1000

    @staticmethod
    def validate():
        if not Config.BOT_TOKEN:
            raise ValueError(
                "DISCORD_BOT_TOKEN is not set. Create a .env file and add DISCORD_BOT_TOKEN=your_token."
            )
        if not Config.OPENAI_API_KEY:
            raise ValueError(
                "OPENAI_API_KEY is not set. Add OPENAI_API_KEY=your_key to your .env file."
            )
        return True