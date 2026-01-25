#!/usr/bin/env python3
"""
Advanced converter from Cockatrice XML to Forge card format with comprehensive ability parsing
"""

import xml.etree.ElementTree as ET
import os
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional

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
    text = text.replace('\n', '\\n').replace('—', '-')
    return text

class AbilityParser:
    """Comprehensive Magic card ability parser for Forge format"""
    
    def __init__(self):
        self.ability_lines = []
        self.svar_lines = []
        self.svar_counter = 0
    
    def parse_abilities(self, text: str) -> Tuple[List[str], List[str]]:
        """Parse card text and generate Forge abilities and SVars"""
        if not text:
            return [], []
        
        text = text.strip()
        self.ability_lines = []
        self.svar_lines = []
        self.svar_counter = 0
        
        # Split abilities
        ability_blocks = self._split_ability_blocks(text)
        
        for block in ability_blocks:
            block = block.strip()
            if not block:
                continue
            self._parse_ability_block(block)
        
        return self.ability_lines, self.svar_lines
    
    def _split_ability_blocks(self, text: str) -> List[str]:
        """Split text into logical ability blocks"""
        # Replace common separators with a marker
        text = text.replace('\n', ' | NEWLINE | ')
        
        # Split on periods followed by capital letters or triggers
        blocks = re.split(r'(?<=[.!?])\s+(?=[A-Z{])', text)
        
        # Clean up markers
        blocks = [b.replace(' | NEWLINE | ', '\n') for b in blocks]
        
        return blocks
    
    def _parse_ability_block(self, text: str):
        """Parse a single ability block"""
        text = text.strip()
        if not text:
            return
        
        # Check for multiple choice abilities (Choose one —)
        if 'Choose' in text and ('—' in text or '-' in text):
            self._parse_modal_ability(text)
            return
        
        # Triggered abilities
        if text.startswith('Whenever '):
            self._parse_whenever_ability(text)
            return
        
        if text.startswith('When '):
            self._parse_when_ability(text)
            return
        
        if text.startswith('At the beginning of '):
            self._parse_beginning_ability(text)
            return
        
        # Upkeep costs
        if 'Upkeep—' in text or 'Upkeep:' in text:
            self._parse_upkeep_ability(text)
            return
        
        # Activated abilities
        if re.match(r'^\{.+?\}:', text):
            self._parse_activated_ability(text)
            return
        
        # Static abilities
        if any(kw in text for kw in ['gets ', 'have ', 'has ', 'can\'t', 'doesn\'t', 'is ', 'are ']):
            self._parse_static_ability(text)
            return
        
        # Spell effects (cards without costs)
        self._parse_spell_effect(text)
    
    def _parse_modal_ability(self, text: str):
        """Parse Choose one / Choose two abilities"""
        # Extract main trigger/timing
        trigger_match = re.match(r'^(.*?)(Choose (?:one|two|up to \w+).*?)$', text, re.DOTALL)
        
        if trigger_match:
            prefix = trigger_match.group(1).strip()
            choices_text = trigger_match.group(2).strip()
        else:
            choices_text = text
            prefix = ''
        
        # Parse choices
        choices = self._extract_modal_choices(choices_text)
        
        if not choices:
            self._parse_spell_effect(text)
            return
        
        # Create charm ability
        charm_num = len(choices)
        svar_name = self._get_next_svar_name('Choices')
        choice_svars = []
        
        for i, choice in enumerate(choices, 1):
            choice_svar = self._parse_modal_choice(choice, i)
            choice_svars.append(choice_svar)
        
        self.svar_lines.append(f"SVar:{svar_name}:{','.join(choice_svars)}")
        
        if prefix and ('Whenever' in prefix or 'When' in prefix or 'At the beginning' in prefix):
            # Triggered charm
            trigger_line = self._extract_trigger(prefix)
            if trigger_line:
                svar_exec = self._get_next_svar_name('CharmEffect')
                self.svar_lines.append(f"SVar:{svar_exec}:AB$ Charm | CharmNum$ {charm_num} | Choices$ {svar_name}")
                self.ability_lines.append(f"T:{trigger_line} | Execute$ {svar_exec} | TriggerDescription$ {text[:80]}")
        else:
            # Spell charm
            self.ability_lines.append(f"A:SP$ Charm | CharmNum$ {charm_num} | Choices$ {svar_name} | SpellDescription$ {text[:100]}")
    
    def _extract_modal_choices(self, choices_text: str) -> List[str]:
        """Extract individual modal choices"""
        # Match bullet points or lines starting with •
        choices = re.findall(r'[•\-]\s*(.+?)(?=\n[•\-]|\n\n|$)', choices_text, re.DOTALL)
        
        if not choices:
            # Try splitting by newlines
            choices = [c.strip() for c in choices_text.split('\n') if c.strip() and not c.strip().startswith('Choose')]
        
        return [c.strip() for c in choices if c.strip()]
    
    def _parse_modal_choice(self, choice_text: str, index: int) -> str:
        """Parse a single modal choice and return SVar name"""
        choice_svar = self._get_next_svar_name(f'Choice{index}')
        
        # Determine choice type and create ability
        if 'target' in choice_text.lower():
            ability = self._parse_effect_to_ability(choice_text)
        else:
            ability = self._parse_effect_to_ability(choice_text)
        
        if ability:
            self.svar_lines.append(f"SVar:{choice_svar}:{ability}")
        
        return choice_svar
    
    def _parse_whenever_ability(self, text: str):
        """Parse Whenever trigger abilities"""
        match = re.match(r'Whenever\s+(.+?),\s+(.+?)(?:\.|$)', text, re.DOTALL)
        if not match:
            return
        
        trigger_text = match.group(1).strip()
        effect_text = match.group(2).strip()
        
        trigger_line = self._extract_trigger(f'Whenever {trigger_text}')
        if trigger_line:
            svar_name = self._get_next_svar_name('Effect')
            effect = self._parse_effect_to_ability(effect_text)
            if effect:
                self.svar_lines.append(f"SVar:{svar_name}:{effect}")
                self.ability_lines.append(f"T:{trigger_line} | Execute$ {svar_name} | TriggerDescription$ {text[:80]}")
    
    def _parse_when_ability(self, text: str):
        """Parse When trigger abilities"""
        match = re.match(r'When\s+(.+?),\s+(.+?)(?:\.|$)', text, re.DOTALL)
        if not match:
            return
        
        trigger_text = match.group(1).strip()
        effect_text = match.group(2).strip()
        
        trigger_line = self._extract_trigger(f'When {trigger_text}')
        if trigger_line:
            svar_name = self._get_next_svar_name('Effect')
            effect = self._parse_effect_to_ability(effect_text)
            if effect:
                self.svar_lines.append(f"SVar:{svar_name}:{effect}")
                self.ability_lines.append(f"T:{trigger_line} | Execute$ {svar_name} | TriggerDescription$ {text[:80]}")
    
    def _parse_beginning_ability(self, text: str):
        """Parse At the beginning of abilities"""
        match = re.match(r'At the beginning of (.+?),\s+(.+?)(?:\.|$)', text, re.DOTALL)
        if not match:
            return
        
        timing = match.group(1).strip().lower()
        effect_text = match.group(2).strip()
        
        phase_map = {
            'upkeep': 'Upkeep',
            'your upkeep': 'Upkeep',
            'combat': 'BeginCombat',
            'your end step': 'EndOfTurn',
            'end step': 'EndOfTurn',
            'each upkeep': 'Upkeep',
            'your next upkeep': 'Upkeep',
        }
        
        phase = next((v for k, v in phase_map.items() if k in timing), None)
        if not phase:
            return
        
        svar_name = self._get_next_svar_name('Effect')
        effect = self._parse_effect_to_ability(effect_text)
        if effect:
            self.svar_lines.append(f"SVar:{svar_name}:{effect}")
            self.ability_lines.append(f"T:Mode$ Phase | Phase$ {phase} | Execute$ {svar_name} | TriggerDescription$ {text[:80]}")
    
    def _parse_upkeep_ability(self, text: str):
        """Parse Upkeep cost abilities"""
        match = re.search(r'Upkeep[—:]\s*(.+?)(?:\.|$)', text)
        if not match:
            return
        
        cost_text = match.group(1).strip()
        
        # Parse as triggered ability with cost
        svar_name = self._get_next_svar_name('UpkeepEffect')
        effect = self._parse_effect_to_ability(cost_text)
        
        if effect:
            self.svar_lines.append(f"SVar:{svar_name}:{effect}")
            self.ability_lines.append(f"T:Mode$ Phase | Phase$ Upkeep | TriggerZones$ Battlefield | Execute$ {svar_name} | TriggerDescription$ Upkeep— {cost_text}")
    
    def _parse_activated_ability(self, text: str):
        """Parse {Cost}: Effect abilities"""
        match = re.match(r'^(\{.+?\}):\s*(.+?)(?:\.|$)', text, re.DOTALL)
        if not match:
            return
        
        cost_str = match.group(1)
        effect_text = match.group(2).strip()
        
        cost = self._parse_cost(cost_str)
        effect = self._parse_effect_to_ability(effect_text)
        
        if cost and effect:
            self.ability_lines.append(f"A:AB$ {effect} | Cost$ {cost} | SpellDescription$ {text[:100]}")
    
    def _parse_static_ability(self, text: str):
        """Parse static abilities"""
        # Common static patterns
        if 'gets ' in text or 'get ' in text:
            self._parse_pump_static(text)
        elif 'can\'t' in text or 'cannot' in text:
            self._parse_restriction_static(text)
        elif 'has ' in text or 'have ' in text:
            self._parse_keyword_static(text)
        else:
            # Generic static ability
            self.ability_lines.append(f"S:Mode$ Continuous | Description$ {text}")
    
    def _parse_pump_static(self, text: str):
        """Parse pump/debuff static abilities"""
        # Extract pump values
        pump_match = re.search(r'gets?\s+([\+\-]\d+)/([\+\-]\d+)', text)
        if pump_match:
            power = pump_match.group(1)
            tough = pump_match.group(2)
            
            # Determine affected cards
            if 'creatures you control' in text:
                affected = 'Creature.YouCtrl'
            elif 'creature' in text and 'you control' in text:
                affected = 'Creature.YouCtrl'
            elif 'creature you control' in text:
                affected = 'Creature.YouCtrl'
            else:
                affected = 'Card'
            
            # Check for duration
            duration = 'Permanent'
            if 'until end of turn' in text:
                duration = 'EndOfTurn'
            
            self.ability_lines.append(f"S:Mode$ Continuous | Affected$ {affected} | AddPower$ {power} | AddToughness$ {tough} | Duration$ {duration} | Description$ {text}")
    
    def _parse_keyword_static(self, text: str):
        """Parse keyword granting static abilities"""
        keywords = ['vigilance', 'flying', 'trample', 'haste', 'first strike', 'double strike', 
                   'indestructible', 'hexproof', 'shroud', 'reach', 'lifelink', 'menace']
        
        found_keywords = [kw for kw in keywords if kw in text.lower()]
        
        if found_keywords:
            if 'creatures you control' in text:
                affected = 'Creature.YouCtrl'
            else:
                affected = 'Card'
            
            duration = 'Permanent'
            if 'until end of turn' in text:
                duration = 'EndOfTurn'
            
            kw_str = ' & '.join(found_keywords)
            self.ability_lines.append(f"S:Mode$ Continuous | Affected$ {affected} | AddKeyword$ {kw_str} | Duration$ {duration} | Description$ {text}")
    
    def _parse_restriction_static(self, text: str):
        """Parse restriction static abilities"""
        self.ability_lines.append(f"S:Mode$ Continuous | Description$ {text}")
    
    def _parse_spell_effect(self, text: str):
        """Parse instant/sorcery spell effects"""
        effect = self._parse_effect_to_ability(text)
        if effect:
            self.ability_lines.append(f"A:SP$ {effect} | SpellDescription$ {text[:100]}")
    
    def _extract_trigger(self, trigger_text: str) -> Optional[str]:
        """Convert trigger text to Forge format"""
        lower = trigger_text.lower()
        
        # Whenever patterns
        if 'whenever' in lower or 'when' in lower:
            # Remove trigger prefix
            clean = re.sub(r'^(whenever|when)\s+', '', lower)
            
            # Specific trigger types
            if 'enters the battlefield' in clean:
                return f"Mode$ ChangesZone | Destination$ Battlefield | ValidCard$ Card.Self | TriggerZones$ Battlefield"
            
            if 'dies' in clean or 'put into a graveyard' in clean:
                return f"Mode$ ChangesZone | Origin$ Battlefield | Destination$ Graveyard | ValidCard$ Card.Self | TriggerZones$ Graveyard"
            
            if 'attacks' in clean:
                return f"Mode$ Attacks | ValidCard$ Card.Self | TriggerZones$ Battlefield"
            
            if 'discards' in clean:
                if 'you' in clean or 'opponent' in clean:
                    return f"Mode$ Discard | TriggerZones$ Battlefield"
            
            if 'creature' in clean and ('enters' in clean or 'etb' in clean):
                return f"Mode$ ChangesZone | Destination$ Battlefield | TriggerZones$ Battlefield"
            
            if 'cast' in clean:
                return f"Mode$ SpellCast | ValidCard$ Card.YouOwn | TriggerZones$ Battlefield"
            
            if 'taps' in clean or 'tapped' in clean:
                return f"Mode$ Taps | TriggerZones$ Battlefield"
            
            if 'sacrifice' in clean:
                return f"Mode$ ChangesZone | Destination$ Graveyard | TriggerZones$ Graveyard"
        
        # Beginning of phase patterns
        if 'beginning of' in lower or 'upkeep' in lower or 'end of' in lower:
            if 'upkeep' in lower:
                return f"Mode$ Phase | Phase$ Upkeep"
            if 'combat' in lower:
                return f"Mode$ Phase | Phase$ BeginCombat"
            if 'end step' in lower or 'end of turn' in lower:
                return f"Mode$ Phase | Phase$ EndOfTurn"
        
        return None
    
    def _parse_effect_to_ability(self, text: str) -> Optional[str]:
        """Convert effect text to Forge ability factory"""
        lower = text.lower().strip()
        
        # Life gain/loss
        if 'you gain' in lower and 'life' in lower:
            num = self._extract_number(text, 'life')
            return f"GainLife | Defined$ You | LifeAmount$ {num}"
        
        if 'loses' in lower and 'life' in lower and 'opponent' in lower:
            num = self._extract_number(text, 'life')
            return f"LoseLife | Defined$ EachOpponent | LifeAmount$ {num}"
        
        if 'loses' in lower and 'life' in lower:
            num = self._extract_number(text, 'life')
            return f"LoseLife | Defined$ You | LifeAmount$ {num}"
        
        # Draw
        if 'draw' in lower:
            num = self._extract_number(text, 'card')
            return f"Draw | Defined$ You | NumCards$ {num}"
        
        # Damage
        if 'deals' in lower and 'damage' in lower:
            num = self._extract_number(text, 'damage')
            if 'target' in lower:
                return f"DealDamage | NumDmg$ {num} | ValidTgts$ Creature.Other,Player | TgtPrompt$ Select target"
            else:
                return f"DealDamage | NumDmg$ {num} | Defined$ TriggeredPlayer"
        
        # Create tokens
        if 'create' in lower and 'token' in lower:
            amount = self._extract_number(text, 'token')
            if 'food' in lower:
                return f"Token | TokenScript$ food | TokenAmount$ {amount}"
            if 'treasure' in lower:
                return f"Token | TokenScript$ treasure | TokenAmount$ {amount}"
            if 'beer' in lower:
                return f"Token | TokenScript$ beer | TokenAmount$ {amount}"
            if 'gnome' in lower:
                return f"Token | TokenScript$ gnome | TokenAmount$ {amount}"
            if 'goblin' in lower:
                return f"Token | TokenScript$ goblin | TokenAmount$ {amount}"
            return f"Token | TokenScript$ generic | TokenAmount$ {amount}"
        
        # Discard
        if 'discard' in lower:
            if 'target opponent' in lower:
                return "Discard | Mode$ TgtChoose | NumCards$ 1 | ValidTgts$ Player.Opponent"
            else:
                return "Discard | Mode$ TgtChoose | NumCards$ 1"
        
        # Mill
        if 'mill' in lower:
            num = self._extract_number(text, 'card')
            return f"Mill | NumCards$ {num} | Defined$ You"
        
        # Counter spell
        if 'counter' in lower and 'spell' in lower:
            return "Counter | Destination$ Hand"
        
        # Tap
        if 'tap' in lower and 'target' in lower:
            return "Tap | ValidTgts$ Creature | TgtPrompt$ Select target creature"
        
        # Untap
        if 'untap' in lower:
            return "Untap | ValidTgts$ Permanent | TgtPrompt$ Select target permanent"
        
        # Scry
        if 'scry' in lower:
            num = self._extract_number(text, '')
            return f"Scry | ScryNum$ {num}"
        
        # Surveil
        if 'surveil' in lower:
            num = self._extract_number(text, '')
            return f"Surveil | NumCards$ {num}"
        
        # Put counter
        if 'put' in lower and 'counter' in lower:
            counter_type = self._extract_counter_type(text)
            num = self._extract_number(text, 'counter')
            return f"PutCounter | CounterType$ {counter_type} | CounterNum$ {num} | Defined$ Targeted"
        
        # Sacrifice
        if 'sacrifice' in lower:
            if 'creature' in lower:
                return "Sacrifice | SacValid$ Creature"
            else:
                return "Sacrifice | SacValid$ Card"
        
        # Search library
        if 'search' in lower and 'library' in lower:
            return "ChangeZone | Origin$ Library | Destination$ Hand | ChangeType$ Card | ChangeNum$ 1 | Mandatory$ False"
        
        # Return from graveyard
        if 'return' in lower and 'graveyard' in lower and 'battlefield' in lower:
            return "ChangeZone | Origin$ Graveyard | Destination$ Battlefield | ChangeType$ Creature"
        
        return None
    
    def _extract_number(self, text: str, keyword: str = '') -> str:
        """Extract number from text"""
        pattern = r'(\d+)'
        if keyword:
            pattern = rf'(\d+)\s+{keyword}'
        
        match = re.search(pattern, text)
        if match:
            return match.group(1)
        
        # Default numbers based on keyword
        if 'a ' in text.lower() or 'one ' in text.lower():
            return '1'
        if 'two ' in text.lower():
            return '2'
        if 'three ' in text.lower():
            return '3'
        
        return '1'
    
    def _extract_counter_type(self, text: str) -> str:
        """Extract counter type from text"""
        counter_types = {
            '+1/+1': 'P1P1',
            '-1/-1': 'M1M1',
            'drunken': 'DRUNKEN',
            'stun': 'STUN',
            'obsession': 'OBSESSION',
            'charge': 'CHARGE',
            'loyalty': 'LOYALTY',
            'haze': 'HAZE',
            'lost family': 'LOST_FAMILY',
        }
        
        for name, forge_type in counter_types.items():
            if name in text.lower():
                return forge_type
        
        return 'GENERIC'
    
    def _parse_cost(self, cost_str: str) -> str:
        """Parse ability cost"""
        cost_str = cost_str.strip()
        cost_str = cost_str.replace('{', '').replace('}', ' ').strip()
        cost_str = re.sub(r'\s+', ' ', cost_str)
        return cost_str
    
    def _get_next_svar_name(self, base: str) -> str:
        """Generate next SVar name"""
        self.svar_counter += 1
        return f"{base}{self.svar_counter}"

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
    ability_lines, svar_lines = parser.parse_abilities(text)
    
    # Add abilities
    output.extend(ability_lines)
    
    # Add SVars
    output.extend(svar_lines)
    
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
    print(f"Converting to Forge format with comprehensive ability parsing...\n")
    
    for card_elem in cards:
        name = card_elem.findtext('name', '').strip()
        if not name:
            continue
        
        forge_text = convert_card(card_elem)
        
        if not forge_text:
            skipped_cards += 1
            continue
        
        filename = sanitize_filename(name)
        first_letter = filename[0].lower() if filename else 'z'
        subdir = os.path.join(output_base_dir, first_letter)
        os.makedirs(subdir, exist_ok=True)
        
        filepath = os.path.join(subdir, f"{filename}.txt")
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(forge_text)
        
        total_cards += 1
        print(f"✓ {name}")
    
    print(f"\nConversion complete!")
    print(f"Total cards converted: {total_cards}")
    print(f"Skipped: {skipped_cards}")
    print(f"Output directory: {output_base_dir}")

if __name__ == '__main__':
    main()
