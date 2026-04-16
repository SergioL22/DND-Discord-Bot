import random
import re
from typing import List, Tuple, Dict

# Stores result of the Dice roll:
class DiceRollResult:
    def __init__(self, notation: str, rolls: List[int], modifier: int = 0, advantage: bool = False, disadvantage: bool = False): 
        self.notation = notation
        self.rolls = rolls
        self.modifier = modifier
        self.advantage = advantage
        self.disadvantage = disadvantage
        self.total = sum(rolls) + modifier
        
    def __str__(self):
        rolls_str = ', '.join(str(r) for r in self.rolls)
        
        if self.modifier != 0:
            modifier_str = f" {'+' if self.modifier > 0 else ''}{self.modifier}"
        else:
            modifier_str = ""
        
        advantage_str = ""
        if self.advantage:
            advantage_str = " (Advantage)"
        elif self.disadvantage:
            advantage_str = " (Disadvantage)"
            
        return f"🎲 {self.notation}{advantage_str}\nRolls: [{rolls_str}]{modifier_str}\nTotal: {self.total}"
    
# Rolling Logic
class DiceRoller:
    DICE_PATTERN = re.compile(r'(\d+)d(\d+)\s*([+\-]\s*\d+)?', re.IGNORECASE)
    
    @staticmethod
    def parse_dice_notation(notation: str) -> Tuple[int, int, int]:
        match = DiceRoller.DICE_PATTERN.fullmatch(notation.strip())
        if not match:
            raise ValueError(f"Invalid dice notation: {notation}")
        
        num_dice = int(match.group(1))
        dice_sides = int(match.group(2))
        modifier = int(match.group(3).replace(" ", "")) if match.group(3) else 0
        
        return num_dice, dice_sides, modifier

    @staticmethod
    def roll_dice(num_dice: int, dice_sides: int) -> List[int]:
        return [random.randint(1, dice_sides) for _ in range(num_dice)]
    
    @staticmethod
    def roll(notation: str, advantage: bool = False, disadvantage: bool = False) -> DiceRollResult:
        num_dice, dice_sides, modifier = DiceRoller.parse_dice_notation(notation)
        
        if advantage and disadvantage:
            advantage = disadvantage = False
        
        if advantage or disadvantage:
            first_roll = DiceRoller.roll_dice(num_dice, dice_sides)
            second_roll = DiceRoller.roll_dice(num_dice, dice_sides)
            
            first_total = sum(first_roll)
            second_total = sum(second_roll)
            
            if advantage:
                chosen_roll = first_roll if first_total >= second_total else second_roll
            else:
                chosen_roll = first_roll if first_total <= second_total else second_roll
                
            return DiceRollResult(notation, chosen_roll, modifier, advantage, disadvantage)
        else:
            final_roll = DiceRoller.roll_dice(num_dice, dice_sides)
            return DiceRollResult(notation, final_roll, modifier, advantage, disadvantage)
        
    @staticmethod
    def roll_ability_score() -> int:
        rolls = DiceRoller.roll_dice(4, 6)
        rolls.remove(min(rolls))
        return sum(rolls)

    @staticmethod
    def roll_stats() -> Dict[str, int]:

        abilities = ["Strength", "Dexterity", "Constitution", "Intelligence", "Wisdom", "Charisma"]
        return {ability: DiceRoller.roll_ability_score() for ability in abilities}

    @staticmethod
    def calculate_modifier(ability_score: int) -> int:

        return (ability_score - 10) // 2

    @staticmethod
    def is_valid_notation(notation: str) -> bool:
        try:
            DiceRoller.parse_dice_notation(notation)
            return True
        except ValueError:
            return False