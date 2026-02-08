"""Tests for SkillLoader and SKILL.md parsing."""

import pytest
from pathlib import Path

from skills import SkillLoader, DeclarativeSkill, SkillRegistry
from knowledge import KnowledgeBase


class TestFrontmatterParsing:
    def test_parse_valid_frontmatter(self):
        text = (
            "---\n"
            "name: my-skill\n"
            "description: A skill.\n"
            "---\n"
            "\n"
            "# Body\n"
        )
        result = SkillLoader._parse_frontmatter(text)
        assert result["name"] == "my-skill"
        assert result["description"] == "A skill."

    def test_parse_frontmatter_with_metadata(self):
        text = (
            "---\n"
            "name: my-skill\n"
            "description: Test.\n"
            "metadata:\n"
            "  triggers:\n"
            "    - foo\n"
            "    - bar\n"
            "  output_type: widget\n"
            "---\n"
            "# Body\n"
        )
        result = SkillLoader._parse_frontmatter(text)
        assert result["metadata"]["triggers"] == ["foo", "bar"]
        assert result["metadata"]["output_type"] == "widget"

    def test_parse_no_frontmatter(self):
        assert SkillLoader._parse_frontmatter("# Just markdown") == {}

    def test_parse_incomplete_frontmatter(self):
        assert SkillLoader._parse_frontmatter("---\nname: x\n") == {}


class TestSkillLoading:
    def test_load_skill_from_directory(self, sample_skill_dir, knowledge_base):
        skill = SkillLoader._load_skill(sample_skill_dir, knowledge_base)
        assert skill is not None
        assert skill.name == "test_skill"  # Hyphen -> underscore
        assert isinstance(skill, DeclarativeSkill)

    def test_load_skill_extracts_metadata(self, sample_skill_dir, knowledge_base):
        skill = SkillLoader._load_skill(sample_skill_dir, knowledge_base)
        assert skill.output_type == "test_output"
        assert "test" in skill.triggers
        assert "run test" in skill.triggers

    def test_load_skill_extracts_context_fields(self, sample_skill_dir, knowledge_base):
        skill = SkillLoader._load_skill(sample_skill_dir, knowledge_base)
        defaults = skill.get_default_context_values()
        assert defaults == {"test_flag": False}

    def test_load_missing_name_returns_none(self, tmp_skills_dir, knowledge_base):
        bad_dir = tmp_skills_dir / "bad-skill"
        bad_dir.mkdir()
        (bad_dir / "SKILL.md").write_text(
            "---\ndescription: No name field.\n---\n# Bad\n"
        )
        assert SkillLoader._load_skill(bad_dir, knowledge_base) is None

    def test_load_missing_description_returns_none(self, tmp_skills_dir, knowledge_base):
        bad_dir = tmp_skills_dir / "bad-skill2"
        bad_dir.mkdir()
        (bad_dir / "SKILL.md").write_text(
            "---\nname: bad-skill2\n---\n# Bad\n"
        )
        assert SkillLoader._load_skill(bad_dir, knowledge_base) is None

    def test_load_all_skips_non_directories(self, tmp_skills_dir, knowledge_base):
        (tmp_skills_dir / "not_a_dir.txt").write_text("ignored")
        skills = SkillLoader.load_all(knowledge_base, tmp_skills_dir)
        assert "not_a_dir" not in skills

    def test_load_all_skips_dirs_without_skill_md(self, tmp_skills_dir, knowledge_base):
        (tmp_skills_dir / "empty-dir").mkdir()
        skills = SkillLoader.load_all(knowledge_base, tmp_skills_dir)
        assert "empty_dir" not in skills

    def test_load_all_missing_directory(self, knowledge_base, tmp_path):
        skills = SkillLoader.load_all(knowledge_base, tmp_path / "nonexistent")
        assert skills == {}


class TestSkillRegistry:
    def test_registry_loads_from_disk(self, skill_registry):
        assert "test_skill" in skill_registry.list_skills()

    def test_get_by_name(self, skill_registry):
        skill = skill_registry.get("test_skill")
        assert skill is not None
        assert skill.name == "test_skill"

    def test_get_for_task_matches_trigger(self, skill_registry):
        skill = skill_registry.get_for_task("Please run test now")
        assert skill is not None
        assert skill.name == "test_skill"

    def test_get_for_task_no_match(self, skill_registry):
        assert skill_registry.get_for_task("completely unrelated") is None

    def test_register_programmatic_skill(self, skill_registry, knowledge_base):
        """Power users can still register skills programmatically."""
        from skills import BaseSkill, ExecutionContext, ExecutionResult, ExecutionStatus

        class CustomSkill(BaseSkill):
            def _execute_impl(self, context):
                return ExecutionResult(status=ExecutionStatus.SUCCESS)

        custom = CustomSkill("custom", knowledge_base)
        skill_registry.register(custom)
        assert "custom" in skill_registry.list_skills()

    def test_real_skills_loaded(self, real_skill_registry):
        """Verify the project's actual skills load correctly."""
        skills = real_skill_registry.list_skills()
        assert "email_writer" in skills
        assert "calendar_manager" in skills
        assert "web_searcher" in skills
        assert "content_summarizer" in skills
