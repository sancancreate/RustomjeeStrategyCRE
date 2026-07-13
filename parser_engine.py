def extract_marathi_property_details(raw_text, row_context=None):
    """
    Robust property detail extraction engine protected against Devanagari numeral representations,
    text-based structural floor definitions, volatile punctuation variations, and cross-metric duplication.
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

    # 4. Unit / Flat Number Extraction
    unit_no = "Not Mentioned"
    unit_match = re.search(r'(?:सदनिका|फ्लॅट|युनिट|दुकान|कार्यालय|निवासी\s+सदनिका)\s*(?:क्र|नं|नंबर|नो|no|num)?[\s.:-]*([A-Za-z0-9\-\/]+)', text)
    if not unit_match:
        unit_match = re.search(r'(?:क्र|नं|नंबर|नो)[\s.:-]*([A-Za-z0-9\-\/]+)', text)
        
    if unit_match:
        unit_no = unit_match.group(1).strip()
        
    if unit_no == "Not Mentioned" and row_context is not None:
        for fallback_col in ['Unit no', 'Unit No', 'Unit', 'Unit Number', 'Flat No', 'Flat no']:
            if fallback_col in row_context and pd.notna(row_context[fallback_col]):
                unit_no = str(row_context[fallback_col]).strip()
                break

    # High-floor architectural sanity guard to filter out Unit Numbers leaking into Floor column
    try:
        if floor_no != "Not Mentioned" and int(floor_no) > 120:
            floor_no = "Not Mentioned"
    except ValueError:
        pass

    # 5. Component Space Metrics Extraction
    carpet_area = 0.0
    balcony_area = 0.0
    utility_area = 0.0
    
    # Carpet Extraction
    carpet_ft_match = re.search(r'([0-9.]+)\s*(?:चौ\.\s*फु\.|चौ\.फु\.|चौ.फूट|स्क्वेअर फूट)\s*(?:रेरा\s+)?(?:कारपेट|कार्पेट)', text)
    if not carpet_ft_match:
        carpet_ft_match = re.search(r'(?:क्षेत्रफळ|चटईक्षेत्र|कारपेट क्षेत्रफळ)\s*([0-9.]+)\s*(?:चौ\.\s*फु\.|चौ\.फु\.)', text)
    if not carpet_ft_match:
        carpet_ft_match = re.search(r'म्हणजेच\s*([0-9.]+)\s*(?:चौ\.\s*फु\.|चौ\.फु\.)', text)
        
    if carpet_ft_match:
        carpet_area = safe_float(carpet_ft_match.group(1))
    else:
        carpet_m_match = re.search(r'([0-9.]+)\s*(?:चौ\.\s*मी\.|चौ\.मी\.)\s*(?:रेरा\s+)?(?:कारपेट|कार्पेट)', text)
        if carpet_m_match:
            carpet_area = round(safe_float(carpet_m_match.group(1)) * 10.76, 2)
            
    if carpet_area == 0.0 and row_context is not None:
        for fallback_col in ['Area', 'Total Usable Area (sq.ft.)', 'Carpet Area']:
            if fallback_col in row_context and pd.notna(row_context[fallback_col]):
                carpet_area = safe_float(row_context[fallback_col])
                if carpet_area > 0.0:
                    break

    # Balcony Extraction (Guarded against sweeping lookaheads)
    balcony_ft_match = re.search(r'([0-9.]+)\s*(?:चौ\.\s*फु\.|चौ\.फु\.)\s*(?:एरिया\s+)?(?:क्षेत्रफळाची\s+)?बाल्कनी', text)
    if not balcony_ft_match:
        matches = list(re.finditer(r'बाल्कनी(.*?)([0-9.]+)\s*(?:चौ\.\s*फु\.|चौ\.फु\.)', text))
        for m in matches:
            between_text = m.group(1)
            # Guard 1: Abort if carpet keywords appear between 'balcony' and the target number
            if any(k in between_text for k in ['कारपेट', 'कार्पेट', 'चटईक्षेत्र']):
                continue
            # Guard 2: Abort if the gap spans too far across sentence structures
            if len(between_text) > 40:
                continue
            balcony_area = safe_float(m.group(2))
            break
    else:
        balcony_area = safe_float(balcony_ft_match.group(1))

    if balcony_area == 0.0:
        balcony_m_match = re.search(r'([0-9.]+)\s*(?:चौ\.\s*मी\.|चौ\.मी\.)\s*(?:एरिया\s+)?(?:क्षेत्रफळाची\s+)?बाल्कनी', text)
        if not balcony_m_match:
            matches = list(re.finditer(r'बाल्कनी(.*?)([0-9.]+)\s*(?:चौ\.\s*मी\.|चौ\.मी\.)', text))
            for m in matches:
                between_text = m.group(1)
                if any(k in between_text for k in ['कारपेट', 'कार्पेट', 'चटईक्षेत्र']) or len(between_text) > 40:
                    continue
                balcony_area = round(safe_float(m.group(2)) * 10.76, 2)
                break
        else:
            balcony_area = round(safe_float(balcony_m_match.group(1)) * 10.76, 2)

    # Utility Extraction (Guarded against sweeping lookaheads)
    utility_ft_match = re.search(r'([0-9.]+)\s*(?:चौ\.\s*फु\.|चौ\.फु\.)\s*(?:एरिया\s+)?(?:क्षेत्रफळाचे\s+)?(?:युटीलिटी|युटिलिटी|ड्राय)', text)
    if not utility_ft_match:
        matches = list(re.finditer(r'(?:युटीलिटी|युटिलिटी|ड्राय)(.*?)([0-9.]+)\s*(?:चौ\.\s*फु\.|चौ\.फु\.)', text))
        for m in matches:
            between_text = m.group(1)
            if any(k in between_text for k in ['कारपेट', 'कार्पेट', 'चटईक्षेत्र']) or len(between_text) > 40:
                continue
            utility_area = safe_float(m.group(2))
            break
    else:
        utility_area = safe_float(utility_ft_match.group(1))

    if utility_area == 0.0:
        utility_m_match = re.search(r'([0-9.]+)\s*(?:चौ\.\s*मी\.|चौ\.मी\.)\s*(?:एरिया\s+)?(?:क्षेत्रफळाचे\s+)?(?:युटीलिटी|युटिलिटी|ड्राय)', text)
        if not utility_m_match:
            matches = list(re.finditer(r'(?:युटीलिटी|युटिलिटी|ड्राय)(.*?)([0-9.]+)\s*(?:चौ\.\s*मी\.|चौ\.मी\.)', text))
            for m in matches:
                between_text = m.group(1)
                if any(k in between_text for k in ['कारपेट', 'कार्पेट', 'चटईक्षेत्र']) or len(between_text) > 40:
                    continue
                utility_area = round(safe_float(m.group(2)) * 10.76, 2)
                break
        else:
            utility_area = round(safe_float(utility_m_match.group(1)) * 10.76, 2)

    total_area = round(carpet_area + balcony_area + utility_area, 2)

    # 6. Parking Allocation Scanner
    parking_desc = "0"
    lower_text = text.lower()
    if "दोन कार पार्किंग" in text or "two car parking" in lower_text or "फोर व्हीलर पार्किंग २" in text:
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
