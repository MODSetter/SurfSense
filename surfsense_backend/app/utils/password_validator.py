"""
Password validation utilities for enforcing strong password policies.

This module provides comprehensive password validation including:
- Complexity requirements (length, character types)
- Common weak password checking
- Password strength scoring
"""

import re
from typing import Any


# List of common weak passwords to reject
# In production, this should be loaded from a larger dictionary file
COMMON_WEAK_PASSWORDS = {
    "password",
    "password123",
    "123456",
    "12345678",
    "123456789",
    "qwerty",
    "abc123",
    "monkey",
    "letmein",
    "trustno1",
    "dragon",
    "baseball",
    "iloveyou",
    "master",
    "sunshine",
    "ashley",
    "bailey",
    "passw0rd",
    "shadow",
    "123123",
    "654321",
    "superman",
    "qazwsx",
    "michael",
    "football",
    "admin",
    "welcome",
    "login",
    "starwars",
    "pokemon",
    "welcome123",
    "password1",
    "P@ssw0rd",
    "Password1",
    "Password123",
    "Qwerty123",
}


class PasswordValidationError(ValueError):
    """Exception raised when password validation fails."""

    pass


class PasswordValidator:
    """
    Validator for enforcing strong password policies.

    Default requirements:
    - Minimum 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character
    - Not in the list of common weak passwords
    """

    def __init__(
        self,
        min_length: int = 8,
        require_uppercase: bool = True,
        require_lowercase: bool = True,
        require_digit: bool = True,
        require_special: bool = True,
        check_common_passwords: bool = True,
    ):
        """
        Initialize the password validator with custom requirements.

        Args:
            min_length: Minimum password length
            require_uppercase: Require at least one uppercase letter
            require_lowercase: Require at least one lowercase letter
            require_digit: Require at least one digit
            require_special: Require at least one special character
            check_common_passwords: Check against list of common weak passwords
        """
        self.min_length = min_length
        self.require_uppercase = require_uppercase
        self.require_lowercase = require_lowercase
        self.require_digit = require_digit
        self.require_special = require_special
        self.check_common_passwords = check_common_passwords

    def validate(self, password: str | Any) -> str:
        """
        Validate a password against the configured requirements.

        Args:
            password: The password to validate

        Returns:
            The validated password

        Raises:
            PasswordValidationError: If password doesn't meet requirements
            TypeError: If password is not a string
        """
        # Ensure password is a string
        if not isinstance(password, str):
            raise TypeError(
                f"Password must be a string, got {type(password).__name__}"
            )

        errors = []

        # Check minimum length
        if len(password) < self.min_length:
            errors.append(f"at least {self.min_length} characters")

        # Check uppercase
        if self.require_uppercase and not re.search(r"[A-Z]", password):
            errors.append("at least one uppercase letter")

        # Check lowercase
        if self.require_lowercase and not re.search(r"[a-z]", password):
            errors.append("at least one lowercase letter")

        # Check digit
        if self.require_digit and not re.search(r"\d", password):
            errors.append("at least one number")

        # Check special character
        if self.require_special and not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            errors.append("at least one special character (!@#$%^&*(),.?\":{}|<>)")

        # Check against common weak passwords
        if self.check_common_passwords:
            password_lower = password.lower()
            if password_lower in COMMON_WEAK_PASSWORDS:
                errors.append(
                    "this is a commonly used password and is not secure. "
                    "Please choose a more unique password"
                )

            # Check for simple patterns
            if re.match(r"^(.)\1+$", password):  # All same character
                errors.append("cannot be all the same character")

            if re.match(r"^(?:012|123|234|345|456|567|678|789)+", password):
                errors.append("cannot contain sequential numbers")

            if re.match(r"^(?:abc|bcd|cde|def|efg|fgh|ghi)+", password.lower()):
                errors.append("cannot contain sequential letters")

        if errors:
            error_message = "Password must contain " + ", ".join(errors) + "."
            raise PasswordValidationError(error_message)

        return password

    def get_password_strength(self, password: str) -> dict[str, Any]:
        """
        Calculate password strength score and provide feedback.

        Args:
            password: The password to analyze

        Returns:
            Dictionary containing strength score (0-100) and feedback
        """
        score = 0
        feedback = []

        # Length contribution (max 30 points)
        if len(password) >= 16:
            score += 30
            feedback.append("Excellent length")
        elif len(password) >= 12:
            score += 25
            feedback.append("Good length")
        elif len(password) >= 8:
            score += 20
        else:
            feedback.append("Password is too short")

        # Character diversity (max 40 points)
        if re.search(r"[a-z]", password):
            score += 10
        else:
            feedback.append("Add lowercase letters")

        if re.search(r"[A-Z]", password):
            score += 10
        else:
            feedback.append("Add uppercase letters")

        if re.search(r"\d", password):
            score += 10
        else:
            feedback.append("Add numbers")

        if re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            score += 10
        else:
            feedback.append("Add special characters")

        # Uniqueness (max 30 points)
        if password.lower() not in COMMON_WEAK_PASSWORDS:
            score += 20
        else:
            feedback.append("This is a commonly used password")
            score = min(score, 30)  # Cap score for common passwords

        # No patterns
        if not re.match(r"^(.)\1+$", password):
            score += 5
        else:
            feedback.append("Avoid repeating characters")

        if not re.match(r"^(?:012|123|234|345|456|567|678|789)+", password):
            score += 5
        else:
            feedback.append("Avoid sequential numbers")

        # Determine strength category
        if score >= 80:
            strength = "Very Strong"
        elif score >= 60:
            strength = "Strong"
        elif score >= 40:
            strength = "Medium"
        elif score >= 20:
            strength = "Weak"
        else:
            strength = "Very Weak"

        return {
            "score": score,
            "strength": strength,
            "feedback": feedback if feedback else ["Password is strong"],
        }


# Create a default validator instance
default_password_validator = PasswordValidator()


def validate_password(password: str | Any) -> str:
    """
    Validate a password using the default validator.

    This is a convenience function that uses the default password policy.

    Args:
        password: The password to validate

    Returns:
        The validated password

    Raises:
        PasswordValidationError: If password doesn't meet requirements
    """
    return default_password_validator.validate(password)


def get_password_strength(password: str) -> dict[str, Any]:
    """
    Get password strength score and feedback.

    Args:
        password: The password to analyze

    Returns:
        Dictionary containing strength score and feedback
    """
    return default_password_validator.get_password_strength(password)
