from dataclasses import dataclass, field
from typing import Dict, List, Optional
import random

import discord
from discord import app_commands
from discord.ext import commands

from utils.database import get_database


@dataclass
class EncounterParticipant:
	owner_id: str
	character_name: str
	initiative: int
	initiative_mod: int
	is_npc: bool = False
	npc_hp: Optional[int] = None
	npc_max_hp: Optional[int] = None


@dataclass
class EncounterState:
	participants: List[EncounterParticipant] = field(default_factory=list)
	current_index: int = 0
	round_number: int = 1


class Combat(commands.Cog):
	"""Combat encounter tracking commands."""

	combat_group = app_commands.Group(name="combat", description="Run and track combat encounters")

	def __init__(self, bot: commands.Bot):
		self.bot = bot
		self.db = get_database()
		self.active_encounters: Dict[int, EncounterState] = {}

	async def _owned_character_autocomplete(
		self,
		interaction: discord.Interaction,
		current: str,
	) -> List[app_commands.Choice[str]]:
		owner_id = str(interaction.user.id)
		names = self.db.get_all_character_names(owner_id)
		filtered = [name for name in names if current.lower() in name.lower()]
		return [app_commands.Choice(name=n, value=n) for n in filtered[:25]]

	async def _encounter_character_autocomplete(
		self,
		interaction: discord.Interaction,
		current: str,
	) -> List[app_commands.Choice[str]]:
		if interaction.channel_id is None:
			return []

		encounter = self.active_encounters.get(interaction.channel_id)
		if not encounter:
			return []

		names = [p.character_name for p in encounter.participants]
		filtered = [name for name in names if current.lower() in name.lower()]
		unique_names: List[str] = []
		for name in filtered:
			if name not in unique_names:
				unique_names.append(name)
		return [app_commands.Choice(name=n, value=n) for n in unique_names[:25]]

	def _sort_participants(self, encounter: EncounterState) -> None:
		current_key: Optional[str] = None
		if encounter.participants:
			current = encounter.participants[encounter.current_index]
			current_key = f"{current.owner_id}:{current.character_name.lower()}"

		encounter.participants.sort(
			key=lambda p: (-p.initiative, -p.initiative_mod, p.character_name.lower())
		)

		if current_key is None:
			encounter.current_index = 0
			return

		for i, p in enumerate(encounter.participants):
			key = f"{p.owner_id}:{p.character_name.lower()}"
			if key == current_key:
				encounter.current_index = i
				return

		encounter.current_index = 0

	def _find_participant(
		self,
		encounter: EncounterState,
		character_name: str,
	) -> Optional[EncounterParticipant]:
		matches = [
			p for p in encounter.participants if p.character_name.lower() == character_name.lower().strip()
		]
		if len(matches) != 1:
			return None
		return matches[0]

	@staticmethod
	def _display_name(participant: EncounterParticipant) -> str:
		if participant.is_npc:
			return f"{participant.character_name} (NPC)"
		return f"{participant.character_name} (<@{participant.owner_id}>)"

	@combat_group.command(name="start", description="Start a new combat encounter in this channel")
	async def start_combat(self, interaction: discord.Interaction):
		if interaction.channel_id is None:
			await interaction.response.send_message("❌ This command must be used in a server channel.", ephemeral=True)
			return

		self.active_encounters[interaction.channel_id] = EncounterState()
		await interaction.response.send_message(
			"⚔️ Combat started for this channel. Use `/combat join` or `/combat addnpc` to add participants."
		)

	@combat_group.command(name="join", description="Join combat with one of your characters")
	@app_commands.describe(
		character_name="Your character to join the encounter",
		initiative="Optional total initiative. If omitted, bot rolls d20 + Dex modifier",
	)
	@app_commands.autocomplete(character_name=_owned_character_autocomplete)
	async def join_combat(
		self,
		interaction: discord.Interaction,
		character_name: str,
		initiative: Optional[int] = None,
	):
		if interaction.channel_id is None:
			await interaction.response.send_message("❌ This command must be used in a server channel.", ephemeral=True)
			return

		encounter = self.active_encounters.get(interaction.channel_id)
		if not encounter:
			await interaction.response.send_message(
				"❌ No active combat here. Use `/combat start` first.",
				ephemeral=True,
			)
			return

		owner_id = str(interaction.user.id)
		character = self.db.get_character(owner_id, character_name)
		if not character:
			await interaction.response.send_message(
				f"❌ Character **{character_name}** not found.",
				ephemeral=True,
			)
			return

		existing = self._find_participant(encounter, character.name)
		if existing and existing.owner_id == owner_id:
			await interaction.response.send_message(
				f"❌ **{character.name}** is already in this encounter.",
				ephemeral=True,
			)
			return

		initiative_mod = character.initiative_bonus()
		if initiative is None:
			roll = random.randint(1, 20)
			total_initiative = roll + initiative_mod
			roll_text = f"(rolled {roll} + {initiative_mod:+d})"
		else:
			total_initiative = int(initiative)
			roll_text = "(manual)"

		encounter.participants.append(
			EncounterParticipant(
				owner_id=owner_id,
				character_name=character.name,
				initiative=total_initiative,
				initiative_mod=initiative_mod,
			)
		)
		self._sort_participants(encounter)

		await interaction.response.send_message(
			f"✅ **{character.name}** joined combat with initiative **{total_initiative}** {roll_text}."
		)

	@combat_group.command(name="addnpc", description="Add an NPC/monster to this encounter")
	@app_commands.describe(
		name="NPC or monster name",
		initiative="Initiative total for the NPC",
		hp="Current/max HP for tracking damage and healing",
	)
	async def add_npc(
		self,
		interaction: discord.Interaction,
		name: str,
		initiative: int,
		hp: int,
	):
		if interaction.channel_id is None:
			await interaction.response.send_message("❌ This command must be used in a server channel.", ephemeral=True)
			return

		encounter = self.active_encounters.get(interaction.channel_id)
		if not encounter:
			await interaction.response.send_message(
				"❌ No active combat here. Use `/combat start` first.",
				ephemeral=True,
			)
			return

		npc_name = name.strip()
		if not npc_name:
			await interaction.response.send_message("❌ NPC name cannot be empty.", ephemeral=True)
			return

		if hp <= 0:
			await interaction.response.send_message("❌ NPC HP must be greater than 0.", ephemeral=True)
			return

		npc_hp = int(hp)
		npc_max_hp = int(hp)

		encounter.participants.append(
			EncounterParticipant(
				owner_id="",
				character_name=npc_name,
				initiative=int(initiative),
				initiative_mod=0,
				is_npc=True,
				npc_hp=npc_hp,
				npc_max_hp=npc_max_hp,
			)
		)
		self._sort_participants(encounter)

		await interaction.response.send_message(
			f"👹 Added NPC **{npc_name}** with initiative **{initiative}** (HP {npc_hp}/{npc_max_hp})."
		)

	@combat_group.command(name="status", description="Show current combat order and turn")
	async def combat_status(self, interaction: discord.Interaction):
		if interaction.channel_id is None:
			await interaction.response.send_message("❌ This command must be used in a server channel.", ephemeral=True)
			return

		encounter = self.active_encounters.get(interaction.channel_id)
		if not encounter:
			await interaction.response.send_message(
				"❌ No active combat here. Use `/combat start` first.",
				ephemeral=True,
			)
			return

		if not encounter.participants:
			await interaction.response.send_message(
				"⚔️ Combat is active but empty. Use `/combat join` or `/combat addnpc` to add participants.",
				ephemeral=True,
			)
			return

		current = encounter.participants[encounter.current_index]
		embed = discord.Embed(
			title="⚔️ Combat Status",
			description=(
				f"**Round:** {encounter.round_number}\n"
				f"**Current Turn:** {self._display_name(current)}"
			),
			color=discord.Color.red(),
		)

		order_lines: List[str] = []
		for i, p in enumerate(encounter.participants):
			marker = "▶" if i == encounter.current_index else "•"
			hp_text = ""
			if p.is_npc and p.npc_hp is not None and p.npc_max_hp is not None:
				hp_text = f" | HP {p.npc_hp}/{p.npc_max_hp}"
			order_lines.append(
				f"{marker} **{i + 1}.** {self._display_name(p)} - Init {p.initiative}{hp_text}"
			)

		embed.add_field(name="Initiative Order", value="\n".join(order_lines), inline=False)
		await interaction.response.send_message(embed=embed)

	@combat_group.command(name="next", description="Advance to the next turn")
	async def next_turn(self, interaction: discord.Interaction):
		if interaction.channel_id is None:
			await interaction.response.send_message("❌ This command must be used in a server channel.", ephemeral=True)
			return

		encounter = self.active_encounters.get(interaction.channel_id)
		if not encounter or not encounter.participants:
			await interaction.response.send_message(
				"❌ No active combat with participants here.",
				ephemeral=True,
			)
			return

		encounter.current_index += 1
		if encounter.current_index >= len(encounter.participants):
			encounter.current_index = 0
			encounter.round_number += 1

		current = encounter.participants[encounter.current_index]
		await interaction.response.send_message(
			f"➡️ **Round {encounter.round_number}** - It is now **{current.character_name}**'s turn."
		)

	@combat_group.command(name="prev", description="Move turn back to the previous participant")
	async def previous_turn(self, interaction: discord.Interaction):
		if interaction.channel_id is None:
			await interaction.response.send_message("❌ This command must be used in a server channel.", ephemeral=True)
			return

		encounter = self.active_encounters.get(interaction.channel_id)
		if not encounter or not encounter.participants:
			await interaction.response.send_message(
				"❌ No active combat with participants here.",
				ephemeral=True,
			)
			return

		encounter.current_index -= 1
		if encounter.current_index < 0:
			encounter.current_index = len(encounter.participants) - 1
			encounter.round_number = max(1, encounter.round_number - 1)

		current = encounter.participants[encounter.current_index]
		await interaction.response.send_message(
			f"⬅️ **Round {encounter.round_number}** - It is now **{current.character_name}**'s turn."
		)

	@combat_group.command(name="remove", description="Remove a participant from this encounter")
	@app_commands.describe(character_name="Participant name to remove")
	@app_commands.autocomplete(character_name=_encounter_character_autocomplete)
	async def remove_participant(self, interaction: discord.Interaction, character_name: str):
		if interaction.channel_id is None:
			await interaction.response.send_message("❌ This command must be used in a server channel.", ephemeral=True)
			return

		encounter = self.active_encounters.get(interaction.channel_id)
		if not encounter:
			await interaction.response.send_message("❌ No active combat here.", ephemeral=True)
			return

		participant = self._find_participant(encounter, character_name)
		if not participant:
			await interaction.response.send_message(
				f"❌ Character **{character_name}** not found in this encounter.",
				ephemeral=True,
			)
			return

		old_index = encounter.current_index
		remove_index = encounter.participants.index(participant)
		del encounter.participants[remove_index]

		if not encounter.participants:
			encounter.current_index = 0
			display = self._display_name(participant)
			await interaction.response.send_message(f"🗑️ Removed **{display}**. Encounter is now empty.")
			return

		if remove_index < old_index:
			encounter.current_index -= 1
		elif remove_index == old_index and encounter.current_index >= len(encounter.participants):
			encounter.current_index = 0

		display = self._display_name(participant)
		await interaction.response.send_message(f"🗑️ Removed **{display}** from the encounter.")

	@combat_group.command(name="damage", description="Apply damage to a combat participant")
	@app_commands.describe(character_name="Character in this encounter", amount="Damage amount (positive integer)")
	@app_commands.autocomplete(character_name=_encounter_character_autocomplete)
	async def damage_character(self, interaction: discord.Interaction, character_name: str, amount: int):
		if amount <= 0:
			await interaction.response.send_message("❌ Damage amount must be greater than 0.", ephemeral=True)
			return

		if interaction.channel_id is None:
			await interaction.response.send_message("❌ This command must be used in a server channel.", ephemeral=True)
			return

		encounter = self.active_encounters.get(interaction.channel_id)
		if not encounter:
			await interaction.response.send_message("❌ No active combat here.", ephemeral=True)
			return

		participant = self._find_participant(encounter, character_name)
		if not participant:
			await interaction.response.send_message(
				f"❌ Character **{character_name}** not found in this encounter.",
				ephemeral=True,
			)
			return

		if participant.is_npc:
			if participant.npc_hp is None or participant.npc_max_hp is None:
				await interaction.response.send_message(
					f"❌ NPC **{participant.character_name}** has no HP tracked. Re-add with `/combat addnpc hp:<value>`.",
					ephemeral=True,
				)
				return

			old_hp = participant.npc_hp
			participant.npc_hp = max(0, participant.npc_hp - amount)
			await interaction.response.send_message(
				f"💥 **{participant.character_name}** took {amount} damage: {old_hp} → {participant.npc_hp}/{participant.npc_max_hp}"
			)
			return

		character = self.db.get_character(participant.owner_id, participant.character_name)
		if not character:
			await interaction.response.send_message(
				f"❌ Could not load **{participant.character_name}** from the database.",
				ephemeral=True,
			)
			return

		old_hp = character.current_hp
		character.adjust_hp(-amount)
		self.db.save_character(character)
		await interaction.response.send_message(
			f"💥 **{character.name}** took {amount} damage: {old_hp} → {character.current_hp}/{character.max_hp}"
		)

	@combat_group.command(name="heal", description="Heal a combat participant")
	@app_commands.describe(character_name="Character in this encounter", amount="Healing amount (positive integer)")
	@app_commands.autocomplete(character_name=_encounter_character_autocomplete)
	async def heal_character(self, interaction: discord.Interaction, character_name: str, amount: int):
		if amount <= 0:
			await interaction.response.send_message("❌ Healing amount must be greater than 0.", ephemeral=True)
			return

		if interaction.channel_id is None:
			await interaction.response.send_message("❌ This command must be used in a server channel.", ephemeral=True)
			return

		encounter = self.active_encounters.get(interaction.channel_id)
		if not encounter:
			await interaction.response.send_message("❌ No active combat here.", ephemeral=True)
			return

		participant = self._find_participant(encounter, character_name)
		if not participant:
			await interaction.response.send_message(
				f"❌ Character **{character_name}** not found in this encounter.",
				ephemeral=True,
			)
			return

		if participant.is_npc:
			if participant.npc_hp is None or participant.npc_max_hp is None:
				await interaction.response.send_message(
					f"❌ NPC **{participant.character_name}** has no HP tracked. Re-add with `/combat addnpc hp:<value>`.",
					ephemeral=True,
				)
				return

			old_hp = participant.npc_hp
			participant.npc_hp = min(participant.npc_max_hp, participant.npc_hp + amount)
			await interaction.response.send_message(
				f"💚 **{participant.character_name}** healed {amount}: {old_hp} → {participant.npc_hp}/{participant.npc_max_hp}"
			)
			return

		character = self.db.get_character(participant.owner_id, participant.character_name)
		if not character:
			await interaction.response.send_message(
				f"❌ Could not load **{participant.character_name}** from the database.",
				ephemeral=True,
			)
			return

		old_hp = character.current_hp
		character.adjust_hp(amount)
		self.db.save_character(character)
		await interaction.response.send_message(
			f"💚 **{character.name}** healed {amount}: {old_hp} → {character.current_hp}/{character.max_hp}"
		)

	@combat_group.command(name="end", description="End the combat encounter in this channel")
	async def end_combat(self, interaction: discord.Interaction):
		if interaction.channel_id is None:
			await interaction.response.send_message("❌ This command must be used in a server channel.", ephemeral=True)
			return

		if interaction.channel_id not in self.active_encounters:
			await interaction.response.send_message("❌ No active combat here.", ephemeral=True)
			return

		del self.active_encounters[interaction.channel_id]
		await interaction.response.send_message("🏁 Combat ended and cleared for this channel.")


async def setup(bot: commands.Bot):
	await bot.add_cog(Combat(bot))
