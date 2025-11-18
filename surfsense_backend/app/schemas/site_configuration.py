from pydantic import BaseModel, Field


class SiteConfigurationBase(BaseModel):
    # Header/Navbar toggles
    show_pricing_link: bool = False
    show_docs_link: bool = False
    show_github_link: bool = False
    show_sign_in: bool = True

    # Homepage toggles
    show_get_started_button: bool = False
    show_talk_to_us_button: bool = False

    # Footer toggles
    show_pages_section: bool = False
    show_legal_section: bool = False
    show_register_section: bool = False

    # Route disabling
    disable_pricing_route: bool = True
    disable_docs_route: bool = True
    disable_contact_route: bool = True
    disable_terms_route: bool = True
    disable_privacy_route: bool = True

    # Registration control
    disable_registration: bool = False

    # Custom text
    custom_copyright: str | None = Field(default="SurfSense 2025", max_length=200)


class SiteConfigurationUpdate(SiteConfigurationBase):
    """Schema for updating site configuration (all fields optional)"""
    show_pricing_link: bool | None = None
    show_docs_link: bool | None = None
    show_github_link: bool | None = None
    show_sign_in: bool | None = None
    show_get_started_button: bool | None = None
    show_talk_to_us_button: bool | None = None
    show_pages_section: bool | None = None
    show_legal_section: bool | None = None
    show_register_section: bool | None = None
    disable_pricing_route: bool | None = None
    disable_docs_route: bool | None = None
    disable_contact_route: bool | None = None
    disable_terms_route: bool | None = None
    disable_privacy_route: bool | None = None
    disable_registration: bool | None = None
    custom_copyright: str | None = None


class SiteConfigurationRead(SiteConfigurationBase):
    id: int

    model_config = {"from_attributes": True}


class SiteConfigurationPublic(SiteConfigurationBase):
    """Public-facing schema (same as base, but explicitly named for clarity)"""
    pass
