from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from modules.llm.models import ModelRole, OnboardingCompletion, SelectedModel
from modules.llm.providers import get_provider


async def choose_model(
    session: Session, role: ModelRole, provider_name: str, model_name: str
) -> SelectedModel:
    provider = get_provider(provider_name, session)
    if provider is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"unknown provider: {provider_name}",
        )

    model = next(
        (model for model in await provider.models() if model.name == model_name),
        None,
    )
    if model is None or not model.installed:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"model is not installed: {model_name}",
        )
    if role is ModelRole.GENERATION and "completion" not in model.capabilities:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"model does not support generation: {model_name}",
        )

    selected = session.get(SelectedModel, role)
    if selected is None:
        selected = SelectedModel(
            role=role,
            provider=provider_name,
            name=model_name,
        )
        session.add(selected)
    else:
        selected.provider = provider_name
        selected.name = model_name
    if session.get(OnboardingCompletion, 1) is None:
        session.add(OnboardingCompletion())
    session.flush()
    return selected
