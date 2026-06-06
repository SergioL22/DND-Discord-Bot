# Discord DND Bot

A Discord bot designed to support Dungeons & Dragons 5e sessions with campaign management, player character handling, combat utilities, dice rolling, and AI-driven DM storytelling. It helps manage game state, character data, combat flows, and creative scene generation from within Discord.

## About
A Discord bot for D&D 5e with campaign management, character sheets, combat tools, and AI-driven DM features.

## Work in progress
- This project is still under active development.
- Use the `wip` branch or a draft pull request when uploading to GitHub.

## Setup
1. Copy `.env.example` to `.env`.
2. Fill in your own values.
3. Install dependencies from `requirements.txt`.
4. Run `bot.py` after configuring your environment.

## Environment variables
- `DISCORD_BOT_TOKEN`
- `COMMAND_PREFIX` (default `!`)
- `BOT_STATUS`
- `AI_PROVIDER`
- `GOOGLE_API_KEY`
- `GEMINI_MODEL`
- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `AI_MAX_TOKENS_SCENE`
- `AI_MAX_TOKENS_TALK`

## Planned improvements

### Core project improvements
- Add detailed `README.md` with setup, commands, and AI configuration
- Add `LICENSE` for open-source publishing
- Pin versions in `requirements.txt` and add missing dependencies like `python-dotenv`, `discord.py`, `google-genai`
- Add unit tests for bot logic and AI prompt handling
- Enhance `utils` with shared helpers for JSON I/O, validation, and persistence

### Bot architecture improvements
- Refactor cogs for better separation: `campaign.py` for state management, `characters.py` for creation/stats, `combat.py` for initiative/HP, `ai_dm.py` for storytelling
- Standardize on slash commands over prefix commands
- Improve error handling and user feedback in interactions
- Replace `print(...)` with proper logging
- Expand config validation for all required environment values

### Persistence / data improvements
- Replace ad-hoc JSON storage with a structured data layer (e.g., SQLite wrapper in `utils/database.py`)
- Add versioned schemas for campaign state
- Store campaign metadata, player characters, NPCs, scene summaries, and events
- Add export/import functionality for campaign logs and notes

### AI integration improvements
- Implement full `cogs/campaign.py` with commands like `/campaign create`, `/campaign status`, `/campaign summary`, `/campaign save`, `/campaign load`
- Add channel-specific AI sessions for isolated campaign contexts
- Optimize memory by summarizing past scenes instead of storing full history
- Include explicit NPC memory and world facts in session state
- Add player input prompts: `/dm next_scene`, `/dm npc_dialogue`, `/dm plot_hook`, `/dm describe_location`, `/dm generate_encounter`
- Introduce AI world builder for generating villages, factions, quests, NPC motivations, and rivalries
- Add DM control commands: `/dm revise_setting`, `/dm add_twist`, `/dm change_tone`

### AI provider/design improvements
- Abstract AI providers into a shared interface (OpenAI and Gemini classes with consistent contracts)
- Switch to async HTTP clients like `aiohttp` or `httpx` for non-blocking requests
- Implement prompt templates and a prompt manager
- Add JSON schema validation for AI outputs
- Include fallbacks for invalid AI responses
- Add content filtering for campaign text

### Nice-to-have campaign AI features
- NPC generation with stats and backstories
- Quest generation with hooks, objectives, and rewards
- Encounter balancing based on party level
- Item and magic item generation
- Character backstory creation
- Automatic scene recap summaries
- "What if" scenario simulations or suggestions
- Campaign save/resume with state checkpoints
- Adventure log generation for players

### UX improvements
- Add `/help` or auto-generated command help
- Use embed-based responses for better readability
- Implement reaction-based or button-driven flows for choices
- Add persistent party sheet commands like `/party add`, `/party hp`, `/party xp`
