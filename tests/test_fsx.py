import pytest
from deskill.core.fsx import safe_join, walk_skills


def mkskill(root, rel):
    d = root / rel
    d.mkdir(parents=True, exist_ok=True)
    (d / 'SKILL.md').write_text('---\nname: x\ndescription: d\n---\nb', encoding='utf-8')


def test_safe_join_confines(tmp_path):
    assert safe_join(tmp_path, 'a/b') == (tmp_path / 'a' / 'b').resolve()
    for bad in ['../out', 'a/../../out']:
        with pytest.raises(ValueError):
            safe_join(tmp_path, bad)


def test_walk_leaf_rule_and_dot_dirs(tmp_path):
    mkskill(tmp_path, '.claude/skills/alpha')
    mkskill(tmp_path, '.agents/skills/beta')
    mkskill(tmp_path, 'skills/gamma')
    # nested SKILL.md inside a bundle is that bundle's file
    (tmp_path / 'skills/gamma/examples/nested').mkdir(parents=True)
    (tmp_path / 'skills/gamma/examples/nested/SKILL.md').write_text('not a skill')
    # .git is never content
    (tmp_path / '.git/objects/fake').mkdir(parents=True)
    (tmp_path / '.git/objects/fake/SKILL.md').write_text('not a skill')
    assert walk_skills(tmp_path) == ['.agents/skills/beta', '.claude/skills/alpha', 'skills/gamma']


def test_walk_root_skill(tmp_path):
    mkskill(tmp_path, '.')
    assert walk_skills(tmp_path) == ['']
