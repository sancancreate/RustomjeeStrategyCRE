import re
import pandas as pd

# Global Devanagari to Arabic Digit Mapping
DEVANAGARI_DIGITS = {
    '०': '0', '१': '1', '२': '2', '३': '3', '४': '4',
    '५': '5', '६': '6', '७': '7', '८': '8', '९': '9'
}

METER_KEYWORDS = ['चौ', 'मी', 'मीटर', 'mtr', 'mt', 'sqm', 'sq.m', 'sq m']
UNIT_PATTERN = r'(चौ\.?\s*मी\.?|चौरस\s*मीटर|मीटर|mtr|mt|sq\.?m|sq\.?\s*m|sqft|sq\.?\s*ft|ft|फूट|फिट|sq\.?\s*feet)'

def clean_and_normalize_text(text):
    if pd.isna(text): 
        return ""
    text = str(text).replace('\xa0', ' ').replace('\t', ' ').replace('\n', ' ').replace('\r', ' ')
    # Remove thousand-separator formatting commas to preserve digits
    text = re.sub(r'(?<=\d),(?=\d)', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    for dev, eng in DEVANAGARI_DIGITS.items():
        text = text.replace(dev, eng)
    return text

def get_sqft(val_str, unit_str, context_str):
    """Safely converts string values to sqft while avoiding massive IDs/Phone numbers."""
    try:
        val = float(val_str)
        # HARD CEILING: No residential area is > 20,000. This kills the Registration ID bug.
        if val > 20000:
            return 0.0
            
        unit_lower = (unit_str or "").lower()
        context_lower = (context_str or "").lower()
        
        is_meter = False
        if unit_lower and any(m in unit_lower for m in METER_KEYWORDS):
            is_meter = True
        elif not unit_lower and any(m in context_lower for m in METER_KEYWORDS):
            is_meter = True
            
        if is_meter:
            return val * 10.7639
        return val
    except Exception:
        return 0.0

def extract_all_areas_explicitly(text):
    carpet, balcony, utility = 0.0, 0.0, 0.0
    
    # ---------------------------------------------------------
    # PATH A: Chained Equation Evaluator (+)
    # ---------------------------------------------------------
    if '+' in text:
        segments = text.split('+')
        for idx, seg in enumerate(segments):
            # STRICT REGEX: Must be a number followed EXACTLY by an area unit. 
            # This completely ignores "Flat 1204" or "Floor 3".
            match = re.search(r'(\d+(?:\.\d+)?)\s*' + UNIT_PATTERN, seg, re.IGNORECASE)
            
            if match:
                val_str = match.group(1)
                unit_str = match.group(2)
                sqft_val = get_sqft(val_str, unit_str, seg)
                
                if sqft_val == 0.0:
                    continue
                    
                seg_lower = seg.lower()
                # Route based on keywords present in the segment
                if any(k in seg_lower for k in ['युटिलिटी', 'युटीलिटी', 'युटिलीटी', 'यूटिलीटी', 'यूटिलिटी', 'ड्राय', 'सर्व्हिस', 'utility', 'dry', 'service']):
                    utility += sqft_val
                elif any(k in seg_lower for k in ['बाल्कनी', 'बालकॉनी', 'गॅलरी', 'गॅलेरी', 'डेक', 'deck', 'balcony', 'terrace', 'टेरेस']):
                    balcony += sqft_val
                elif any(k in seg_lower for k in ['कार्पेट', 'कारपेट', 'चटई', 'carpet']):
                    carpet += sqft_val
                else:
                    # Fallback for "+ 5.23 sq m" without a label
                    if idx == 0 and carpet == 0.0:
                        carpet += sqft_val
                    elif idx == 1 and balcony == 0.0:
                        balcony += sqft_val
                    elif idx == 2 and utility == 0.0:
                        utility += sqft_val
        
        if carpet > 0 or balcony > 0 or utility > 0:
            return round(carpet, 2), round(balcony, 2), round(utility, 2)

    # ---------------------------------------------------------
    # PATH B: Sequential Proximity Patterns 
    # ---------------------------------------------------------
    carpet_patterns = [
        r'(?:कार्पेट|कारपेट|चटई|carpet|एकूण क्षेत्रफळ|क्षेत्रफळ)\s*(?:एरिया|क्षेत्र|area)?\s*(?::|=)?\s*(\d+(?:\.\d+)?)\s*' + UNIT_PATTERN + r'?',
        r'(\d+(?:\.\d+)?)\s*' + UNIT_PATTERN + r'?\s*(?:कार्पेट|कारपेट|चटई|carpet|एकूण क्षेत्रफळ|क्षेत्रफळ)'
    ]
    
    balcony_patterns = [
        r'(?:बाल्कनी|बालकॉनी|गॅलरी|गॅलेरी|डेक|ओपन डेक|टेरेस|balcony|gallery|deck|terrace)\s*(?:एरिया|क्षेत्र|area)?\s*(?::|=)?\s*(\d+(?:\.\d+)?)\s*' + UNIT_PATTERN + r'?',
        r'(\d+(?:\.\d+)?)\s*' + UNIT_PATTERN + r'?\s*(?:बाल्कनी|बालकॉनी|गॅलरी|गॅलेरी|डेक|ओपन डेक|टेरेस|balcony|gallery|deck|terrace)'
    ]
    
    utility_patterns = [
        r'(?:युटिलिटी|युटीलिटी|युटिलीटी|यूटिलीटी|यूटिलिटी|ड्राय|सर्व्हिस|ड्राय बाल्कनी|utility|dry|service)\s*(?:एरिया|क्षेत्र|area)?\s*(?::|=)?\s*(\d+(?:\.\d+)?)\s*' + UNIT_PATTERN + r'?',
        r'(\d+(?:\.\d+)?)\s*' + UNIT_PATTERN + r'?\s*(?:युटिलिटी|युटीलिटी|युटिलीटी|यूटिलीटी|यूटिलिटी|ड्राय|सर्व्हिस|ड्राय बाल्कनी|utility|dry|service)'
    ]

    def extract_first_match(patterns, text_to_search):
        for pattern in patterns:
            match = re.search(pattern, text_to_search, re.IGNORECASE)
            if match:
                val = match.group(1)
                unit = match.group(2) if len(match.groups()) > 1 else ""
                
                # SAFEGUARD: Prevents capturing isolated "1" or "2" from "1 BHK" 
                # if there is no specific unit attached.
                if float(val) < 10 and not unit:
                    continue 
                    
                start_pos = match.start()
                context = text_to_search[max(0, start_pos - 15): min(len(text_to_search), match.end() + 15)]
                sqft_val = get_sqft(val, unit, context)
                if sqft_val > 0:
                    return sqft_val
        return 0.0

    carpet = extract_first_match(carpet_patterns, text)
    balcony = extract_first_match(balcony_patterns, text)
    utility = extract_first_match(utility_patterns, text)

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

    # 3. Unit / Flat Number Extraction
    unit_num = "Not Mentioned"
    if row_context is not None and unit_col in row_context and pd.notna(row_context[unit_col]):
        val = row_context[unit_col]
        if isinstance(val, (int, float)):
            if float(val).is_integer(): unit_num = str(int(val))
            else: unit_num = str(val).strip()
        else:
            unit_num = str(val).strip()
    else:
        unit_match = re.search(r'(?:सदनिका|फ्लॅट|शॉप|दुकान|गाळा|फ्लॅट नं|सदनिका नं|फ्लॅट क्र|सदनिका क्र|नंबर|क्रमांक)\s*(?:नं|क्र|क्रमांक|नंबर)?\.?\s*([A-Za-z0-9\-/_]+)', text, re.IGNORECASE)
        if unit_match:
            raw_unit = unit_match.group(1).strip()
            unit_num = re.split(r'[\s,ं.]', raw_unit)[0]

    if unit_num.endswith('.0'): unit_num = unit_num[:-2]

    # 4. Strictly Bound Area Calculation Engine
    carpet_area, balcony_area, utility_area = extract_all_areas_explicitly(text)
    total_area = round(carpet_area + balcony_area + utility_area, 2)

    # 5. Stable Parking Allocation Logic
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
        'Unit Number': unit_num,
        'Carpet Area (sq ft)': carpet_area,
        'Balcony Area (sq ft)': balcony_area,
        'Utility Area (sq ft)': utility_area,
        'Total Area (sq ft)': total_area,
        'Parking Space': str(parking_val)
    }
