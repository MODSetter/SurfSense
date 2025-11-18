"""
Language detection service for European languages.
Detects which of the 34 European languages supported by TildeOpen a text is written in.
"""

import re
from typing import Optional


# Language detection patterns
# Each language has common words and character patterns
LANGUAGE_PATTERNS = {
    # Baltic languages
    "lv": {  # Latvian
        "name": "Latvian",
        "keywords": ["un", "ir", "var", "kas", "ar", "par", "no", "uz", "vai", "kā", "bet", "jā", "nē", "es", "tu", "viņš", "mēs"],
        "chars": "āčēģīķļņšūž",
    },
    "lt": {  # Lithuanian
        "name": "Lithuanian",
        "keywords": ["ir", "kad", "su", "kas", "yra", "bet", "tai", "jo", "ar", "į", "iš", "per", "taip", "ne", "aš", "tu"],
        "chars": "ąčęėįšųūž",
    },
    "et": {  # Estonian
        "name": "Estonian",
        "keywords": ["ja", "on", "ei", "see", "kas", "või", "kui", "et", "mis", "kes", "ma", "sa", "ta", "me", "te", "nad"],
        "chars": "äöüõšž",
    },
    # Slavic languages
    "pl": {  # Polish
        "name": "Polish",
        "keywords": ["i", "w", "na", "z", "do", "nie", "się", "jest", "to", "o", "że", "ale", "jak", "czy", "tak", "co"],
        "chars": "ąćęłńóśźż",
    },
    "cs": {  # Czech
        "name": "Czech",
        "keywords": ["a", "je", "v", "na", "se", "to", "z", "o", "že", "s", "pro", "není", "jak", "ale", "jsem", "být"],
        "chars": "áčďéěíňóřšťúůýž",
    },
    "sk": {  # Slovak
        "name": "Slovak",
        "keywords": ["a", "je", "v", "na", "sa", "to", "z", "o", "že", "s", "ako", "nie", "by", "som", "ale", "pre"],
        "chars": "áäčďéíľňóôŕšťúýž",
    },
    "sl": {  # Slovenian
        "name": "Slovenian",
        "keywords": ["in", "je", "v", "na", "z", "da", "se", "ne", "s", "o", "ki", "so", "za", "ali", "kot", "pa"],
        "chars": "čšž",
    },
    "hr": {  # Croatian
        "name": "Croatian",
        "keywords": ["i", "u", "je", "na", "se", "da", "s", "za", "ne", "o", "su", "kao", "iz", "ili", "biti", "koji"],
        "chars": "čćđšž",
    },
    "sr": {  # Serbian
        "name": "Serbian",
        "keywords": ["i", "u", "je", "na", "se", "da", "s", "za", "ne", "o", "su", "kao", "iz", "ili", "biti", "koji"],
        "chars": "čćđšž",
    },
    "bs": {  # Bosnian
        "name": "Bosnian",
        "keywords": ["i", "u", "je", "na", "se", "da", "s", "za", "ne", "o", "su", "kao", "iz", "ili", "biti", "koji"],
        "chars": "čćđšž",
    },
    "bg": {  # Bulgarian
        "name": "Bulgarian",
        "keywords": ["и", "в", "на", "е", "не", "за", "да", "с", "от", "се", "че", "като", "то", "са", "по", "но"],
        "chars": "абвгдежзийклмнопрстуфхцчшщъьюя",
    },
    "mk": {  # Macedonian
        "name": "Macedonian",
        "keywords": ["и", "во", "на", "е", "не", "за", "да", "со", "од", "се", "што", "како", "тоа", "се", "по", "но"],
        "chars": "абвгдѓежзѕијклљмнњопрстќуфхцчџш",
    },
    "ru": {  # Russian
        "name": "Russian",
        "keywords": ["и", "в", "не", "на", "я", "что", "он", "с", "а", "как", "это", "то", "все", "она", "так", "его"],
        "chars": "абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
    },
    "uk": {  # Ukrainian
        "name": "Ukrainian",
        "keywords": ["і", "в", "не", "на", "що", "з", "у", "та", "він", "це", "як", "до", "за", "я", "по", "але"],
        "chars": "абвгґдеєжзиіїйклмнопрстуфхцчшщьюя",
    },
    # Romance languages
    "ro": {  # Romanian
        "name": "Romanian",
        "keywords": ["și", "în", "de", "la", "cu", "a", "pentru", "ce", "este", "că", "din", "pe", "nu", "sau", "dar", "mai"],
        "chars": "ăâîșț",
    },
    "it": {  # Italian
        "name": "Italian",
        "keywords": ["e", "di", "il", "la", "che", "a", "è", "per", "in", "un", "una", "non", "con", "le", "si", "da"],
        "chars": "àèéìòù",
    },
    "es": {  # Spanish
        "name": "Spanish",
        "keywords": ["y", "de", "el", "la", "que", "a", "en", "es", "un", "por", "con", "no", "una", "para", "los", "se"],
        "chars": "áéíñóú",
    },
    "pt": {  # Portuguese
        "name": "Portuguese",
        "keywords": ["e", "de", "o", "a", "que", "é", "do", "da", "em", "um", "para", "com", "não", "uma", "os", "no"],
        "chars": "ãáàâçéêíóôõú",
    },
    "fr": {  # French
        "name": "French",
        "keywords": ["et", "de", "le", "la", "à", "un", "une", "est", "en", "que", "pour", "dans", "ce", "il", "qui", "ne"],
        "chars": "àâçéèêëîïôùûü",
    },
    # Germanic languages
    "de": {  # German
        "name": "German",
        "keywords": ["und", "der", "die", "das", "in", "ist", "zu", "den", "mit", "von", "ein", "eine", "nicht", "sich", "auf", "für"],
        "chars": "äöüß",
    },
    "nl": {  # Dutch
        "name": "Dutch",
        "keywords": ["de", "het", "een", "van", "en", "in", "is", "dat", "op", "te", "voor", "met", "niet", "zijn", "aan", "er"],
        "chars": "ëïé",
    },
    "sv": {  # Swedish
        "name": "Swedish",
        "keywords": ["och", "i", "att", "det", "som", "är", "en", "på", "för", "av", "med", "till", "den", "ett", "har", "om"],
        "chars": "åäö",
    },
    "da": {  # Danish
        "name": "Danish",
        "keywords": ["og", "i", "at", "det", "er", "en", "til", "på", "som", "af", "for", "med", "ikke", "har", "den", "de"],
        "chars": "æøå",
    },
    "no": {  # Norwegian
        "name": "Norwegian",
        "keywords": ["og", "i", "det", "er", "til", "en", "på", "som", "at", "av", "for", "med", "ikke", "har", "den", "de"],
        "chars": "æøå",
    },
    "is": {  # Icelandic
        "name": "Icelandic",
        "keywords": ["og", "í", "að", "er", "sem", "á", "til", "um", "með", "fyrir", "ekki", "en", "það", "við", "af", "var"],
        "chars": "áðéíóúýþæö",
    },
    # Finno-Ugric languages
    "fi": {  # Finnish
        "name": "Finnish",
        "keywords": ["ja", "on", "ei", "se", "että", "oli", "olla", "joka", "mutta", "tai", "kun", "vain", "niin", "kuin", "jos", "hän"],
        "chars": "äö",
    },
    "hu": {  # Hungarian
        "name": "Hungarian",
        "keywords": ["a", "az", "és", "is", "volt", "van", "hogy", "nem", "egy", "mint", "azt", "már", "csak", "még", "ami", "volt"],
        "chars": "áéíóöőúüű",
    },
    # Greek
    "el": {  # Greek
        "name": "Greek",
        "keywords": ["και", "το", "της", "την", "του", "στο", "με", "για", "από", "που", "είναι", "στη", "στην", "ότι", "δεν", "τα"],
        "chars": "αβγδεζηθικλμνξοπρστυφχψω",
    },
    # Maltese
    "mt": {  # Maltese
        "name": "Maltese",
        "keywords": ["u", "li", "ta", "fl", "għal", "ma", "il", "tal", "f", "b", "minn", "jew", "kif", "bħal", "meta", "għax"],
        "chars": "ċġħż",
    },
    # Turkish
    "tr": {  # Turkish
        "name": "Turkish",
        "keywords": ["ve", "bir", "bu", "da", "de", "ile", "için", "mi", "ne", "var", "daha", "olarak", "çok", "gibi", "ancak", "ya"],
        "chars": "çğıöşü",
    },
    # Albanian
    "sq": {  # Albanian
        "name": "Albanian",
        "keywords": ["dhe", "i", "të", "e", "në", "për", "me", "që", "një", "nga", "është", "si", "por", "ka", "u", "nga"],
        "chars": "çë",
    },
    # English (for completeness, but won't trigger grammar check)
    "en": {  # English
        "name": "English",
        "keywords": ["the", "and", "is", "to", "of", "a", "in", "that", "it", "was", "for", "on", "are", "with", "as", "be"],
        "chars": "",
    },
}


def detect_language(text: str) -> Optional[str]:
    """
    Detect which European language a text is written in.
    
    Args:
        text: The text to analyze
        
    Returns:
        ISO 639-1 language code (e.g., 'lv', 'et', 'pl') or None if no language detected
    """
    if not text or len(text) < 10:
        return None
    
    # Require at least 3 words
    words = re.findall(r'\w+', text.lower())
    if len(words) < 3:
        return None
    
    text_lower = text.lower()
    
    # Score each language
    scores = {}
    
    for lang_code, lang_data in LANGUAGE_PATTERNS.items():
        score = 0
        
        # Check for special characters
        if lang_data["chars"]:
            for char in lang_data["chars"]:
                if char in text_lower:
                    score += 3  # Special chars are strong indicators
        
        # Check for common keywords
        keyword_matches = 0
        for keyword in lang_data["keywords"]:
            # Count occurrences as whole words
            pattern = r'\b' + re.escape(keyword) + r'\b'
            matches = len(re.findall(pattern, text_lower))
            if matches > 0:
                keyword_matches += 1
                score += matches * 2
        
        # Require at least 2 keyword matches for short texts or 3 for longer
        min_keyword_matches = 2 if len(words) < 20 else 3
        if keyword_matches < min_keyword_matches:
            score = 0
        
        scores[lang_code] = score
    
    # Find the highest scoring language
    if not scores:
        return None
    
    max_score = max(scores.values())
    if max_score == 0:
        return None
    
    # Get the language with highest score
    detected_lang = max(scores.items(), key=lambda x: x[1])[0]
    
    return detected_lang


def get_language_name(lang_code: str) -> str:
    """
    Get the full name of a language from its code.
    
    Args:
        lang_code: ISO 639-1 language code
        
    Returns:
        Full language name or the code if not found
    """
    if lang_code in LANGUAGE_PATTERNS:
        return LANGUAGE_PATTERNS[lang_code]["name"]
    return lang_code
