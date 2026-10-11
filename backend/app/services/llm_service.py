from app.core.config import settings


class LlmService:
    async def complete(self, text: str) -> str:
        if not settings.llm_api_key:
            # shortcut: no provider wired yet; echo so the pipeline runs locally
            return text
        raise NotImplementedError("wire the configured LLM provider here")


llm_service = LlmService()
