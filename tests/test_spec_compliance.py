"""Validate all SKILL.md files against AgentSkills.io specification rules.

Run standalone: pytest tests/test_spec_compliance.py -v
This is designed to be a fast CI gate that catches malformed skill definitions.
"""

import re
import pytest
from pathlib import Path

import yaml

SKILLS_DIR = Path(__file__).parent.parent / "skills"

# Spec rules for skill names
NAME_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
NAME_MAX_LENGTH = 64
DESCRIPTION_MAX_LENGTH = 1024


def _parse_frontmatter(text: str) -> dict:
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    return yaml.safe_load(parts[1]) or {}


def _get_all_skill_dirs():
    """Find all directories in skills/ that contain SKILL.md."""
    if not SKILLS_DIR.exists():
        return []
    return [
        d for d in sorted(SKILLS_DIR.iterdir())
        if d.is_dir() and (d / "SKILL.md").exists()
    ]


SKILL_DIRS = _get_all_skill_dirs()


@pytest.fixture(params=SKILL_DIRS, ids=[d.name for d in SKILL_DIRS])
def skill_dir(request):
    return request.param


@pytest.fixture
def frontmatter(skill_dir):
    text = (skill_dir / "SKILL.md").read_text()
    return _parse_frontmatter(text)


class TestSpecCompliance:
    def test_has_frontmatter(self, skill_dir):
        text = (skill_dir / "SKILL.md").read_text()
        fm = _parse_frontmatter(text)
        assert fm, f"{skill_dir.name}/SKILL.md has no YAML frontmatter"

    def test_name_present(self, frontmatter, skill_dir):
        assert "name" in frontmatter, f"{skill_dir.name}: missing 'name'"

    def test_name_format(self, frontmatter, skill_dir):
        name = frontmatter.get("name", "")
        assert NAME_PATTERN.match(name), (
            f"{skill_dir.name}: name '{name}' must be lowercase alphanumeric + hyphens, "
            f"no leading/trailing/consecutive hyphens"
        )

    def test_name_length(self, frontmatter, skill_dir):
        name = frontmatter.get("name", "")
        assert len(name) <= NAME_MAX_LENGTH, (
            f"{skill_dir.name}: name exceeds {NAME_MAX_LENGTH} chars"
        )

    def test_name_matches_directory(self, frontmatter, skill_dir):
        name = frontmatter.get("name", "")
        assert name == skill_dir.name, (
            f"SKILL.md name '{name}' does not match directory '{skill_dir.name}'"
        )

    def test_description_present(self, frontmatter, skill_dir):
        desc = frontmatter.get("description", "")
        assert desc and desc.strip(), f"{skill_dir.name}: missing 'description'"

    def test_description_length(self, frontmatter, skill_dir):
        desc = frontmatter.get("description", "")
        assert len(desc) <= DESCRIPTION_MAX_LENGTH, (
            f"{skill_dir.name}: description exceeds {DESCRIPTION_MAX_LENGTH} chars"
        )

    def test_metadata_is_dict_if_present(self, frontmatter, skill_dir):
        if "metadata" in frontmatter:
            assert isinstance(frontmatter["metadata"], dict), (
                f"{skill_dir.name}: metadata must be a key-value mapping"
            )

    def test_triggers_are_list(self, frontmatter, skill_dir):
        metadata = frontmatter.get("metadata", {})
        if "triggers" in metadata:
            triggers = metadata["triggers"]
            assert isinstance(triggers, list), (
                f"{skill_dir.name}: triggers must be a list"
            )
            assert all(isinstance(t, str) for t in triggers), (
                f"{skill_dir.name}: all triggers must be strings"
            )

    def test_markdown_body_exists(self, skill_dir):
        text = (skill_dir / "SKILL.md").read_text()
        parts = text.split("---", 2)
        body = parts[2].strip() if len(parts) >= 3 else ""
        assert body, f"{skill_dir.name}: SKILL.md has no markdown body"


class TestProjectSkillsDiscovery:
    def test_at_least_one_skill_exists(self):
        assert len(SKILL_DIRS) >= 1, "No skills found in skills/ directory"

    def test_expected_skills_present(self):
        names = {d.name for d in SKILL_DIRS}
        expected = {"email-writer", "calendar-manager", "web-searcher", "content-summarizer"}
        assert expected.issubset(names), f"Missing skills: {expected - names}"
