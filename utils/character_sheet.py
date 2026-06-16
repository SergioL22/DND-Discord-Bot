from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional

ABILITY_NAMES: List[str] = [
    "Strength",
    "Dexterity",
    "Constitution",
    "Intelligence",
    "Wisdom",
    "Charisma"
]

SKILL_TO_ABILITY: Dict[str, str] = {
    "Acrobatics": "Dexterity",
    "Animal Handling": "Wisdom",
    "Arcana": "Intelligence",
    "Athletics": "Strength",
    "Deception": "Charisma",
    "History": "Intelligence",
    "Insight": "Wisdom",
    "Intimidation": "Charisma",
    "Investigation": "Intelligence",
    "Medicine": "Wisdom",
    "Nature": "Intelligence",
    "Perception": "Wisdom",
    "Performance": "Charisma",
    "Persuasion": "Charisma",
    "Religion": "Intelligence",
    "Sleight of Hand": "Dexterity",
    "Stealth": "Dexterity",
    "Survival": "Wisdom"
}

@dataclass 
class CharacterSheet:
    #Indenity
    owner_id: str
    name: str
    character_class: str
    race: str
    background: str = ""
    alignment: str = ""
    
    #Progression
    level: int = 1
    exp: int = 0
    
    #Core Stats
    abilities: Dict[str, int] = field(
        default_factory=lambda:{
            "strength": 10,
            "dexterity": 10,
            "constitution": 10,
            "intelligence": 10,
            "wisdom": 10,
            "charisma": 10
        }
    )
    
    #Combat
    max_hp: int = 1
    current_hp: int = 1
    temp_hp: int = 0
    armor_class: int = 10
    speed: int = 30
    hit_dice: str = "1d8"
    
    #Proficiencies
    saving_throw_proficiencies: List[str] = field(default_factory = list)
    skill_proficiencies: List[str] = field(default_factory = list)
    
    # Equipment / currency
    inventory: List[str] = field(default_factory=list)
    gold: int = 0
    silver: int = 0
    copper: int = 0
    
    # Inspiration
    inspiration: bool = False

    # Roleplay
    personality_traits: List[str] = field(default_factory=list)
    ideals: List[str] = field(default_factory = list)
    bonds: List[str] = field(default_factory= list)
    flaws: List[str] = field(default_factory = list)
    languages: List[str] = field(default_factory = list)
    
    # Features
    class_features: List[str] = field(default_factory=list)
    racial_traits: List[str] = field(default_factory=list)
    
    # Spellcasting
    spellcasting_ability: Optional[str] = None
    spell_save_dc: int = 0
    spell_attack_bonus: int = 0 
    spells_known: List[str] = field(default_factory=list)
    spells_prepared: List[str] =field(default_factory=list)
    spell_slots: Dict[str, int] = field(default_factory=dict)
    spell_slots_max: Dict[str, int] = field(default_factory=dict)
    
    def __post_init__(self) -> None:
        self._normalize()
        self.validate()
        self.recalculate_spellcasting()
    
    def _normalize(self) -> None:
        self.owner_id = str(self.owner_id).strip()
        self.name = self.name.strip()
        self.character_class = self.character_class.strip()
        self.race = self.race.strip()
        self.background = self.background.strip()
        self.alignment = self.alignment.strip()
        
        normalized_abilities = {k.lower().strip(): int(v) for k,v in self.abilities.items()}
        self.abilities = normalized_abilities
        
        self.saving_throw_proficiencies = sorted(
            {s.lower().strip() for s in self.saving_throw_proficiencies if s.strip()}
        )
        self.skill_proficiencies = sorted(
            {s.lower().strip() for s in self.skill_proficiencies if s.strip()}
        )
        
        self.inventory = [item.strip() for item in self.inventory if item.strip()]
        self.languages = [lang.strip() for lang in self.languages if lang.strip()]
        
        self.personality_traits = [x.strip() for x in self.personality_traits if x.strip()]
        self.ideals = [x.strip() for x in self.ideals if x.strip()]
        self.bonds = [x.strip() for x in self.bonds if x.strip()]
        self.flaws = [x.strip() for x in self.flaws if x.strip()]
        self.class_features = [x.strip() for x in self.class_features if x.strip()]
        self.racial_traits = [x.strip() for x in self.racial_traits if x.strip()]
        
        if self.spellcasting_ability:
            self.spellcasting_ability = self.spellcasting_ability.strip().lower()
    
    def validate(self) -> None:
        if not self.owner_id:
            raise ValueError("Owner_ID is required")
        if not self.name:
            raise ValueError("Name is required")
        if not self.character_class:
            raise ValueError("Character class is required")
        if not self.race:
            raise ValueError("Race is required")
        
        if not(1 <= self.level <= 20):
            raise ValueError("Level must be between 1 and 20")
        if self.exp < 0:
            raise ValueError("xp cannot be negative")
        
        if set(self.abilities.keys()) != set(a.lower() for a in ABILITY_NAMES):
            raise ValueError(f"Abilities must include: {', '.join(ABILITY_NAMES)}")
        for ability, score in self.abilities.items():
            if not(1 <= score <= 30):
                raise ValueError(f"{ability} must be between 1 and 30.")
        
        if self.max_hp < 1:
            raise ValueError("Max_hp must be at least 1")
        if not (0 <= self.current_hp <= self.max_hp):
            raise ValueError("Current_hp must be between 0 and max_hp")
        if self.temp_hp < 0:
            raise ValueError("Temp_hp cannot be negative")
        if self.armor_class < 1:
            raise ValueError("Armor class must be at least 1")
        if self.speed < 0:
            raise ValueError(" Speed cannot be negative")
        
        invalid_saves = [s for s in self.saving_throw_proficiencies if s not in [a.lower() for a in ABILITY_NAMES]]
        if invalid_saves:
            raise ValueError(f"Invalid saving throw proficiencies: {(invalid_saves)}")
        
        invalid_skills = [s for s in self.skill_proficiencies if s not in [k.lower() for k in SKILL_TO_ABILITY.keys()]]
        if invalid_skills:
            raise ValueError(f"Invalid skill proficiencies: {invalid_skills}")
        
        if self.spellcasting_ability and self.spellcasting_ability not in [a.lower() for a in ABILITY_NAMES]:
            raise ValueError("spellcasting_ability must be a valid ability or None.")

        if self.gold < 0 or self.silver < 0 or self.copper < 0:
            raise ValueError("currency values cannot be negative.")
        
        
    @staticmethod
    def ability_modifier(score: int) -> int:
        return (score - 10) // 2
    
    def get_modifier(self, ability: str) -> int:
        key = ability.lower().strip()
        if key not in self.abilities:
            raise ValueError(f" Unknown ability: {ABILITY_NAMES}")
        return self.ability_modifier(self.abilities[key])
    
    def proficiency_bonus(self) -> int:
        return 2 + ((self.level -1) // 4)
    
    def initiative_bonus(self) -> int:
        return self.get_modifier("dexterity")

    def effective_ac(self) -> int:
        return self.armor_class + self.get_modifier("dexterity")
    
    def saving_throw_bonus(self, ability_name: str) -> int:
        key = ability_name.lower().strip()
        valid = [a.lower() for a in ABILITY_NAMES]
        if key not in valid:
            raise ValueError(f"Unknown ability: {ABILITY_NAMES}")
        bonus = self.get_modifier(key)
        if key in self.saving_throw_proficiencies:
            bonus += self.proficiency_bonus()
        return bonus

    def skill_bonus(self, skill_name: str) -> int:
        key = skill_name.lower().strip()
        skill_map = {k.lower(): v for k, v in SKILL_TO_ABILITY.items()}
        if key not in skill_map:
            raise ValueError(f"Unknown skill: {skill_name}")
        base = self.get_modifier(skill_map[key])
        if key in self.skill_proficiencies:
            base += self.proficiency_bonus()
        return base
    
    def passive_perception(self) -> int:
        base = 10 + self.get_modifier("wisdom")
        if "perception" in self.skill_proficiencies:
            base += self.proficiency_bonus()
        return base
    
    def recalculate_spellcasting(self) -> None:
        if not self.spellcasting_ability:
            self.spell_save_dc = 0
            self.spell_attack_bonus = 0
            return
        
        ability_mod = self.get_modifier(self.spellcasting_ability)
        prof = self.proficiency_bonus()
        self.spell_save_dc = 8 + ability_mod + prof
        self.spell_attack_bonus = ability_mod + prof
        
    def adjust_hp(self, delta: int) -> None:
        self.current_hp = max(0, min(self.max_hp, self.current_hp + int(delta)))
        
    def set_temp_hp(self, value: int) -> None:
        value = int(value)
        if value < 0:
            raise ValueError("Temp hp cannot be negative.")
        self.temp_hp = value
        
    def add_item(self, item: str) -> None:
        item = item.strip()
        if not item:
            raise ValueError("Item cannot be empty.")
        self.inventory.append(item)
        
    def remove_item(self, item: str) -> bool:
        target = item.strip().lower()
        for i, inv_item in enumerate(self.inventory):
            if inv_item.lower() == target:
                self.inventory.pop(i)
                return True
        return False
    
    def adjust_currency(self, gp: int = 0, sp: int = 0, cp: int = 0) -> None:
        new_gp = self.gold + int(gp)
        new_sp = self.silver + int(sp)
        new_cp = self.copper + int(cp)
        if new_gp < 0 or new_sp < 0 or new_cp < 0:
            raise ValueError("Currency values cannot be negative.")
        self.gold = new_gp
        self.silver = new_sp
        self.copper = new_cp
        
    def use_spell_slot(self, level: int) -> bool:
        key = str(level)
        current = self.spell_slots.get(key, 0)
        if current <= 0:
            return False
        self.spell_slots[key] = current - 1
        return True

    def restore_spell_slots(self) -> None:
        self.spell_slots = dict(self.spell_slots_max)

    def set_max_spell_slots(self, level: int, count: int) -> None:
        if count < 0:
            raise ValueError("Slot count cannot be negative.")
        key = str(level)
        self.spell_slots_max[key] = count
        self.spell_slots[key] = min(self.spell_slots.get(key, count), count)

    def add_xp(self, amount: int) -> None:
        amount = int(amount)
        if amount < 0:
            raise ValueError("XP amount cannot be negative.")
        self.exp += amount

    def level_up(self, levels: int = 1) -> None:
        levels = int(levels)
        if levels < 1:
            raise ValueError("Level increase must be at least 1.")
        self.level = min(20, self.level + levels)
        self.recalculate_spellcasting()
        
    def summary_line(self) -> str:
        return f"{self.name} (Lv {self.level} {self.race} {self.character_class})"
    
    def combat_snapshot(self) -> Dict[str, Any]:
        return {
            "hp": f"{self.current_hp}/{self.max_hp}",
            "temp_hp": self.temp_hp,
            "ac": self.effective_ac(),
            "initiative": self.initiative_bonus(),
            "speed": self.speed,
            "passive_perception": self.passive_perception(),
        }
        
    def to_dict(self) -> Dict[str, Any]:
          return {
            "owner_id": self.owner_id,
            "name": self.name,
            "character_class": self.character_class,
            "race": self.race,
            "background": self.background,
            "alignment": self.alignment,
            "level": self.level,
            "xp": self.exp,
            "abilities": dict(self.abilities),
            "max_hp": self.max_hp,
            "current_hp": self.current_hp,
            "temp_hp": self.temp_hp,
            "armor_class": self.armor_class,
            "speed": self.speed,
            "hit_dice": self.hit_dice,
            "saving_throw_proficiencies": list(self.saving_throw_proficiencies),
            "skill_proficiencies": list(self.skill_proficiencies),
            "inventory": list(self.inventory),
            "gold": self.gold,
            "silver": self.silver,
            "copper": self.copper,
            "inspiration": self.inspiration,
            "personality_traits": list(self.personality_traits),
            "ideals": list(self.ideals),
            "bonds": list(self.bonds),
            "flaws": list(self.flaws),
            "languages": list(self.languages),
            "class_features": list(self.class_features),
            "racial_traits": list(self.racial_traits),
            "spellcasting_ability": self.spellcasting_ability,
            "spell_save_dc": self.spell_save_dc,
            "spell_attack_bonus": self.spell_attack_bonus,
            "spells_known": list(self.spells_known),
            "spells_prepared": list(self.spells_prepared),
            "spell_slots": dict(self.spell_slots),
            "spell_slots_max": dict(self.spell_slots_max),
        }
          
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CharacterSheet":
        abilities = data.get(
            "abilities",
            {
                "strength": 10,
                "dexterity": 10,
                "constitution": 10,
                "intelligence": 10,
                "wisdom": 10,
                "charisma": 10,
            },
        )
        
        return cls(
            owner_id=str(data.get("owner_id", "")),
            name=str(data.get("name", "")),
            character_class=str(data.get("character_class", "")),
            race=str(data.get("race", "")),
            background=str(data.get("background", "")),
            alignment=str(data.get("alignment", "")),
            level=int(data.get("level", 1)),
            exp=int(data.get("xp", 0)),
            abilities=abilities,
            max_hp=int(data.get("max_hp", 1)),
            current_hp=int(data.get("current_hp", data.get("max_hp", 1))),
            temp_hp=int(data.get("temp_hp", 0)),
            armor_class=int(data.get("armor_class", 10)),
            speed=int(data.get("speed", 30)),
            hit_dice=str(data.get("hit_dice", "1d8")),
            saving_throw_proficiencies=list(data.get("saving_throw_proficiencies", [])),
            skill_proficiencies=list(data.get("skill_proficiencies", [])),
            inventory=list(data.get("inventory", [])),
            gold=int(data.get("gold", 0)),
            silver=int(data.get("silver", 0)),
            copper=int(data.get("copper", 0)),
            personality_traits=list(data.get("personality_traits", [])),
            ideals=list(data.get("ideals", [])),
            bonds=list(data.get("bonds", [])),
            flaws=list(data.get("flaws", [])),
            languages=list(data.get("languages", [])),
            class_features=list(data.get("class_features", [])),
            racial_traits=list(data.get("racial_traits", [])),
            inspiration=bool(data.get("inspiration", False)),
            spellcasting_ability=data.get("spellcasting_ability"),
            spell_save_dc=int(data.get("spell_save_dc", 0)),
            spell_attack_bonus=int(data.get("spell_attack_bonus", 0)),
            spells_known=list(data.get("spells_known", [])),
            spells_prepared=list(data.get("spells_prepared", [])),
            spell_slots=dict(data.get("spell_slots", {})),
            spell_slots_max=dict(data.get("spell_slots_max", {})),
        )