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
BALCONY_KEYWORDS = ["बाल्कनी", "बालकॉनी", "गॅलरी", "गॅलरी", "गॅलेरी", "balcony", "gallery"]
UTILITY_KEYWORDS = ["युटिलिटी", "युटीलिटी", "युटिलीटी", "ड्राय", "सर्व्हिस", "utility", "dry"]

def clean_and_normalize_text(text):
    if pd.isna(text): 
        return ""
    # Force string type and unpack common encoding spacing quirks
    text = str(text).replace('\xa0', ' ').replace('\t', ' ').replace('\n', ' ').replace('\r', ' ')
    # Flatten multiple consecutive spaces into a single clean space strip
    text = re.sub(r'\s+', ' ', text).strip()
    # Normalize Devanagari numbers to English characters immediately
    for dev, eng in DEVANAGARI_DIGITS.items():
        text = text.replace(dev, eng)
    return text

def parse_unit_conversion(value_str, context_window):
    """
    Checks the context around the extracted number to evaluate if it is a 
    Square Meter value (requiring scaling multiplication) or native Square Feet.
    """
    try:
        val = float(value_str)
        context_lower = context_window.lower()
        # Look for square meter indicators even if separated by spaces
        meter_indicators = ['मी', 'मीटर', 'mtr', 'mt', 'sqm', 'sq.m']
        for ind in meter_indicators:
            if ind in context_lower:
                return round(val * 10.7639, 2)
        return round(val, 2)
    except Exception:
        return 0.0

def extract_area_by_proximity(text, keywords):
    """
    Advanced window proximity locator. Finds keywords, slices local text blocks, 
    and extracts numbers irrespective of string token order anomalies.
    """
    for kw in keywords:
        idx = text.lower().find(kw.lower())
        if idx != -1:
            # Slice a local context tracking bubble around the keyword
            start = max(0, idx - 45)
            end = min(len(text), idx + len(kw) + 45)
            window = text[start:end]
            
            # Find all numbers (integers or decimals) inside this structural window
            numbers = re.findall(r'\d+(?:\.\d+)?', window)
            if numbers:
                # Prioritize numbers that sit immediately adjacent to unit characters
                for num in numbers:
                    num_idx = window.find(num)
                    local_slice = window[max(0, num_idx - 15):min(len(window), num_idx + len(num) + 15)]
                    if any(u in local_slice for u in ['चौ', 'मी', 'फू', 'sq', 'ft', 'mtr', 'मीटर']):
                        return parse_unit_conversion(num, local_slice)
                # Fallback to the absolute closest extracted number token inside the window block
                return parse_unit_conversion(numbers[0], window)
    return 0.0

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

    # 3. Floor Level Extraction
    floor_num = "Not Mentioned"
    # Clean up common text variations before running dictionary evaluation loops
    normalized_floor_text = text.replace(' ', '')
    
    floor_found = False
    for word, replacement in MARATHI_FLOOR_WORDS.items():
        if word in normalized_floor_text:
            floor_num = replacement
            floor_found = True
            break
            
    if not floor_found:
        floor_match = re.search(r'(\d+)\s*(?:मजला|फ्लोअर|floor)', text, re.IGNORECASE)
        if floor_match:
            floor_num = floor_match.group(1).strip()
        else:
            floor_word_match = re.search(r'([A-Za-z0-9\u0900-\u097F]+)\s*(?:मजला|फ्लोअर)', text, re.IGNORECASE)
            if floor_word_match:
                floor_num = floor_word_match.group(1).strip()

    if floor_num.endswith('.0'): floor_num = floor_num[:-2]

    # 4. Unit / Flat Number Extraction
    unit_num = "Not Mentioned"
    if row_context is not None and unit_col in row_context and pd.notna(row_context[unit_col]):
        val = row_context[unit_col]
        if isinstance(val, (int, float)):
            if float(val).is_integer(): unit_num = str(int(val))
            else: unit_num = str(val).strip()
        else:
            unit_num = str(val).strip()
    else:
        # Robust multi-pattern pattern lookup targeting punctuation variations like नं. or क्रं.
        unit_match = re.search(r'(?:सदनिका|फ्लॅट|शॉप|दुकान|गाळा|फ्लॅट नं|सदनिका नं)\s*(?:नं|क्र|क्रमांक|नंबर)?\.?\s*([A-Za-z0-9\-]+)', text, re.IGNORECASE)
        if unit_match: unit_num = unit_match.group(1).strip()

    if unit_num.endswith('.0'): unit_num = unit_num[:-2]

    # 5. Advanced Component Area Extractions using Proximity Context Window Strategy
    carpet_area = extract_area_by_proximity(text, CARPET_KEYWORDS)
    balcony_area = extract_area_by_proximity(text, BALCONY_KEYWORDS)
    utility_area = extract_area_by_proximity(text, UTILITY_KEYWORDS)
    total_area = round(carpet_area + balcony_area + utility_area, 2)

    # 6. Parking Allocation Scanner (Excel Look-Behind Formula Logic)
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
