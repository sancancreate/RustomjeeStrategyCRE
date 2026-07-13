import re
import pandas as pd

# Global Mappings for Standardization
DEVANAGARI_DIGITS = {
    '०': '0', '१': '1', '२': '2', '३': '3', '४': '4',
    '५': '5', '६': '6', '७': '7', '८': '8', '९': '9'
}

MARATHI_FLOOR_WORDS = {
    "तळ": "0", "ग्राउंड": "0", "पहिला": "1", "पहिले": "1", "दुसरा": "2", "दुसरे": "2",
    "तिसरा": "3", "तिसरे": "3", "चौथा": "4", "चौथे": "4", "पाचवा": "5", "पाचवे": "5",
    "सहावा": "6", "सातवा": "7", "आठवा": "8", "नवा": "9", "दहावा": "10"
}

# Extensive variations for spelling normalization
CARPET_KEYWORDS = ["कार्पेट", "कारपेट", "चटई", "carpet"]
BALCONY_KEYWORDS = ["बाल्कनी", "बालकॉनी", "गॅलरी", "गॅलरी", "गॅलेरी", "balcony", "gallery"]
UTILITY_KEYWORDS = ["युटिलिटी", "युटीलिटी", "युटिलीटी", "ड्राय", "सर्व्हिस", "utility", "dry"]

def clean_and_normalize_text(text):
    if pd.isna(text): 
        return ""
    text = str(text).strip()
    # Standardize Devnagari digits to Western Arabic numerals
    for dev, eng in DEVANAGARI_DIGITS.items():
        text = text.replace(dev, eng)
    return text

def convert_to_sqft(value_str, unit_str):
    try:
        val = float(value_str)
        unit_str = str(unit_str).lower()
        # If unit contains common representations of Sq. Meters, convert to Sq. Feet
        if any(m in unit_str for m in ['मी', 'मीटर', 'm', 'mtr', 'mtrs']):
            return round(val * 10.7639, 2)
        return round(val, 2)
    except Exception:
        return 0.0

def extract_area_metric(text, keywords):
    """
    Robust area extractor that scans text for both ordering scenarios:
    1. Keyword followed by Area Number (e.g., 'कार्पेट क्षेत्रफळ 41.5 चौ.मी.')
    2. Area Number followed by Keyword (e.g., '41.5 चौ.मी. कार्पेट')
    """
    kw_pattern = "|".join(keywords)
    
    # Pattern Variant A: Number + Unit + Optional Text + Keyword
    # e.g., "41.5 चौ.मी. कार्पेट" or "41.5 चौ.मी. क्षेत्रफळ चटई"
    pattern_a = rf"(\d+(?:\.\d+)?)\s*([^\s,]*)\s*(?:क्षेत्रफळ|एरिया|क्षेत्र)?\s*(?:{kw_pattern})"
    match_a = re.search(pattern_a, text, re.IGNORECASE)
    if match_a:
        return convert_to_sqft(match_a.group(1), match_a.group(2))

    # Pattern Variant B: Keyword + Optional descriptive words + Number + Unit
    # e.g., "कार्पेट क्षेत्रफळ: 41.5 चौ.मी."
    pattern_b = rf"(?:{kw_pattern})\s*(?:क्षेत्रफळ|एरिया|क्षेत्र)?\s*(?:नं|क्र)?\s*[:\-\=]?\s*(\d+(?:\.\d+)?)\s*([^\s,]*)"
    match_b = re.search(pattern_b, text, re.IGNORECASE)
    if match_b:
        return convert_to_sqft(match_b.group(1), match_b.group(2))
        
    # Pattern Variant C: Generic "क्षेत्रफळ" lookup if we are seeking carpet area and nothing else matched
    if "कार्पेट" in keywords:
        pattern_c = r"क्षेत्रफळ\s*(\d+(?:\.\d+)?)\s*([^\s,]*)"
        match_c = re.search(pattern_c, text, re.IGNORECASE)
        if match_c:
            return convert_to_sqft(match_c.group(1), match_c.group(2))

    return 0.0

def locate_description_column(df):
    possible_targets = ['property description', 'description', 'वर्णन', 'मालमत्ता वर्णन', 'column_0', 'column_1']
    for col in df.columns:
        if any(t in str(col).lower() for t in possible_targets): 
            return col
    return None

def extract_marathi_property_details(raw_text, row_context=None):
    text = clean_and_normalize_text(raw_text)
    
    # 1. Project Identity Extraction
    project_name = "Not Mentioned"
    project_match = re.search(r'([\w\s\-]+?)\s*(?:प्रोजेक्ट|फेज|प्रकल्प|गार्डन्स|रेसिडेन्सी)', text, re.IGNORECASE)
    if project_match:
        project_name = project_match.group(1).strip()

    # 2. Tower / Building Target Extraction
    tower_num = "Not Mentioned"
    tower_match = re.search(r'(?:बिल्डिंग|बिल्डींग|टाॅवर|टॉवर|विंग|बिल्डिंग नं)\s*(?:नं|क्र|क्रमांक)?\s*([A-Za-z0-9\-]+)', text, re.IGNORECASE)
    if tower_match:
        tower_num = tower_match.group(1).strip()

    # 3. Floor Level Extraction
    floor_num = "Not Mentioned"
    floor_match = re.search(r'([A-Za-z0-9\u0900-\u097F]+)\s*(?:मजला|फ्लोअर)', text, re.IGNORECASE)
    if floor_match:
        matched_floor = floor_match.group(1).strip().lower()
        if matched_floor in MARATHI_FLOOR_WORDS:
            floor_num = MARATHI_FLOOR_WORDS[matched_floor]
        else:
            floor_num = matched_floor
    else:
        for word, replacement in MARATHI_FLOOR_WORDS.items():
            if word in text:
                floor_num = replacement
                break

    # 4. Unit / Flat Number Extraction
    unit_num = "Not Mentioned"
    unit_match = re.search(r'(?:सदनिका|फ्लॅट|शॉप|दुकान|गाळा)\s*(?:नं|क्र|क्रमांक)?\s*([A-Za-z0-9\-]+)', text, re.IGNORECASE)
    if unit_match:
        unit_num = unit_match.group(1).strip()

    # 5. Advanced Component Area Extractions
    carpet_area = extract_area_metric(text, CARPET_KEYWORDS)
    balcony_area = extract_area_metric(text, BALCONY_KEYWORDS)
    utility_area = extract_area_metric(text, UTILITY_KEYWORDS)
    total_area = round(carpet_area + balcony_area + utility_area, 2)

    # 6. Parking Allocation Scanner (Incorporated Look-Behind Excel Formula Logic)
    parking_val = 0
    triggers = ["फोर व्हीलर", "फोर व्हिलर", "कार पार्किंग", "कार पार्कींग"]
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
            
            if last_word in num_map:
                parking_val = num_map[last_word]
            elif last_word.isdigit():
                parking_val = int(last_word)
            else:
                parking_val = 1
        else:
            parking_val = 1
    elif "पार्किंग" in text or "पार्कींग" in text:
        parking_val = 1

    return {
        'Project Name': project_name,
        'Tower Number': tower_num,
        'Floor Number': floor_num,
        'Unit Number': unit_num,
        'Carpet Area (sq ft)': carpet_area,
        'Balcony Area (sq ft)': balcony_area,
        'Utility Area (sq ft)': utility_area,
        'Total Area (sq ft)': total_area,
        'Parking Space': str(parking_val)
    }
