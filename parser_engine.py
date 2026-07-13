import re
import pandas as pd

# Global Devanagari to Arabic Digit Mapping
DEVANAGARI_DIGITS = {
    '०': '0', '१': '1', '२': '2', '३': '3', '४': '4',
    '५': '5', '६': '6', '७': '7', '८': '8', '९': '9'
}

# Exhaustive Hardcoded Alternative Matrices for Area Mapping
CARPET_ALT_PATTERNS = [
    r'(?:कार्पेट|कारपेट|चटई|एकूण क्षेत्रफळ|क्षेत्रफळ)\s*(?:एरिया|क्षेत्र)?\s*(?::|=)?\s*(\d+(?:\.\d+)?)',
    r'(\d+(?:\.\d+)?)\s*(?:चौ\.?\s*मी\.?|मीटर|sq\.?\s*m|sqft|ft|फूट|फिट)?\s*(?:कार्पेट|कारपेट|चटई|क्षेत्रफळ)',
    r'carpet\s*(?:area)?\s*(?::|=)?\s*(\d+(?:\.\d+)?)',
    r'(\d+(?:\.\d+)?)\s*(?:sqft|sq\s*ft|sq\.ft\.)\s*(?:carpet)'
]

BALCONY_ALT_PATTERNS = [
    r'(?:बाल्कनी|बालकॉनी|गॅलरी|गॅलेरी|डेक|ओपन डेक|टेरेस)\s*(?:एरिया|क्षेत्र)?\s*(?::|=)?\s*(\d+(?:\.\d+)?)',
    r'(\d+(?:\.\d+)?)\s*(?:चौ\.?\s*मी\.?|मीटर|sq\.?\s*m|sqft|ft|फूट|फिट)?\s*(?:बाल्कनी|बालकॉनी|गॅलरी|गॅलेरी|डेक|टेरेस)',
    r'(?:balcony|gallery|deck|terrace)\s*(?:area)?\s*(?::|=)?\s*(\d+(?:\.\d+)?)',
    r'(\d+(?:\.\d+)?)\s*(?:sqft|sq\s*ft)\s*(?:balcony|gallery|deck)'
]

UTILITY_ALT_PATTERNS = [
    r'(?:युटिलिटी|युटीलिटी|युटिलीटी|यूटिलीटी|यूटिलिटी|ड्राय|सर्व्हिस|ड्राय बाल्कनी)\s*(?:एरिया|क्षेत्र|गॅलरी)?\s*(?::|=)?\s*(\d+(?:\.\d+)?)',
    r'(\d+(?:\.\d+)?)\s*(?:चौ\.?\s*मी\.?|मीटर|sq\.?\s*m|sqft|ft|फूट|फिट)?\s*(?:युटिलिटी|युटीलिटी|युटिलीटी|यूटिलीटी|यूटिलिटी|ड्राय|सर्व्हिस)',
    r'(?:utility|dry\s*balcony|service)\s*(?:area)?\s*(?::|=)?\s*(\d+(?:\.\d+)?)',
    r'(\d+(?:\.\d+)?)\s*(?:sqft|sq\s*ft)\s*(?:utility|dry)'
]

# Explicit Unit Identifiers for Square Meter Detection
METER_KEYWORDS = ['चौ', 'मी', 'मीटर', 'mtr', 'mt', 'sqm', 'sq.m', 'sq m']

def clean_and_normalize_text(text):
    if pd.isna(text): 
        return ""
    # Strip out non-breaking space characters and complex whitespace traps
    text = str(text).replace('\xa0', ' ').replace('\t', ' ').replace('\n', ' ').replace('\r', ' ')
    # Remove thousand-separator formatting commas inside numbers to preserve digits
    text = re.sub(r'(?<=\d),(?=\d)', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    # Normalize Devanagari numerals directly to Arabic characters
    for dev, eng in DEVANAGARI_DIGITS.items():
        text = text.replace(dev, eng)
    return text

def parse_value_with_conversion(val_str, context_text):
    try:
        val = float(val_str)
        context_lower = context_text.lower()
        if any(m in context_lower for m in METER_KEYWORDS):
            return round(val * 10.7639, 2)
        return round(val, 2)
    except Exception:
        return 0.0

def extract_all_areas_explicitly(text):
    carpet = 0.0
    balcony = 0.0
    utility = 0.0
    
    # SYSTEM PATH A: Chained Equation Evaluator (e.g., 45.71चौ.मी.+ 0.00 चौ.मी. डेक एरिया + 1.21 चौ.मी. यूटिलीटी एरिया)
    if '+' in text:
        segments = text.split('+')
        for idx, seg in enumerate(segments):
            seg_lower = seg.lower()
            numbers = re.findall(r'\d+(?:\.\d+)?', seg)
            if not numbers:
                continue
                
            # Isolate the numeric token that belongs strictly to area measurements
            target_number = None
            for num in numbers:
                n_pos = seg.find(num)
                look_ahead_local = seg[n_pos+len(num):n_pos+len(num)+20].lower()
                # Filter out numbers tied directly to parking slots or layout structural tags
                if "पार्क" in look_ahead_local or "व्हिलर" in look_ahead_local or "मजला" in look_ahead_local:
                    continue
                target_number = num
                break
                
            if target_number is None:
                continue
                
            sqft_calculated = parse_value_with_conversion(target_number, seg)
            
            # Explicit routing matching based on literal layout identifiers inside the segment block
            if any(k in seg_lower for k in ['युटिलिटी', 'युटीलिटी', 'युटिलीटी', 'यूटिलीटी', 'यूटिलिटी', 'ड्राय', 'सर्व्हिस', 'utility']):
                utility += sqft_calculated
            elif any(k in seg_lower for k in ['बाल्कनी', 'बालकॉनी', 'गॅलरी', 'गॅलेरी', 'डेक', 'deck', 'balcony', 'terrace', 'टेरेस']):
                balcony += sqft_calculated
            elif any(k in seg_lower for k in ['कार्पेट', 'कारपेट', 'चटई', 'carpet', 'क्षेत्रफळ']):
                carpet += sqft_calculated
            else:
                # Literal Fallback Cascade for equation strings missing explicit labels inside segments
                if idx == 0 or carpet == 0.0:
                    carpet += sqft_calculated
                else:
                    carpet += sqft_calculated
        return round(carpet, 2), round(balcony, 2), round(utility, 2)

    # SYSTEM PATH B: Sequential Hardcoded Pattern Fallback Cascade Engine
    # 1. Evaluate Carpet Area patterns explicitly
    for pattern in CARPET_ALT_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            val_str = match.group(1)
            start_pos = text.find(val_str)
            context_window = text[max(0, start_pos - 20):min(len(text), start_pos + len(val_str) + 20)]
            carpet = parse_value_with_conversion(val_str, context_window)
            break
            
    # 2. Evaluate Balcony/Deck Area patterns explicitly
    for pattern in BALCONY_ALT_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            val_str = match.group(1)
            start_pos = text.find(val_str)
            context_window = text[max(0, start_pos - 20):min(len(text), start_pos + len(val_str) + 20)]
            balcony = parse_value_with_conversion(val_str, context_window)
            break
            
    # 3. Evaluate Utility/Dry Area patterns explicitly
    for pattern in UTILITY_ALT_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            val_str = match.group(1)
            start_pos = text.find(val_str)
            context_window = text[max(0, start_pos - 20):min(len(text), start_pos + len(val_str) + 20)]
            utility = parse_value_with_conversion(val_str, context_window)
            break
            
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

    # 3. Unit / Flat Number Extraction (Preserved and Refined)
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

    # 4. Explicit Area Alternative Matrix Calculation Engine
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
