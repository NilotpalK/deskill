"""The synthetic skill corpus: 10 hand-authored targets, 10 checkable skills,
and a programmatic distractor pool (topic x aspect) taking the total past 120.
"""
import json
import re
from dataclasses import dataclass, field
from typing import Callable


@dataclass(frozen=True)
class Domain:
    name: str                      # kebab-case skill name (= its .atskills path)
    description: str               # one-line frontmatter description (goes resident)
    body: str                      # SKILL.md body
    task_paraphrases: tuple = ()   # what a user actually types — never the description verbatim


@dataclass(frozen=True)
class CheckableDomain(Domain):
    checker: Callable[[str], bool] = None
    good_example: str = ''


TARGETS = [
    Domain(
        name='pdf-form-filling',
        description='Use when the user needs to fill out or complete fields in a PDF form',
        body='Extract the form fields first, then fill each one; flatten before returning.',
        task_paraphrases=(
            'I have this tax document with blank boxes I need to complete',
            'Can you help me put my details into this fillable PDF?',
            'This application form is a PDF and I need the fields filled in',
        )),
    Domain(
        name='commit-message-style',
        description='Use when the user is writing or rewording a git commit message',
        body='Imperative mood, subject under 50 chars, wrapped body explaining why.',
        task_paraphrases=(
            'How should I describe this change when I commit it?',
            'Reword this so it reads like a proper commit subject line',
            "I'm about to git commit — what do I write?",
        )),
    Domain(
        name='aws-key-rotation',
        description='Use when the user wants to rotate AWS access keys or credentials',
        body='Create the new key, roll deployments, verify, then disable and delete the old key.',
        task_paraphrases=(
            'Our IAM access keys are 9 months old and security wants them replaced',
            'Walk me through swapping out the AWS credentials our app uses',
            'I need to retire this leaked AWS key without downtime',
        )),
    Domain(
        name='sql-migration-review',
        description='Use when the user asks to review a database schema migration for safety',
        body='Check for table locks, backfill strategy, index build mode, and rollback path.',
        task_paraphrases=(
            'Is this ALTER TABLE going to lock production?',
            'Look over my new migration before I run it on the main database',
            'Sanity-check this schema change for our Postgres cluster',
        )),
    Domain(
        name='api-error-copywriting',
        description='Use when the user is wording error messages shown to API consumers',
        body='State what failed, why, and the caller action; never leak internals.',
        task_paraphrases=(
            'What should the 429 response body say to developers?',
            'Help me phrase the message users see when validation fails',
            'Write friendlier text for our API failure responses',
        )),
    Domain(
        name='dockerfile-slimming',
        description='Use when the user wants to shrink a Docker image or speed up its build',
        body='Multi-stage builds, pinned slim bases, layer-order caching, .dockerignore.',
        task_paraphrases=(
            'Our container image is 2GB, how do I cut it down?',
            'The docker build takes forever — make it smaller and faster',
            'Trim this Dockerfile so deploys stop timing out',
        )),
    Domain(
        name='i18n-string-extraction',
        description='Use when the user is extracting hardcoded UI strings for translation',
        body='Move literals to message catalogs, key by meaning, never concatenate fragments.',
        task_paraphrases=(
            'We are localizing the app — what do I do with all the inline English text?',
            'Pull the user-facing strings out of these components for the translators',
            'Prepare this screen for a French version',
        )),
    Domain(
        name='oncall-handoff-notes',
        description='Use when the user is writing an on-call shift handoff summary',
        body='Open incidents first, then watches, then quiet confirmations; link runbooks.',
        task_paraphrases=(
            'My rotation ends in an hour, what do I tell the next person?',
            'Draft the pager handover for tonight',
            'Summarize this week of incidents for whoever takes over on-call',
        )),
    Domain(
        name='csv-data-cleaning',
        description='Use when the user needs to clean or normalize messy CSV data',
        body='Sniff the dialect, normalize encodings and dates, dedupe on a declared key.',
        task_paraphrases=(
            'This spreadsheet export has broken characters and duplicate rows',
            'Tidy up this comma-separated dump before I load it into the warehouse',
            'The dates in this CSV are in three different formats — fix them',
        )),
    Domain(
        name='changelog-writing',
        description='Use when the user is drafting release notes or a changelog entry',
        body='Group by user impact, lead with breaking changes, link issues.',
        task_paraphrases=(
            'We ship Friday — turn these merged PRs into something users can read',
            'What goes in the CHANGELOG for version 2.3?',
            'Write the announcement list of what changed this sprint',
        )),
]


def _has_json_with_keys(reply: str, keys: set) -> bool:
    decoder = json.JSONDecoder()
    for i, ch in enumerate(reply):
        if ch != '{':
            continue
        try:
            obj, _ = decoder.raw_decode(reply, i)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and keys <= set(obj):
            return True
    return False


CHECKABLE = [
    CheckableDomain(
        name='incident-summary-json',
        description='Use when the user asks to summarize a production incident',
        body='Reply with a JSON object containing exactly the keys "severity", "summary", and "next_steps".',
        task_paraphrases=(
            'The checkout service was down 40 minutes this morning after a bad deploy — write it up',
            'Give me the postmortem-ready summary: database failover failed at 2am, on-call recovered manually',
            'Summarize this outage: CDN misconfiguration served stale pages to EU users for 2 hours',
        ),
        checker=lambda r: _has_json_with_keys(r, {'severity', 'summary', 'next_steps'}),
        good_example='{"severity": "high", "summary": "checkout down", "next_steps": "add deploy gate"}'),
    CheckableDomain(
        name='conventional-commits',
        description='Use when the user asks for a commit message for a change',
        body='Write commit subjects as Conventional Commits: type(scope): description — types feat, fix, chore, docs, refactor, test.',
        task_paraphrases=(
            'I fixed the retry logic in the payments client, what do I commit with?',
            'Give me a commit message: added dark mode toggle to settings',
            'Commit message for removing the deprecated v1 endpoints please',
        ),
        checker=lambda r: bool(re.search(  # tolerate inline-code (backtick) wrapping
            r'^(feat|fix|chore|docs|refactor|test)(\([\w-]+\))?!?: .{1,72}$',
            r.replace('`', ''), re.MULTILINE)),
        good_example='fix(payments): retry idempotently on gateway timeouts'),
    CheckableDomain(
        name='semver-verdict',
        description='Use when the user asks what version bump a change requires',
        body='End your answer with a line "VERDICT: MAJOR", "VERDICT: MINOR", or "VERDICT: PATCH".',
        task_paraphrases=(
            'We renamed a public function parameter — what do we bump?',
            'Added an optional flag to the CLI, nothing else changed. Version?',
            'Fixed a typo in an error string only. What release number does this need?',
        ),
        checker=lambda r: bool(re.search(r'^VERDICT: (MAJOR|MINOR|PATCH)\s*$', r, re.MULTILINE)),
        good_example='This breaks callers.\nVERDICT: MAJOR'),
    CheckableDomain(
        name='ticket-title-format',
        description='Use when the user asks to title or file an engineering ticket',
        body='Ticket titles must look like "[TEAM-123] Imperative summary" — team key in brackets, then an imperative sentence.',
        task_paraphrases=(
            'File something for the flaky login test, team key AUTH, next number is 481',
            'What do I call the ticket about slow search indexing? Team SRCH, number 92',
            'Name the bug report: mobile app crashes on rotate. Team APP, id 1204',
        ),
        checker=lambda r: bool(re.search(r'\[[A-Z]+-\d+\] \w', r)),
        good_example='[AUTH-481] Stabilize the flaky login test'),
    CheckableDomain(
        name='rollback-plan-steps',
        description='Use when the user asks for a deployment rollback plan',
        body='Rollback plans are exactly three numbered steps followed by a final line starting "RISK:".',
        task_paraphrases=(
            'If tonight\'s release goes bad, how do we back out?',
            'Write the revert procedure for the payments deploy',
            'Give me the undo plan for shipping the new router config',
        ),
        checker=lambda r: bool(re.search(r'1\..+\n.*2\..+\n.*3\..+', r, re.DOTALL)
                               and re.search(r'^RISK:', r, re.MULTILINE)),
        good_example='1. Freeze traffic\n2. Redeploy previous tag\n3. Verify health\nRISK: cache skew'),
    CheckableDomain(
        name='sql-review-verdict',
        description='Use when the user asks for a review of a SQL statement',
        body='End every review with "APPROVED" or "BLOCKED: <one-line reason>" on its own line.',
        task_paraphrases=(
            'Review: DELETE FROM sessions WHERE last_seen < now() - interval \'90 days\';',
            'Is this okay to run? UPDATE users SET plan = \'free\' WHERE plan IS NULL;',
            'Check this query before I ship it: ALTER TABLE orders ADD COLUMN note text;',
        ),
        checker=lambda r: bool(re.search(r'^(APPROVED|BLOCKED: .+)\s*$', r, re.MULTILINE)),
        good_example='Safe, bounded delete.\nAPPROVED'),
    CheckableDomain(
        name='release-notes-sections',
        description='Use when the user asks to draft release notes for a version',
        body='Release notes must contain the markdown headers "## Added" and "## Fixed".',
        task_paraphrases=(
            'Draft notes for 3.1: new export button, fixed the timezone bug',
            'Users need to hear about the SSO support and the crash fix — write the notes',
            'Release write-up please: added webhooks, fixed duplicate emails',
        ),
        checker=lambda r: '## Added' in r and '## Fixed' in r,
        good_example='## Added\n- Webhooks\n## Fixed\n- Duplicate emails'),
    CheckableDomain(
        name='eta-format',
        description='Use when the user asks how long a piece of engineering work will take',
        body='Every estimate must include a line "ETA: <number>h".',
        task_paraphrases=(
            'How long to add rate limiting to the public API?',
            'Ballpark the effort for migrating the cron jobs to the scheduler',
            'Time estimate for writing the S3 backup script?',
        ),
        checker=lambda r: bool(re.search(r'\bETA: \d+(\.\d+)?h\b', r)),
        good_example='Straightforward middleware change.\nETA: 6h'),
    CheckableDomain(
        name='api-response-shape',
        description='Use when the user asks to design a JSON API response payload',
        body='All example payloads use the envelope {"status": ..., "data": ..., "error": ...}.',
        task_paraphrases=(
            'Show me the JSON we should return for the list-invoices endpoint',
            'Design the response body for a successful profile fetch',
            'What does the payload look like when the lookup succeeds?',
        ),
        checker=lambda r: _has_json_with_keys(r, {'status', 'data', 'error'}),
        good_example='{"status": "ok", "data": {"id": 1}, "error": null}'),
    CheckableDomain(
        name='standup-format',
        description='Use when the user asks to write a daily standup update',
        body='Standup updates are three lines starting "Y:" (yesterday), "T:" (today), "B:" (blockers).',
        task_paraphrases=(
            'Yesterday I finished the login flow, today I start on sessions, waiting on designs — write my update',
            'Turn this into my standup: shipped the importer, next is validation, no blockers',
            'Post for me: worked on flaky tests, continuing today, blocked on CI access',
        ),
        checker=lambda r: bool(re.search(r'^Y:.+', r, re.MULTILINE)
                               and re.search(r'^T:.+', r, re.MULTILINE)
                               and re.search(r'^B:', r, re.MULTILINE)),
        good_example='Y: shipped importer\nT: validation\nB: none'),
]


def _sib(name, desc):
    return Domain(name=name, description=desc, body=f'Guidance for {name.replace("-", " ")}.')


# Two confusable siblings per target: same topic family, different scope.
# exp5 measures whether models select the exact right skill when neighbors overlap.
SIBLINGS = {
    'pdf-form-filling': [
        _sib('pdf-page-splitting', 'Use when the user wants to split, merge, or extract pages from a PDF'),
        _sib('pdf-text-ocr', 'Use when the user needs to pull text out of scanned or image-based PDFs')],
    'commit-message-style': [
        _sib('pr-description-style', 'Use when the user is writing a pull request title or description'),
        _sib('code-review-comments', 'Use when the user is wording review comments on someone\'s code')],
    'aws-key-rotation': [
        _sib('aws-iam-policy-review', 'Use when the user is auditing or tightening AWS IAM policies'),
        _sib('secrets-vault-migration', 'Use when the user is moving credentials into a secrets manager')],
    'sql-migration-review': [
        _sib('sql-query-tuning', 'Use when the user wants to speed up a slow SQL query'),
        _sib('database-backup-strategy', 'Use when the user is planning database backups or restores')],
    'api-error-copywriting': [
        _sib('api-docs-writing', 'Use when the user is writing reference documentation for an API'),
        _sib('api-versioning-policy', 'Use when the user is deciding how to version or deprecate API endpoints')],
    'dockerfile-slimming': [
        _sib('docker-compose-setup', 'Use when the user is wiring services together with docker compose'),
        _sib('k8s-resource-limits', 'Use when the user is setting container CPU or memory limits in Kubernetes')],
    'i18n-string-extraction': [
        _sib('locale-date-formatting', 'Use when the user is formatting dates, numbers, or currency per locale'),
        _sib('rtl-layout-support', 'Use when the user is adapting a UI for right-to-left languages')],
    'oncall-handoff-notes': [
        _sib('incident-postmortems', 'Use when the user is writing a post-incident review document'),
        _sib('alert-runbook-writing', 'Use when the user is writing or updating an alert runbook')],
    'csv-data-cleaning': [
        _sib('excel-formula-help', 'Use when the user needs help with spreadsheet formulas'),
        _sib('data-schema-inference', 'Use when the user wants to infer column types from a data sample')],
    'changelog-writing': [
        _sib('release-versioning', 'Use when the user is choosing version numbers for a release'),
        _sib('announcement-blog-drafting', 'Use when the user is drafting a product announcement post')],
}


def exp5_pool() -> list[Domain]:
    """Targets + all confusable siblings + distractors, 50 skills total."""
    sibs = [s for pair in SIBLINGS.values() for s in pair]
    return TARGETS + sibs + distractors()[:50 - len(TARGETS) - len(sibs)]


_TOPICS = [
    'kubernetes', 'terraform', 'react', 'django', 'kafka', 'redis', 'graphql',
    'grpc', 'nginx', 'postgres', 'mongodb', 'elasticsearch', 'rabbitmq',
    'jenkins', 'github-actions', 'stripe-integration', 'oauth-flows', 'webpack',
    'typescript', 'pandas', 'spark', 'airflow', 'dbt', 'snowflake', 'looker',
    'figma-plugins', 'jira-automation', 'slack-bots', 'chrome-extensions', 'electron',
]
_ASPECTS = ['debugging', 'upgrading', 'cost-tuning', 'onboarding']


def distractors() -> list[Domain]:
    out = []
    for topic in _TOPICS:
        for aspect in _ASPECTS:
            human = topic.replace('-', ' ')
            out.append(Domain(
                name=f'{topic}-{aspect}',
                description=f'Use when the user needs help {aspect.replace("-", " ")} {human}',
                body=f'Guidance for {aspect} work on {human}.'))
    return out


def all_domains() -> list[Domain]:
    return TARGETS + CHECKABLE + distractors()
