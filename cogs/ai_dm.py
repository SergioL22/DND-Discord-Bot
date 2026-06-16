import asyncio
import json
import random
import time
from typing import Any, Dict, List, Optional
from urllib import error, request

import discord
from discord import app_commands
from discord.ext import commands

from config import Config
from utils import schema as db
from utils.database import get_database


class AIDM(commands.Cog):
    """AI-powered storytelling and NPC dialogue tools."""

    dm_group = app_commands.Group(name="dm", description="AI Dungeon Master tools")

    @staticmethod
    def _to_int(value: Any, default: int) -> int:
        try:
            parsed = int(value)
            return parsed if parsed > 0 else default
        except (TypeError, ValueError):
            return default

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.openai_api_key = Config.OPENAI_API_KEY
        self.openai_model = Config.OPENAI_MODEL
        self.openai_base_url = Config.OPENAI_BASE_URL.rstrip("/")
        self.ai_max_tokens_scene = self._to_int(Config.AI_MAX_TOKENS_SCENE, 2000)
        self.ai_max_tokens_talk = self._to_int(Config.AI_MAX_TOKENS_TALK, 1000)

    def _get_or_create_session(self, channel_id: int) -> Dict[str, Any]:
        session = db.session_get(channel_id)
        if session is None:
            session = {
                "campaign": {"title": "", "tone": "", "premise": ""},
                "scene_summary": "",
                "known_npcs": [],
                "recent_events": [],
                "npc_memories": {},
                "history": [],
                "updated_at": int(time.time()),
            }
            db.session_save(channel_id, session)
        return session

    def _update_session(self, channel_id: int, session: Dict[str, Any]) -> None:
        db.session_save(channel_id, session)

    def _delete_session(self, channel_id: int) -> bool:
        return db.session_delete(channel_id)

    def _ensure_provider(self) -> str:
        if not self.openai_api_key:
            return (
                "❌ Missing `OPENAI_API_KEY` in your `.env`. "
                "Add it, restart the bot, and try again."
            )
        return ""

    def _trim_history(self, history: List[Dict[str, str]], limit: int = 10) -> List[Dict[str, str]]:
        return history[-limit:]

    @staticmethod
    def _chunk_text(text: str, limit: int = 4000) -> List[str]:
        """Split text into Discord-safe chunks, breaking at paragraph or sentence boundaries."""
        if len(text) <= limit:
            return [text]
        chunks: List[str] = []
        while text:
            if len(text) <= limit:
                chunks.append(text)
                break
            split_at = text.rfind("\n\n", 0, limit)
            if split_at == -1:
                split_at = text.rfind("\n", 0, limit)
            if split_at == -1:
                split_at = text.rfind(". ", 0, limit)
            if split_at == -1:
                split_at = limit
            chunks.append(text[:split_at].rstrip())
            text = text[split_at:].lstrip()
        return chunks

    def _format_ai_error(self, err: Exception) -> str:
        raw = str(err)
        lowered = raw.lower()

        if "insufficient_quota" in lowered or "quota" in lowered:
            return "❌ OpenAI quota exceeded. Check your billing/usage limits in your OpenAI project."

        if "invalid_api_key" in lowered:
            return "❌ Invalid `OPENAI_API_KEY`. Check your `.env`, then restart the bot."

        if "429" in lowered or "rate limit" in lowered:
            return "❌ OpenAI rate limit hit. Please wait a moment and try again."

        return f"❌ AI error: {raw}"

    def _call_openai(self, system_prompt: str, user_prompt: str, max_tokens: int) -> str:
        payload = {
            "model": self.openai_model,
            "temperature": 0.8,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }

        req = request.Request(
            f"{self.openai_base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Bearer {self.openai_api_key}",
                "Content-Type": "application/json",
            },
        )

        try:
            with request.urlopen(req, timeout=60) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
        except error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenAI HTTP {e.code}: {err_body}") from e
        except Exception as e:
            raise RuntimeError(f"OpenAI request failed: {e}") from e

        try:
            return raw["choices"][0]["message"]["content"]
        except Exception as e:
            raise RuntimeError(f"Invalid OpenAI response: {e}") from e

    async def _generate_json(self, system_prompt: str, user_prompt: str, max_tokens: int) -> Dict[str, Any]:
        try:
            raw_text = await asyncio.to_thread(
                self._call_openai, system_prompt, user_prompt, max_tokens,
            )
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(f"AI request failed: {e}") from e

        try:
            return json.loads(raw_text.strip())
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid AI JSON response: {e}\nRaw: {raw_text[:500]}") from e

    @dm_group.command(name="start_campaign", description="Initialize AI DM campaign context for this channel")
    @app_commands.describe(
        title="Campaign title",
        premise="Short setup or hook for the campaign",
        tone="Tone like heroic, dark, mystery, political, horror",
    )
    async def start_campaign(self, interaction: discord.Interaction, title: str, premise: str, tone: str):
        if interaction.channel_id is None:
            await interaction.response.send_message(
                "❌ This command must be used in a server channel.", ephemeral=True
            )
            return

        key_error = self._ensure_provider()
        if key_error:
            await interaction.response.send_message(key_error, ephemeral=True)
            return

        await interaction.response.defer()

        session = self._get_or_create_session(interaction.channel_id)
        session["campaign"] = {
            "title": title.strip(),
            "premise": premise.strip(),
            "tone": tone.strip(),
        }
        session["scene_summary"] = "The campaign is about to begin."
        session["recent_events"] = [f"Campaign started: {title.strip()}"]
        session["history"] = []

        system_prompt = (
            "You are a D&D 5e Dungeon Master assistant. "
            "Respond with STRICT JSON only. No markdown, no prose outside JSON."
        )
        user_prompt = (
            f"Campaign title: {title.strip()}\n"
            f"Campaign premise: {premise.strip()}\n"
            f"Campaign tone: {tone.strip()}\n\n"
            "Generate a strong opening scene that immediately starts play.\n"
            "Return JSON with this exact schema:\n"
            "{"
            "\"opening_narration\": string,"
            "\"scene_summary\": string,"
            "\"new_npcs\": [string],"
            "\"hooks\": [string],"
            "\"opening_dialogue\": string,"
            "\"dm_question\": string"
            "}"
        )

        try:
            result = await self._generate_json(system_prompt, user_prompt, self.ai_max_tokens_scene)
        except RuntimeError as e:
            await interaction.followup.send(self._format_ai_error(e), ephemeral=True)
            return

        opening_narration = str(result.get("opening_narration", "A new adventure begins..."))
        scene_summary = str(result.get("scene_summary", session.get("scene_summary", "")))
        new_npcs = [str(n) for n in result.get("new_npcs", []) if str(n).strip()][:10]
        hooks = [str(h) for h in result.get("hooks", []) if str(h).strip()][:5]
        opening_dialogue = str(result.get("opening_dialogue", ""))
        dm_question = str(result.get("dm_question", "What does your party do?"))

        for npc in new_npcs:
            if npc not in session["known_npcs"]:
                session["known_npcs"].append(npc)

        session["scene_summary"] = scene_summary
        session["recent_events"].append("Opening scene generated by AI DM")
        session["recent_events"] = session["recent_events"][-12:]
        session["history"].append({"role": "dm", "content": opening_narration})
        if opening_dialogue:
            session["history"].append({"role": "npc", "content": opening_dialogue})
        session["history"] = self._trim_history(session["history"])
        self._update_session(interaction.channel_id, session)

        narration_chunks = self._chunk_text(opening_narration, 1800)

        await interaction.followup.send(content=f"✅ **{title.strip()}** has begun!")
        await interaction.followup.send(
            content=f"# 🎬 {title.strip()} — Opening Scene\n\n{narration_chunks[0]}"
        )
        for chunk in narration_chunks[1:]:
            await interaction.followup.send(content=chunk)

        if opening_dialogue:
            await interaction.followup.send(content=f"> 💬 *{opening_dialogue}*")

        details_embed = discord.Embed(title="📋 Campaign Details", color=discord.Color.blurple())
        details_embed.add_field(name="📖 Premise", value=premise.strip()[:1024], inline=False)
        if new_npcs:
            details_embed.add_field(
                name="👥 Introduced NPCs",
                value="\n".join(f"• {n}" for n in new_npcs)[:1024],
                inline=False,
            )
        if hooks:
            details_embed.add_field(
                name="🪝 Adventure Hooks",
                value="\n".join(f"• {h}" for h in hooks)[:1024],
                inline=False,
            )
        details_embed.set_footer(text=f"Tone: {tone.strip()}")
        await interaction.followup.send(embed=details_embed)

        question_embed = discord.Embed(
            description=f"## ❓ {dm_question}",
            color=discord.Color.gold(),
        )
        question_embed.set_footer(text="Use /dm scene <your action> to respond")
        await interaction.followup.send(embed=question_embed)

        if interaction.guild_id:
            party_members = db.party_list(interaction.guild_id)
            if not party_members:
                checklist_embed = discord.Embed(
                    title="📋 Session Zero — Before You Begin",
                    description=(
                        "No characters are registered for this campaign yet. "
                        "The AI DM uses your character's name, class, race, and HP to personalise "
                        "the story and scale encounters. Each player should complete these two steps:"
                    ),
                    color=discord.Color.orange(),
                )
                checklist_embed.add_field(
                    name="Step 1 — Create your character",
                    value="Use `/stats` and click **Create Character** to roll and register your character.",
                    inline=False,
                )
                checklist_embed.add_field(
                    name="Step 2 — Join the party",
                    value="```/party add <your character name>```",
                    inline=False,
                )
                checklist_embed.set_footer(
                    text="You can still play without characters, but the AI will have no party context."
                )
                await interaction.followup.send(embed=checklist_embed)

    @dm_group.command(name="delete_campaign", description="Delete AI DM campaign data for this channel")
    @app_commands.describe(confirm="Set to true to confirm deletion")
    async def delete_campaign(self, interaction: discord.Interaction, confirm: bool):
        if interaction.channel_id is None:
            await interaction.response.send_message(
                "❌ This command must be used in a server channel.", ephemeral=True
            )
            return

        if not confirm:
            await interaction.response.send_message(
                "⚠️ Deletion canceled. Re-run with `confirm: true` to delete this channel's campaign.",
                ephemeral=True,
            )
            return

        deleted = self._delete_session(interaction.channel_id)
        if not deleted:
            await interaction.response.send_message(
                "ℹ️ No AI campaign data exists for this channel.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            "🗑️ AI campaign data deleted for this channel. You can start fresh with `/dm start_campaign`.",
            ephemeral=True,
        )

    @dm_group.command(name="scene", description="Ask AI DM to narrate the next scene")
    @app_commands.describe(player_action="What the party does next")
    @app_commands.checks.cooldown(1, 30.0)
    async def scene(self, interaction: discord.Interaction, player_action: str):
        if interaction.channel_id is None:
            await interaction.response.send_message(
                "❌ This command must be used in a server channel.", ephemeral=True
            )
            return

        key_error = self._ensure_provider()
        if key_error:
            await interaction.response.send_message(key_error, ephemeral=True)
            return

        await interaction.response.defer()

        session = self._get_or_create_session(interaction.channel_id)
        campaign = session.get("campaign", {})

        party_context = ""
        if interaction.guild_id:
            char_db = get_database()
            members = db.party_list(interaction.guild_id)
            if members:
                party_lines = []
                for m in members:
                    char = char_db.get_character(m["owner_id"], m["name_key"])
                    if char:
                        party_lines.append(
                            f"  - {char.name} (Lv{char.level} {char.race} {char.character_class},"
                            f" HP {char.current_hp}/{char.max_hp})"
                        )
                if party_lines:
                    party_context = "Current party:\n" + "\n".join(party_lines) + "\n"

        system_prompt = (
            "You are a D&D 5e Dungeon Master assistant. "
            "Respond with STRICT JSON only. No markdown, no prose outside JSON."
        )
        user_prompt = (
            f"Campaign title: {campaign.get('title', '')}\n"
            f"Campaign premise: {campaign.get('premise', '')}\n"
            f"Campaign tone: {campaign.get('tone', '')}\n"
            f"Current scene summary: {session.get('scene_summary', '')}\n"
            f"Recent events: {session.get('recent_events', [])}\n"
            f"Known NPCs: {session.get('known_npcs', [])}\n"
            f"{party_context}"
            f"Player action: {player_action}\n\n"
            "Return JSON with this exact schema:\n"
            "{"
            "\"narration\": string,"
            "\"scene_summary\": string,"
            "\"new_npcs\": [string],"
            "\"hooks\": [string],"
            "\"combat_hint\": string,"
            "\"dm_question\": string"
            "}"
        )

        try:
            result = await self._generate_json(system_prompt, user_prompt, self.ai_max_tokens_scene)
        except RuntimeError as e:
            await interaction.followup.send(self._format_ai_error(e), ephemeral=True)
            return

        narration = str(result.get("narration", "The world waits in silence..."))
        scene_summary = str(result.get("scene_summary", session.get("scene_summary", "")))
        new_npcs = [str(n) for n in result.get("new_npcs", [])][:10]
        hooks = [str(h) for h in result.get("hooks", [])][:5]
        combat_hint = str(result.get("combat_hint", ""))
        dm_question = str(result.get("dm_question", "What does your party do next?"))

        for npc in new_npcs:
            if npc and npc not in session["known_npcs"]:
                session["known_npcs"].append(npc)
        session["scene_summary"] = scene_summary
        session["recent_events"].append(f"Players acted: {player_action}")
        session["recent_events"] = session["recent_events"][-12:]
        session["history"].append({"role": "player", "content": player_action})
        session["history"].append({"role": "dm", "content": narration})
        session["history"] = self._trim_history(session["history"])
        self._update_session(interaction.channel_id, session)

        narration_chunks = self._chunk_text(narration, 1800)

        await interaction.followup.send(
            content=f"## 📖 Scene Update\n\n{narration_chunks[0]}"
        )
        for chunk in narration_chunks[1:]:
            await interaction.followup.send(content=chunk)

        if new_npcs or hooks or combat_hint:
            details_embed = discord.Embed(color=discord.Color.blurple())
            if new_npcs:
                details_embed.add_field(
                    name="👥 New NPCs",
                    value=", ".join(new_npcs)[:1024],
                    inline=False,
                )
            if hooks:
                details_embed.add_field(
                    name="🪝 Story Hooks",
                    value="\n".join(f"• {h}" for h in hooks)[:1024],
                    inline=False,
                )
            if combat_hint:
                details_embed.add_field(name="⚔️ Combat Tension", value=combat_hint[:1024], inline=False)
            await interaction.followup.send(embed=details_embed)

        question_embed = discord.Embed(
            description=f"## ❓ {dm_question}",
            color=discord.Color.gold(),
        )
        question_embed.set_footer(text="Use /dm scene <your action> to respond")
        await interaction.followup.send(embed=question_embed)

    @dm_group.command(name="talk", description="Talk to an NPC with AI-driven dialogue")
    @app_commands.describe(npc_name="NPC you are speaking to", message="What your character says")
    @app_commands.checks.cooldown(1, 20.0)
    async def talk_to_npc(self, interaction: discord.Interaction, npc_name: str, message: str):
        if interaction.channel_id is None:
            await interaction.response.send_message(
                "❌ This command must be used in a server channel.", ephemeral=True
            )
            return

        key_error = self._ensure_provider()
        if key_error:
            await interaction.response.send_message(key_error, ephemeral=True)
            return

        await interaction.response.defer()

        session = self._get_or_create_session(interaction.channel_id)
        campaign = session.get("campaign", {})

        if npc_name not in session["known_npcs"]:
            session["known_npcs"].append(npc_name)

        npc_memory = session.get("npc_memories", {}).get(npc_name, "")

        system_prompt = (
            "You are roleplaying one D&D NPC. "
            "Respond with STRICT JSON only. Keep speech in-character and concise."
        )
        user_prompt = (
            f"Campaign title: {campaign.get('title', '')}\n"
            f"Campaign tone: {campaign.get('tone', '')}\n"
            f"Scene summary: {session.get('scene_summary', '')}\n"
            f"Recent events: {session.get('recent_events', [])}\n"
            f"NPC name: {npc_name}\n"
            f"NPC memory so far: {npc_memory}\n"
            f"Player says: {message}\n\n"
            "Return JSON with this exact schema:\n"
            "{"
            "\"npc_dialogue\": string,"
            "\"narration\": string,"
            "\"updated_scene_summary\": string,"
            "\"npc_memory_update\": string"
            "}"
        )

        try:
            result = await self._generate_json(system_prompt, user_prompt, self.ai_max_tokens_talk)
        except RuntimeError as e:
            await interaction.followup.send(self._format_ai_error(e), ephemeral=True)
            return

        npc_dialogue = str(result.get("npc_dialogue", "..."))
        narration = str(result.get("narration", ""))
        updated_scene_summary = str(result.get("updated_scene_summary", session.get("scene_summary", "")))
        npc_memory_update = str(result.get("npc_memory_update", ""))

        session["scene_summary"] = updated_scene_summary
        session["recent_events"].append(f"Talked with {npc_name}: {message}")
        session["recent_events"] = session["recent_events"][-12:]

        if "npc_memories" not in session or not isinstance(session["npc_memories"], dict):
            session["npc_memories"] = {}

        old_memory = str(session["npc_memories"].get(npc_name, "")).strip()
        merged_memory = " ".join(part for part in [old_memory, npc_memory_update] if part).strip()
        session["npc_memories"][npc_name] = merged_memory[:800]

        session["history"].append({"role": "player", "content": f"To {npc_name}: {message}"})
        session["history"].append({"role": "npc", "content": f"{npc_name}: {npc_dialogue}"})
        session["history"] = self._trim_history(session["history"])
        self._update_session(interaction.channel_id, session)

        dialogue_chunks = self._chunk_text(npc_dialogue)

        embed = discord.Embed(
            title=f"🗣️ {npc_name}",
            description=dialogue_chunks[0],
            color=discord.Color.green(),
        )
        if narration:
            embed.add_field(name="Scene", value=narration[:1024], inline=False)

        await interaction.followup.send(embed=embed)
        for chunk in dialogue_chunks[1:]:
            await interaction.followup.send(content=chunk)

    @dm_group.command(name="encounter", description="Generate a combat encounter and start initiative tracking")
    @app_commands.checks.cooldown(1, 60.0)
    @app_commands.describe(
        description="What kind of encounter? e.g. 'bandits ambush the party at a crossroads'",
        difficulty="How tough the encounter should be",
    )
    @app_commands.choices(difficulty=[
        app_commands.Choice(name="Easy", value="easy"),
        app_commands.Choice(name="Medium", value="medium"),
        app_commands.Choice(name="Hard", value="hard"),
        app_commands.Choice(name="Deadly", value="deadly"),
    ])
    async def generate_encounter(
        self,
        interaction: discord.Interaction,
        description: str,
        difficulty: Optional[str] = "medium",
    ):
        if interaction.channel_id is None:
            await interaction.response.send_message(
                "❌ This command must be used in a server channel.", ephemeral=True
            )
            return

        key_error = self._ensure_provider()
        if key_error:
            await interaction.response.send_message(key_error, ephemeral=True)
            return

        existing = db.encounter_get(interaction.channel_id)
        if existing and existing.get("participants"):
            await interaction.response.send_message(
                "⚔️ There is already an active combat encounter in this channel. "
                "Use `/combat end` first, then try again.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        session = self._get_or_create_session(interaction.channel_id)
        campaign = session.get("campaign", {})

        party_context = ""
        if interaction.guild_id:
            char_db = get_database()
            members = db.party_list(interaction.guild_id)
            if members:
                party_lines = []
                for m in members:
                    char = char_db.get_character(m["owner_id"], m["name_key"])
                    if char:
                        party_lines.append(
                            f"  - {char.name} (Lv{char.level} {char.race} {char.character_class},"
                            f" HP {char.current_hp}/{char.max_hp})"
                        )
                if party_lines:
                    party_context = "Party:\n" + "\n".join(party_lines) + "\n"

        difficulty = difficulty or "medium"
        system_prompt = (
            "You are a D&D 5e Dungeon Master. "
            "Respond with STRICT JSON only. No markdown, no prose outside JSON."
        )
        user_prompt = (
            f"Campaign: {campaign.get('title', 'Unknown')}\n"
            f"Tone: {campaign.get('tone', 'heroic')}\n"
            f"Current scene: {session.get('scene_summary', '')}\n"
            f"{party_context}"
            f"Encounter difficulty: {difficulty}\n"
            f"Encounter description: {description}\n\n"
            "Generate a combat encounter. Use real D&D 5e monsters with accurate HP and initiative modifiers.\n"
            "Difficulty guidelines:\n"
            "  easy: 1-2 weak monsters (CR 1/4 to 1/2)\n"
            "  medium: 2-4 moderate monsters\n"
            "  hard: 3-5 strong monsters\n"
            "  deadly: 4-6+ powerful monsters or one boss\n"
            "If multiple of the same monster appear, suffix names with A, B, C (e.g. 'Bandit A').\n\n"
            "Return JSON with this EXACT schema:\n"
            "{"
            '"encounter_narration": "2-3 sentence dramatic description of the encounter starting",'
            '"scene_summary": "updated scene summary reflecting combat has begun",'
            '"monsters": ['
            '  {"name": "string", "hp": integer, "initiative_mod": integer}'
            "],"
            '"dm_tip": "one short tactical note about this encounter"'
            "}"
        )

        try:
            result = await self._generate_json(system_prompt, user_prompt, 1200)
        except RuntimeError as e:
            await interaction.followup.send(self._format_ai_error(e), ephemeral=True)
            return

        encounter_narration = str(result.get("encounter_narration", "Combat begins!"))
        scene_summary = str(result.get("scene_summary", session.get("scene_summary", "")))
        monsters_raw = result.get("monsters", [])
        dm_tip = str(result.get("dm_tip", ""))

        if not monsters_raw or not isinstance(monsters_raw, list):
            await interaction.followup.send(
                "❌ AI did not generate any monsters. Try rephrasing the encounter description.",
                ephemeral=True,
            )
            return

        participants = []
        for m in monsters_raw[:12]:
            name = str(m.get("name", "Unknown")).strip()
            if not name:
                continue
            try:
                hp = max(1, int(m.get("hp", 5)))
            except (TypeError, ValueError):
                hp = 5
            try:
                initiative_mod = max(-5, min(10, int(m.get("initiative_mod", 0))))
            except (TypeError, ValueError):
                initiative_mod = 0
            roll = random.randint(1, 20)
            participants.append({
                "owner_id": "",
                "character_name": name,
                "initiative": roll + initiative_mod,
                "initiative_mod": initiative_mod,
                "is_npc": True,
                "npc_hp": hp,
                "npc_max_hp": hp,
                "conditions": [],
                "death_saves_successes": 0,
                "death_saves_failures": 0,
                "_roll": roll,
            })

        if not participants:
            await interaction.followup.send(
                "❌ No valid monsters were generated. Try rephrasing the encounter description.",
                ephemeral=True,
            )
            return

        participants.sort(key=lambda p: (-p["initiative"], -p["initiative_mod"], p["character_name"].lower()))

        encounter_data = {
            "participants": [{k: v for k, v in p.items() if k != "_roll"} for p in participants],
            "current_index": 0,
            "round_number": 1,
        }
        db.encounter_save(interaction.channel_id, encounter_data)

        combat_cog = self.bot.cogs.get("Combat")
        if combat_cog is not None and hasattr(combat_cog, "active_encounters"):
            try:
                from cogs.combat import EncounterState
                combat_cog.active_encounters[interaction.channel_id] = EncounterState.from_dict(encounter_data)
            except Exception:
                pass

        session["scene_summary"] = scene_summary
        session["recent_events"].append(f"Combat started: {description}")
        session["recent_events"] = session["recent_events"][-12:]
        session["history"].append({"role": "dm", "content": encounter_narration})
        session["history"] = self._trim_history(session["history"])
        self._update_session(interaction.channel_id, session)

        narration_chunks = self._chunk_text(encounter_narration, 1800)
        await interaction.followup.send(content=f"## ⚔️ Encounter!\n\n{narration_chunks[0]}")
        for chunk in narration_chunks[1:]:
            await interaction.followup.send(content=chunk)

        roster_embed = discord.Embed(title="👹 Enemies", color=discord.Color.red())
        for p in participants:
            roll = p["initiative"] - p["initiative_mod"]
            mod_str = f"{p['initiative_mod']:+d}" if p["initiative_mod"] != 0 else "±0"
            roster_embed.add_field(
                name=p["character_name"],
                value=f"HP: **{p['npc_hp']}** | Init: **{p['initiative']}** (d20={roll} {mod_str})",
                inline=True,
            )
        if dm_tip:
            roster_embed.set_footer(text=f"DM Tip: {dm_tip}")
        await interaction.followup.send(embed=roster_embed)

        await interaction.followup.send(
            content=(
                "Combat tracker is live. Use `/combat join` to roll your initiative and enter the fight.\n"
                "Use `/combat status` to see the full initiative order."
            )
        )

    @dm_group.command(name="npcs", description="List known NPCs and memory notes for this session")
    async def list_npcs(self, interaction: discord.Interaction):
        if interaction.channel_id is None:
            await interaction.response.send_message(
                "❌ This command must be used in a server channel.", ephemeral=True
            )
            return

        session = self._get_or_create_session(interaction.channel_id)
        known_npcs = session.get("known_npcs", [])
        npc_memories = session.get("npc_memories", {})

        if not known_npcs:
            await interaction.response.send_message(
                "ℹ️ No NPCs have been encountered yet in this session.", ephemeral=True
            )
            return

        embed = discord.Embed(
            title="👥 Known NPCs",
            color=discord.Color.teal(),
        )
        for npc in known_npcs:
            memory = npc_memories.get(npc, "")
            embed.add_field(
                name=npc,
                value=memory[:512] if memory else "*(no notes yet)*",
                inline=False,
            )
        embed.set_footer(text=f"{len(known_npcs)} NPC(s) known • Use /dm talk to interact")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(AIDM(bot))
