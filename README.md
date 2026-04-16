# Discord DND Bot

> Work in progress. This repository is not production-ready yet.

## About
A Discord bot for D&D 5e with campaign management, character sheets, combat tools, and AI-driven DM features.

## Work in progress
- This project is still under active development.
- Use the `wip` branch or a draft pull request when uploading to GitHub.

## Security
- Do not commit `.env` or any secret keys.
- Keep your Discord bot token, OpenAI key, and Google API key private.
- If you have exposed any token already, revoke it immediately.

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
