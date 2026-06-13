import random
from typing import List, Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils import dnd5e_api as dnd5e


CLASS_CHOICES = [
    app_commands.Choice(name=c, value=c.lower())
    for c in ["Barbarian", "Bard", "Cleric", "Druid", "Fighter",
              "Monk", "Paladin", "Ranger", "Rogue", "Sorcerer", "Warlock", "Wizard"]
]

RACE_CHOICES = [
    app_commands.Choice(name=r, value=r.lower())
    for r in ["Dragonborn", "Dwarf", "Elf", "Gnome", "Half-Elf",
              "Half-Orc", "Halfling", "Human", "Tiefling"]
]

ABILITY_ABBREVS = {
    "strength": "STR", "dexterity": "DEX", "constitution": "CON",
    "intelligence": "INT", "wisdom": "WIS", "charisma": "CHA",
}


class Lookup(commands.Cog):
    """D&D 5e reference lookup — powered by dnd5eapi.co."""

    lookup_group = app_commands.Group(name="lookup", description="Look up D&D 5e rules and stats")

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── Autocomplete ──────────────────────────────────────────────────────────

    async def _monster_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        try:
            matches = await dnd5e.search("monsters", current)
            return [app_commands.Choice(name=name, value=index) for name, index in matches]
        except Exception:
            return []

    async def _spell_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        try:
            matches = await dnd5e.search("spells", current)
            return [app_commands.Choice(name=name, value=index) for name, index in matches]
        except Exception:
            return []

    async def _equipment_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        try:
            matches = await dnd5e.search("equipment", current)
            return [app_commands.Choice(name=name, value=index) for name, index in matches]
        except Exception:
            return []

    # ── /lookup monster ───────────────────────────────────────────────────────

    @lookup_group.command(name="monster", description="Look up a D&D 5e monster's stats")
    @app_commands.describe(
        name="Monster name (use autocomplete)",
        add_to_combat="Also add this monster to the active combat encounter",
        initiative="Override initiative roll (auto-rolled from DEX if omitted)",
    )
    @app_commands.autocomplete(name=_monster_autocomplete)
    async def lookup_monster(
        self,
        interaction: discord.Interaction,
        name: str,
        add_to_combat: bool = False,
        initiative: Optional[int] = None,
    ):
        await interaction.response.defer()

        try:
            monster = await dnd5e.get_monster(name)
        except RuntimeError as e:
            await interaction.followup.send(f"❌ {e}", ephemeral=True)
            return

        if not monster:
            await interaction.followup.send(
                f"❌ Monster **{name}** not found. Use autocomplete to search.", ephemeral=True
            )
            return

        m_name = monster.get("name", name)
        size = monster.get("size", "")
        m_type = monster.get("type", "")
        alignment = monster.get("alignment", "—")
        cr = monster.get("challenge_rating", "?")
        xp = monster.get("xp", 0)
        xp_text = f"{xp:,} XP" if isinstance(xp, int) else ""

        avg_hp = monster.get("hit_points", "?")
        hp_formula = monster.get("hit_points_roll", monster.get("hit_dice", ""))
        hp_text = f"{avg_hp} ({hp_formula})" if hp_formula else str(avg_hp)

        ac_list = monster.get("armor_class", [])
        if isinstance(ac_list, list) and ac_list:
            ac_val = ac_list[0].get("value", "?")
            ac_type = ac_list[0].get("type", "")
            ac_text = f"{ac_val} ({ac_type})" if ac_type else str(ac_val)
        else:
            ac_text = str(ac_list)

        speed_dict = monster.get("speed", {})
        speed_text = ", ".join(f"{k} {v}" for k, v in speed_dict.items()) or "30 ft."

        embed = discord.Embed(
            title=f"🐉 {m_name}",
            description=(
                f"*{size} {m_type}, {alignment}*\n"
                f"**CR {cr}**" + (f"  •  {xp_text}" if xp_text else "")
            ),
            color=discord.Color.dark_red(),
        )

        embed.add_field(
            name="Combat Stats",
            value=f"**HP:** {hp_text}\n**AC:** {ac_text}\n**Speed:** {speed_text}",
            inline=False,
        )

        abilities = {k: monster.get(k, 10) for k in ABILITY_ABBREVS}
        ability_text = "  ".join(
            f"**{ABILITY_ABBREVS[k]}** {v} ({dnd5e.modifier(v)})"
            for k, v in abilities.items()
        )
        embed.add_field(name="Ability Scores", value=ability_text, inline=False)

        saves = monster.get("saving_throws", [])
        if saves:
            save_text = "  ".join(
                f"{s['name']} {'+' if s['value'] >= 0 else ''}{s['value']}" for s in saves
            )
            embed.add_field(name="Saving Throws", value=save_text, inline=True)

        skills = monster.get("skills", [])
        if skills:
            skill_text = "  ".join(
                f"{s['name']} {'+' if s['value'] >= 0 else ''}{s['value']}" for s in skills
            )
            embed.add_field(name="Skills", value=skill_text[:512], inline=True)

        immunities = monster.get("damage_immunities", [])
        resistances = monster.get("damage_resistances", [])
        vulnerabilities = monster.get("damage_vulnerabilities", [])
        cond_immunities = [c.get("name", "") for c in monster.get("condition_immunities", [])]

        if immunities:
            embed.add_field(name="Damage Immunities", value=", ".join(immunities)[:512], inline=False)
        if resistances:
            embed.add_field(name="Resistances", value=", ".join(resistances)[:512], inline=False)
        if vulnerabilities:
            embed.add_field(name="Vulnerabilities", value=", ".join(vulnerabilities)[:512], inline=True)
        if cond_immunities:
            embed.add_field(name="Condition Immunities", value=", ".join(cond_immunities)[:512], inline=True)

        special = monster.get("special_abilities", [])[:3]
        if special:
            lines = [f"**{s['name']}**: {s.get('desc', '')[:200]}" for s in special]
            embed.add_field(name="Special Abilities", value="\n".join(lines)[:1024], inline=False)

        actions = monster.get("actions", [])[:3]
        if actions:
            lines = [f"**{a['name']}**: {a.get('desc', '')[:200]}" for a in actions]
            embed.add_field(name="Actions", value="\n".join(lines)[:1024], inline=False)

        # ── Add to combat ──────────────────────────────────────────────────────
        footer_text = f"Source: dnd5eapi.co"
        if add_to_combat and interaction.channel_id:
            combat_cog = self.bot.get_cog("Combat")
            encounter = combat_cog._get_encounter(interaction.channel_id) if combat_cog else None

            if not encounter:
                footer_text = "⚠️ No active combat in this channel — start one with `/combat start`."
            else:
                dex_score = abilities.get("dexterity", 10)
                dex_mod = (dex_score - 10) // 2
                if initiative is not None:
                    total_init = initiative
                    roll_text = "(manual)"
                else:
                    roll = random.randint(1, 20)
                    total_init = roll + dex_mod
                    roll_text = f"(rolled {roll} + {dex_mod:+d})"

                from cogs.combat import EncounterParticipant
                encounter.participants.append(
                    EncounterParticipant(
                        owner_id="",
                        character_name=m_name,
                        initiative=total_init,
                        initiative_mod=dex_mod,
                        is_npc=True,
                        npc_hp=int(avg_hp) if isinstance(avg_hp, (int, float)) else 10,
                        npc_max_hp=int(avg_hp) if isinstance(avg_hp, (int, float)) else 10,
                    )
                )
                combat_cog._sort_participants(encounter)
                combat_cog._save_encounter(interaction.channel_id)
                footer_text = f"✅ Added to combat — Initiative {total_init} {roll_text} | HP {avg_hp}"

        embed.set_footer(text=footer_text)
        await interaction.followup.send(embed=embed)

    # ── /lookup spell ─────────────────────────────────────────────────────────

    @lookup_group.command(name="spell", description="Look up a D&D 5e spell")
    @app_commands.describe(name="Spell name (use autocomplete)")
    @app_commands.autocomplete(name=_spell_autocomplete)
    async def lookup_spell(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer()

        try:
            spell = await dnd5e.get_spell(name)
        except RuntimeError as e:
            await interaction.followup.send(f"❌ {e}", ephemeral=True)
            return

        if not spell:
            await interaction.followup.send(
                f"❌ Spell **{name}** not found. Use autocomplete to search.", ephemeral=True
            )
            return

        s_name = spell.get("name", name)
        level = spell.get("level", 0)
        level_text = "Cantrip" if level == 0 else f"Level {level}"
        school = spell.get("school", {}).get("name", "")
        casting_time = spell.get("casting_time", "")
        range_ = spell.get("range", "")
        duration = spell.get("duration", "")
        concentration = spell.get("concentration", False)
        ritual = spell.get("ritual", False)

        components = spell.get("components", [])
        material = spell.get("material", "")
        comp_text = ", ".join(components)
        if "M" in components and material:
            comp_text += f" ({material})"

        classes = [c["name"] for c in spell.get("classes", [])]
        flags = (["Concentration"] if concentration else []) + (["Ritual"] if ritual else [])

        meta_lines = [
            f"**{level_text} {school}**",
            f"**Casting Time:** {casting_time}  •  **Range:** {range_}",
            f"**Components:** {comp_text}",
            f"**Duration:** {duration}",
        ]
        if flags:
            meta_lines.append(f"**Tags:** {', '.join(flags)}")
        if classes:
            meta_lines.append(f"**Classes:** {', '.join(classes)}")

        desc_parts = spell.get("desc", [])
        description = "\n".join(desc_parts)
        higher_parts = spell.get("higher_level", [])
        higher_text = "\n".join(higher_parts)

        embed = discord.Embed(
            title=f"🔮 {s_name}",
            description="\n".join(meta_lines),
            color=discord.Color.purple(),
        )

        if description:
            embed.add_field(
                name="Description",
                value=description[:1024] if len(description) <= 1024 else description[:1021] + "…",
                inline=False,
            )

        if higher_text:
            embed.add_field(name="At Higher Levels", value=higher_text[:512], inline=False)

        damage = spell.get("damage", {})
        if damage:
            dmg_type = damage.get("damage_type", {}).get("name", "")
            dmg_at_slot = damage.get("damage_at_slot_level", {})
            dmg_at_char = damage.get("damage_at_character_level", {})
            dmg_table = dmg_at_slot or dmg_at_char
            if dmg_table and dmg_type:
                dmg_lines = [f"**{k}:** {v} {dmg_type}" for k, v in sorted(dmg_table.items(), key=lambda x: int(x[0]))]
                embed.add_field(name="Damage", value="\n".join(dmg_lines)[:512], inline=True)

        embed.set_footer(text="Source: dnd5eapi.co")
        await interaction.followup.send(embed=embed)

    # ── /lookup item ──────────────────────────────────────────────────────────

    @lookup_group.command(name="item", description="Look up a D&D 5e item or piece of equipment")
    @app_commands.describe(name="Item name (use autocomplete)")
    @app_commands.autocomplete(name=_equipment_autocomplete)
    async def lookup_item(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer()

        try:
            item = await dnd5e.get_equipment(name)
        except RuntimeError as e:
            await interaction.followup.send(f"❌ {e}", ephemeral=True)
            return

        if not item:
            await interaction.followup.send(
                f"❌ Item **{name}** not found. Use autocomplete to search.", ephemeral=True
            )
            return

        i_name = item.get("name", name)
        category = item.get("equipment_category", {}).get("name", "")
        cost = item.get("cost", {})
        cost_text = f"{cost.get('quantity', 0)} {cost.get('unit', 'gp')}" if cost else "—"
        weight = item.get("weight", None)

        if "Weapon" in category:
            title = f"⚔️ {i_name}"
            color = discord.Color.red()
        elif "Armor" in category:
            title = f"🛡️ {i_name}"
            color = discord.Color.blue()
        else:
            title = f"🎒 {i_name}"
            color = discord.Color.orange()

        embed = discord.Embed(title=title, description=f"*{category}*", color=color)

        info_parts = [f"**Cost:** {cost_text}"]
        if weight:
            info_parts.append(f"**Weight:** {weight} lb.")
        embed.add_field(name="Info", value="\n".join(info_parts), inline=True)

        damage = item.get("damage", {})
        if damage:
            dmg_dice = damage.get("damage_dice", "")
            dmg_type = damage.get("damage_type", {}).get("name", "")
            embed.add_field(name="Damage", value=f"{dmg_dice} {dmg_type}", inline=True)

        two_handed = item.get("two_handed_damage", {})
        if two_handed:
            dmg_dice = two_handed.get("damage_dice", "")
            dmg_type = two_handed.get("damage_type", {}).get("name", "")
            embed.add_field(name="Two-Handed", value=f"{dmg_dice} {dmg_type}", inline=True)

        weapon_range = item.get("range", {})
        if weapon_range:
            normal = weapon_range.get("normal", "")
            long_ = weapon_range.get("long", "")
            embed.add_field(
                name="Range",
                value=f"{normal}/{long_} ft." if long_ else f"{normal} ft.",
                inline=True,
            )

        armor_class = item.get("armor_class", {})
        if armor_class:
            base = armor_class.get("base", "")
            dex_bonus = armor_class.get("dex_bonus", False)
            max_bonus = armor_class.get("max_bonus", None)
            ac_text = f"AC {base}"
            if dex_bonus:
                ac_text += " + DEX" + (f" (max {max_bonus})" if max_bonus else "")
            str_min = item.get("str_minimum", 0)
            if str_min:
                ac_text += f" | Requires STR {str_min}"
            stealth = item.get("stealth_disadvantage", False)
            if stealth:
                ac_text += " | Stealth disadvantage"
            embed.add_field(name="Armor Class", value=ac_text, inline=True)

        properties = item.get("properties", [])
        if properties:
            embed.add_field(name="Properties", value=", ".join(p.get("name", "") for p in properties), inline=False)

        desc = item.get("desc", [])
        if desc:
            embed.add_field(name="Description", value="\n".join(desc)[:1024], inline=False)

        embed.set_footer(text="Source: dnd5eapi.co")
        await interaction.followup.send(embed=embed)

    # ── /lookup class ─────────────────────────────────────────────────────────

    @lookup_group.command(name="class", description="Look up a D&D 5e class")
    @app_commands.describe(name="Class name")
    @app_commands.choices(name=CLASS_CHOICES)
    async def lookup_class(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer()

        try:
            cls = await dnd5e.get_class(name)
        except RuntimeError as e:
            await interaction.followup.send(f"❌ {e}", ephemeral=True)
            return

        if not cls:
            await interaction.followup.send(f"❌ Class **{name}** not found.", ephemeral=True)
            return

        c_name = cls.get("name", name)
        hit_die = cls.get("hit_die", "?")
        saving_throws = [s["name"] for s in cls.get("saving_throws", [])]
        proficiencies = [p["name"] for p in cls.get("proficiencies", []) if "Saving" not in p["name"]][:12]
        subclasses = [s["name"] for s in cls.get("subclasses", [])]

        embed = discord.Embed(
            title=f"🏹 {c_name}",
            color=discord.Color.blue(),
        )
        embed.add_field(name="Hit Die", value=f"d{hit_die}", inline=True)
        if saving_throws:
            embed.add_field(name="Saving Throws", value=", ".join(saving_throws), inline=True)
        if proficiencies:
            embed.add_field(
                name="Proficiencies",
                value="\n".join(f"• {p}" for p in proficiencies)[:1024],
                inline=False,
            )
        if subclasses:
            embed.add_field(name="Subclasses", value=", ".join(subclasses)[:512], inline=False)

        spellcasting = cls.get("spellcasting", {})
        if spellcasting:
            sc_ability = spellcasting.get("spellcasting_ability", {}).get("name", "")
            embed.add_field(name="Spellcasting Ability", value=sc_ability, inline=True)
            embed.add_field(
                name="Tip",
                value=f"Use `/spellslots setup` on a {c_name} character to auto-fill spell slots.",
                inline=False,
            )

        embed.set_footer(text="Source: dnd5eapi.co")
        await interaction.followup.send(embed=embed)

    # ── /lookup race ──────────────────────────────────────────────────────────

    @lookup_group.command(name="race", description="Look up a D&D 5e race")
    @app_commands.describe(name="Race name")
    @app_commands.choices(name=RACE_CHOICES)
    async def lookup_race(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer()

        try:
            race = await dnd5e.get_race(name)
        except RuntimeError as e:
            await interaction.followup.send(f"❌ {e}", ephemeral=True)
            return

        if not race:
            await interaction.followup.send(f"❌ Race **{name}** not found.", ephemeral=True)
            return

        r_name = race.get("name", name)
        speed = race.get("speed", 30)
        size = race.get("size", "")
        size_desc = race.get("size_description", "")
        age = race.get("age", "")
        alignment_info = race.get("alignment", "")

        ability_bonuses = race.get("ability_bonuses", [])
        bonus_text = (
            ", ".join(f"{b['ability_score']['name']} +{b['bonus']}" for b in ability_bonuses)
            if ability_bonuses else "None"
        )

        languages = [lang["name"] for lang in race.get("languages", [])]
        lang_desc = race.get("language_desc", "")
        traits = [t["name"] for t in race.get("traits", [])]

        embed = discord.Embed(
            title=f"🧝 {r_name}",
            color=discord.Color.green(),
        )
        embed.add_field(name="Size", value=size, inline=True)
        embed.add_field(name="Speed", value=f"{speed} ft.", inline=True)
        embed.add_field(name="Ability Score Increases", value=bonus_text, inline=False)

        if size_desc:
            embed.add_field(name="Size Details", value=size_desc[:512], inline=False)
        if age:
            embed.add_field(name="Age", value=age[:512], inline=False)
        if alignment_info:
            embed.add_field(name="Alignment", value=alignment_info[:512], inline=False)
        if languages:
            lang_text = ", ".join(languages)
            if lang_desc:
                lang_text += f"\n*{lang_desc[:256]}*"
            embed.add_field(name="Languages", value=lang_text[:512], inline=False)
        if traits:
            embed.add_field(name="Racial Traits", value=", ".join(traits)[:512], inline=False)

        embed.set_footer(text="Source: dnd5eapi.co")
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Lookup(bot))
