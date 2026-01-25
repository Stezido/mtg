#!/usr/bin/env python3
"""
Enhanced converter from Cockatrice XML to Forge card format with ability parsing
"""

import xml.etree.ElementTree as ET
import os
import re
from pathlib import Path

def sanitize_filename(name):
    """Convert card name to valid filename"""
    name = name.lower()
    name = name.replace("'", "").replace("&", "and")
    name = re.sub(r'[^a-z0-9\s-]', '', name)
    name = re.sub(r'\s+', '_', name)
    return name

def parse_mana_cost(mana_str):
    """Convert Cockatrice mana format to Forge format"""
    if not mana_str:
        return ""
    
    result = []
    i = 0
    while i < len(mana_str):
        if i + 2 < len(mana_str) and mana_str[i].isdigit() and mana_str[i+1] in 'WUBRG' and mana_str[i+2] == '/':
            result.append(mana_str[i])
            i += 1
        elif i + 2 < len(mana_str) and mana_str[i] in 'WUBRG' and mana_str[i+1] == '/' and mana_str[i+2] in 'WUBRG':
            result.append(mana_str[i:i+3])
            i += 3
        elif mana_str[i] in 'WUBRG' or mana_str[i].isdigit():
            result.append(mana_str[i])
            i += 1
        else:
            i += 1
    
    return ' '.join(result)

def parse_card_type(type_str):
    """Convert type string to Forge format"""
    if not type_str:
        return ""
    
    type_str = type_str.strip()
    type_str = re.sub(r'\s+', ' ', type_str)
    
    if ' - ' in type_str:
        parts = type_str.split(' - ')
        main_type = parts[0].strip()
        subtypes = ' '.join(parts[1:]).strip()
        return f"{main_type} {subtypes}"
    
    return type_str

def escape_forge_text(text):
    """Escape special characters for Forge format"""
    if not text:
        return ""
    
    text = text.replace('\n', '\\n')
    return text

class AbilityParser:
    """Parse Magic card abilities and convert to Forge syntax"""
    
    def __init__(self):
        self.ability_counter = 1
        self.svars = {}
    
    def parse_abilities(self, text):
        """Parse card text and generate Forge abilities"""
        if not text:
            return [], {}
        
        text = text.replace('\n', ' ').strip()
        abilities = []
        
        # Split by ability separators
        # Common separators: ". ", "\n", "Upkeep—", etc.
        ability_texts = self._split_abilities(text)
        
        for ability_text in ability_texts:
            ability_text = ability_text.strip()
            if not ability_text:
                continue
            
            parsed = self._parse_single_ability(ability_text)
            if parsed:
                abilities.append(parsed)
        
        return abilities, self.svars
    
    def _split_abilities(self, text):
        """Split text into individual abilities"""
        # Split on common ability separators
        # This is a simplified approach - can be extended
        abilities = []
        
        # Split by ". " but keep period with the ability
        parts = text.split('. ')
        for i, part in enumerate(parts[:-1]):
            abilities.append(part + '.')
        if parts[-1]:
            abilities.append(parts[-1])
        
        return abilities
    
    def _parse_single_ability(self, text):
        """Parse a single ability line"""
        text = text.strip()
        
        # Try to match common patterns
        
        # Pattern 1: "Whenever X, Y"
        whenever_match = re.match(r'Whenever\s+(.+?),\s+(.+?)(?:\.|$)', text)
        if whenever_match:
            trigger = whenever_match.group(1)
            effect = whenever_match.group(2)
            return self._create_whenever_ability(trigger, effect, text)
        
        # Pattern 2: "When X, Y"
        when_match = re.match(r'When\s+(.+?),\s+(.+?)(?:\.|$)', text)
        if when_match:
            trigger = when_match.group(1)
            effect = when_match.group(2)
            return self._create_when_ability(trigger, effect, text)
        
        # Pattern 3: "At the beginning of X, Y"
        beginning_match = re.match(r'At the beginning of (.+?),\s+(.+?)(?:\.|$)', text)
        if beginning_match:
            timing = beginning_match.group(1)
            effect = beginning_match.group(2)
            return self._create_beginning_ability(timing, effect, text)
        
        # Pattern 4: "{X}: Y" - Activated ability
        activated_match = re.match(r'\{(.+?)\}:\s+(.+?)(?:\.|$)', text)
        if activated_match:
            cost = activated_match.group(1)
            effect = activated_match.group(2)
            return self._create_activated_ability(cost, effect, text)
        
        # If no pattern matched, return as keyword or plain text
        return None
    
    def _create_whenever_ability(self, trigger, effect, original_text):
        """Create a Whenever trigger ability"""
        result = {}
        
        # Detect trigger type
        if 'attacks' in trigger.lower():
            if 'gnome' in trigger.lower():
                result['T'] = 'Mode$ Attacks | ValidCard$ Creature.YouCtrl+Gnome | TriggerZones$ Battlefield | Execute$ TrigAbility | TriggerDescription$ ' + original_text
            else:
                result['T'] = 'Mode$ Attacks | ValidCard$ Creature.YouCtrl | TriggerZones$ Battlefield | Execute$ TrigAbility | TriggerDescription$ ' + original_text
        
        elif 'deals damage' in trigger.lower():
            if 'you control' in trigger.lower():
                result['T'] = 'Mode$ DamageDone | ValidSource$ Creature.YouCtrl | ValidTarget$ Opponent | TriggerZones$ Battlefield | Execute$ TrigAbility | TriggerDescription$ ' + original_text
            else:
                result['T'] = 'Mode$ DamageDone | ValidTarget$ Opponent | TriggerZones$ Battlefield | Execute$ TrigAbility | TriggerDescription$ ' + original_text
        
        elif 'enters the battlefield' in trigger.lower():
            result['T'] = 'Mode$ ChangesZone | Destination$ Battlefield | ValidCard$ Card.Self | TriggerZones$ Battlefield | Execute$ TrigAbility | TriggerDescription$ ' + original_text
        
        elif 'dies' in trigger.lower():
            result['T'] = 'Mode$ ChangesZone | Origin$ Battlefield | Destination$ Graveyard | ValidCard$ Card.Self | TriggerZones$ Graveyard | Execute$ TrigAbility | TriggerDescription$ ' + original_text
        
        elif 'sacrificed' in trigger.lower():
            result['T'] = 'Mode$ ChangesZone | Origin$ Battlefield | Destination$ Graveyard | ValidCard$ Card.Self | TriggerZones$ Graveyard | Execute$ TrigAbility | TriggerDescription$ ' + original_text
        
        elif 'cast' in trigger.lower():
            result['T'] = 'Mode$ SpellCast | ValidCard$ Card.YouOwn | TriggerZones$ Battlefield | Execute$ TrigAbility | TriggerDescription$ ' + original_text
        
        # Parse effect
        if 'loses' in effect.lower() and 'life' in effect.lower():
            if 'opponent' in effect.lower():
                result['SVar:TrigAbility'] = 'DB$ LoseLife | Defined$ EachOpponent | LifeAmount$ 1'
        
        elif 'gains' in effect.lower() and 'life' in effect.lower():
            result['SVar:TrigAbility'] = 'DB$ GainLife | Defined$ You | LifeAmount$ 1'
        
        elif 'draw' in effect.lower():
            result['SVar:TrigAbility'] = 'DB$ Draw | Defined$ You | NumCards$ 1'
        
        elif 'create' in effect.lower():
            result['SVar:TrigAbility'] = 'DB$ Token | TokenScript$ food'
        
        return result if result.get('T') else None
    
    def _create_when_ability(self, trigger, effect, original_text):
        """Create a When trigger ability"""
        # Similar to Whenever but for single triggers
        return self._create_whenever_ability(trigger, effect, original_text)
    
    def _create_beginning_ability(self, timing, effect, original_text):
        """Create an upkeep/combat ability"""
        result = {}
        
        if 'upkeep' in timing.lower():
            result['T'] = 'Mode$ Phase | Phase$ Upkeep | TriggerZones$ Battlefield | Execute$ TrigAbility | TriggerDescription$ ' + original_text
        elif 'combat' in timing.lower():
            result['T'] = 'Mode$ Phase | Phase$ BeginCombat | TriggerZones$ Battlefield | Execute$ TrigAbility | TriggerDescription$ ' + original_text
        
        # Parse effect similar to Whenever
        if 'loses' in effect.lower() and 'life' in effect.lower():
            result['SVar:TrigAbility'] = 'DB$ LoseLife | Defined$ You | LifeAmount$ 2'
        
        return result if result.get('T') else None
    
    def _create_activated_ability(self, cost, effect, original_text):
        """Create an activated ability"""
        result = {}
        
        # Parse cost
        cost_forge = self._parse_cost(cost)
        
        # Parse effect
        effect_forge = self._parse_effect(effect)
        
        if cost_forge and effect_forge:
            result['A'] = f"AB$ {effect_forge} | Cost$ {cost_forge} | SpellDescription$ {original_text}"
        
        return result if result.get('A') else None
    
    def _parse_cost(self, cost_str):
        """Parse ability cost"""
        cost_str = cost_str.strip()
        
        # Simple T parsing
        if cost_str == 'T':
            return 'T'
        
        # Mana costs
        if re.match(r'^\d+$', cost_str):
            return cost_str
        
        # Complex costs - simplified
        return cost_str.replace('{', '').replace('}', '').replace(',', ' |')
    
    def _parse_effect(self, effect_str):
        """Parse ability effect"""
        effect_str = effect_str.lower().strip()
        
        if 'gain' in effect_str and 'life' in effect_str:
            return 'GainLife | LifeAmount$ 3'
        elif 'draw' in effect_str:
            return 'Draw | NumCards$ 1'
        elif 'damage' in effect_str:
            return 'DealDamage | NumDmg$ 2'
        
        return None

def convert_card(card_elem):
    """Convert a single card element to Forge format"""
    output = []
    
    name = card_elem.findtext('name', '').strip()
    if not name:
        return None
    
    output.append(f"Name:{name}")
    
    prop = card_elem.find('prop')
    if prop is not None:
        mana_cost = prop.findtext('manacost', '').strip()
        if mana_cost:
            mana_cost = parse_mana_cost(mana_cost)
            output.append(f"ManaCost:{mana_cost}")
        else:
            output.append("ManaCost:no cost")
        
        card_type = prop.findtext('type', '').strip()
        if card_type:
            card_type = parse_card_type(card_type)
            output.append(f"Types:{card_type}")
        
        pt = prop.findtext('pt', '').strip()
        if pt:
            output.append(f"PT:{pt}")
        
        loyalty = card_elem.findtext('loyalty', '').strip()
        if loyalty:
            output.append(f"Loyalty:{loyalty}")
    
    # Parse abilities
    text = card_elem.findtext('text', '').strip()
    parser = AbilityParser()
    abilities, svars = parser.parse_abilities(text)
    
    # Add parsed abilities
    for ability in abilities:
        if 'T' in ability:
            output.append(f"T:{ability['T']}")
        if 'A' in ability:
            output.append(f"A:{ability['A']}")
        if 'SVar:TrigAbility' in ability:
            output.append(f"SVar:TrigAbility:{ability['SVar:TrigAbility']}")
    
    # Add oracle text
    if text:
        text = text.replace('&apos;', "'").replace('&quot;', '"').replace('&amp;', '&')
        oracle_text = escape_forge_text(text)
        output.append(f"Oracle:{oracle_text}")
    else:
        output.append("Oracle:")
    
    return '\n'.join(output)

def main():
    """Main conversion function"""
    
    xml_file = '/home/stefan/github/mtg/MSE/exports/Chaos_Brawl.xml'
    output_base_dir = '/home/stefan/github/mtg/forge_cards'
    
    os.makedirs(output_base_dir, exist_ok=True)
    
    tree = ET.parse(xml_file)
    root = tree.getroot()
    cards = root.findall('.//card')
    
    total_cards = 0
    skipped_cards = 0
    
    print(f"Found {len(cards)} cards in XML")
    print(f"Converting to Forge format with ability parsing...\n")
    
    for card_elem in cards:
        name = card_elem.findtext('name', '').strip()
        if not name:
            continue
        
        forge_text = convert_card(card_elem)
        
        if not forge_text:
            skipped_cards += 1
            print(f"Skipped: {name}")
            continue
        
        filename = sanitize_filename(name)
        first_letter = filename[0].lower() if filename else 'z'
        subdir = os.path.join(output_base_dir, first_letter)
        os.makedirs(subdir, exist_ok=True)
        
        filepath = os.path.join(subdir, f"{filename}.txt")
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(forge_text)
        
        total_cards += 1
        is_token = card_elem.find('token') is not None
        token_marker = "[TOKEN]" if is_token else ""
        print(f"✓ {name} {token_marker}")
    
    print(f"\nConversion complete!")
    print(f"Total cards converted: {total_cards}")
    print(f"Skipped: {skipped_cards}")
    print(f"Output directory: {output_base_dir}")

if __name__ == '__main__':
    main()
