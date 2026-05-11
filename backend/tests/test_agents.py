from pathlib import Path

from app.services.agents import AgentClient
from app.services.agents.mock import MockAgentClient
from app.services.notion import NotionSyncClient
from app.services.notion.mock import MockNotionSyncClient


def test_mock_agent_client_implements_agent_client_contract() -> None:
    fixture_path = Path(__file__).resolve().parents[2] / "data" / "snake_escape_fixture.json"

    client = MockAgentClient(fixture_path)

    assert isinstance(client, AgentClient)


def test_mock_notion_sync_client_implements_notion_contract() -> None:
    client = MockNotionSyncClient()

    assert isinstance(client, NotionSyncClient)
