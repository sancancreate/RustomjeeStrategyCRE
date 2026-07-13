import re
import pandas as pd

# Global Devanagari to Arabic Digit Mapping
DEVANAGARI_DIGITS = {
    '०': '0', '१': '1', '२': '2', '३': '3', '४': '4',
    '५': '5', '६': '6', '७': '7', '८': '8', '९': '9'
}

METER_KEYWORDS = ['चौ', 'मी', 'मीटर', 'mtr', 'mt', 'sqm', 'sq.m', 'sq m', 'चौरस']

def clean_and_normalize_text(text):
    if pd.isna(text): 
        return ""
    text = str(text).replace('\xa0', ' ').replace('\t', ' ').replace('\n', ' ').replace('\r', ' ')
    # Strip out formatting commas inside numbers to preserve pure floats
    text = re.sub(r'(?<=\d),(?=\d)', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    for dev, eng in DEVANAGARI_DIGITS.items():
        text = text.replace(dev, eng)
    return text

def extract_all_areas_explicitly(raw_text):
    text = clean_and_normalize_text(raw_text)
    
    # STAGE 1: Aggressive Masking of Non-Area Numbers
    masked_text = text
    masked_text = re.sub(r'(?:सदनिका|फ्लॅट|शॉप|दुकान|गाळा|कार्यालय|flat|shop|unit|tenement)\s*(?:नं|क्र|क्रमांक|नंबर)?\.?\s*\d+\b', ' [UNIT_MASK] ', masked_text, flags=re.IGNORECASE)
    masked_text = re.sub(r'(?:मजला|फ्लोअर|floor|level)\s*(?:नं|क्र|क्रमांक|नंबर)?\.?\s*\d+\b', ' [FLOOR_MASK] ', masked_text, flags=re.IGNORECASE)
    masked_text = re.sub(r'\d+\s*(?:st|nd|rd|th)\s*floor\b', ' [FLOOR_MASK] ', masked_text, flags=re.IGNORECASE)
    masked_text = re.sub(r'\d+\s*(?:bhk|बीएचके|आरके|rk)\b', ' [BHK_MASK] ', masked_text, flags=re.IGNORECASE)
    masked_text = re.sub(r'(?:दस्त|रजिस्ट्रेशन|नोंदणी|अनुक्रमणिका|index|reg|document|पावती)\s*(?:नं|क्र|क्रमांक|नंबर)?\.?\s*\d+', ' [REG_MASK] ', masked_text, flags=re.IGNORECASE)
    masked_text = re.sub(r'\b\d{6}\b', ' [PIN_MASK] ', masked_text)
    masked_text = re.sub(r'\b\d{7,}\b', ' [LONG_ID_MASK] ', masked_text)

    carpet, balcony, utility = 0.0, 0.0, 0.0
    
    # STAGE 2: Handle Explicit Equation Math Allocations (+)
    if '+' in masked_text:
        segments = masked_text.split('+')
        valid_segments = []
        for seg in segments:
            nums = re.findall(r'\b\d+(?:\.\d+)?\b', seg)
            if nums:
                valid_segments.append((seg, float(nums[0])))
        
        if valid_segments:
            for idx, (seg_text, val) in enumerate(valid_segments):
                if val > 5000:
                    continue
                
                is_meter = False
                if any(m in seg_text.lower() for m in METER_KEYWORDS) or (val < 180 and any(m in text.lower() for m in METER_KEYWORDS)):
                    is_meter = True
                
                sqft_val = val * 10.7639 if is_meter else val
                seg_lower = seg_text.lower()
                
                if any(k in seg_lower for k in ['युटिलिटी', 'युटीलिटी', 'युटिलीटी', 'यूटिलीटी', 'यूटिलिटी', 'ड्राय', 'सर्व्हिस', 'utility', 'dry', 'service']):
                    utility += sqft_val
                elif any(k in seg_lower for k in ['बाल्कनी', 'बालकॉनी', 'गॅलरी', 'गॅलेरी', 'डेक', 'deck', 'balcony', 'terrace', 'टेरेस', 'वरंडा']):
                    balcony += sqft_val
                elif any(k in seg_lower for k in ['कार्पेट', 'कारपेट', 'चटई', 'carpet']):
                    carpet += sqft_val
                else:
                    if idx == 0: carpet += sqft_val
                    elif idx == 1: balcony += sqft_val
                    elif idx == 2: utility += sqft_val
            
            if carpet > 0 or balcony > 0 or utility > 0:
                return round(carpet, 2), round(balcony, 2), round(utility, 2)

    # STAGE 3: Floating Proximity Window Engine
    carpet_keywords = ['कार्पेट', 'कारपेट', 'चटई', 'एकूण क्षेत्रफळ', 'क्षेत्रफळ', 'वापरण्यायोग्य', 'usable', 'carpet']
    balcony_keywords = ['बाल्कनी', 'बालकॉनी', 'गॅलरी', 'गॅलेरी', 'डेक', 'ओपन डेक', 'टेरेस', 'वरंडा', 'balcony', 'gallery', 'deck', 'terrace', 'verandah']
    utility_keywords = ['युटिलिटी', 'युटीलिटी', 'युटिलीटी', 'यूटिलीटी', 'यूटिलिटी', 'ड्राय', 'सर्व्हिस', 'ड्राय बाल्कनी', 'utility', 'dry', 'service']

    def get_closest_number(keywords_list):
        kw_positions = []
        for kw in keywords_list:
            for m in re.finditer(re.escape(kw), masked_text, re.IGNORECASE):
                kw_positions.append(m.start())
        
        if not kw_positions:
            return 0.0
            
        best_val = 0.0
        min_dist = 999999
        chosen_num_start = -1
        chosen_num_end = -1
        
        for num_match in re.finditer(r'\b\d+(?:\.\d+)?\b', masked_text):
            val = float(num_match.group())
            if val > 5000:
                continue
            if val < 5:
                trailing = masked_text[num_match.end():num_match.end()+15].lower()
                if not any(m in trailing for m in METER_KEYWORDS + ['ft', 'फूट', 'फिट']):
                    continue
            
            num_start = num_match.start()
            num_end = num_match.end()
            
            for kp in kw_positions:
                dist = num_start - kp if num_start >= kp else kp - num_end
                if dist < min_dist and dist <= 75:
                    min_dist = dist
                    best_val = val
                    chosen_num_start = num_start
                    chosen_num_end = num_end
                    
        if best_val > 0.0:
            local_window = masked_text[max(0, chosen_num_start - 20): min(len(masked_text), chosen_num_end + 20)].lower()
            is_meter = False
            if any(m in local_window for m in METER_KEYWORDS):
                is_meter = True
            elif best_val < 180 and any(m in text.lower() for m in METER_KEYWORDS):
                is_meter = True
                
            return best_val * 10.7639 if is_meter else best_val
        return 0.0

    carpet = get_closest_number(carpet_keywords)
    balcony = get_closest_number(balcony_keywords)
    utility = get_closest_number(utility_keywords)
    
    # STAGE 4: Ultimate Catch-All Rule for missing keyword entries
    if carpet == 0.0 and balcony == 0.0 and utility == 0.0:
        remaining_nums = []
        for num_match in re.finditer(r'\b\d+(?:\.\d+)?\b', masked_text):
            v = float(num_match.group())
            if 20 <= v <= 2500:
                remaining_nums.append((v, num_match.start(), num_match.end()))
        if len(remaining_nums) == 1:
            v, s, e = remaining_nums[0]
            local_w = masked_text[max(0, s-20): min(len(masked_text), e+20)].lower()
            is_meter = any(m in local_w for m in METER_KEYWORDS) or (v < 180 and any(m in text.lower() for m in METER_KEYWORDS))
            carpet = v * 10.7639 if is_meter else v

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

    # 3. Unit / Flat Number Extraction (Floor extraction fully removed)
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

    # 4. Run Proximity Area Calculation Engine
    carpet_area, balcony_area, utility_area = extract_all_areas_explicitly(text)
    total_area = round(carpet_area + balcony_area + utility_area, 2)

    # 5. Stable Parking Allocation Logic (Working perfectly)
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
