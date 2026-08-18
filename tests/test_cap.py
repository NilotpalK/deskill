import pytest
from deskill.core.cap import (
    MAX_COLLECTION_SKILLS, leaf_skill_dirs, largest_usable_collections,
    assert_collection_fits, CollectionTooLargeError,
)


def files(n, prefix):
    return [f'{prefix}/s{i:03d}/SKILL.md' for i in range(n)]


def test_leaf_rule():
    assert leaf_skill_dirs(['a/SKILL.md', 'a/examples/nested/SKILL.md',
                            'b/c/SKILL.md', 'b/c/README.md']) == ['a', 'b/c']
    assert leaf_skill_dirs(['SKILL.md', 'refs/x.md']) == ['']
    assert leaf_skill_dirs(['.git/objects/SKILL.md', '.claude/skills/d/SKILL.md',
                            'real/SKILL.md']) == ['.claude/skills/d', 'real']


def test_cap_boundary_inclusive():
    assert_collection_fits(files(MAX_COLLECTION_SKILLS, 'skills'), 'gh:o/r')  # no raise
    with pytest.raises(CollectionTooLargeError) as e:
        assert_collection_fits(files(129, 'skills'), 'gh:o/r')
    assert e.value.count == 129
    assert '129 skills' in str(e.value) and '128' in str(e.value)


def test_cap_counts_skills_not_files():
    paths = ['solo/SKILL.md'] + [f'solo/refs/r{i}.md' for i in range(500)]
    assert_collection_fits(paths, 'gh:o/r')  # one skill, huge bundle: allowed


def test_suggestions_descend_past_oversized_parents():
    paths = (files(400, 'plugins/mega-catalog/skills')
             + files(12, 'plugins/bundle-design-it')
             + files(12, 'plugins/bundle-super-code'))
    with pytest.raises(CollectionTooLargeError) as e:
        assert_collection_fits(paths, 'gh:sickn33/catalog')
    rels = [s.rel for s in e.value.suggestions]
    assert 'plugins/bundle-design-it' in rels and 'plugins/bundle-super-code' in rels
    assert 'plugins' not in rels                      # oversized: never offered
    assert all(s.count > 1 for s in e.value.suggestions)
    assert 'gh:sickn33/catalog/plugins/bundle-design-it' in str(e.value)


def test_repeated_collection_offered_once_shortest():
    paths = []
    for copy in ['skills', 'plugins/claude-copy', 'plugins/codex-copy']:
        paths += files(200, f'{copy}/dump') + files(10, f'{copy}/design-it')
    with pytest.raises(CollectionTooLargeError) as e:
        assert_collection_fits(paths, 'gh:o/r')
    design = [s for s in e.value.suggestions if s.rel.endswith('/design-it')]
    assert len(design) == 1 and design[0].rel == 'skills/design-it'


def test_largest_first_and_flat_fallback():
    skills = ([f'a/big/s{i}' for i in range(200)]
              + [f'a/medium/s{i}' for i in range(100)]
              + [f'a/small/s{i}' for i in range(5)])
    top = largest_usable_collections(skills)[0]
    assert (top.rel, top.count) == ('a/medium', 100)
    flat = largest_usable_collections([f's{i}' for i in range(200)])
    assert len(flat) == 200 and all(o.count == 1 for o in flat)
    # a flat oversized dir still suggests individual skills
    with pytest.raises(CollectionTooLargeError) as e:
        assert_collection_fits([f's{i}/SKILL.md' for i in range(200)], 'gh:o/r')
    assert len(e.value.suggestions) > 0
