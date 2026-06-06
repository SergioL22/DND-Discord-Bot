import io
import logging
import time
from typing import List

import discord
from discord import app_commands
from discord.ext import commands

from utils import db

logger = logging.getLogger(__name__)


class Campaign(commands.Cog):
    """Campaign save/load, status, and export commands."""

    campaign_group = app_commands.Group(name="campaign", description="Manage D&D campaigns")

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _campaign_name_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> List[app_commands.Choice[str]]:
        if not interaction.guild_id:
            return []
        names = db.campaign_names(interaction.guild_id)
        filtered = [n for n in names if current.lower() in n.lower()]
        return [app_commands.Choice(name=n, value=n) for n in filtered[:25]]

    @campaign_group.command(name="save", description="Save the current channel's AI DM session as a named campaign")
    @app_commands.describe(name="A name for this campaign save")
    async def save_campaign(self, interaction: discord.Interaction, name: str):
        if not interaction.guild_id or not interaction.channel_id:
            await interaction.response.send_message("❌ This command must be used in a server channel.", ephemeral=True)
            return

        session = db.session_get(interaction.channel_id)
        if not session:
            await interaction.response.send_message(
                "❌ No active AI DM session in this channel. Start one with `/dm start_campaign` first.",
                ephemeral=True,
            )
            return

        db.campaign_save(interaction.guild_id, name, str(interaction.user.id), session)

        title = session.get("campaign", {}).get("title", "Unnamed Campaign")
        embed = discord.Embed(
            title="💾 Campaign Saved",
            description=f"**{name.strip()}** saved successfully.",
            color=discord.Color.green(),
        )
        embed.add_field(name="Campaign", value=title, inline=True)
        embed.add_field(name="Saved by", value=interaction.user.display_name, inline=True)
        await interaction.response.send_message(embed=embed)

    @campaign_group.command(name="load", description="Load a saved campaign into this channel")
    @app_commands.describe(name="Name of the campaign save to load")
    @app_commands.autocomplete(name=_campaign_name_autocomplete)
    async def load_campaign(self, interaction: discord.Interaction, name: str):
        if not interaction.guild_id or not interaction.channel_id:
            await interaction.response.send_message("❌ This command must be used in a server channel.", ephemeral=True)
            return

        saved = db.campaign_get(interaction.guild_id, name)
        if not saved:
            await interaction.response.send_message(
                f"❌ No campaign save named **{name}** found. Use `/campaign list` to see available saves.",
                ephemeral=True,
            )
            return

        db.session_save(interaction.channel_id, saved["session"])

        title = saved["session"].get("campaign", {}).get("title", "Unnamed Campaign")
        scene = saved["session"].get("scene_summary", "")
        npcs = saved["session"].get("known_npcs", [])

        embed = discord.Embed(
            title="📂 Campaign Loaded",
            description=f"**{name.strip()}** loaded into this channel.",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Campaign", value=title, inline=True)
        if scene:
            embed.add_field(name="Last Scene", value=scene[:512], inline=False)
        if npcs:
            embed.add_field(name="Known NPCs", value=", ".join(npcs[:15]), inline=False)
        embed.set_footer(text="Use /dm scene to continue the story.")
        await interaction.response.send_message(embed=embed)

    @campaign_group.command(name="status", description="Show the active campaign in this channel")
    async def campaign_status(self, interaction: discord.Interaction):
        if not interaction.channel_id:
            await interaction.response.send_message("❌ This command must be used in a server channel.", ephemeral=True)
            return

        session = db.session_get(interaction.channel_id)
        if not session:
            await interaction.response.send_message(
                "ℹ️ No active AI DM campaign in this channel. Start one with `/dm start_campaign`.",
                ephemeral=True,
            )
            return

        campaign = session.get("campaign", {})
        title = campaign.get("title") or "Unnamed Campaign"
        premise = campaign.get("premise") or "—"
        tone = campaign.get("tone") or "—"
        scene = session.get("scene_summary") or "—"
        npcs = session.get("known_npcs", [])
        events = session.get("recent_events", [])

        embed = discord.Embed(
            title=f"📖 {title}",
            description=premise,
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Tone", value=tone, inline=True)
        embed.add_field(name="Known NPCs", value=", ".join(npcs) if npcs else "None yet", inline=True)
        embed.add_field(name="Current Scene", value=scene[:512], inline=False)
        if events:
            embed.add_field(
                name="Recent Events",
                value="\n".join(f"• {e}" for e in events[-5:])[:1024],
                inline=False,
            )
        await interaction.response.send_message(embed=embed)

    @campaign_group.command(name="list", description="List all saved campaigns in this server")
    async def list_campaigns(self, interaction: discord.Interaction):
        if not interaction.guild_id:
            await interaction.response.send_message("❌ This command must be used in a server.", ephemeral=True)
            return

        campaigns = db.campaign_list(interaction.guild_id)
        if not campaigns:
            await interaction.response.send_message(
                "ℹ️ No saved campaigns yet. Use `/campaign save` after starting a session.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(title="📚 Saved Campaigns", color=discord.Color.gold())
        for c in campaigns:
            title = c["session"].get("campaign", {}).get("title", "Unnamed")
            saved_dt = time.strftime("%Y-%m-%d", time.localtime(c["saved_at"]))
            embed.add_field(name=c["name"], value=f"**{title}** · Saved {saved_dt}", inline=False)
        embed.set_footer(text=f"{len(campaigns)} save(s) total")
        await interaction.response.send_message(embed=embed)

    @campaign_group.command(name="delete", description="Delete a saved campaign")
    @app_commands.describe(name="Name of the campaign save to delete", confirm="Set to true to confirm deletion")
    @app_commands.autocomplete(name=_campaign_name_autocomplete)
    async def delete_campaign(self, interaction: discord.Interaction, name: str, confirm: bool):
        if not interaction.guild_id:
            await interaction.response.send_message("❌ This command must be used in a server.", ephemeral=True)
            return

        if not confirm:
            await interaction.response.send_message(
                f"⚠️ Re-run with `confirm: true` to delete **{name}**.", ephemeral=True
            )
            return

        if not db.campaign_delete(interaction.guild_id, name):
            await interaction.response.send_message(f"❌ No campaign save named **{name}** found.", ephemeral=True)
            return

        await interaction.response.send_message(f"🗑️ Deleted campaign save **{name}**.")

    @campaign_group.command(name="export", description="Export the current session as a text adventure log")
    async def export_campaign(self, interaction: discord.Interaction):
        if not interaction.channel_id:
            await interaction.response.send_message("❌ This command must be used in a server channel.", ephemeral=True)
            return

        session = db.session_get(interaction.channel_id)
        if not session:
            await interaction.response.send_message(
                "ℹ️ No active AI DM campaign in this channel.", ephemeral=True
            )
            return

        campaign = session.get("campaign", {})
        lines: List[str] = []

        title = campaign.get("title") or "Unnamed Campaign"
        lines.append(f"# {title}")
        lines.append("")

        if campaign.get("premise"):
            lines.append(f"**Premise:** {campaign['premise']}")
        if campaign.get("tone"):
            lines.append(f"**Tone:** {campaign['tone']}")
        lines.append("")

        scene = session.get("scene_summary", "")
        if scene:
            lines.append("## Current Scene")
            lines.append(scene)
            lines.append("")

        npcs = session.get("known_npcs", [])
        if npcs:
            lines.append("## Known NPCs")
            for npc in npcs:
                lines.append(f"- {npc}")
            lines.append("")

        npc_memories = session.get("npc_memories", {})
        if npc_memories:
            lines.append("## NPC Notes")
            for npc, memory in npc_memories.items():
                if memory:
                    lines.append(f"**{npc}:** {memory}")
            lines.append("")

        events = session.get("recent_events", [])
        if events:
            lines.append("## Recent Events")
            for event in events:
                lines.append(f"- {event}")
            lines.append("")

        history = session.get("history", [])
        if history:
            lines.append("## Session Log")
            for entry in history:
                role = entry.get("role", "").upper()
                content = entry.get("content", "")
                lines.append(f"**[{role}]** {content}")
                lines.append("")

        text = "\n".join(lines)
        file_bytes = io.BytesIO(text.encode("utf-8"))
        safe_title = "".join(c if c.isalnum() or c in " _-" else "_" for c in title).strip()[:40]
        filename = f"{safe_title or 'campaign'}_log.txt"

        await interaction.response.send_message(
            f"📜 Here is the adventure log for **{title}**.",
            file=discord.File(file_bytes, filename=filename),
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Campaign(bot))
