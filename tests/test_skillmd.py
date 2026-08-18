import pytest
from deskill.core.skillmd import parse_skill_md, require_trigger_fields

FULL = '---\nname: tdd\ndescription: Test-driven development\ntags: [a, b]\n---\n# Body\n'


def test_parse_full():
    s = parse_skill_md(FULL)
    assert s.frontmatter['name'] == 'tdd'
    assert s.frontmatter['tags'] == ['a', 'b']
    assert s.body.strip() == '# Body'


def test_no_frontmatter_is_valid():
    s = parse_skill_md('just a body\n')
    assert s.frontmatter == {} and s.body == 'just a body\n'


def test_unknown_fields_ignored_not_rejected():
    s = parse_skill_md('---\nname: x\ndescription: d\nfuture_field: ok\n---\nb')
    assert s.frontmatter['future_field'] == 'ok'   # kept, never an error


def test_unclosed_frontmatter_raises():
    with pytest.raises(ValueError):
        parse_skill_md('---\nname: x\nno closing fence')


def test_require_trigger_fields():
    require_trigger_fields({'name': 'x', 'description': 'd'})
    for fm in [{}, {'name': 'x'}, {'description': 'd'}, {'name': '', 'description': 'd'}]:
        with pytest.raises(ValueError, match='frontmatter'):
            require_trigger_fields(fm)
