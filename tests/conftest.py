"""Shared fixtures for SkillForge tests."""

import shutil
import pytest
from pathlib import Path

from knowledge import KnowledgeBase
from skills import SkillRegistry, SkillLoader, DeclarativeSkill, ExecutionContext
from llm import MockProvider
from tools import ToolRegistry


@pytest.fixture
def tmp_data_dir(tmp_path):
    """Temporary directory for learning data."""
    data_dir = tmp_path / "data" / "learning"
    data_dir.mkdir(parents=True)
    return data_dir


@pytest.fixture
def tmp_skills_dir(tmp_path):
    """Temporary skills directory with a minimal test skill."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    return skills_dir


@pytest.fixture
def sample_skill_dir(tmp_skills_dir):
    """Create a minimal spec-compliant skill directory."""
    skill_dir = tmp_skills_dir / "test-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: test-skill\n"
        "description: A test skill for unit testing.\n"
        "license: MIT\n"
        "metadata:\n"
        "  triggers:\n"
        "    - test\n"
        "    - run test\n"
        "  output_type: test_output\n"
        "  context_fields:\n"
        "    test_flag: { type: bool, default: false }\n"
        "---\n"
        "\n"
        "# Test Skill\n"
        "\n"
        "A skill used for testing the declarative engine.\n"
    )
    return skill_dir


@pytest.fixture
def sample_skill_with_templates(sample_skill_dir):
    """Add templates to the sample skill."""
    assets_dir = sample_skill_dir / "assets"
    assets_dir.mkdir()
    (assets_dir / "templates.yaml").write_text(
        "greeting:\n"
        "  match: [hello, hi]\n"
        "  subject: Greeting\n"
        "  body: Hello there!\n"
        "\n"
        "farewell:\n"
        "  match: [bye, goodbye]\n"
        "  subject: Farewell\n"
        "  body: Goodbye!\n"
        "\n"
        "default:\n"
        "  match: []\n"
        "  subject: Default\n"
        "  body: Default output\n"
    )
    return sample_skill_dir


@pytest.fixture
def knowledge_base(tmp_data_dir):
    """Fresh KnowledgeBase instance."""
    return KnowledgeBase(tmp_data_dir)


@pytest.fixture
def skill_registry(knowledge_base, tmp_skills_dir, sample_skill_dir):
    """Registry loaded from the tmp skills directory."""
    return SkillRegistry(knowledge_base, tmp_skills_dir)


@pytest.fixture
def real_skills_dir():
    """Path to the project's actual skills directory."""
    return Path(__file__).parent.parent / "skills"


@pytest.fixture
def real_skill_registry(knowledge_base, real_skills_dir):
    """Registry loaded from the project's real skills directory."""
    return SkillRegistry(knowledge_base, real_skills_dir)


@pytest.fixture
def mock_llm_provider():
    """MockProvider instance for deterministic LLM testing."""
    return MockProvider()


@pytest.fixture
def tool_registry():
    """Fresh ToolRegistry instance."""
    return ToolRegistry()
