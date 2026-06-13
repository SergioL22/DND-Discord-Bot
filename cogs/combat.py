from dataclasses import dataclass, field
from typing import Dict, List, Optional
import random

import discord
from discord import app_commands
from discord.ext import commands

from utils import db
from utils.database import get_database


DND_CONDITIONS = [
    "Blinded", "Charmed", "Deafened", "Frightened", "Grappled",
    "Incapacitated", "Invisible", "Paralyzed", "Petrified", "Poisoned",
    "Prone", "Restrained", "Stunned", "Unconscious",
    "Exhaustion 1", "Exhaustion 2", "Exhaustion 3",
    "Exhaustion 4", "Exhaustion 5", "Exhaustion 6",
    "Concentration", "Blessed", "Cursed", "Raging",
]


@dataclass
class EncounterParticipant:
    owner_id: str
    character_name: str
    initiative: int
    initiative_mod: int
    is_npc: bool = False
    npc_hp: Optional[int] = None
    npc_max_hp: Optional[int] = None
    conditions: List[str] = field(default_factory=list)
    death_saves_successes: int = 0
    death_saves_failures: int = 0

    def to_dict(self) -> Dict:
        return {
            "owner_id": self.owner_id,
            "character_name": self.character_name,
            "initiative": self.initiative,
            "initiative_mod": self.initiative_mod,
            "is_npc": self.is_npc,
            "npc_hp": self.npc_hp,
            "npc_max_hp": self.npc_max_hp,
            "conditions": self.conditions,
            "death_saves_successes": self.death_saves_successes,
            "death_saves_failures": self.death_saves_failures,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "EncounterParticipant":
        p = cls(
            owner_id=data["owner_id"],
            character_name=data["character_name"],
            initiative=data["initiative"],
            initiative_mod=data["initiative_mod"],
            is_npc=data.get("is_npc", False),
            npc_hp=data.get("npc_hp"),
            npc_max_hp=data.get("npc_max_hp"),
        )
        p.conditions = data.get("conditions", [])
        p.death_saves_successes = data.get("death_saves_successes", 0)
        p.death_saves_failures = data.get("death_saves_failures", 0)
        return p


@dataclass
class EncounterState:
    participants: List[EncounterParticipant] = field(default_factory=list)
    current_index: int = 0
    round_number: int = 1

    def to_dict(self) -> Dict:
        return {
            "participants": [p.to_dict() for p in self.participants],
            "current_index": self.current_index,
            "round_number": self.round_number,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "EncounterState":
        state = cls()
        state.participants = [EncounterParticipant.from_dict(p) for p in data.get("participants", [])]
        state.current_index = data.get("current_index", 0)
        state.round_number = data.get("round_number", 1)
        return state


class Combat(commands.Cog):
    """Combat encounter tracking commands."""

    combat_group = app_commands.Group(name="combat", description="Run and track combat encounters")

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = get_database()
        self.active_encounters: Dict[int, EncounterState] = {}

    # ── Persistence helpers ───────────────────────────────────────────────────

    def _get_encounter(self, channel_id: int) -> Optional[EncounterState]:
        if channel_id in self.active_encounters:
            return self.active_encounters[channel_id]
        data = db.encounter_get(channel_id)
        if data is None:
            return None
        state = EncounterState.from_dict(data)
        self.active_encounters[channel_id] = state
        return state

    def _save_encounter(self, channel_id: int) -> None:
        encounter = self.active_encounters.get(channel_id)
        if encounter:
            db.encounter_save(channel_id, encounter.to_dict())

    def _delete_encounter(self, channel_id: int) -> None:
        self.active_encounters.pop(channel_id, None)
        db.encounter_delete(channel_id)

    # ── Autocomplete ──────────────────────────────────────────────────────────

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
        encounter = self._get_encounter(interaction.channel_id)
        if not encounter:
            return []
        names = [p.character_name for p in encounter.participants]
        filtered = [name for name in names if current.lower() in name.lower()]
        unique: List[str] = []
        for name in filtered:
            if name not in unique:
                unique.append(name)
        return [app_commands.Choice(name=n, value=n) for n in unique[:25]]

    async def _condition_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> List[app_commands.Choice[str]]:
        filtered = [c for c in DND_CONDITIONS if current.lower() in c.lower()]
        return [app_commands.Choice(name=c, value=c) for c in filtered[:25]]

    async def _remove_condition_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> List[app_commands.Choice[str]]:
        if interaction.channel_id is None:
            return []
        char_name = getattr(interaction.namespace, "character_name", None)
        encounter = self._get_encounter(interaction.channel_id)
        if encounter and char_name:
            participant = self._find_participant(encounter, char_name)
            if participant and participant.conditions:
                filtered = [c for c in participant.conditions if current.lower() in c.lower()]
                return [app_commands.Choice(name=c, value=c) for c in filtered[:25]]
        filtered = [c for c in DND_CONDITIONS if current.lower() in c.lower()]
        return [app_commands.Choice(name=c, value=c) for c in filtered[:25]]

    # ── Internal helpers ──────────────────────────────────────────────────────

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
            if f"{p.owner_id}:{p.character_name.lower()}" == current_key:
                encounter.current_index = i
                return
        encounter.current_index = 0

    def _find_participant(
        self,
        encounter: EncounterState,
        character_name: str,
    ) -> Optional[EncounterParticipant]:
        matches = [
            p for p in encounter.participants
            if p.character_name.lower() == character_name.lower().strip()
        ]
        return matches[0] if len(matches) == 1 else None

    @staticmethod
    def _display_name(participant: EncounterParticipant) -> str:
        if participant.is_npc:
            return f"{participant.character_name} (NPC)"
        return f"{participant.character_name} (<@{participant.owner_id}>)"

    # ── Commands ──────────────────────────────────────────────────────────────

    @combat_group.command(name="start", description="Start a new combat encounter in this channel")
    async def start_combat(self, interaction: discord.Interaction):
        if interaction.channel_id is None:
            await interaction.response.send_message("❌ This command must be used in a server channel.", ephemeral=True)
            return

        self.active_encounters[interaction.channel_id] = EncounterState()
        self._save_encounter(interaction.channel_id)
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

        encounter = self._get_encounter(interaction.channel_id)
        if not encounter:
            await interaction.response.send_message(
                "❌ No active combat here. Use `/combat start` first.", ephemeral=True,
            )
            return

        owner_id = str(interaction.user.id)
        character = self.db.get_character(owner_id, character_name)
        if not character:
            await interaction.response.send_message(f"❌ Character **{character_name}** not found.", ephemeral=True)
            return

        existing = self._find_participant(encounter, character.name)
        if existing and existing.owner_id == owner_id:
            await interaction.response.send_message(
                f"❌ **{character.name}** is already in this encounter.", ephemeral=True,
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
        self._save_encounter(interaction.channel_id)

        await interaction.response.send_message(
            f"✅ **{character.name}** joined combat with initiative **{total_initiative}** {roll_text}."
        )

    @combat_group.command(name="addnpc", description="Add an NPC/monster to this encounter")
    @app_commands.describe(
        name="NPC or monster name",
        initiative="Initiative total for the NPC",
        hp="Current/max HP for tracking damage and healing",
    )
    async def add_npc(self, interaction: discord.Interaction, name: str, initiative: int, hp: int):
        if interaction.channel_id is None:
            await interaction.response.send_message("❌ This command must be used in a server channel.", ephemeral=True)
            return

        encounter = self._get_encounter(interaction.channel_id)
        if not encounter:
            await interaction.response.send_message(
                "❌ No active combat here. Use `/combat start` first.", ephemeral=True,
            )
            return

        npc_name = name.strip()
        if not npc_name:
            await interaction.response.send_message("❌ NPC name cannot be empty.", ephemeral=True)
            return
        if hp <= 0:
            await interaction.response.send_message("❌ NPC HP must be greater than 0.", ephemeral=True)
            return

        encounter.participants.append(
            EncounterParticipant(
                owner_id="",
                character_name=npc_name,
                initiative=int(initiative),
                initiative_mod=0,
                is_npc=True,
                npc_hp=int(hp),
                npc_max_hp=int(hp),
            )
        )
        self._sort_participants(encounter)
        self._save_encounter(interaction.channel_id)

        await interaction.response.send_message(
            f"👹 Added NPC **{npc_name}** with initiative **{initiative}** (HP {hp}/{hp})."
        )

    @combat_group.command(name="status", description="Show current combat order and turn")
    async def combat_status(self, interaction: discord.Interaction):
        if interaction.channel_id is None:
            await interaction.response.send_message("❌ This command must be used in a server channel.", ephemeral=True)
            return

        encounter = self._get_encounter(interaction.channel_id)
        if not encounter:
            await interaction.response.send_message(
                "❌ No active combat here. Use `/combat start` first.", ephemeral=True,
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

            if p.is_npc and p.npc_hp is not None and p.npc_max_hp is not None:
                hp_text = f" | HP {p.npc_hp}/{p.npc_max_hp}"
            else:
                char = self.db.get_character(p.owner_id, p.character_name)
                hp_text = ""
                if char:
                    hp_text = f" | HP {char.current_hp}/{char.max_hp}"
                    if char.current_hp == 0:
                        hp_text += f" 💀 {p.death_saves_successes}✅/{p.death_saves_failures}❌"

            cond_text = f" [{', '.join(p.conditions)}]" if p.conditions else ""
            order_lines.append(
                f"{marker} **{i + 1}.** {self._display_name(p)} - Init {p.initiative}{hp_text}{cond_text}"
            )

        embed.add_field(name="Initiative Order", value="\n".join(order_lines), inline=False)
        await interaction.response.send_message(embed=embed)

    @combat_group.command(name="next", description="Advance to the next turn")
    async def next_turn(self, interaction: discord.Interaction):
        if interaction.channel_id is None:
            await interaction.response.send_message("❌ This command must be used in a server channel.", ephemeral=True)
            return

        encounter = self._get_encounter(interaction.channel_id)
        if not encounter or not encounter.participants:
            await interaction.response.send_message("❌ No active combat with participants here.", ephemeral=True)
            return

        encounter.current_index += 1
        if encounter.current_index >= len(encounter.participants):
            encounter.current_index = 0
            encounter.round_number += 1

        current = encounter.participants[encounter.current_index]
        self._save_encounter(interaction.channel_id)
        await interaction.response.send_message(
            f"➡️ **Round {encounter.round_number}** - It is now **{current.character_name}**'s turn."
        )

    @combat_group.command(name="prev", description="Move turn back to the previous participant")
    async def previous_turn(self, interaction: discord.Interaction):
        if interaction.channel_id is None:
            await interaction.response.send_message("❌ This command must be used in a server channel.", ephemeral=True)
            return

        encounter = self._get_encounter(interaction.channel_id)
        if not encounter or not encounter.participants:
            await interaction.response.send_message("❌ No active combat with participants here.", ephemeral=True)
            return

        encounter.current_index -= 1
        if encounter.current_index < 0:
            encounter.current_index = len(encounter.participants) - 1
            encounter.round_number = max(1, encounter.round_number - 1)

        current = encounter.participants[encounter.current_index]
        self._save_encounter(interaction.channel_id)
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

        encounter = self._get_encounter(interaction.channel_id)
        if not encounter:
            await interaction.response.send_message("❌ No active combat here.", ephemeral=True)
            return

        participant = self._find_participant(encounter, character_name)
        if not participant:
            await interaction.response.send_message(
                f"❌ Character **{character_name}** not found in this encounter.", ephemeral=True,
            )
            return

        old_index = encounter.current_index
        remove_index = encounter.participants.index(participant)
        display = self._display_name(participant)
        del encounter.participants[remove_index]

        if not encounter.participants:
            encounter.current_index = 0
            self._save_encounter(interaction.channel_id)
            await interaction.response.send_message(f"🗑️ Removed **{display}**. Encounter is now empty.")
            return

        if remove_index < old_index:
            encounter.current_index -= 1
        elif remove_index == old_index and encounter.current_index >= len(encounter.participants):
            encounter.current_index = 0

        self._save_encounter(interaction.channel_id)
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

        encounter = self._get_encounter(interaction.channel_id)
        if not encounter:
            await interaction.response.send_message("❌ No active combat here.", ephemeral=True)
            return

        participant = self._find_participant(encounter, character_name)
        if not participant:
            await interaction.response.send_message(
                f"❌ Character **{character_name}** not found in this encounter.", ephemeral=True,
            )
            return

        if participant.is_npc:
            if participant.npc_hp is None or participant.npc_max_hp is None:
                await interaction.response.send_message(
                    f"❌ NPC **{participant.character_name}** has no HP tracked.", ephemeral=True,
                )
                return
            old_hp = participant.npc_hp
            participant.npc_hp = max(0, participant.npc_hp - amount)
            self._save_encounter(interaction.channel_id)
            msg = f"💥 **{participant.character_name}** took {amount} damage: {old_hp} → {participant.npc_hp}/{participant.npc_max_hp}"
            if participant.npc_hp == 0:
                msg += "\n☠️ **Defeated!**"
            await interaction.response.send_message(msg)
            return

        character = self.db.get_character(participant.owner_id, participant.character_name)
        if not character:
            await interaction.response.send_message(
                f"❌ Could not load **{participant.character_name}** from the database.", ephemeral=True,
            )
            return

        old_hp = character.current_hp
        character.adjust_hp(-amount)
        self.db.save_character(character)
        self._save_encounter(interaction.channel_id)

        msg = f"💥 **{character.name}** took {amount} damage: {old_hp} → {character.current_hp}/{character.max_hp}"
        if character.current_hp == 0 and old_hp > 0:
            msg += "\n💀 **DOWN!** Use `/combat deathsave` to track death saving throws."
        await interaction.response.send_message(msg)

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

        encounter = self._get_encounter(interaction.channel_id)
        if not encounter:
            await interaction.response.send_message("❌ No active combat here.", ephemeral=True)
            return

        participant = self._find_participant(encounter, character_name)
        if not participant:
            await interaction.response.send_message(
                f"❌ Character **{character_name}** not found in this encounter.", ephemeral=True,
            )
            return

        if participant.is_npc:
            if participant.npc_hp is None or participant.npc_max_hp is None:
                await interaction.response.send_message(
                    f"❌ NPC **{participant.character_name}** has no HP tracked.", ephemeral=True,
                )
                return
            old_hp = participant.npc_hp
            participant.npc_hp = min(participant.npc_max_hp, participant.npc_hp + amount)
            self._save_encounter(interaction.channel_id)
            await interaction.response.send_message(
                f"💚 **{participant.character_name}** healed {amount}: {old_hp} → {participant.npc_hp}/{participant.npc_max_hp}"
            )
            return

        character = self.db.get_character(participant.owner_id, participant.character_name)
        if not character:
            await interaction.response.send_message(
                f"❌ Could not load **{participant.character_name}** from the database.", ephemeral=True,
            )
            return

        old_hp = character.current_hp
        character.adjust_hp(amount)
        self.db.save_character(character)

        if old_hp == 0 and character.current_hp > 0:
            participant.death_saves_successes = 0
            participant.death_saves_failures = 0

        self._save_encounter(interaction.channel_id)
        await interaction.response.send_message(
            f"💚 **{character.name}** healed {amount}: {old_hp} → {character.current_hp}/{character.max_hp}"
        )

    @combat_group.command(name="addcondition", description="Apply a condition to a combatant")
    @app_commands.describe(character_name="Target combatant", condition="D&D condition to apply")
    @app_commands.autocomplete(character_name=_encounter_character_autocomplete, condition=_condition_autocomplete)
    async def add_condition(self, interaction: discord.Interaction, character_name: str, condition: str):
        if interaction.channel_id is None:
            await interaction.response.send_message("❌ This command must be used in a server channel.", ephemeral=True)
            return

        encounter = self._get_encounter(interaction.channel_id)
        if not encounter:
            await interaction.response.send_message("❌ No active combat here.", ephemeral=True)
            return

        participant = self._find_participant(encounter, character_name)
        if not participant:
            await interaction.response.send_message(
                f"❌ **{character_name}** not found in this encounter.", ephemeral=True,
            )
            return

        condition = condition.strip()
        if condition.lower() in [c.lower() for c in participant.conditions]:
            await interaction.response.send_message(
                f"⚠️ **{participant.character_name}** already has **{condition}**.", ephemeral=True,
            )
            return

        participant.conditions.append(condition)
        self._save_encounter(interaction.channel_id)
        await interaction.response.send_message(
            f"🔴 **{participant.character_name}** is now **{condition}**."
        )

    @combat_group.command(name="removecondition", description="Remove a condition from a combatant")
    @app_commands.describe(character_name="Target combatant", condition="Condition to remove")
    @app_commands.autocomplete(character_name=_encounter_character_autocomplete, condition=_remove_condition_autocomplete)
    async def remove_condition(self, interaction: discord.Interaction, character_name: str, condition: str):
        if interaction.channel_id is None:
            await interaction.response.send_message("❌ This command must be used in a server channel.", ephemeral=True)
            return

        encounter = self._get_encounter(interaction.channel_id)
        if not encounter:
            await interaction.response.send_message("❌ No active combat here.", ephemeral=True)
            return

        participant = self._find_participant(encounter, character_name)
        if not participant:
            await interaction.response.send_message(
                f"❌ **{character_name}** not found in this encounter.", ephemeral=True,
            )
            return

        condition_lower = condition.strip().lower()
        before = len(participant.conditions)
        participant.conditions = [c for c in participant.conditions if c.lower() != condition_lower]

        if len(participant.conditions) == before:
            await interaction.response.send_message(
                f"⚠️ **{participant.character_name}** doesn't have **{condition.strip()}**.", ephemeral=True,
            )
            return

        self._save_encounter(interaction.channel_id)
        await interaction.response.send_message(
            f"✅ Removed **{condition.strip()}** from **{participant.character_name}**."
        )

    @combat_group.command(name="deathsave", description="Record a death saving throw result")
    @app_commands.describe(character_name="The downed character", result="success or fail")
    @app_commands.autocomplete(character_name=_encounter_character_autocomplete)
    @app_commands.choices(result=[
        app_commands.Choice(name="Success", value="success"),
        app_commands.Choice(name="Fail", value="fail"),
    ])
    async def death_save(self, interaction: discord.Interaction, character_name: str, result: str):
        if interaction.channel_id is None:
            await interaction.response.send_message("❌ This command must be used in a server channel.", ephemeral=True)
            return

        encounter = self._get_encounter(interaction.channel_id)
        if not encounter:
            await interaction.response.send_message("❌ No active combat here.", ephemeral=True)
            return

        participant = self._find_participant(encounter, character_name)
        if not participant:
            await interaction.response.send_message(
                f"❌ **{character_name}** not found in this encounter.", ephemeral=True,
            )
            return

        if participant.is_npc:
            await interaction.response.send_message("❌ NPCs don't make death saving throws.", ephemeral=True)
            return

        if result == "success":
            participant.death_saves_successes += 1
        else:
            participant.death_saves_failures += 1

        successes = participant.death_saves_successes
        failures = participant.death_saves_failures
        name = participant.character_name

        if successes >= 3:
            participant.death_saves_successes = 0
            participant.death_saves_failures = 0
            self._save_encounter(interaction.channel_id)
            await interaction.response.send_message(
                f"💚 **{name}** is **stable**! (3 successes) They are unconscious but no longer dying."
            )
            return

        if failures >= 3:
            participant.death_saves_successes = 0
            participant.death_saves_failures = 0
            self._save_encounter(interaction.channel_id)
            await interaction.response.send_message(
                f"💀 **{name}** has **died**. (3 failures) Use `/combat remove` to remove them."
            )
            return

        self._save_encounter(interaction.channel_id)
        await interaction.response.send_message(
            f"🎲 **{name}** death save **{result}**! ✅×{successes} | ❌×{failures} (need 3 of either)"
        )

    @combat_group.command(name="end", description="End the combat encounter in this channel")
    async def end_combat(self, interaction: discord.Interaction):
        if interaction.channel_id is None:
            await interaction.response.send_message("❌ This command must be used in a server channel.", ephemeral=True)
            return

        if not self._get_encounter(interaction.channel_id):
            await interaction.response.send_message("❌ No active combat here.", ephemeral=True)
            return

        self._delete_encounter(interaction.channel_id)
        await interaction.response.send_message("🏁 Combat ended and cleared for this channel.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Combat(bot))
