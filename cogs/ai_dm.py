import asyncio
import json
import os
import re
import time
from typing import Any, Dict, List
from urllib import error, request

import discord
import google.genai as genai
from discord import app_commands
from discord.ext import commands

from config import Config
from utils import db

try:
    import anthropic as _anthropic
    _ANTHROPIC_AVAILABLE = True
except ImportError:
    _ANTHROPIC_AVAILABLE = False


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
        self.ai_provider = getattr(Config, "AI_PROVIDER", os.getenv("AI_PROVIDER", "google")).strip().lower()
        self.google_api_key = getattr(Config, "GOOGLE_API_KEY", os.getenv("GOOGLE_API_KEY", ""))
        self.gemini_model_name = getattr(Config, "GEMINI_MODEL", os.getenv("GEMINI_MODEL", "gemini-2.0-flash"))
        self.openai_api_key = getattr(Config, "OPENAI_API_KEY", os.getenv("OPENAI_API_KEY", ""))
        self.openai_model = getattr(Config, "OPENAI_MODEL", os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
        self.openai_base_url = getattr(
            Config,
            "OPENAI_BASE_URL",
            os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        ).rstrip("/")
        self.anthropic_api_key = getattr(Config, "ANTHROPIC_API_KEY", os.getenv("ANTHROPIC_API_KEY", ""))
        self.claude_model = getattr(Config, "CLAUDE_MODEL", os.getenv("CLAUDE_MODEL", "claude-haiku-4-5"))
        self.ai_max_tokens_scene = self._to_int(
            getattr(Config, "AI_MAX_TOKENS_SCENE", os.getenv("AI_MAX_TOKENS_SCENE", 2000)),
            2000,
        )
        self.ai_max_tokens_talk = self._to_int(
            getattr(Config, "AI_MAX_TOKENS_TALK", os.getenv("AI_MAX_TOKENS_TALK", 1000)),
            1000,
        )
        self._client = None
        self._fallback_models = ["gemini-2.0-flash", "gemini-1.5-flash"]
        if self.google_api_key:
            self._client = genai.Client(api_key=self.google_api_key)

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
        if self.ai_provider == "openai":
            if not self.openai_api_key:
                return (
                    "❌ Missing `OPENAI_API_KEY` in your `.env`. "
                    "Add it, restart the bot, and try again."
                )
            return ""

        if self.ai_provider == "claude":
            if not _ANTHROPIC_AVAILABLE:
                return "❌ `anthropic` package not installed. Run: `pip install anthropic`"
            if not self.anthropic_api_key:
                return (
                    "❌ Missing `ANTHROPIC_API_KEY` in your `.env`. "
                    "Get one at console.anthropic.com, then restart the bot."
                )
            return ""

        if not self.google_api_key or self._client is None:
            return (
                "❌ Missing `GOOGLE_API_KEY` in your `.env`. "
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

        if "insufficient_quota" in lowered or ("quota" in lowered and "openai" in lowered):
            return "❌ OpenAI quota exceeded. Check your billing/usage limits in your OpenAI project."

        if "invalid_api_key" in lowered:
            return "❌ Invalid `OPENAI_API_KEY`. Check your `.env`, then restart the bot."

        if "claude authentication" in lowered:
            return "❌ Invalid `ANTHROPIC_API_KEY`. Check your `.env`, then restart the bot."

        if "claude rate limit" in lowered:
            return "❌ Claude rate limit hit. Please wait a moment and try again."

        if "claude api error" in lowered:
            return f"❌ Claude error: {raw}"

        if "resource_exhausted" in lowered or "quota exceeded" in lowered or "429" in lowered:
            retry_match = re.search(r"retry in\s+([0-9]+(?:\.[0-9]+)?)s", raw, flags=re.IGNORECASE)
            delay_match = re.search(r"retryDelay'?:\s*'?(\d+)s", raw, flags=re.IGNORECASE)
            retry_msg = ""
            if retry_match:
                retry_msg = f" Try again in about {int(float(retry_match.group(1)))} seconds."
            elif delay_match:
                retry_msg = f" Try again in about {delay_match.group(1)} seconds."

            return (
                "❌ Gemini quota exceeded for your project. "
                "Your key currently has no free-tier capacity (or it is temporarily exhausted)."
                f"{retry_msg}"
            )

        if "api key" in lowered and ("invalid" in lowered or "not valid" in lowered):
            return "❌ Invalid `GOOGLE_API_KEY`. Check your `.env`, then restart the bot."

        return f"❌ AI error: {raw}"

    def _call_gemini(self, prompt: str, max_output_tokens: int) -> str:
        models_to_try = [self.gemini_model_name] + [
            m for m in self._fallback_models if m != self.gemini_model_name
        ]
        last_error = None

        for model_name in models_to_try:
            try:
                response = self._client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config={
                        "max_output_tokens": max_output_tokens,
                    },
                )
                text = getattr(response, "text", "") or ""
                if not text.strip():
                    raise RuntimeError(f"Gemini returned an empty response for model '{model_name}'.")
                self.gemini_model_name = model_name
                return text
            except Exception as e:
                last_error = e
                err = str(e).lower()
                if "not_found" in err or "not found" in err or "404" in err:
                    continue
                raise RuntimeError(f"Gemini request failed using model '{model_name}': {e}") from e

        tried = ", ".join(models_to_try)
        raise RuntimeError(f"No available Gemini model found. Tried: {tried}. Last error: {last_error}")

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

    def _call_claude(self, system_prompt: str, user_prompt: str, max_tokens: int) -> str:
        if not _ANTHROPIC_AVAILABLE:
            raise RuntimeError(
                "The `anthropic` package is not installed. Run: pip install anthropic"
            )
        client = _anthropic.Anthropic(api_key=self.anthropic_api_key)
        try:
            response = client.messages.create(
                model=self.claude_model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
        except _anthropic.AuthenticationError as e:
            raise RuntimeError(f"Claude authentication error: {e}") from e
        except _anthropic.RateLimitError as e:
            raise RuntimeError(f"Claude rate limit exceeded: {e}") from e
        except _anthropic.APIStatusError as e:
            raise RuntimeError(f"Claude API error ({e.status_code}): {e.message}") from e
        except Exception as e:
            raise RuntimeError(f"Claude request failed: {e}") from e

        text = next((b.text for b in response.content if b.type == "text"), "")
        if not text.strip():
            raise RuntimeError("Claude returned an empty response.")
        return text

    @staticmethod
    def _rate_limit_delay(err: str) -> int:
        """Return retry delay in seconds if this looks like a rate-limit error, else 0."""
        low = err.lower()
        is_limit = (
            "resource_exhausted" in low or "429" in low
            or "quota exceeded" in low or "claude rate limit" in low
        )
        if not is_limit:
            return 0
        match = re.search(r"retry in\s+([0-9]+(?:\.[0-9]+)?)s", err, re.IGNORECASE)
        return int(float(match.group(1))) + 1 if match else 15

    async def _generate_json(self, system_prompt: str, user_prompt: str, max_tokens: int) -> Dict[str, Any]:
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        last_err: Exception = RuntimeError("Unknown error")
        for attempt in range(2):
            try:
                if self.ai_provider == "openai":
                    raw_text = await asyncio.to_thread(
                        self._call_openai, system_prompt, user_prompt, max_tokens,
                    )
                elif self.ai_provider == "claude":
                    raw_text = await asyncio.to_thread(
                        self._call_claude, system_prompt, user_prompt, max_tokens,
                    )
                else:
                    raw_text = await asyncio.to_thread(
                        self._call_gemini, full_prompt, max_tokens,
                    )
                break
            except RuntimeError as e:
                last_err = e
                delay = self._rate_limit_delay(str(e))
                if delay and attempt == 0:
                    await asyncio.sleep(delay)
                    continue
                raise
            except Exception as e:
                raise RuntimeError(f"AI request failed: {e}") from e
        else:
            raise last_err

        # Strip markdown code fences that Gemini sometimes wraps around JSON
        text = raw_text.strip()
        if text.startswith("```"):
            parts = text.split("```")
            # parts[1] is the fenced block; strip optional language tag
            inner = parts[1]
            lines = inner.split("\n")
            if lines[0].strip().lower() in ("json", ""):
                lines = lines[1:]
            text = "\n".join(lines).strip()

        try:
            return json.loads(text)
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
            "\"opening_dialogue\": string"
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

        narration_chunks = self._chunk_text(opening_narration)

        embed = discord.Embed(
            title=f"🎬 {title.strip()} - Opening Scene",
            description=narration_chunks[0],
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Tone", value=tone.strip()[:1024], inline=True)
        embed.add_field(name="Premise", value=premise.strip()[:1024], inline=False)
        if opening_dialogue:
            embed.add_field(name="First Voice", value=opening_dialogue[:1024], inline=False)
        if new_npcs:
            embed.add_field(name="Introduced NPCs", value=", ".join(new_npcs)[:1024], inline=False)
        if hooks:
            embed.add_field(name="Adventure Hooks", value="\n".join(f"• {h}" for h in hooks)[:1024], inline=False)

        await interaction.followup.send(
            content=f"✅ AI campaign initialized for this channel: **{title.strip()}**",
            embed=embed,
        )
        for chunk in narration_chunks[1:]:
            await interaction.followup.send(content=chunk)

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
            f"Player action: {player_action}\n\n"
            "Return JSON with this exact schema:\n"
            "{"
            "\"narration\": string,"
            "\"scene_summary\": string,"
            "\"new_npcs\": [string],"
            "\"hooks\": [string],"
            "\"combat_hint\": string"
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

        # Update channel memory so future responses stay coherent.
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

        narration_chunks = self._chunk_text(narration)

        embed = discord.Embed(
            title="📖 Scene Update",
            description=narration_chunks[0],
            color=discord.Color.blurple(),
        )
        if new_npcs:
            embed.add_field(name="New NPCs", value=", ".join(new_npcs), inline=False)
        if hooks:
            embed.add_field(name="Story Hooks", value="\n".join(f"• {h}" for h in hooks), inline=False)
        if combat_hint:
            embed.add_field(name="Combat Tension", value=combat_hint[:1024], inline=False)

        await interaction.followup.send(embed=embed)
        for chunk in narration_chunks[1:]:
            await interaction.followup.send(content=chunk)

    @dm_group.command(name="talk", description="Talk to an NPC with AI-driven dialogue")
    @app_commands.describe(npc_name="NPC you are speaking to", message="What your character says")
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


async def setup(bot: commands.Bot):
    await bot.add_cog(AIDM(bot))
