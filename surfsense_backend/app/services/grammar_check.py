"""
Grammar checking service using TildeOpen multilingual LLM via Ollama.
Automatically checks grammar for European languages.
"""

import asyncio
import logging
from typing import Optional

import httpx

from app.services.language_detector import detect_language, get_language_name

logger = logging.getLogger(__name__)


# Language-specific prompts for better results
LANGUAGE_PROMPTS = {
    "lv": "Pārbaudi šī teksta gramatiku un ieteikt uzlabojumus. Norādi kļūdas un piedāvā labojumus latviešu valodā.",
    "lt": "Patikrink šio teksto gramatiką ir pasiūlyk pataisymus. Nurodyk klaidas ir pasiūlyk taisymus lietuvių kalba.",
    "et": "Kontrolli selle teksti grammatikat ja soovita parandusi. Näita vigu ja paku parandusi eesti keeles.",
    "pl": "Sprawdź gramatykę tego tekstu i zaproponuj poprawki. Wskaż błędy i zasugeruj poprawki po polsku.",
    "fi": "Tarkista tämän tekstin kielioppi ja ehdota parannuksia. Osoita virheet ja ehdota korjauksia suomeksi.",
    "ru": "Проверьте грамматику этого текста и предложите улучшения. Укажите ошибки и предложите исправления на русском языке.",
    "uk": "Перевірте граматику цього тексту та запропонуйте покращення. Вкажіть помилки та запропонуйте виправлення українською мовою.",
    "cs": "Zkontrolujte gramatiku tohoto textu a navrhněte vylepšení. Uveďte chyby a navrhněte opravy v češtině.",
    "sk": "Skontrolujte gramatiku tohto textu a navrhnite vylepšenia. Uveďte chyby a navrhnite opravy v slovenčine.",
    "hu": "Ellenőrizze ennek a szövegnek a nyelvtanát, és javasoljon fejlesztéseket. Jelezze a hibákat és javasoljon javításokat magyarul.",
    "ro": "Verifică gramatica acestui text și sugerează îmbunătățiri. Indică erorile și sugerează corecții în limba română.",
    "bg": "Проверете граматиката на този текст и предложете подобрения. Посочете грешките и предложете корекции на български език.",
    "hr": "Provjerite gramatiku ovog teksta i predložite poboljšanja. Navedite greške i predložite ispravke na hrvatskom jeziku.",
    "sr": "Проверите граматику овог текста и предложите побољшања. Наведите грешке и предложите исправке на српском језику.",
    "sl": "Preverite slovnico tega besedila in predlagajte izboljšave. Navedite napake in predlagajte popravke v slovenščini.",
}


def get_grammar_prompt(lang_code: str, text: str) -> str:
    """
    Get language-specific grammar check prompt.
    
    Args:
        lang_code: ISO 639-1 language code
        text: The text to check
        
    Returns:
        Formatted prompt for TildeOpen
    """
    if lang_code in LANGUAGE_PROMPTS:
        specific_prompt = LANGUAGE_PROMPTS[lang_code]
    else:
        lang_name = get_language_name(lang_code)
        specific_prompt = f"Check the grammar of this text and suggest improvements in {lang_name}. Point out errors and suggest corrections."
    
    return f"""{specific_prompt}

Text to check:
{text}

Please provide:
1. A brief assessment of the grammar quality
2. Any errors found with corrections
3. Suggestions for improvement

Keep your response concise and focused on grammar issues."""


async def check_grammar_with_tildeopen(
    text: str,
    lang_code: str,
    ollama_base_url: str = "http://localhost:11434",
    timeout: float = 8.0,
) -> dict:
    """
    Check grammar using TildeOpen via Ollama.
    
    Args:
        text: The text to check
        lang_code: ISO 639-1 language code
        ollama_base_url: Base URL for Ollama API
        timeout: Request timeout in seconds
        
    Returns:
        Dict with success status and grammar check results or error message
    """
    try:
        prompt = get_grammar_prompt(lang_code, text)
        
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{ollama_base_url}/api/generate",
                json={
                    "model": "tildeopen",
                    "prompt": prompt,
                    "stream": False,
                },
            )
            
            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "language": get_language_name(lang_code),
                    "language_code": lang_code,
                    "suggestions": result.get("response", "").strip(),
                }
            else:
                logger.warning(f"TildeOpen returned status {response.status_code}")
                return {
                    "success": False,
                    "error": f"TildeOpen API returned status {response.status_code}",
                }
    
    except asyncio.TimeoutError:
        logger.warning("Grammar check timed out")
        return {
            "success": False,
            "error": "Grammar check timed out",
        }
    
    except Exception as e:
        logger.warning(f"Grammar check failed: {e}")
        return {
            "success": False,
            "error": f"Grammar check failed: {str(e)}",
        }


async def auto_grammar_check(
    user_query: str,
    llm_response: str,
    ollama_base_url: str = "http://localhost:11434",
) -> Optional[dict]:
    """
    Automatically detect language and check grammar if it's a European language.
    
    Args:
        user_query: The user's original query
        llm_response: The LLM's response to check
        ollama_base_url: Base URL for Ollama API
        
    Returns:
        Grammar check result dict or None if language not detected or is English
    """
    # Try to detect language from user query first
    lang_code = detect_language(user_query)
    
    # If not detected, try the response
    if not lang_code:
        lang_code = detect_language(llm_response)
    
    # Skip if no language detected or if it's English
    if not lang_code or lang_code == "en":
        return None
    
    logger.info(f"Detected language: {lang_code} ({get_language_name(lang_code)}), running grammar check")
    
    # Run grammar check
    result = await check_grammar_with_tildeopen(
        llm_response,
        lang_code,
        ollama_base_url,
    )
    
    return result
