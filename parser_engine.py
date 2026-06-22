import re
import pandas as pd

# Layer 1: Brand name mapping definitions
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
    "सदनिका": "Flat",
    "अेड्रेस": "Address",
    "जीएस": "GS",
    "टाॅवर": "Tower",
    "टॉवर": "Tower",
    "गृहसंकुल": "Complex"
}

def universal_marathi_to_english(text):
    """
    Converts Marathi Devanagari text strings into clean English titles phonetically.
    """
    if not text or pd.isna(text):
        return "Not Mentioned"
    
    text = str(text).strip()
    
    for regional_word, english_word in OFFICIAL_BRAND_MAP.items():
        text = text.replace(regional_word, english_word)
        
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
        if ord(char) < 128:
            translated_chars.append(char)
            idx += 1
            continue
            
        if char in VOWELS:
            translated_chars.append(VOWELS[char])
            idx += 1
        elif char in CONSONANTS:
            base_phonetic = CONSONANTS[char]
            if idx + 1 < length:
                next_char = text[idx + 1]
                if next_char == '्':
                    translated_chars.append(base_phonetic)
                    idx += 2
                elif next_char == 'ं':
                    translated_chars.append(base_phonetic + 'an')
                    idx += 2
                elif next_char in MATRAS:
                    translated_chars.append(base_phonetic + MATRAS[next_char])
                    idx += 2
                else:
                    translated_chars.append(base_phonetic + 'a')
                    idx += 1
            else:
                translated_chars.append(base_phonetic)
                idx += 1
        else:
            if char not in ['्', 'ं']:
                translated_chars.append(char)
            idx += 1
            
    final_output = "".join(translated_chars)
    final_output = re.sub(r'\s+', ' ', final_output).strip()
    return final_output.title()

def locate_description_column(df):
    """
    Scans data headers to auto-match the description source column location.
    """
    possible_targets = [
        'property description', 'property_description', 'description', 
        'property details', 'property_details', 'वर्णन', 'मालमत्ता वर्णन'
    ]
    for col in df.columns:
        normalized_col = str(col).strip().lower()
        if normalized_col in possible_targets or any(target in normalized_col for target in possible_targets):
            return col
    return None

def extract_marathi_property_details(text, row_context=None):
    """
    Robust property detail extraction routine featuring multi-unit conversion 
    mechanisms and cross-tabular column reference fallbacks.
    """
    if pd.isna(text):
        text = ""
    text = str(text).strip()
    
    # 1. Structural Project Name Extraction
    project_name = "Not Mentioned"
    project_match = re.search(r'(?:वरील|येथील|मधील|येणाऱ्या)\s+(.*?)\s+(?:प्रोजेक्ट|प्रकल्प|गृहसंकुल|या मिळकतीवर)', text)
    if project_match:
        project_name = universal_marathi_to_english(project_match.group(1).strip())
    
    # Fallback Option: Extract from existing tabular data if raw match comes up short
    if (project_name == "Not Mentioned" or len(project_name) < 3) and row_context is not None:
        for fallback_col in ['Property', 'Property Name', 'Project', 'Developer']:
            if fallback_col in row_context and pd.notna(row_context[fallback_col]):
                project_name = str(row_context[fallback_col]).strip()
                break

    # 2. Building and Tower Level Extraction 
    tower = "Not Mentioned"
    tower_match = re.search(r'(?:बिल्डिंग\s+नं\.|इमारत\s+क्र\.|टॉवर\s*-\s*)\s*([0-9\w\-]+),(.*?)\s+(?:बिल्डिंग|इमारत|टॉवर)', text)
    if not tower_match:
        tower_match = re.search(r'(?:टॉवर\s*-\s*)\s*([0-9\w\-]+)', text)
        
    if tower_match:
        groups = tower_match.groups()
        b_num = groups[0].strip() if len(groups) > 0 else ""
        raw_b_name = groups[1].strip() if (len(groups) > 1 and groups[1]) else ""
        if raw_b_name:
            tower = f"Tower/Building {b_num} ({universal_marathi_to_english(raw_b_name)})"
        else:
            tower = f"Tower {b_num}"
    else:
        alt_tower = re.search(r'([A-Za-z0-9\s\-]+)\s*(?:विंग|टॉवर|टॉवर नं)', text)
        if alt_tower:
            tower = universal_marathi_to_english(alt_tower.group(0).strip())
            
    if tower == "Not Mentioned" and row_context is not None:
        for fallback_col in ['Building', 'Tower/Wing', 'Tower', 'Wing']:
            if fallback_col in row_context and pd.notna(row_context[fallback_col]):
                tower = str(row_context[fallback_col]).strip()
                break

    # 3. Dynamic Area Calculation Component (Handles sq ft and sq m tracking)
    carpet_area = 0.0
    balcony_area = 0.0
    utility_area = 0.0
    
    # Carpet Target Checks
    m_carpet = re.search(r'([0-9.]+)\s*(?:चौ\.\s*फु\.|चौ\.फु\.)\s*(?:रेरा\s+)?का्?रपेट', text)
    if not m_carpet:
        m_carpet = re.search(r'(?:क्षेत्रफळ|चटईक्षेत्र)\s*([0-9.]+)\s*(?:चौ\.\s*फु\.|चौ\.फु\.)', text)
    if m_carpet:
        carpet_area = float(m_carpet.group(1))
    else:
        # Check for square meter metrics and convert
        m_carpet_m = re.search(r'([0-9.]+)\s*(?:चौ\.\s*मी\.|चौ\.मी\.)\s*(?:रेरा\s+)?का्?रपेट', text)
        if m_carpet_m:
            carpet_area = round(float(m_carpet_m.group(1)) * 10.7639, 2)
            
    if carpet_area == 0.0 and row_context is not None:
        for fallback_col in ['Area', 'Total Usable Area (sq.ft.)', 'Carpet Area']:
            if fallback_col in row_context and pd.notna(row_context[fallback_col]):
                try:
                    carpet_area = float(row_context[fallback_col])
                    break
                except:
                    pass

    # Balcony Target Checks
    m_balcony = re.search(r'([0-9.]+)\s*(?:चौ\.\s*फु\.|चौ\.फु\.)\s*(?:एरिया\s+सह\s*\+?\s*)?.*?बाल्कनी', text)
    if not m_balcony:
        m_balcony = re.search(r'बाल्कनी.*?\s*([0-9.]+)\s*(?:चौ\.\s*फु\.|चौ\.फु\.)', text)
    if m_balcony:
        balcony_area = float(m_balcony.group(1))
    else:
        m_balcony_m = re.search(r'([0-9.]+)\s*(?:चौ\.\s*मी\.|चौ\.मी\.)\s*(?:क्षेत्रफळाची\s+)?बाल्कनी', text)
        if m_balcony_m:
            balcony_area = round(float(m_balcony_m.group(1)) * 10.7639, 2)

    # Utility Target Checks
    m_utility = re.search(r'([0-9.]+)\s*(?:चौ\.\s*फु\.|चौ\.फु\.)\s*.*?युटिलिटी', text)
    if not m_utility:
        m_utility = re.search(r'युटीलिटी.*?\s*([0-9.]+)\s*(?:चौ\.\s*फु\.|चौ\.फु\.)', text)
    if m_utility:
        utility_area = float(m_utility.group(1))
    else:
        m_utility_m = re.search(r'([0-9.]+)\s*(?:चौ\.\s*मी\.|चौ\.मी\.)\s*(?:क्षेत्रफळाचे\s+)?युटीलिटी', text)
        if m_utility_m:
            utility_area = round(float(m_utility_m.group(1)) * 10.7639, 2)

    total_area = round(carpet_area + balcony_area + utility_area, 2)

    # 4. Parking Allocations Analysis 
    parking_desc = "0"
    if "दोन कार पार्किंग" in text or "two car parking" in text.lower():
        parking_desc = "2"
    elif "एक कार पार्किंग" in text or "कार पार्किंग" in text or "पार्किंग" in text:
        parking_desc = "1"
        
    p_num_match = re.search(r'\+\s*(\d+)\s+(?:पोडीयम|पार्किंग|वाहनाचा)', text)
    if p_num_match:
        parking_desc = str(p_num_match.group(1))

    return {
        'Project Name': project_name,
        'Tower Number': tower,
        'Carpet Area (sq ft)': carpet_area,
        'Balcony Area (sq ft)': balcony_area,
        'Utility Area (sq ft)': utility_area,
        'Total Area (sq ft)': total_area,
        'Parking Space': parking_desc
    }
