"""
Latvian text preprocessing service for TTS.
Uses TildeOpen for grammar checking and text normalization.
"""

import logging
import re
from typing import List, Optional

from app.services.grammar_check import check_grammar_with_tildeopen

logger = logging.getLogger(__name__)


class LatvianTextPreprocessor:
    """Service for preprocessing Latvian text before TTS synthesis."""

    # Common Latvian abbreviations and their expansions
    ABBREVIATIONS = {
        # Common abbreviations
        "u.c.": "un citi",
        "u.tml.": "un tamlīdzīgi",
        "piem.": "piemēram",
        "t.i.": "tas ir",
        "t.sk.": "tajā skaitā",
        "utt.": "un tā tālāk",
        "u.t.t.": "un tā tālāk",
        "nr.": "numurs",
        "Nr.": "Numurs",
        "lpp.": "lappuse",
        "p.": "pants",
        "st.": "stāvs",
        "iela": "iela",
        "ielā": "ielā",
        # Units
        "kg": "kilogrami",
        "g": "grami",
        "m": "metri",
        "km": "kilometri",
        "cm": "centimetri",
        "mm": "milimetri",
        "l": "litri",
        "ml": "mililitri",
        # Time
        "min": "minūtes",
        "sek": "sekundes",
        "h": "stundas",
        # Organizations
        "SIA": "sabiedrība ar ierobežotu atbildību",
        "AS": "akciju sabiedrība",
        "IK": "individuālais komersants",
        "a/s": "akciju sabiedrība",
        # Titles
        "Dr.": "doktors",
        "prof.": "profesors",
        "akad.": "akadēmiķis",
    }

    # Number words in Latvian
    ONES = [
        "nulle",
        "viens",
        "divi",
        "trīs",
        "četri",
        "pieci",
        "seši",
        "septiņi",
        "astoņi",
        "deviņi",
    ]
    TEENS = [
        "desmit",
        "vienpadsmit",
        "divpadsmit",
        "trīspadsmit",
        "četrpadsmit",
        "piecpadsmit",
        "sešpadsmit",
        "septiņpadsmit",
        "astoņpadsmit",
        "deviņpadsmit",
    ]
    TENS = [
        "",
        "",
        "divdesmit",
        "trīsdesmit",
        "četrdesmit",
        "piecdesmit",
        "sešdesmit",
        "septiņdesmit",
        "astoņdesmit",
        "deviņdesmit",
    ]

    def __init__(self, ollama_base_url: str = "http://localhost:11434"):
        """
        Initialize the Latvian text preprocessor.

        Args:
            ollama_base_url: Base URL for Ollama API (for TildeOpen)
        """
        self.ollama_base_url = ollama_base_url

    def expand_abbreviations(self, text: str) -> str:
        """
        Expand common Latvian abbreviations.

        Args:
            text: Input text

        Returns:
            Text with expanded abbreviations
        """
        result = text
        for abbr, expansion in self.ABBREVIATIONS.items():
            # Use word boundary to avoid partial matches
            pattern = r"\b" + re.escape(abbr) + r"\b"
            result = re.sub(pattern, expansion, result)

        return result

    def number_to_words(self, number: int) -> str:
        """
        Convert a number to Latvian words.

        Args:
            number: Integer to convert (0-999)

        Returns:
            Number in Latvian words
        """
        if number == 0:
            return self.ONES[0]

        if number < 10:
            return self.ONES[number]

        if number < 20:
            return self.TEENS[number - 10]

        if number < 100:
            tens = number // 10
            ones = number % 10
            if ones == 0:
                return self.TENS[tens]
            return f"{self.TENS[tens]} {self.ONES[ones]}"

        if number < 1000:
            hundreds = number // 100
            remainder = number % 100

            # Hundreds place
            if hundreds == 1:
                result = "simts"
            else:
                result = f"{self.ONES[hundreds]} simti"

            # Add remainder if any
            if remainder > 0:
                result += f" {self.number_to_words(remainder)}"

            return result

        # For larger numbers, use a simple representation
        return str(number)

    def normalize_numbers(self, text: str) -> str:
        """
        Convert numbers in text to Latvian words.

        Args:
            text: Input text with numbers

        Returns:
            Text with numbers converted to words
        """

        def replace_number(match):
            try:
                num = int(match.group(0))
                if 0 <= num < 1000:
                    return self.number_to_words(num)
                # For numbers >= 1000, keep as digits
                return match.group(0)
            except ValueError:
                return match.group(0)

        # Replace standalone numbers
        result = re.sub(r"\b\d{1,3}\b", replace_number, text)

        return result

    def normalize_dates(self, text: str) -> str:
        """
        Normalize dates to a more speech-friendly format.

        Args:
            text: Input text with dates

        Returns:
            Text with normalized dates
        """
        # Match dates in format YYYY-MM-DD
        def replace_date(match):
            year, month, day = match.groups()
            month_names = [
                "",
                "janvārī",
                "februārī",
                "martā",
                "aprīlī",
                "maijā",
                "jūnijā",
                "jūlijā",
                "augustā",
                "septembrī",
                "oktobrī",
                "novembrī",
                "decembrī",
            ]

            try:
                y = int(year)
                m = int(month)
                d = int(day)

                if 1 <= m <= 12:
                    month_name = month_names[m]
                    return f"{self.number_to_words(y)} gada {month_name} {self.number_to_words(d)}"
            except (ValueError, IndexError):
                pass

            return match.group(0)

        result = re.sub(r"(\d{4})-(\d{2})-(\d{2})", replace_date, text)

        return result

    def clean_special_characters(self, text: str) -> str:
        """
        Remove or replace special characters that TTS cannot handle well.

        Args:
            text: Input text

        Returns:
            Cleaned text
        """
        # Replace common symbols with words
        replacements = {
            "&": " un ",
            "@": " pie ",
            "%": " procenti",
            "€": " eiro",
            "$": " dolāri",
            "£": " mārciņas",
            "+": " plus ",
            "=": " vienāds ar ",
            "<": " mazāk nekā ",
            ">": " lielāks nekā ",
        }

        result = text
        for symbol, word in replacements.items():
            result = result.replace(symbol, word)

        # Remove other problematic characters but keep punctuation
        result = re.sub(r"[^\w\s,.!?;:\-']", " ", result)

        # Normalize whitespace
        result = re.sub(r"\s+", " ", result).strip()

        return result

    def split_into_sentences(self, text: str) -> List[str]:
        """
        Split text into sentences for better TTS processing.

        Args:
            text: Input text

        Returns:
            List of sentences
        """
        # Split on sentence boundaries
        sentences = re.split(r"[.!?]+\s+", text)

        # Filter out empty sentences and trim
        sentences = [s.strip() for s in sentences if s.strip()]

        return sentences

    async def check_grammar_with_tildeopen(self, text: str) -> str:
        """
        Use TildeOpen to check and potentially correct grammar.

        Args:
            text: Input text in Latvian

        Returns:
            Grammar-checked text (original if check fails)
        """
        try:
            result = await check_grammar_with_tildeopen(
                text=text,
                lang_code="lv",
                ollama_base_url=self.ollama_base_url,
                timeout=10.0,
            )

            if result.get("success") and result.get("suggestions"):
                # Extract corrected text from TildeOpen's suggestions
                # This is a simplified approach - might need refinement
                suggestions = result["suggestions"]
                logger.info(f"TildeOpen grammar check: {suggestions}")

                # For now, return original text
                # In production, you might want to parse the suggestions
                # and apply corrections
                return text

            return text

        except Exception as e:
            logger.warning(f"Grammar check with TildeOpen failed: {e}")
            return text

    async def preprocess_for_tts(self, text: str, use_grammar_check: bool = True) -> str:
        """
        Preprocess Latvian text for TTS synthesis.

        This is the main method that applies all preprocessing steps.

        Args:
            text: Input text in Latvian
            use_grammar_check: Whether to use TildeOpen for grammar checking

        Returns:
            Preprocessed text ready for TTS
        """
        try:
            # Step 1: Optional grammar check with TildeOpen
            if use_grammar_check:
                text = await self.check_grammar_with_tildeopen(text)

            # Step 2: Normalize dates
            text = self.normalize_dates(text)

            # Step 3: Normalize numbers
            text = self.normalize_numbers(text)

            # Step 4: Expand abbreviations
            text = self.expand_abbreviations(text)

            # Step 5: Clean special characters
            text = self.clean_special_characters(text)

            # Step 6: Normalize whitespace and trim
            text = re.sub(r"\s+", " ", text).strip()

            logger.info(f"Preprocessed text: {text[:100]}...")

            return text

        except Exception as e:
            logger.error(f"Error preprocessing text: {e}")
            # Return original text if preprocessing fails
            return text


# Global instance
_latvian_preprocessor: Optional[LatvianTextPreprocessor] = None


def get_latvian_text_preprocessor(
    ollama_base_url: str = "http://localhost:11434",
) -> LatvianTextPreprocessor:
    """
    Get or create the global Latvian text preprocessor instance.

    Args:
        ollama_base_url: Base URL for Ollama API

    Returns:
        LatvianTextPreprocessor instance
    """
    global _latvian_preprocessor

    if _latvian_preprocessor is None:
        _latvian_preprocessor = LatvianTextPreprocessor(ollama_base_url)

    return _latvian_preprocessor
