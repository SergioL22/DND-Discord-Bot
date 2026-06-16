# Discord D&D Bot

A feature-complete Discord bot for running Dungeons & Dragons 5e sessions. Covers character management, combat tracking, inventory and spell slots, skill checks and saving throws, spell tracking with live API lookup, inspiration, live D&D 5e reference lookups, AI-driven Dungeon Master storytelling, campaign save/load, and DM utilities — all through slash commands.

## Features

- **Dice Rolling** — Standard notation (`1d20`, `2d6+3`), advantage/disadvantage, ability score rolling
- **Character Sheets** — Full D&D 5e character sheets with abilities, proficiencies, HP, AC, spellcasting, inventory, and currency
- **Skill Checks & Saving Throws** — Roll any skill check or saving throw with auto-calculated proficiency bonus and optional DC pass/fail
- **Spell Tracking** — Learn, prepare, and cast spells; auto-expends slots, supports upcasting, and pulls full spell details from the D&D 5e API
- **Inspiration** — Award and spend D&D inspiration; spending it announces advantage to the table
- **Combat Tracking** — Initiative order, HP management, D&D 5e conditions with mechanical reminders on apply and on each turn, death saving throws, persistent encounters across restarts
- **Items & Resources** — Inventory management, spell slot tracking (with auto-setup from the API), short/long rests, gold/silver/copper ledger
- **D&D 5e Lookup** — Live reference data for monsters, spells, items, classes, and races via the [D&D 5e API](https://www.dnd5eapi.co/)
- **AI Dungeon Master** — Scene generation, NPC dialogue, and AI-generated combat encounters powered by OpenAI with per-channel campaign context and party-aware narration
- **Campaign Management** — Save, load, export, and delete campaign sessions; full history log
- **Party Management** — Shared HP adjustments, bulk XP awards, party roster with HP bars
- **DM Tools** — Private dice rolls, session notes, random NPC generation, encounter difficulty rolling

## Setup

1. Copy `.env.example` to `.env` and fill in `DISCORD_BOT_TOKEN` and `OPENAI_API_KEY` (both required — the bot validates them at startup and exits with a clear message if either is missing).
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
| `/d20` | Quick d20 roll |

### 📜 Character Management
| Command | Description |
|---|---|
| `/stats` | Roll ability scores (4d6 drop lowest) — click the button to open guided character creation |
| `/viewchar` | View a full character sheet |
| `/listchars` | List all your characters |
| `/deletechar` | Delete a character |
| `/hp` | Adjust HP (+heal / -damage) |
| `/levelup` | Level up a character |
| `/addxp` | Add XP (notifies when ready to level up) |

### 🎯 Skill Checks & Saving Throws
| Command | Description |
|---|---|
| `/check skill` | Roll a skill check with proficiency bonus auto-applied |
| `/check save` | Roll a saving throw with proficiency bonus auto-applied |
| `/check ability` | Roll a raw ability check (no skill proficiency) |

All three commands accept an optional `dc` argument — if set, the result shows ✅ Pass or ❌ Fail.

### 📖 Spells
| Command | Description |
|---|---|
| `/spell add` | Add a spell to your character's spells known (autocompletes from the D&D 5e API) |
| `/spell remove` | Remove a spell from spells known |
| `/spell prepare` | Mark a known spell as prepared |
| `/spell unprepare` | Remove a spell from your prepared list |
| `/spell list` | View all spells known (✨ = prepared, 📖 = known only) |
| `/spell cast` | Cast a spell — shows full API details and auto-expends a spell slot; supports upcasting via `slot_level` |

### ⭐ Inspiration
| Command | Description |
|---|---|
| `/inspiration give` | Award inspiration to a character (DM use) |
| `/inspiration use` | Spend inspiration to declare advantage on your next roll |
| `/inspiration status` | Check whether a character currently has inspiration |

### ⚔️ Combat
| Command | Description |
|---|---|
| `/combat start` | Start combat in this channel |
| `/combat join` | Join with one of your characters |
| `/combat addnpc` | Add an NPC/monster to initiative |
| `/combat status` | Show initiative order and current turn |
| `/combat next` | Advance to the next turn (shows mechanical reminders for any active conditions) |
| `/combat prev` | Go back one turn |
| `/combat damage` | Apply damage to a participant |
| `/combat heal` | Heal a participant |
| `/combat addcondition` | Apply a D&D 5e condition (shows its mechanical effects) |
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
| `/dm scene` | Generate the next story scene based on a player action |
| `/dm encounter` | Generate a combat encounter and auto-populate the combat tracker with AI-created monsters |
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
  checks.py             — Skill checks and saving throws
  spells.py             — Spell management and casting
  inspiration.py        — Inspiration tracking
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
  database.py           — Character persistence (high-level API)
  schema.py             — SQLite connection, table schema, and all low-level DB helpers
  dice_roller.py        — Dice rolling logic
  dnd5e_api.py          — Async D&D 5e API client with caching
```
