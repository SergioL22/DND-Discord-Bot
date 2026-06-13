# Discord D&D Bot

A feature-complete Discord bot for running Dungeons & Dragons 5e sessions. Covers character management, combat tracking, inventory and spell slots, live D&D 5e reference lookups, AI-driven Dungeon Master storytelling, campaign save/load, and DM utilities — all through slash commands.

## Features

- **Dice Rolling** — Standard notation (`1d20`, `2d6+3`), advantage/disadvantage, ability score rolling
- **Character Sheets** — Full D&D 5e character sheets with abilities, proficiencies, HP, AC, spellcasting, inventory, and currency
- **Combat Tracking** — Initiative order, HP management, D&D 5e conditions (Poisoned, Stunned, etc.), death saving throws, persistent encounters across restarts
- **Items & Resources** — Inventory management, spell slot tracking (with auto-setup from the API), short/long rests, gold/silver/copper ledger
- **D&D 5e Lookup** — Live reference data for monsters, spells, items, classes, and races via the [D&D 5e API](https://www.dnd5eapi.co/)
- **AI Dungeon Master** — Scene generation and NPC dialogue powered by OpenAI with per-channel campaign context
- **Campaign Management** — Save, load, export, and delete campaign sessions; full history log
- **Party Management** — Shared HP adjustments, bulk XP awards, party roster with HP bars
- **DM Tools** — Private dice rolls, session notes, random NPC generation, encounter difficulty rolling

## Setup

1. Copy `.env.example` to `.env` and fill in your values.
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Run the bot:
   ```
   python bot.py
   ```

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `DISCORD_BOT_TOKEN` | Yes | Your Discord bot token |
| `COMMAND_PREFIX` | No | Prefix for legacy commands (default `!`) |
| `BOT_STATUS` | No | Bot status message (default `D&D 5e \| !help`) |
| `OPENAI_API_KEY` | Yes | OpenAI API key |
| `OPENAI_MODEL` | No | Model name (default `gpt-4o-mini`) |
| `OPENAI_BASE_URL` | No | Override base URL (default `https://api.openai.com/v1`) |
| `AI_MAX_TOKENS_SCENE` | No | Max tokens for scene generation (default `2000`) |
| `AI_MAX_TOKENS_TALK` | No | Max tokens for NPC dialogue (default `1000`) |

## Commands

### 🎲 Dice Rolling
| Command | Description |
|---|---|
| `/roll <dice>` | Roll dice using standard notation (`1d20`, `2d6+3`) |
| `/roll_adv <dice>` | Roll with advantage |
| `/roll_dis <dice>` | Roll with disadvantage |
| `/stats` | Roll 6 ability scores (4d6 drop lowest) |
| `/d20` | Quick d20 roll |

### 📜 Character Management
| Command | Description |
|---|---|
| `/createchar` | Create a new character with class/race dropdowns |
| `/viewchar` | View a full character sheet |
| `/listchars` | List all your characters |
| `/deletechar` | Delete a character |
| `/hp` | Adjust HP (+heal / -damage) |
| `/levelup` | Level up a character |
| `/addxp` | Add XP (notifies when ready to level up) |

### ⚔️ Combat
| Command | Description |
|---|---|
| `/combat start` | Start combat in this channel |
| `/combat join` | Join with one of your characters |
| `/combat addnpc` | Add an NPC/monster to initiative |
| `/combat status` | Show initiative order and current turn |
| `/combat next` | Advance to the next turn |
| `/combat prev` | Go back one turn |
| `/combat damage` | Apply damage to a participant |
| `/combat heal` | Heal a participant |
| `/combat addcondition` | Apply a D&D 5e condition |
| `/combat removecondition` | Remove a condition |
| `/combat deathsave` | Record a death saving throw |
| `/combat remove` | Remove a participant |
| `/combat end` | End the encounter |

### 🎒 Items & Resources
| Command | Description |
|---|---|
| `/item add` | Add an item to inventory |
| `/item remove` | Remove an item from inventory |
| `/item list` | View a character's inventory |
| `/spellslots view` | View current and max spell slots |
| `/spellslots set` | Set max slots for a spell level |
| `/spellslots use` | Expend a spell slot |
| `/spellslots restore` | Restore all spell slots |
| `/spellslots setup` | Auto-populate slots from the D&D 5e API |
| `/rest short` | Short rest — recover HP |
| `/rest long` | Long rest — full HP and all spell slots |
| `/gold view` | View gold, silver, and copper |
| `/gold add` | Add currency |
| `/gold spend` | Spend currency |

### 🔍 D&D 5e Lookup
| Command | Description |
|---|---|
| `/lookup monster` | Stat block: CR, HP, AC, abilities, actions |
| `/lookup spell` | School, range, components, description |
| `/lookup item` | Weapon damage, armor AC, properties |
| `/lookup class` | Hit die, saves, proficiencies, spellcasting |
| `/lookup race` | Speed, size, ability bonuses, traits |

### 📚 Campaign Management
| Command | Description |
|---|---|
| `/campaign save` | Save the current AI session as a named campaign |
| `/campaign load` | Restore a saved campaign |
| `/campaign status` | Show active campaign scene, NPCs, and events |
| `/campaign list` | List all saved campaigns for this server |
| `/campaign export` | Download the full session log as a text file |
| `/campaign delete` | Delete a saved campaign |

### 🤖 AI Dungeon Master
| Command | Description |
|---|---|
| `/dm start_campaign` | Initialize AI campaign context in this channel |
| `/dm scene` | Generate the next story scene |
| `/dm talk` | Talk to an NPC with AI-driven dialogue |
| `/dm npcs` | List known NPCs and memory notes |
| `/dm delete_campaign` | Wipe AI campaign data for this channel |

### 🛡️ Party
| Command | Description |
|---|---|
| `/party add` | Add your character to the party roster |
| `/party remove` | Remove your character from the party |
| `/party list` | Show all party members with HP bars |
| `/party hp` | Apply healing or damage to the whole party |
| `/party xp` | Award XP to every party member |
| `/party clear` | Clear the entire party roster |

### 🎭 DM Tools
| Command | Description |
|---|---|
| `/dmtool secret_roll` | Roll dice privately |
| `/dmtool note` | Save a private DM note |
| `/dmtool notes` | View all DM notes for this session |
| `/dmtool npc` | Generate a random NPC |
| `/dmtool encounter` | Roll a random encounter difficulty |

## Project Structure

```
bot.py                  — Entry point, loads all cogs
config.py               — Environment variable config
cogs/
  character.py          — Character creation and management
  combat.py             — Combat tracking and initiative
  resources.py          — Items, spell slots, rests, currency
  lookup.py             — D&D 5e API reference lookups
  dice.py               — Dice rolling commands
  ai_dm.py              — AI Dungeon Master
  campaign.py           — Campaign save/load
  party.py              — Party management
  dm_tools.py           — DM utility commands
  help.py               — Help and about commands
utils/
  character_sheet.py    — CharacterSheet dataclass
  database.py           — SQLite database interface
  db.py                 — Low-level DB helpers and schema
  dice_roller.py        — Dice rolling logic
  dnd5e_api.py          — Async D&D 5e API client with caching
```
