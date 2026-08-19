"""Pure tests for app.modules.ai.llm_client.resolve_ai_credentials (see
docs/features/55-dual-ai-provider.md) -- no network, no SDK mocking; this
only exercises the "which provider, which key" decision, not either
provider's own real call shape.
"""

import unittest

from app.core.config import Settings
from app.modules.ai.llm_client import AICredentials, resolve_ai_credentials


class ResolveAICredentialsTests(unittest.TestCase):
    # Settings is a pydantic-settings BaseSettings subclass that reads the
    # real .env for any field NOT explicitly passed to the constructor --
    # so every test here passes all three relevant fields explicitly
    # (ai_provider/anthropic_api_key/openai_api_key), never relying on a
    # "default," to stay isolated from whatever the developer's own real
    # .env currently has configured.
    def test_defaults_to_anthropic_credentials_when_key_present(self):
        settings = Settings(ai_provider="anthropic", anthropic_api_key="ak", openai_api_key=None)
        self.assertEqual(resolve_ai_credentials(settings), AICredentials(provider="anthropic", api_key="ak"))

    def test_no_key_at_all_returns_none(self):
        settings = Settings(ai_provider="anthropic", anthropic_api_key=None, openai_api_key=None)
        self.assertIsNone(resolve_ai_credentials(settings))

    def test_selected_provider_missing_its_own_key_returns_none_even_if_the_other_has_one(self):
        settings = Settings(ai_provider="openai", anthropic_api_key="ak", openai_api_key=None)
        self.assertIsNone(resolve_ai_credentials(settings))

    def test_selects_openai_credentials_when_configured(self):
        settings = Settings(ai_provider="openai", anthropic_api_key=None, openai_api_key="ok")
        self.assertEqual(resolve_ai_credentials(settings), AICredentials(provider="openai", api_key="ok"))

    def test_switching_provider_back_to_anthropic_uses_anthropic_key_again(self):
        settings = Settings(ai_provider="anthropic", anthropic_api_key="ak", openai_api_key="ok")
        self.assertEqual(resolve_ai_credentials(settings), AICredentials(provider="anthropic", api_key="ak"))


if __name__ == "__main__":
    unittest.main()
