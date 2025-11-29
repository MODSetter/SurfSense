"""
Security tests for file upload validation.

These tests verify that the file upload system properly handles malicious
files, path traversal attempts, and other security threats.
"""

import pytest
from unittest.mock import Mock

from app.routes.documents_routes import (
    sanitize_file_extension,
    validate_file_upload,
    validate_magic_bytes,
    ALLOWED_EXTENSIONS,
    DANGEROUS_SIGNATURES,
)


class TestFileUploadSecurity:
    """Security-focused tests for file upload validation."""

    @pytest.mark.security
    def test_sanitize_path_traversal_extension(self):
        """Test that path traversal attempts in extensions are sanitized."""
        # Path traversal with null byte
        assert sanitize_file_extension("../../etc/passwd%00.pdf") == ".pdf"

        # Path traversal without null byte
        assert sanitize_file_extension("../../../etc/shadow.txt") == ".txt"

        # Multiple dots
        assert sanitize_file_extension("....pdf") == ".pdf"

        # Null byte injection
        assert sanitize_file_extension("document.pdf\x00.exe") == ".pdf"

    @pytest.mark.security
    def test_sanitize_special_characters_in_extension(self):
        """Test that special characters are stripped from extensions."""
        # Special characters that could be used for attacks
        assert sanitize_file_extension("file.pdf;rm -rf /") == ".pdf"
        assert sanitize_file_extension("file.pdf|bash") == ".pdf"
        assert sanitize_file_extension("file.pdf&whoami") == ".pdf"
        assert sanitize_file_extension("file.pdf`ls`") == ".pdf"

    @pytest.mark.security
    def test_sanitize_invalid_extension_returns_bin(self):
        """Test that invalid extensions default to .bin."""
        assert sanitize_file_extension("file") == ".bin"
        assert sanitize_file_extension("file.") == ".bin"
        assert sanitize_file_extension("file.xyz") == ".bin"
        assert sanitize_file_extension("file.exe") == ".bin"  # Not in ALLOWED_EXTENSIONS

    @pytest.mark.security
    def test_blocks_windows_executable(self):
        """Test that Windows PE executables are blocked."""
        exe_signature = b"MZ" + b"\x00" * 100  # Windows executable signature
        is_valid, error = validate_magic_bytes(exe_signature, ".pdf")

        assert is_valid is False
        assert "Windows executable" in error or "PE" in error

    @pytest.mark.security
    def test_blocks_linux_elf_executable(self):
        """Test that Linux ELF executables are blocked."""
        elf_signature = b"\x7fELF" + b"\x00" * 100  # ELF header
        is_valid, error = validate_magic_bytes(elf_signature, ".pdf")

        assert is_valid is False
        assert "executable" in error.lower() or "ELF" in error

    @pytest.mark.security
    def test_blocks_macos_mach_o_executable(self):
        """Test that macOS Mach-O executables are blocked."""
        # 32-bit Mach-O
        macho_signature = b"\xfe\xed\xfa\xce" + b"\x00" * 100
        is_valid, error = validate_magic_bytes(macho_signature, ".pdf")

        assert is_valid is False
        assert "Mach-O" in error or "executable" in error.lower()

    @pytest.mark.security
    def test_blocks_shell_script(self):
        """Test that shell scripts are blocked."""
        # Bash shebang
        shell_script = b"#!/bin/bash\nrm -rf /"
        is_valid, error = validate_magic_bytes(shell_script, ".txt")

        # Shell scripts should be blocked as dangerous
        assert is_valid is False
        assert "script" in error.lower() or "shebang" in error.lower()

    @pytest.mark.security
    def test_valid_pdf_passes(self):
        """Test that legitimate PDF files pass validation."""
        pdf_signature = b"%PDF-1.4\n" + b"x" * 100
        is_valid, error = validate_magic_bytes(pdf_signature, ".pdf")

        assert is_valid is True
        assert error == ""

    @pytest.mark.security
    def test_valid_png_passes(self):
        """Test that legitimate PNG files pass validation."""
        png_signature = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        is_valid, error = validate_magic_bytes(png_signature, ".png")

        assert is_valid is True
        assert error == ""

    @pytest.mark.security
    def test_valid_jpeg_passes(self):
        """Test that legitimate JPEG files pass validation."""
        jpeg_signature = b"\xff\xd8\xff\xe0" + b"\x00" * 100
        is_valid, error = validate_magic_bytes(jpeg_signature, ".jpg")

        assert is_valid is True
        assert error == ""

    @pytest.mark.security
    def test_empty_file_text_format(self):
        """Test that empty text files are handled safely."""
        empty_content = b""
        # Text-based files don't require magic bytes
        is_valid, error = validate_magic_bytes(empty_content, ".txt")

        assert is_valid is True
        assert error == ""

    @pytest.mark.security
    def test_file_type_spoofing_detected(self):
        """Test that file type spoofing is detected."""
        # Executable with .pdf extension
        exe_as_pdf = b"MZ" + b"\x00" * 100
        is_valid, error = validate_magic_bytes(exe_as_pdf, ".pdf")

        assert is_valid is False
        assert "spoofing" in error.lower() or "executable" in error.lower()

    @pytest.mark.security
    def test_wrong_signature_for_extension(self):
        """Test that wrong magic bytes for claimed extension are rejected."""
        # PNG signature but claiming to be PDF
        png_signature = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        is_valid, error = validate_magic_bytes(png_signature, ".pdf")

        assert is_valid is False
        assert "spoofing" in error.lower() or "does not match" in error.lower()

    @pytest.mark.security
    def test_disallowed_extension_blocked(self):
        """Test that disallowed file extensions are rejected."""
        file = Mock()
        file.filename = "malware.exe"
        file.content_type = "application/x-executable"

        is_valid, error = validate_file_upload(file)

        assert is_valid is False
        assert ".exe" in error or "not allowed" in error.lower()

    @pytest.mark.security
    def test_disallowed_script_extensions(self):
        """Test that script file extensions are blocked."""
        dangerous_extensions = [".py", ".js", ".sh", ".bat", ".cmd", ".vbs"]

        for ext in dangerous_extensions:
            file = Mock()
            file.filename = f"script{ext}"
            file.content_type = "text/plain"

            is_valid, error = validate_file_upload(file)

            assert is_valid is False, f"Extension {ext} should be blocked"
            assert ext in error or "not allowed" in error.lower()

    @pytest.mark.security
    def test_no_filename_rejected(self):
        """Test that files without filenames are rejected."""
        file = Mock()
        file.filename = None

        is_valid, error = validate_file_upload(file)

        assert is_valid is False
        assert "filename" in error.lower()

    @pytest.mark.security
    def test_empty_filename_rejected(self):
        """Test that empty filenames are rejected."""
        file = Mock()
        file.filename = ""

        is_valid, error = validate_file_upload(file)

        assert is_valid is False
        assert "filename" in error.lower()

    @pytest.mark.security
    def test_all_allowed_extensions_are_safe(self):
        """Verify that all allowed extensions are non-executable."""
        # Executable extensions that should NOT be in ALLOWED_EXTENSIONS
        dangerous_exts = {
            ".exe", ".dll", ".so", ".dylib",  # Executables
            ".py", ".js", ".java", ".class", ".jar",  # Code
            ".sh", ".bash", ".bat", ".cmd", ".ps1",  # Scripts
            ".vbs", ".vba", ".wsf",  # Windows scripts
            ".app", ".dmg", ".pkg",  # macOS executables
        }

        # Ensure no dangerous extensions are allowed
        overlap = ALLOWED_EXTENSIONS & dangerous_exts
        assert len(overlap) == 0, f"Dangerous extensions found in ALLOWED_EXTENSIONS: {overlap}"

    @pytest.mark.security
    def test_case_insensitive_extension_check(self):
        """Test that extension checking is case-insensitive."""
        # Mixed case extensions should work
        assert sanitize_file_extension("file.PDF") == ".pdf"
        assert sanitize_file_extension("file.TxT") == ".txt"
        assert sanitize_file_extension("file.JpG") == ".jpg"

    @pytest.mark.security
    def test_media_files_bypass_strict_validation(self):
        """Test that media files with variable formats are handled."""
        # MP3 files can have different formats, should pass if no dangerous signature
        mp3_data = b"ID3" + b"\x00" * 100  # MP3 ID3 tag
        is_valid, error = validate_magic_bytes(mp3_data, ".mp3")

        # Should pass - media files are allowed through if no dangerous signature
        assert is_valid is True

    @pytest.mark.security
    def test_csv_injection_not_validated_at_magic_byte_level(self):
        """Test that CSV files are validated by extension not content."""
        # CSV with formula injection attempt (validation happens elsewhere)
        csv_with_formula = b'=1+1,"test"\n'
        is_valid, error = validate_magic_bytes(csv_with_formula, ".csv")

        # Should pass magic byte validation (text-based format)
        # Formula injection prevention happens at processing level
        assert is_valid is True


@pytest.mark.security
class TestSanitizationEdgeCases:
    """Edge case tests for file sanitization."""

    def test_unicode_in_filename(self):
        """Test handling of unicode characters in filenames."""
        # Unicode should be stripped, leaving only safe extension
        assert sanitize_file_extension("文件.pdf") == ".pdf"
        assert sanitize_file_extension("файл.txt") == ".txt"

    def test_very_long_extension(self):
        """Test handling of abnormally long extensions."""
        long_ext = "." + "a" * 1000 + "pdf"
        # Should extract .pdf at the end
        result = sanitize_file_extension(f"file{long_ext}")
        assert result == ".pdf" or result == ".bin"

    def test_multiple_extensions(self):
        """Test files with multiple extensions."""
        # Should take the last extension
        assert sanitize_file_extension("file.tar.gz") == ".gz"
        assert sanitize_file_extension("document.backup.pdf") == ".pdf"

    def test_no_extension(self):
        """Test files without any extension."""
        assert sanitize_file_extension("README") == ".bin"
        assert sanitize_file_extension("Makefile") == ".bin"
