import re
import pandas as pd

# Global Mappings for Standardization
DEVANAGARI_DIGITS = {
    '०': '0', '१': '1', '२': '2', '३': '3', '४': '4',
    '५': '5', '६': '6', '७': '7', '८': '8', '९': '9'
}

MARATHI_FLOOR_WORDS = {
    "तळ": "0", "ग्राउंड": "0", "पहिला": "1", "दुसरा": "2", 
    "तिसरा": "3", "चौथा": "4", "पाचवा": "5", "सहावा": "6", 
    "सातवा": "7", "आठवा": "8", "नवा": "9", "दहावा": "10"
}

OFFICIAL_BRAND_MAP = {
    "दि": "The", "बाय": "By", "अेड्रेस": "Address", "जीएस": "GS",
    "टाॅवर": "Tower", "टॉवर": "Tower", "बिल्डिंग": "Building",
    "इमारत": "Building", "गृहसंकुल": "Complex", "प्रोजेक्ट": "Project",
    "प्रकल्प": "Project", "अनंतम": "Anantam", "रिजन्सी": "Regency",
    "एनएक्सटी": "Nxt", "फेज": "Phase", "मजला": "Floor",
    "सदनिका": "Flat", "युटीलिटी": "Utility", "युटिलिटी": "Utility",
    "एसएसडब्ल्यु": "SSW", "टी": "T", "ए": "A", "बी": "B", 
    "सी": "C", "डी": "D"
}

def clean_and_normalize_text(text):
    """
    Standardizes raw text by normalizing Devanagari digits to English numbers
    and cleaning up erratic white space variations.
    """
    if pd.isna(text):
        return ""
    text = str(text).strip()
    for dev, eng in DEVANAGARI_DIGITS.items():
        text = text.replace(dev, eng)
    return text

def safe_float(val):
    """
    Isolates clean numeric sequences to gracefully handle typical typos
    like double decimals or trailing characters.
    """
    if not val:
        return 0.0
    try:
        cleaned = str(val).strip().strip('.')
        match = re.search(r'\d+(?:\.\d+)?', cleaned)
        if match:
            return float(match.group(0))
        return 0.0
    except Exception:
        return 0.0

def universal_marathi_to_english(text):
    """
    Converts Marathi text strings into clean English titles phonetically,
    applying key corporate structural overrides and handling terminal consonants cleanly.
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
                    if idx + 2 == length or text[idx + 1] == ' ':
                        translated_chars.append(base_phonetic)
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
    possible_targets = [
        'property description', 'property_description', 'description', 
        'property details', 'property_details', 'वर्णन', 'मालमत्ता वर्णन'
    ]
    for col in df.columns:
        normalized_col = str(col).strip().lower()
        if normalized_col in possible_targets or any(target in normalized_col for target in possible_targets):
            return col
    return None

def extract_marathi_property_details(raw_text, row_context=None):
    """
    Robust property detail extraction engine protected against Devanagari numeral representations,
    text-based structural floor definitions, complex area equations, and volatile punctuation variations.
    """
    # Pre-parse normalization phase
    text = clean_and_normalize_text(raw_text)
    
    # 1. Project Name Extraction
    project_name = "Not Mentioned"
    project_match = re.search(r'(?:वरील|येथील|मधील|येणाऱ्या|स्थित)\s+(.*?)\s+(?:या\s+)?(?:प्रोजेक्ट|प्रकल्प|गृहसंकुल|इमारत|या मिळकतीवर)', text)
    if project_match:
        project_name = universal_marathi_to_english(project_match.group(1).strip())
    
    if (project_name == "Not Mentioned" or len(project_name) < 3) and row_context is not None:
        for fallback_col in ['Property', 'Property Name', 'Project', 'Developer']:
            if fallback_col in row_context and pd.notna(row_context[fallback_col]):
                project_name = str(row_context[fallback_col]).strip()
                break

    # 2. Tower / Wing Extraction
    tower = "Not Mentioned"
    tower_match = re.search(r'(?:बिल्डिंग|इमारत|टॉवर|विंग)\s*(?:नं|क्र|नंबर)?[\s.:-]*([A-Za-z0-9\u0900-\u097F\-]+)', text)
    if tower_match:
        tower = f"Tower {universal_marathi_to_english(tower_match.group(1).strip())}"
    else:
        alt_tower = re.search(r'([A-Za-z0-9\u0900-\u097F\-]+)\s*(?:विंग|टॉवर|इमारतीचे नाव)', text)
        if alt_tower:
            tower = universal_marathi_to_english(alt_tower.group(1).strip())
            
    if tower == "Not Mentioned" and row_context is not None:
        for fallback_col in ['Building', 'Tower/Wing', 'Tower', 'Wing']:
            if fallback_col in row_context and pd.notna(row_context[fallback_col]):
                tower = str(row_context[fallback_col]).strip()
                break

    # 3. Floor Number Extraction
    floor_no = "Not Mentioned"
    for word, num in MARATHI_FLOOR_WORDS.items():
        if word in text:
            floor_no = num
            break
            
    if floor_no == "Not Mentioned":
        floor_match = re.search(r'(\d+)\s*(?:वे|वा|वेळ|मजला|मजल्यावरील|माळा)', text)
        if not floor_match:
            floor_match = re.search(r'(?:माळा नं|मजला नं|मजला)[\s.:-]*(\d+)', text)
        if floor_match:
            floor_no = floor_match.group(1).strip()
        
    if floor_no == "Not Mentioned" and row_context is not None:
        for fallback_col in ['Floor no', 'Floor No', 'Floor', 'Floor Number']:
            if fallback_col in row_context and pd.notna(row_context[fallback_col]):
                floor_no = str(row_context[fallback_col]).strip()
                break

    # High-floor sanity filter: check for leaked unit numbers in fallback columns
    try:
        if floor_no != "Not Mentioned" and int(floor_no) > 120:
            floor_no = "Not Mentioned"
    except ValueError:
        pass

    # 4. Unit / Flat Number Extraction
    unit_no = "Not Mentioned"
    unit_match = re.search(r'(?:सदनिका|फ्लॅट|युनिट|दुकान|कार्यालय|निवासी\s+सदनिका)\s*(?:क्र|नं|नंबर|नो|no|num)?[\s.:-]*([A-Za-z0-9\-\/]+)', text)
    if not unit_match:
        unit_match = re.search(r'(?:क्र|नं|नंबर|नो)[\s.:-]*([A-Za-z0-9\-\/]+)', text)
        
    if unit_match:
        unit_no = unit_match.group(1).strip()
        
    if unit_no == "Not Mentioned" and row_context is not None:
        for fallback_col in ['Unit no', 'Unit No', 'Unit', 'Unit Number', 'Flat No', 'Flat no', 'Floor No', 'Floor no']:
            if fallback_col in row_context and pd.notna(row_context[fallback_col]):
                val_str = str(row_context[fallback_col]).strip()
                if len(val_str) >= 3 or (unit_no == "Not Mentioned" and val_str != "Not Mentioned"):
                    unit_no = val_str
                    break

    # 5. Component Space Metrics Extraction (Upgraded for Mathematical Expressions & Chains)
    carpet_area = 0.0
    balcony_area = 0.0
    utility_area = 0.0
    
    # Pre-clean: Remove parenthetical meter conversions to avoid regex confusion (e.g., "(47.43 चौ.मी.)")
    clean_text_for_area = re.sub(r'\([\d.]+\s*चौ\.\s*मी\.\)', '', text)
    clean_text_for_area = re.sub(r'\([\d.]+\s*चौ\.मी\.\)', '', clean_text_for_area)

    # Strategy A: Check for structured math equation formats containing '+'
    if '+' in clean_text_for_area:
        parts = clean_text_for_area.split('+')
        for part in parts:
            part = part.strip()
            num_match = re.search(r'([0-9.]+)', part)
            if num_match:
                val = safe_float(num_match.group(1))
                if "कारपेट" in part or "चटईक्षेत्र" in part:
                    if "चौ.मी" in part or "चौ. मी" in part:
                        carpet_area = round(val * 10.76, 2)
                    else:
                        carpet_area = val
                elif "बाल्कनी" in part or "डेक" in part:
                    if "चौ.मी" in part or "चौ. मी" in part:
                        balcony_area = round(val * 10.76, 2)
                    else:
                        balcony_area = val
                elif "युटीलिटी" in part or "युटिलिटी" in part or "ड्राय" in part:
                    if "चौ.मी" in part or "चौ. मी" in part:
                        utility_area = round(val * 10.76, 2)
                    else:
                        utility_area = val
                elif parts.index(part) == 0:
                    if "चौ.मी" in part or "चौ. मी" in part:
                        carpet_area = round(val * 10.76, 2)
                    else:
                        carpet_area = val

    # Strategy B: Fallback to direct lookarounds if no expression layout is found
    if carpet_area == 0.0:
        carpet_ft_match = re.search(r'([0-9.]+)\s*(?:चौ\.\s*फु\.|चौ\.फु\.|चौ.फूट|स्क्वेअर फूट)\s*(?:रेरा\s+)?(?:कारपेट|कार्पेट)', clean_text_for_area)
        if not carpet_ft_match:
            carpet_ft_match = re.search(r'(?:क्षेत्रफळ|चटईक्षेत्र|कारपेट क्षेत्रफळ)\s*([0-9.]+)\s*(?:चौ\.\s*फु\.|चौ\.फु\.)', clean_text_for_area)
        if carpet_ft_match:
            carpet_area = safe_float(carpet_ft_match.group(1))
        else:
            carpet_m_match = re.search(r'([0-9.]+)\s*(?:चौ\.\s*मी\.|चौ\.मी\.)\s*(?:रेरा\s+)?(?:कारपेट|कार्पेट)', clean_text_for_area)
            if carpet_m_match:
                carpet_area = round(safe_float(carpet_m_match.group(1)) * 10.76, 2)

    if balcony_area == 0.0:
        balcony_ft_match = re.search(r'([0-9.]+)\s*(?:चौ\.\s*फु\.|चौ\.फु\.)\s*(?:एरिया\s+)?(?:क्षेत्रफळाची\s+)?बाल्कनी', clean_text_for_area)
        if not balcony_ft_match:
            balcony_ft_match = re.search(r'बाल्कनी.*?\s*([0-9.]+)\s*(?:चौ\.\s*फु\.|चौ\.फु\.)', clean_text_for_area)
        if balcony_ft_match:
            balcony_area = safe_float(balcony_ft_match.group(1))
        else:
            balcony_m_match = re.search(r'([0-9.]+)\s*(?:चौ\.\s*मी\.|चौ\.मी\.)\s*(?:एरिया\s+)?(?:क्षेत्रफळाची\s+)?बाल्कनी', clean_text_for_area)
            if not balcony_m_match:
                balcony_m_match = re.search(r'बाल्कनी.*?\s*([0-9.]+)\s*(?:चौ\.\s*मी\.|चौ\.मी\.)', clean_text_for_area)
            if balcony_m_match:
                balcony_area = round(safe_float(balcony_m_match.group(1)) * 10.76, 2)

    if utility_area == 0.0:
        utility_ft_match = re.search(r'([0-9.]+)\s*(?:चौ\.\s*फु\.|चौ\.फु\.)\s*(?:एरिया\s+)?(?:क्षेत्रफळाचे\s+)?(?:युटीलिटी|युटिलिटी|ड्राय)', clean_text_for_area)
        if not utility_ft_match:
            utility_ft_match = re.search(r'(?:युटीलिटी|युटिलिटी|ड्राय).*?\s*([0-9.]+)\s*(?:चौ\.\s*फु\.|चौ\.फु\.)', clean_text_for_area)
        if utility_ft_match:
            utility_area = safe_float(utility_ft_match.group(1))
        else:
            utility_m_match = re.search(r'([0-9.]+)\s*(?:चौ\.\s*मी\.|चौ\.मी\.)\s*(?:एरिया\s+)?(?:क्षेत्रफळाचे\s+)?(?:युटीलिटी|युटिलिटी|ड्राय)', clean_text_for_area)
            if not utility_m_match:
                utility_m_match = re.search(r'(?:युटीलिटी|युटिलिटी|ड्राय).*?\s*([0-9.]+)\s*(?:चौ\.\s*मी\.|चौ\.मी\.)', clean_text_for_area)
            if utility_m_match:
                utility_area = round(safe_float(utility_m_match.group(1)) * 10.76, 2)

    if carpet_area == 0.0 and row_context is not None:
        for fallback_col in ['Area', 'Total Usable Area (sq.ft.)', 'Carpet Area']:
            if fallback_col in row_context and pd.notna(row_context[fallback_col]):
                carpet_area = safe_float(row_context[fallback_col])
                if carpet_area > 0.0:
                    break

    # Explicit handling for "असे एकूण क्षेत्रफळ [Total] चौ.फु." style overrides
    total_override_match = re.search(r'असे\s+एकूण\s+क्षेत्रफळ\s*([0-9.]+)\s*(?:चौ\.\s*फु\.|चौ\.फु\.)', clean_text_for_area)
    if total_override_match:
        total_area = safe_float(total_override_match.group(1))
    else:
        total_area = round(carpet_area + balcony_area + utility_area, 2)

    # 6. Parking Allocation Scanner
    parking_desc = "0"
    lower_text = text.lower()
    if "दोन कार पार्किंग" in text or "two car parking" in lower_text or "फोर व्हीラー पार्किंग २" in text:
        parking_desc = "2"
    elif "एक कार पार्किंग" in text or "कार पार्किंग" in text or "पार्किंग" in text or "four wheeler parking" in lower_text:
        parking_desc = "1"
        
    p_num_match = re.search(r'\+\s*(\d+)\s+(?:पोडीयम|पार्किंग|वाहनाचा|फोर व्हीलर)', text)
    if p_num_match:
        parking_desc = str(p_num_match.group(1))

    return {
        'Project Name': project_name,
        'Tower Number': tower,
        'Floor Number': floor_no,
        'Unit Number': unit_no,
        'Carpet Area (sq ft)': carpet_area,
        'Balcony Area (sq ft)': balcony_area,
        'Utility Area (sq ft)': utility_area,
        'Total Area (sq ft)': total_area,
        'Parking Space': parking_desc
    }
