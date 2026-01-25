#!/usr/bin/env python3
# types Planeswalker do not work in forge there is a indexoutofbounceexception - workarround use creature type
# only "a" folder tested 
"""
Convert Cockatrice XML card format to Forge card scripting format
"""

import xml.etree.ElementTree as ET
import os
import re
from pathlib import Path
import sys

def sanitize_filename(name):
    """Convert card name to valid filename (lowercase, underscores for spaces, no special chars)"""
    name = name.lower()
    name = name.replace("'", "").replace("&", "")
    name = re.sub(r'[^a-z0-9\s-]', '', name)
    name = re.sub(r'\s+', '_', name)
    return name

def parse_mana_cost(mana_str):
    """Convert Cockatrice mana format (e.g., '1BB', '1U/B') to Forge format (e.g., '1 B B', '1 U/B')"""
    if not mana_str:
        return ""
    
    # Handle hybrid mana notation
    result = []
    i = 0
    while i < len(mana_str):
        if i + 2 < len(mana_str) and mana_str[i].isdigit() and mana_str[i+1] in 'WUBRG' and mana_str[i+2] == '/':
            # e.g., "2U/B" - take the 2 first, then handle hybrid
            result.append(mana_str[i])
            i += 1
        elif i + 2 < len(mana_str) and mana_str[i] in 'WUBRG' and mana_str[i+1] == '/' and mana_str[i+2] in 'WUBRG':
            # Hybrid mana e.g., "U/B"
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
    
    # Remove extra spaces and clean up
    type_str = type_str.strip()
    type_str = re.sub(r'\s+', ' ', type_str)
    
    # Handle type with subtypes (e.g., "Creature - Human Warrior")
    # Forge uses spaces to separate, not dashes
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
    
    # Replace newlines with \n for Oracle text
    text = text.replace('\n', '\\n')
    return text

def convert_card(card_elem):
    """Convert a single card element to Forge format"""
    output = []
    
    # Get basic properties
    name = card_elem.findtext('name', '').strip()
    name = re.sub(r'[^a-zA-Z0-9\s]', '', name)
    if not name:
        return None
    
    output.append(f"Name:{name}")
    
    # Get properties
    prop = card_elem.find('prop')
    if prop is not None:
        # Mana cost
        mana_cost = prop.findtext('manacost', '').strip()
        if mana_cost:
            mana_cost = parse_mana_cost(mana_cost)
            output.append(f"ManaCost:{mana_cost}")
        else:
            output.append("ManaCost:no cost")
        
        # Type
        card_type = prop.findtext('type', '').strip()
        if card_type:
            card_type = parse_card_type(card_type)
            output.append(f"Types:{card_type}")
        
        # Power/Toughness
        pt = prop.findtext('pt', '').strip()
        if pt and pt != '*/*':
            output.append(f"PT:{pt}")
        elif pt == '*/*':
            output.append(f"PT:{pt}")
        
        # Loyalty (for Planeswalkers)
        loyalty = card_elem.findtext('loyalty', '').strip()
        if loyalty:
            output.append(f"Loyalty:{loyalty}")
    
    # Get card text
    text = card_elem.findtext('text', '').strip()
    if text:
        # Clean up HTML entities
        text = text.replace('&apos;', "'")
        text = text.replace('&quot;', '"')
        text = text.replace('&amp;', '&')
        
        # For abilities, we'd need complex parsing
        # For now, just put in Oracle
        oracle_text = escape_forge_text(text)
        output.append(f"Oracle:{oracle_text}")
    else:
        output.append("Oracle:")
    
    return '\n'.join(output)

def main():
    """Main conversion function"""
    
    # File paths
    
    if len(sys.argv) < 2:
        print("Usage: python convert_cockatrice_to_forge.py <xml_file>")
        sys.exit(1)
    
    xml_file = sys.argv[1]
    output_base_dir = './forge_cards'
    
    # Create output directory
    os.makedirs(output_base_dir, exist_ok=True)
    
    # Parse XML
    tree = ET.parse(xml_file)
    root = tree.getroot()
    
    # Find all cards
    cards = root.findall('.//card')
    
    total_cards = 0
    skipped_cards = 0
    
    print(f"Found {len(cards)} cards in XML")
    print(f"Converting to Forge format...")
    print()
    
    for card_elem in cards:
        # Check if it's a token
        is_token = card_elem.find('token') is not None
        
        # Get card name
        name = card_elem.findtext('name', '').strip()
        if not name:
            continue
        
        # Convert card
        forge_text = convert_card(card_elem)
        
        if not forge_text:
            skipped_cards += 1
            print(f"Skipped: {name}")
            continue
        
        # Create filename
        filename = sanitize_filename(name)
        
        # Determine subdirectory based on first letter
        first_letter = filename[0].lower() if filename else 'z'
        subdir = os.path.join(output_base_dir, first_letter)
        os.makedirs(subdir, exist_ok=True)
        
        # Write file
        filepath = os.path.join(subdir, f"{filename}.txt")
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(forge_text)
        
        total_cards += 1
        token_marker = "[TOKEN]" if is_token else ""
        print(f"✓ {name} {token_marker}")
    
    print()
    print(f"Conversion complete!")
    print(f"Total cards converted: {total_cards}")
    print(f"Skipped: {skipped_cards}")
    print(f"Output directory: {output_base_dir}")

if __name__ == '__main__':
    main()
