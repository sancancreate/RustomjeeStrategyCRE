import re
import pandas as pd

# Global Devanagari to Arabic Digit Mapping
DEVANAGARI_DIGITS = {
    '०': '0', '१': '1', '२': '2', '३': '3', '४': '4',
    '५': '5', '६': '6', '७': '7', '८': '8', '९': '9'
}

# Exhaustive High-Rise Ordinal Mapping for Marathi Floors
MARATHI_FLOOR_WORDS = {
    "तळ": "0", "ग्राउंड": "0", "फ्लोअर": "0", "तळमजला": "0",
    "पहिला": "1", "पहिले": "1", "पहिल्या": "1", "प्रथमा": "1",
    "दुसरा": "2", "दुसरे": "2", "दुसऱ्या": "2",
    "तिसरा": "3", "तिसरे": "3", "तिसऱ्या": "3",
    "चौथा": "4", "चौथे": "4", "चौथ्या": "4",
    "पाचवा": "5", "पाचवे": "5", "पाचव्या": "5",
    "सहावा": "6", "सहावे": "6", "सहाव्या": "6",
    "सातवा": "7", "सातवे": "7", "सातव्या": "7",
    "आठवा": "8", "आठवे": "8", "आठव्या": "8",
    "नवा": "9", "नववे": "9", "नवव्या": "9", "नववा": "9",
    "दहावा": "10", "दहावे": "10", "दहाव्या": "10",
    "अकरावा": "11", "अकरावे": "11", "अकराव्या": "11",
    "बारावा": "12", "बारावे": "12", "बाराव्या": "12",
    "तेरावा": "13", "तेरावे": "13", "तेराव्या": "13",
    "चौदावा": "14", "चौदावे": "14", "चौदाव्या": "14",
    "पंधरावा": "15", "पंधरावे": "15", "पंधराव्या": "15",
    "सोळावा": "16", "सोळावे": "16", "सोळव्या": "16", "सोळाव्या": "16",
    "सतरावा": "17", "सतरावे": "17", "सतराव्या": "17",
    "अठरावा": "18", "अठरावे": "18", "अठराव्या": "18",
    "एकोणिसावा": "19", "एकोणिसावे": "19", "एकोणिसाव्या": "19", "एकोणिसव्या": "19",
    "विसावा": "20", "विसावे": "20", "विसाव्या": "20",
    "एकविसावा": "21", "एकविसावे": "21", "एकविसाव्या": "21",
    "बाविसावा": "22", "बाविसावे": "22", "बाविसाव्या": "22",
    "तेविसावा": "23", "तेविसावे": "23", "तेविसाव्या": "23",
    "चोविसावा": "24", "चोविसावे": "24", "चोविसाव्या": "24",
    "पंचविसावा": "25", "पंचविसावे": "25", "पंचविसाव्या": "25",
    "सव्विसावा": "26", "सव्विसावे": "26", "सव्विसाव्या": "26",
    "सत्ताविसावा": "27", "सत्ताविसावे": "27", "सत्ताविसाव्या": "27",
    "अठ्ठाविसावा": "28", "अठ्ठाविसावे": "28", "अठ्ठाविसाव्या": "28",
    "एकणतिसावा": "29", "एकणतिसावे": "29", "एकणतिसाव्या": "29", "एकोणतिसावा": "29",
    "तिसावा": "30", "तिसावे": "30", "तिसाव्या": "30",
    "एकतिसावा": "31", "बत्तीसावा": "32", "तेहतीसावा": "33", "चौतीसावा": "34", "पस्तीसावा": "35"
}

CARPET_KEYWORDS = ["कार्पेट", "कारपेट", "चटई", "carpet"]
BALCONY_KEYWORDS = ["बाल्कनी", "बालकॉनी", "गॅलरी", "गॅलेरी", "balcony", "gallery", "डेक", "deck"]
UTILITY_KEYWORDS = ["युटिलिटी", "युटीलिटी", "युटिलीटी", "यूटिलीटी", "यूटिलिटी", "ड्राय", "सर्व्हिस", "utility", "dry"]

def clean_and_normalize_text(text):
    if pd.isna(text): 
        return ""
    text = str(text).replace('\xa0', ' ').replace('\t', ' ').replace('\n', ' ').replace('\r', ' ')
    text = re.sub(r'\s+', ' ', text).strip()
    for dev, eng in DEVANAGARI_DIGITS.items():
        text = text.replace(dev, eng)
    return text

def parse_unit_conversion(value_str, unit_str):
    try:
        val = float(value_str)
        unit_lower = str(unit_str).lower()
        # Direct conversion selector matching square meter keywords
        if any(m in unit_lower for m in ['मी', 'मीटर', 'mtr', 'mt', 'sqm', 'sq.m']):
            return round(val * 10.7639, 2)
        return round(val, 2)
    except Exception:
        return 0.0

def extract_all_areas_globally(text):
    """
    Global Segment Tokenizer: Sweeps the text for mathematical metrics,
    isolates each block, evaluates look-ahead and look-behind contexts,
    and applies direct scaling rules.
    """
    carpet = 0.0
    balcony = 0.0
    utility = 0.0
    
    # Standardize string expressions for robust splitting
    normalized = re.sub(r'\s*\+\s*', ' + ', text)
    
    # Regex matching all digits associated with an area label
    pattern = r'(\d+(?:\.\d+)?)\s*(चौ\.?\s*मी\.?|मीटर|mtrs?|mt|sq\.?\s*m|sqft|ft|फूट|फिट|एरिया|क्षेत्रफळ)'
    matches = list(re.finditer(pattern, normalized, re.IGNORECASE))
    
    for i, match in enumerate(matches):
        val_str = match.group(1)
        unit_str = match.group(2)
        
        # Isolate the text between this measurement and the next one
        start_idx = match.end()
        end_idx = matches[i+1].start() if i + 1 < len(matches) else len(normalized)
        look_ahead = normalized[start_idx:min(end_idx, start_idx + 50)].lower()
        
        # Check backward context up to 40 characters
        look_behind = normalized[max(0, match.start() - 40):match.start()].lower()
        
        # Run conversion rule
        sqft_val = parse_unit_conversion(val_str, unit_str)
        
        # Route to correct metric basket based on context mapping
        if any(k in look_ahead for k in UTILITY_KEYWORDS) or any(k in look_behind for k in UTILITY_KEYWORDS):
            utility += sqft_val
        elif any(k in look_ahead for k in BALCONY_KEYWORDS) or any(k in look_behind for k in BALCONY_KEYWORDS):
            balcony += sqft_val
        elif any(k in look_ahead for k in CARPET_KEYWORDS) or any(k in look_behind for k in CARPET_KEYWORDS):
            carpet += sqft_val
        else:
            # Fallback Rule: If it is the primary number in an equation block,
            # or if the keyword is mentioned at the end of the text, assign to Carpet.
            if i == 0:
                carpet += sqft_val
            elif any(k in normalized.lower() for k in CARPET_KEYWORDS) and carpet == 0.0:
                carpet += sqft_val
            else:
                carpet += sqft_val
                
    return round(carpet, 2), round(balcony, 2), round(utility, 2)

def locate_column_by_keywords(df, keywords):
    for col in df.columns:
        if any(k in str(col).lower() for k in keywords): 
            return col
    return None

def extract_marathi_property_details(raw_text, row_context=None, project_col=None, tower_col=None, unit_col=None):
    text = clean_and_normalize_text(raw_text)
    
    # 1. Project Identity Extraction
    project_name = "Not Mentioned"
    if row_context is not None and project_col in row_context and pd.notna(row_context[project_col]):
        project_name = str(row_context[project_col]).strip()
        if project_name.endswith('.0'): project_name = project_name[:-2]
    else:
        project_match = re.search(r'([\w\s\-]+?)\s*(?:प्रोजेक्ट|फेज|प्रकल्प|गार्डन्स|रेसिडेन्सी)', text, re.IGNORECASE)
        if project_match: project_name = project_match.group(1).strip()

    # 2. Tower / Wing Target Extraction
    tower_wing = "Not Mentioned"
    if row_context is not None and tower_col in row_context and pd.notna(row_context[tower_col]):
        tower_wing = str(row_context[tower_col]).strip()
        if tower_wing.endswith('.0'): tower_wing = tower_wing[:-2]
    else:
        tower_match = re.search(r'(?:बिल्डिंग|बिल्डींग|टाॅवर|टॉवर|विंग|बिल्डिंग नं|बिल्डींग नं)\s*(?:नं|क्र|क्रमांक|नंबर)?\.?\s*([A-Za-z0-9\-]+)', text, re.IGNORECASE)
        if tower_match: tower_wing = tower_match.group(1).strip()

    # 3. Floor Level Extraction (Sharpened)
    floor_num = "Not Mentioned"
    normalized_floor_text = text.replace(' ', '')
    
    floor_found = False
    for word, replacement in MARATHI_FLOOR_WORDS.items():
        if word in normalized_floor_text:
            floor_num = replacement
            floor_found = True
            break
            
    if not floor_found:
        # Match standalone numbers preceding floor markers like "4 था मजला", "12 मजला"
        floor_digit_match = re.search(r'(\d+)\s*(?:वे|वे|था|रा|री|ा)?\s*(?:मजला|फ्लोअर|floor)', text, re.IGNORECASE)
        if floor_digit_match:
            floor_num = floor_digit_match.group(1).strip()
        else:
            floor_word_match = re.search(r'([A-Za-z0-9\u0900-\u097F]+)\s*(?:मजला|फ्लोअर)', text, re.IGNORECASE)
            if floor_word_match:
                floor_num = floor_word_match.group(1).strip()

    if floor_num.endswith('.0'): floor_num = floor_num[:-2]

    # 4. Unit / Flat Number Extraction (Sharpened Boundary Controls)
    unit_num = "Not Mentioned"
    if row_context is not None and unit_col in row_context and pd.notna(row_context[unit_col]):
        val = row_context[unit_col]
        if isinstance(val, (int, float)):
            if float(val).is_integer(): unit_num = str(int(val))
            else: unit_num = str(val).strip()
        else:
            unit_num = str(val).strip()
    else:
        # Matches numbers following unit tokens and breaks cleanly at trailing spaces or punctuation
        unit_match = re.search(r'(?:सदनिका|फ्लॅट|शॉप|दुकान|गाळा|फ्लॅट नं|सदनिका नं|फ्लॅट क्र|सदनिका क्र)\s*(?:नं|क्र|क्रमांक|नंबर)?\.?\s*([A-Za-z0-9\-/_]+)', text, re.IGNORECASE)
        if unit_match:
            raw_unit = unit_match.group(1).strip()
            unit_num = re.split(r'[\s,]', raw_unit)[0]

    if unit_num.endswith('.0'): unit_num = unit_num[:-2]

    # 5. Global Tokenizer Area Calculations
    carpet_area, balcony_area, utility_area = extract_all_areas_globally(text)
    total_area = round(carpet_area + balcony_area + utility_area, 2)

    # 6. Parking Allocation Scanner
    parking_val = 0
    triggers = ["फोर व्हीラー", "फोर व्हीलर", "फोर व्हिलर", "कार पार्किंग", "कार पार्कींग"]
    found_trigger_idx = -1
    
    for trigger in triggers:
        idx = text.find(trigger)
        if idx != -1:
            found_trigger_idx = idx
            break
            
    if found_trigger_idx != -1:
        preceding_text = text[:found_trigger_idx].strip()
        words = re.findall(r'\S+', preceding_text)
        
        if words:
            last_word = words[-1]
            num_map = {"एक": 1, "दोन": 2, "तीन": 3, "चार": 4}
            if last_word in num_map: parking_val = num_map[last_word]
            elif last_word.isdigit(): parking_val = int(last_word)
            else: parking_val = 1
        else:
            parking_val = 1
    elif "पार्किंग" in text or "पार्कींग" in text:
        parking_val = 1

    return {
        'Project Name': project_name,
        'Tower/Wing': tower_wing,
        'Floor Number': floor_num,
        'Unit Number': unit_num,
        'Carpet Area (sq ft)': carpet_area,
        'Balcony Area (sq ft)': balcony_area,
        'Utility Area (sq ft)': utility_area,
        'Total Area (sq ft)': total_area,
        'Parking Space': str(parking_val)
    }
