import pytest
from deskill.core.ids import (
    normalize_id, parse_reference, disk_path, gh_parts,
    reference_spelling, is_gh, is_cloud, is_local_only,
)


def test_case_folding():
    assert normalize_id('GH:SylphAI-Inc/Skills/Deploy/') == 'gh:SylphAI-Inc/Skills/Deploy'
    assert normalize_id('HUB:Stripe/Payments') == 'hub:stripe/payments'
    assert normalize_id('Team-Flows/Deploy') == 'team-flows/deploy'


def test_hub_is_exactly_owner_name():
    assert normalize_id('hub:sylphai/glowmotion') == 'hub:sylphai/glowmotion'
    with pytest.raises(ValueError, match='exactly owner/name'):
        normalize_id('hub:onlyname')
    with pytest.raises(ValueError, match='exactly owner/name'):
        normalize_id('hub:a/b/c')


def test_disk_spellings_fold_back():
    assert normalize_id('gh/anthropics/skills/skills/docx') == 'gh:anthropics/skills/skills/docx'
    assert normalize_id('hub/sylphai/glowmotion') == 'hub:sylphai/glowmotion'


def test_bare_is_local_only():
    assert is_cloud('gh:a/b') and is_cloud('hub:a/b')
    assert not is_cloud('a/b') and not is_cloud('deploy')
    assert is_local_only('team-flows/deploy')


def test_pasted_github_urls():
    want = 'gh:vectorize-io/hindsight/skills/hindsight-docs'
    for s in [
        'gh:vectorize-io/hindsight/skills/hindsight-docs',
        'https://github.com/vectorize-io/hindsight/tree/main/skills/hindsight-docs',
        'https://www.github.com/vectorize-io/hindsight/tree/main/skills/hindsight-docs',
        'github.com/vectorize-io/hindsight/tree/main/skills/hindsight-docs',
        'https://github.com/vectorize-io/hindsight/blob/main/skills/hindsight-docs/SKILL.md',
        'https://github.com/vectorize-io/hindsight/tree/main/skills/hindsight-docs/',
        'https://github.com/vectorize-io/hindsight/tree/main/skills/hindsight-docs?tab=readme-ov-file',
        'https://github.com/vectorize-io/hindsight/tree/main/skills/hindsight-docs#usage',
    ]:
        assert normalize_id(s) == want, s
    assert normalize_id('https://github.com/SylphAI-Inc/skills.git') == 'gh:SylphAI-Inc/skills'
    # URL pasted after the gh: marker is not read as a scheme
    assert normalize_id('gh:https://github.com/itsmostafa/aws-agent-skills') == 'gh:itsmostafa/aws-agent-skills'
    assert normalize_id('gh:github.com/itsmostafa/aws-agent-skills') == 'gh:itsmostafa/aws-agent-skills'


def test_only_github_com_is_github():
    for host in ['https://evil-github.com/owner/repo',
                 'https://github.com.attacker.net/owner/repo',
                 'https://notgithub.com/owner/repo']:
        try:
            got = normalize_id(host)
        except ValueError:
            continue
        assert not is_gh(got), host


def test_traversal_and_junk_rejected():
    for bad in ['../etc/passwd', 'a/../b', 'a/./b', 'a//b', 'a\\b', '',
                'gh:onlyowner', 'gh:owner/repo/../etc',
                'gh:owner/repo/a%2Fb/x', 'gh:owner/repo/%2E%2E/etc',
                'https://github.com/owner/repo/%2E%2E/%2E%2E/etc']:
        with pytest.raises(ValueError):
            normalize_id(bad)


def test_permissive_segments():
    for id in ['gh:owner/repo/.claude/skills/thing',
               'gh:owner/repo/_official/thing',
               'gh:owner/repo/@claude-flow/thing',
               'gh:owner/repo/营销技能库/thing']:
        assert normalize_id(id) == id
    # spaces: canonical keeps the real name; %20 decodes
    assert normalize_id('gh:owner/repo/Deep Research/x') == 'gh:owner/repo/Deep Research/x'
    assert normalize_id('gh:owner/repo/Deep%20Research/x') == 'gh:owner/repo/Deep Research/x'


def test_reference_spelling_round_trips():
    id = normalize_id('gh:owner/repo/skills/API%20Gateway')
    ref = reference_spelling(id)
    assert ref == 'gh:owner/repo/skills/API%20Gateway'   # marker stays literal
    assert normalize_id(ref) == id


def test_disk_path_and_gh_parts():
    assert disk_path('gh:acme/skills/deploy') == 'gh/acme/skills/deploy'
    assert disk_path('hub:sylphai/glowmotion') == 'hub/sylphai/glowmotion'
    assert disk_path('sylphai/glowmotion') == 'sylphai/glowmotion'
    p = gh_parts('gh:acme/skills/a/b')
    assert (p.owner, p.repo, p.sub) == ('acme', 'skills', 'a/b')
    assert gh_parts('gh:acme/skills').sub == ''


def test_parse_reference_suffixes():
    r = parse_reference('@skills:a/b:save')
    assert (r.id, r.whole_dir, r.save, r.install) == ('a/b', False, True, False)
    r = parse_reference('@skills:a/b:save:install')
    assert r.save and r.install
    r = parse_reference('@skills:a/b:install:save')
    assert r.save and r.install
    r = parse_reference('@skills:stripe/agent-toolkit/')
    assert r.id == 'stripe/agent-toolkit' and r.whole_dir
