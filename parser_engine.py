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
    "तेरावा": "13", "तेраवे": "13", "तेराव्या": "13",
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
    "तिसावा": "30", "तिसावे": "30", "तिसाव्या": "30"
}

CARPET_KEYWORDS = ["कार्पेट", "कारपेट", "चटई", "carpet", "एकूण क्षेत्रफळ", "क्षेत्रफळ"]
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

def extract_all_areas_globally(text):
    # Strip down formatting punctuation inside numerical expressions immediately
    text = re.sub(r'(?<=\d),(?=\d)', '', text)
    
    carpet = 0.0
    balcony = 0.0
    utility = 0.0
    
    # PATH A: String Equation Handler (e.g., 45.71चौ.मी.+ 0.00 चौ.मी. डेक एरिया)
    if '+' in text and any(u in text for u in ['चौ', 'मी', 'sq', 'ft', 'एरिया']):
        segments = text.split('+')
        for seg in segments:
            seg_lower = seg.lower()
            nums = re.findall(r'\d+(?:\.\d+)?', seg)
            if not nums:
                continue
                
            # Filter out numbers tied to structural metadata inside the segment
            valid_num = None
            for n in nums:
                n_idx = seg.find(n)
                post_txt = seg[n_idx+len(n):n_idx+len(n)+15].lower()
                if "पार्क" in post_txt or "मजला" in post_txt or "नंबर" in post_txt:
                    continue
                valid_num = float(n)
                break
                
            if valid_num is None:
                continue
                
            is_meter = any(m in seg_lower for m in ['चौ', 'मी', 'मीटर', 'mtr', 'mt', 'sqm', 'sq.m'])
            sqft_val = round(valid_num * 10.7639, 2) if is_meter else round(valid_num, 2)
            
            if any(k in seg_lower for k in UTILITY_KEYWORDS):
                utility += sqft_val
            elif any(k in seg_lower for k in BALCONY_KEYWORDS):
                balcony += sqft_val
            elif any(k in seg_lower for k in CARPET_KEYWORDS):
                carpet += sqft_val
            else:
                if carpet == 0.0:
                    carpet = sqft_val
                else:
                    carpet += sqft_val
        return round(carpet, 2), round(balcony, 2), round(utility, 2)
        
    # PATH B: Descriptive Line Ambient Handler (e.g., कार्पेट एरिया ७५० चौ.मी.)
    matches = list(re.finditer(r'\d+(?:\.\d+)?', text))
    for m in matches:
        num_str = m.group()
        num_val = float(num_str)
        start, end = m.start(), m.end()
        
        look_behind = text[max(0, start - 35):start].lower()
        look_ahead = text[end:min(len(text), end + 35)].lower()
        
        if "मजला" in look_ahead or "floor" in look_ahead or "मजला" in look_behind:
            continue
        if "पार्क" in look_ahead or "व्हिलर" in look_ahead or "व्हीलर" in look_ahead:
            continue
        if ("फ्लॅट" in look_behind or "सदनिका" in look_behind or "नं" in look_behind or "क्र" in look_behind) and not any(u in look_behind or u in look_ahead for u in ['चौ', 'मी', 'एरिया', 'क्षेत्रफळ']):
            continue
            
        has_area_context = any(u in look_behind or u in look_ahead for u in ['चौ', 'मी', 'मीटर', 'mtr', 'mt', 'sq', 'ft', 'फूट', 'फिट', 'एरिया', 'क्षेत्रफळ', 'कारपेट', 'कार्पेट', 'बाल्कनी', 'युटिलिटी', 'डेक'])
        if not has_area_context:
            continue
            
        is_meter = any(m_word in look_behind or m_word in look_ahead for m_word in ['चौ', 'मी', 'मीटर', 'mtr', 'mt', 'sqm', 'sq.m'])
        sqft_val = round(num_val * 10.7639, 2) if is_meter else round(num_val, 2)
        
        if any(k in look_behind or k in look_ahead for k in UTILITY_KEYWORDS):
            utility += sqft_val
        elif any(k in look_behind or k in look_ahead for k in BALCONY_KEYWORDS):
            balcony += sqft_val
        elif any(k in look_behind or k in look_ahead for k in CARPET_KEYWORDS):
            carpet += sqft_val
        else:
            if carpet == 0.0:
                carpet = sqft_val
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

    # 2. Tower / Wing Extraction
    tower_wing = "Not Mentioned"
    if row_context is not None and tower_col in row_context and pd.notna(row_context[tower_col]):
        tower_wing = str(row_context[tower_col]).strip()
        if tower_wing.endswith('.0'): tower_wing = tower_wing[:-2]
    else:
        tower_match = re.search(r'(?:बिल्डिंग|बिल्डींग|टाॅवर|टॉवर|विंग|बिल्डिंग नं|बिल्डींग नं)\s*(?:नं|क्र|क्रमांक|नंबर)?\.?\s*([A-Za-z0-9\-]+)', text, re.IGNORECASE)
        if tower_match: tower_wing = tower_match.group(1).strip()

    # 3. Floor Level Extraction (Refined Boundary Controls)
    floor_num = "Not Mentioned"
    normalized_floor_text = text.replace(' ', '')
    
    floor_found = False
    for word, replacement in MARATHI_FLOOR_WORDS.items():
        if word in normalized_floor_text:
            floor_num = replacement
            floor_found = True
            break
            
    if not floor_found:
        floor_digit_match = re.search(r'(\d+)\s*(?:वे|वा|था|रा|री|ा)?\s*(?:मजला|फ्लोअर|floor)', text, re.IGNORECASE)
        if floor_digit_match:
            floor_num = floor_digit_match.group(1).strip()
        else:
            floor_word_match = re.search(r'([A-Za-z0-9\u0900-\u097F]+)\s*(?:मजला|फ्लोअर)', text, re.IGNORECASE)
            if floor_word_match:
                floor_num = floor_word_match.group(1).strip()

    if floor_num.endswith('.0'): floor_num = floor_num[:-2]

    # 4. Unit / Flat Number Extraction (Isolates Numbers to prevent trailing junk)
    unit_num = "Not Mentioned"
    if row_context is not None and unit_col in row_context and pd.notna(row_context[unit_col]):
        val = row_context[unit_col]
        if isinstance(val, (int, float)):
            if float(val).is_integer(): unit_num = str(int(val))
            else: unit_num = str(val).strip()
        else:
            unit_num = str(val).strip()
    else:
        unit_match = re.search(r'(?:सदनिका|फ्लॅट|शॉप|दुकान|गाळा|फ्लॅट नं|सदनिका नं|फ्लॅट क्र|सदनिका क्र)\s*(?:नं|क्र|क्रमांक|नंबर)?\.?\s*([A-Za-z0-9\-/_]+)', text, re.IGNORECASE)
        if unit_match:
            raw_unit = unit_match.group(1).strip()
            unit_num = re.split(r'[\s,ं.]', raw_unit)[0]

    if unit_num.endswith('.0'): unit_num = unit_num[:-2]

    # 5. Execute Routing Metrics Calculations
    carpet_area, balcony_area, utility_area = extract_all_areas_globally(text)
    total_area = round(carpet_area + balcony_area + utility_area, 2)

    # 6. Parking Allocation Scanner
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
