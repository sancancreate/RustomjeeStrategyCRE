import re
import pandas as pd

# Layer 1: Brand, Component, and Alphanumeric Phonetic Mapping Matrix
OFFICIAL_BRAND_MAP = {
    "दि": "The",
    "बाय": "By",
    "अेड्रेस": "Address",
    "जीएस": "GS",
    "टाॅवर": "Tower",
    "टॉवर": "Tower",
    "बिल्डिंग": "Building",
    "इमारत": "Building",
    "गृहसंकुल": "Complex",
    "प्रोजेक्ट": "Project",
    "प्रकल्प": "Project",
    "अनंतम": "Anantam",
    "रिजन्सी": "Regency",
    "एनएक्सटी": "Nxt",
    "फेज": "Phase",
    "मजला": "Floor",
    "सदनिका": "Flat",
    "युटीलिटी": "Utility",
    "युटिलिटी": "Utility",
    "एसएसडब्ल्यु": "SSW",
    "टी": "T",
    "ए": "A",
    "बी": "B",
    "सी": "C",
    "डी": "D"
}

def safe_float(val):
    """
    Safely converts a string to a float. Isolates clean numeric groups 
    to handle typos like duplicate decimal points (e.g., '.44.59').
    """
    if pd.isna(val) or not val:
        return 0.0
    try:
        cleaned = str(val).strip().strip('.')
        # Isolate the first clean float representation sequence found
        match = re.search(r'\d+(?:\.\d+)?', cleaned)
        if match:
            return float(match.group(0))
        return 0.0
    except Exception:
        return 0.0

def universal_marathi_to_english(text):
    """
    Converts Marathi Devanagari text strings into clean English titles phonetically,
    applying key corporate overrides.
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
    Robust property detail extraction engine protected against data-entry formatting errors.
    """
    if pd.isna(text):
        text = ""
    text = str(text).strip()
    
    # 1. Project Name Extraction
    project_name = "Not Mentioned"
    project_match = re.search(r'(?:वरील|yeथील|मधील|येणाऱ्या)\s+(.*?)\s+(?:या\s+)?(?:प्रोजेक्ट|प्रकल्प|गृहसंकुल|या मिळकतीवर)', text)
    if project_match:
        project_name = universal_marathi_to_english(project_match.group(1).strip())
    
    if (project_name == "Not Mentioned" or len(project_name) < 3) and row_context is not None:
        for fallback_col in ['Property', 'Property Name', 'Project', 'Developer']:
            if fallback_col in row_context and pd.notna(row_context[fallback_col]):
                project_name = str(row_context[fallback_col]).strip()
                break

    # 2. Tower / Wing Extraction 
    tower = "Not Mentioned"
    tower_match = re.search(r'(?:बिल्डिंग\s+नं\.|इमारत\s+क्र\.|टॉवर\s*-\s*)\s*([0-9\w\-]+),(.*?)\s+(?:बिल्डिंग|इमारत|टॉवर)', text)
    if not tower_match:
        tower_match = re.search(r'(?:टॉवर\s*-\s*)\s*([0-9\w\-]+)', text)
    if not tower_match:
        tower_match = re.search(r'(?:टॉवर|बिल्डिंग|विंग)\s*(?:नं|क्र)[\s.:-]*([A-Za-z0-9\u0900-\u097F]+)', text)
        
    if tower_match:
        groups = tower_match.groups()
        b_num = groups[0].strip() if len(groups) > 0 else ""
        raw_b_name = groups[1].strip() if (len(groups) > 1 and groups[1]) else ""
        if raw_b_name:
            tower = f"Tower/Building {universal_marathi_to_english(b_num)} ({universal_marathi_to_english(raw_b_name)})"
        else:
            tower = f"Tower {universal_marathi_to_english(b_num)}"
    else:
        alt_tower = re.search(r'([A-Za-z0-9\u0900-\u097F\s\-]+)\s*(?:विंग|टॉवर|टॉवर नं|इमारतीचे नाव)', text)
        if alt_tower:
            tower = universal_marathi_to_english(alt_tower.group(0).strip())
            
    if tower == "Not Mentioned" and row_context is not None:
        for fallback_col in ['Building', 'Tower/Wing', 'Tower', 'Wing']:
            if fallback_col in row_context and pd.notna(row_context[fallback_col]):
                tower = str(row_context[fallback_col]).strip()
                break

    # 3. Floor Number Extraction
    floor_no = "Not Mentioned"
    floor_match = re.search(r'(\d+)\s*[\u0900-\u097Fa-zA-Z]*\s*(?:मजला|मजल्यावरील|माळा)', text)
    if not floor_match:
        floor_match = re.search(r'(?:माळा नं|मजला नं)[\s.:-]*(\d+)', text)
        
    if floor_match:
        floor_no = floor_match.group(1).strip()
        
    if floor_no == "Not Mentioned" and row_context is not None:
        for fallback_col in ['Floor no', 'Floor No', 'Floor', 'Floor Number']:
            if fallback_col in row_context and pd.notna(row_context[fallback_col]):
                floor_no = str(row_context[fallback_col]).strip()
                break

    # 4. Unit / Flat Number Extraction
    unit_no = "Not Mentioned"
    unit_match = re.search(r'(?:सदनिका|फ्लॅट|युनिट|निवासी\s+सदनिका)\s*(?:क्र|नं|नंबर|नो|no|num)?[\s.:-]*([A-Za-z0-9\u0900-\u097F\-\/]+)', text)
    if not unit_match:
        unit_match = re.search(r'(?:क्र|नं|नंबर|नो)[\s.:-]*([A-Za-z0-9\u0900-\u097F\-\/]+)', text)
        
    if unit_match:
        unit_no = universal_marathi_to_english(unit_match.group(1).strip())
        
    if unit_no == "Not Mentioned" and row_context is not None:
        for fallback_col in ['Unit no', 'Unit No', 'Unit', 'Unit Number', 'Flat No', 'Flat no']:
            if fallback_col in row_context and pd.notna(row_context[fallback_col]):
                unit_no = str(row_context[fallback_col]).strip()
                break

    # 5. Component Space Metrics Extraction
    carpet_area = 0.0
    balcony_area = 0.0
    utility_area = 0.0
    
    # Carpet Extraction
    carpet_ft_match = re.search(r'([0-9.]+)\s*(?:चौ\.\s*फु\.|चौ\.फु\.)\s*(?:रेरा\s+)?(?:का्?रपेट|कारपेट)', text)
    if not carpet_ft_match:
        carpet_ft_match = re.search(r'(?:क्षेत्रफळ|चटईक्षेत्र)\s*([0-9.]+)\s*(?:चौ\.\s*फु\.|चौ\.फु\.)', text)
    if not carpet_ft_match:
        carpet_ft_match = re.search(r'म्हणजेच\s*([0-9.]+)\s*(?:चौ\.\s*फु\.|चौ\.फु\.)', text)
        
    if carpet_ft_match:
        carpet_area = safe_float(carpet_ft_match.group(1))
    else:
        carpet_m_match = re.search(r'([0-9.]+)\s*(?:चौ\.\s*मी\.|चौ\.मी\.)\s*(?:रेरा\s+)?(?:का्?रपेट|कारपेट)', text)
        if carpet_m_match:
            carpet_area = round(safe_float(carpet_m_match.group(1)) * 10.76, 2)
            
    if carpet_area == 0.0 and row_context is not None:
        for fallback_col in ['Area', 'Total Usable Area (sq.ft.)', 'Carpet Area']:
            if fallback_col in row_context and pd.notna(row_context[fallback_col]):
                carpet_area = safe_float(row_context[fallback_col])
                if carpet_area > 0.0:
                    break

    # Balcony Extraction
    balcony_ft_match = re.search(r'([0-9.]+)\s*(?:चौ\.\s*फु\.|चौ\.फु\.)\s*(?:एरिया\s+)?(?:क्षेत्रफळाची\s+)?बाल्कनी', text)
    if not balcony_ft_match:
        balcony_ft_match = re.search(r'बाल्कनी.*?\s*([0-9.]+)\s*(?:चौ\.\s*फु\.|चौ\.फु\.)', text)
        
    if balcony_ft_match:
        balcony_area = safe_float(balcony_ft_match.group(1))
    else:
        balcony_m_match = re.search(r'([0-9.]+)\s*(?:चौ\.\s*मी\.|चौ\.मी\.)\s*(?:एरिया\s+)?(?:क्षेत्रफळाची\s+)?बाल्कनी', text)
        if not balcony_m_match:
            balcony_m_match = re.search(r'बाल्कनी.*?\s*([0-9.]+)\s*(?:चौ\.\s*मी\.|चौ\.मी\.)', text)
        if balcony_m_match:
            balcony_area = round(safe_float(balcony_m_match.group(1)) * 10.76, 2)

    # Utility Extraction
    utility_ft_match = re.search(r'([0-9.]+)\s*(?:चौ\.\s*फु\.|चौ\.फु\.)\s*(?:एरिया\s+)?(?:क्षेत्रफळाचे\s+)?(?:युटीलिटी|युटिलिटी|ड्राय)', text)
    if not utility_ft_match:
        utility_ft_match = re.search(r'(?:युटीलिटी|युटिलिटी|ड्राय).*?\s*([0-9.]+)\s*(?:चौ\.\s*फु\.|चौ\.फु\.)', text)
        
    if utility_ft_match:
        utility_area = safe_float(utility_ft_match.group(1))
    else:
        utility_m_match = re.search(r'([0-9.]+)\s*(?:चौ\.\s*मी\.|चौ\.मी\.)\s*(?:एरिया\s+)?(?:क्षेत्रफळाचे\s+)?(?:युटीलिटी|युटिलिटी|ड्राय)', text)
        if not utility_m_match:
            utility_m_match = re.search(r'(?:युटीलिटी|युटिलिटी|ड्राय).*?\s*([0-9.]+)\s*(?:चौ\.\s*मी\.|चौ\.मी\.)', text)
        if utility_m_match:
            utility_area = round(safe_float(utility_m_match.group(1)) * 10.76, 2)

    total_area = round(carpet_area + balcony_area + utility_area, 2)

    # 6. Parking Allocation Scanner
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
        'Floor Number': floor_no,
        'Unit Number': unit_no,
        'Carpet Area (sq ft)': carpet_area,
        'Balcony Area (sq ft)': balcony_area,
        'Utility Area (sq ft)': utility_area,
        'Total Area (sq ft)': total_area,
        'Parking Space': parking_desc
    }
