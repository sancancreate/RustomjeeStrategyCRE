import re
import pandas as pd

# LAYER 1: Official Real Estate Brand Overrides
# Add any specialized corporate spellings here. If a word isn't here, 
# Layer 2 will automatically translate it phonetically anyway.
OFFICIAL_BRAND_MAP = {
    "रिजन्सी": "Regency",
    "अनंतम": "Anantam",
    "एनएक्सटी": "Nxt",
    "फेज": "Phase",
    "बिल्डिंग": "Building",
    "इमारत": "Building",
    "रोझेटा": "Rosetta",
    "रुस्तमजी": "Rustomjee",
    "लोढा": "Lodha",
    "गोदरेज": "Godrej",
    "शपूरजी": "Shapoorji",
    "पल्लाडिओ": "Palladio",
    "मजला": "Floor",
    "सदनिका": "Flat"
}

def universal_marathi_to_english(text):
    """
    Translates any Marathi/Devanagari text into English using a dual-layer strategy:
    Official brand mapping overrides + an automated phonetic character engine.
    """
    if not text or pd.isna(text):
        return "Not Mentioned"
    
    text = str(text).strip()
    
    # Apply official brand corrections first
    for regional_word, english_word in OFFICIAL_BRAND_MAP.items():
        text = text.replace(regional_word, english_word)
        
    # LAYER 2: Pure Programmatic Phonetic Script Engine
    CONSONANTS = {
        'क': 'k', 'ख': 'kh', 'ग': 'g', 'घ': 'gh', 'ङ': 'n',
        'च': 'ch', 'छ': 'chh', 'ज': 'j', 'झ': 'z', 'ञ': 'n',
        'ट': 't', 'ठ': 'th', 'ड': 'd', 'ढ': 'dh', 'ण': 'n',
        'त': 't', 'थ': 'th', 'द': 'd', 'ध': 'dh', 'न': 'n',
        'प': 'p', 'फ': 'ph', 'ब': 'b', 'भ': 'bh', 'म': 'm',
        'य': 'y', 'र': 'r', 'ल': 'l', 'व': 'v', 'श': 'sh',
        'ष': 'sh', 'स': 's', 'ह': 'h', 'क्ष': 'ksh', 'त्र': 'tr', 'ज्ञ': 'gy',
        'ळ': 'l'
    }
    MATRAS = {
        'ा': 'a', 'ि': 'i', 'ी': 'ee', 'ु': 'u', 'ू': 'oo',
        'े': 'e', 'ै': 'ai', 'ो': 'o', 'ौ': 'au', 'ॅ': 'a', 'ॉ': 'o'
    }
    VOWELS = {
        'अ': 'A', 'आ': 'A', 'इ': 'I', 'ई': 'Ee', 'उ': 'U', 'ऊ': 'Oo',
        'ए': 'E', 'ऐ': 'Ai', 'ओ': 'O', 'औ': 'Au', 'ऑ': 'O', 'अॅ': 'A'
    }
    
    translated_chars = []
    idx = 0
    length = len(text)
    
    while idx < length:
        char = text[idx]
        
        # Keep standard English characters, numbers, and symbols intact
        if ord(char) < 128:
            translated_chars.append(char)
            idx += 1
            continue
            
        if char in VOWELS:
            translated_chars.append(VOWELS[char])
            idx += 1
        elif char in CONSONANTS:
            base_phonetic = CONSONANTS[char]
            
            # Look ahead to handle combination modifiers cleanly
            if idx + 1 < length:
                next_char = text[idx + 1]
                if next_char == '्':  # Halant sound breaker
                    translated_chars.append(base_phonetic)
                    idx += 2
                elif next_char == 'ं':  # Anusvara nasal sound
                    translated_chars.append(base_phonetic + 'an')
                    idx += 2
                elif next_char in MATRAS:  # Vowel modifiers
                    translated_chars.append(base_phonetic + MATRAS[next_char])
                    idx += 2
                elif next_char in CONSONANTS or next_char in VOWELS or next_char == ' ':
                    # Sound blends seamlessly into the next syllable
                    translated_chars.append(base_phonetic + 'a')
                    idx += 1
                else:
                    translated_chars.append(base_phonetic + 'a')
                    idx += 1
            else:
                # Terminal syllable soft-stop rules
                translated_chars.append(base_phonetic)
                idx += 1
        else:
            if char not in ['्', 'ं']:
                translated_chars.append(char)
            idx += 1
            
    # Structure formatting and word title-casing
    final_output = "".join(translated_chars)
    final_output = re.sub(r'\s+', ' ', final_output).strip()
    return final_output.title()

def locate_description_column(df):
    """
    Scans column headings dynamically to find the property description container.
    """
    possible_targets = [
        'property description', 'property_description', 'description', 
        'property details', 'property_details', 'वर्णन', 'मालमत्ता वर्णन'
    ]
    for col in df.columns:
        normalized_col = str(col).strip().lower()
        if normalized_col in possible_targets or any(target in normalized_col for target in possible_targets):
            return col
    if len(df.columns) > 21:
        return df.columns[21]
    return None

def extract_marathi_property_details(text):
    """
    Parses complex property metadata strings and pipes them into the translation engine.
    """
    if pd.isna(text):
        return {
            'Project Name': 'Not Mentioned',
            'Tower Number': 'Not Mentioned',
            'Carpet Area (sq ft)': 0.0,
            'Balcony Area (sq ft)': 0.0,
            'Utility Area (sq ft)': 0.0,
            'Total Area (sq ft)': 0.0,
            'Parking Space': '0'
        }
    
    text = str(text).strip()
    
    # 1. Flexible Project Matching
    project_match = re.search(r'(?:वरील|येथील|मधील)\s+(.*?)\s+(?:प्रोजेक्ट|प्रकल्प)', text)
    raw_project = project_match.group(1).strip() if project_match else "Not Mentioned"
    project_name = universal_marathi_to_english(raw_project)
    
    # 2. Flexible Tower / Building Matching
    tower_match = re.search(r'(?:बिल्डिंग\s+नं\.|इमारत\s+क्र\.)\s*([0-9\w\-]+),(.*?)\s+(?:बिल्डिंग|इमारत)', text)
    if tower_match:
        b_num = tower_match.group(1).strip()
        raw_b_name = tower_match.group(2).strip()
        translated_b_name = universal_marathi_to_english(raw_b_name)
        tower = f"Building {b_num} ({translated_b_name})"
    else:
        alt_tower = re.search(r'([A-Za-z0-9\s\-]+)\s*(?:विंग|टॉवर|टॉवर नं)', text)
        tower = universal_marathi_to_english(alt_tower.group(0).strip()) if alt_tower else "Not Mentioned"
        
    # 3. Component Space Metrics Extraction
    carpet_match = re.search(r'(?:क्षेत्रफळ|चटईक्षेत्र)\s*([0-9.]+)\s*चौ\.\s*फु\.', text)
    carpet_area = float(carpet_match.group(1)) if carpet_match else 0.0
    
    balcony_match = re.search(r'\+\s*([0-9.]+)\s*चौ\.\s*फु\..*?(?:बाल्कनी|गॅलरी)', text)
    balcony_area = float(balcony_match.group(1)) if balcony_match else 0.0
    
    utility_match = re.search(r'\+\s*([0-9.]+)\s*चौ\.\s*फु\..*?(?:युटिलिटी|ड्राय)', text)
    utility_area = float(utility_match.group(1)) if utility_match else 0.0
    
    # Math checksum continuity
    total_area = carpet_area + balcony_area + utility_area
    
    # 4. Parking Space Audit Count
    parking_match = re.search(r'\+\s*(\d+)\s+(?:पोडीयम|पार्किंग|वाहनाचा)', text)
    if parking_match:
        parking_desc = str(parking_match.group(1))
    elif "पार्किंग स्पेस सहित" in text or "पार्किंग" in text:
        parking_desc = "1"
    else:
        parking_desc = "0"

    return {
        'Project Name': project_name,
        'Tower Number': tower,
        'Carpet Area (sq ft)': carpet_area,
        'Balcony Area (sq ft)': balcony_area,
        'Utility Area (sq ft)': utility_area,
        'Total Area (sq ft)': total_area,
        'Parking Space': parking_desc
    }
