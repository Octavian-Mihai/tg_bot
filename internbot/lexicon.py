"""The evidence ranking is computed from: skills, role families, pay, company tiers, résumé signals.

Ported from Jobify's config. These are opinions, not facts, and are meant to be edited: a skill
you don't have is noise, and a company tier list is a guess.
"""
from __future__ import annotations

import re

_I = re.I


def _r(pattern: str) -> re.Pattern:
    return re.compile(pattern, _I)


# Canonical skill -> the shapes a posting writes it in. Bare `go`, `c` and `rest` are
# unmatchable without false positives ("go to market", "C-level"), so they only match in
# unambiguous forms.
SKILL_LEXICON: dict[str, re.Pattern] = {
    "javascript": _r(r"\bjavascript\b|\bes6\b"),
    "typescript": _r(r"\btypescript\b"),
    "python": _r(r"\bpython\b"),
    "java": _r(r"\bjava\b"),
    "c++": _r(r"\bc\+\+|\bcpp\b"),
    "c#": _r(r"\bc#|(?<!\w)\.net\b|\bdotnet\b"),
    "c": _r(r"\bc/c\+\+|\bembedded c\b"),
    "go": _r(r"\bgolang\b|\bgo\s+(?:programming|developer|lang)\b"),
    "rust": _r(r"\brust\b"),
    "ruby": _r(r"\bruby\b|\brails\b"),
    "swift": _r(r"\bswift\b|\bswiftui\b"),
    "kotlin": _r(r"\bkotlin\b"),
    "react": _r(r"\breact\b|\breact\.?js\b|\bnext\.?js\b"),
    "vue": _r(r"\bvue\b|\bnuxt\b"),
    "angular": _r(r"\bangular\b"),
    # Bare "Node" is almost always Node.js, but infrastructure prose says "each compute node".
    "node": _r(
        r"\bnode\.?js\b|\bexpress\.?js\b|"
        r"(?<!compute )(?<!cluster )(?<!worker )(?<!leaf )(?<!graph )(?<!tree )(?<!edge )"
        r"(?<!gpu )(?<!storage )(?<!kubernetes )(?<!k8s )\bnode\b"
    ),
    "django": _r(r"\bdjango\b|\bflask\b|\bfastapi\b"),
    "spring": _r(r"\bspring boot\b|\bspring framework\b"),
    "sql": _r(r"\bsql\b|\bpostgres(?:ql)?\b|\bmysql\b|\bsqlite\b"),
    "nosql": _r(r"\bnosql\b|\bmongodb\b|\bdynamodb\b|\bredis\b|\bcassandra\b"),
    "aws": _r(r"\baws\b|\bamazon web services\b|\bec2\b|\bs3\b|\baws lambda\b"),
    "gcp": _r(r"\bgcp\b|\bgoogle cloud\b"),
    "azure": _r(r"\bazure\b"),
    "docker": _r(r"\bdocker\b|\bcontaineriz(?:ed|ation)\b"),
    "kubernetes": _r(r"\bkubernetes\b|\bk8s\b"),
    "terraform": _r(r"\bterraform\b|\bpulumi\b|\bansible\b"),
    "ci": _r(r"\bci/cd\b|\bcontinuous integration\b|\bgithub actions\b|\bjenkins\b|\bgitlab ci\b"),
    "git": _r(r"\bgit\b|\bgithub\b|\bversion control\b"),
    "linux": _r(r"\blinux\b|\bunix\b|\bbash\b"),
    "networking": _r(r"\btcp/ip\b|\bnetworking\b|\bdns\b|\bfirewalls?\b|\bvpn\b|\brouting\b"),
    "graphql": _r(r"\bgraphql\b"),
    "rest": _r(r"\brest(?:ful)?\s*apis?\b|\brestful\b"),
    "ml": _r(r"\bmachine learning\b|\bdeep learning\b|\bneural network"),
    "pytorch": _r(r"\bpytorch\b|\btensorflow\b|\bjax\b"),
    "nlp": _r(r"\bnlp\b|\bnatural language\b|\bllms?\b|\blarge language model"),
    "cv": _r(r"\bcomputer vision\b|\bopencv\b"),
    "datascience": _r(r"\bpandas\b|\bnumpy\b|\bscikit|\bjupyter\b"),
    "spark": _r(r"\bspark\b|\bhadoop\b|\bkafka\b|\bairflow\b"),
    "distributed": _r(r"\bdistributed systems?\b|\bmicroservices\b"),
    "security": _r(
        r"\bcryptography\b|\bpenetration test|\bappsec\b|\bthreat model|\bvulnerabilit(?:y|ies)\b|"
        r"\bsiem\b|\bowasp\b|\bincident response\b|\bsecurity operations\b"
    ),
    "ios": _r(r"\bios\b|\bxcode\b|\buikit\b"),
    "android": _r(r"\bandroid\b|\bjetpack\b"),
    "embedded": _r(r"\bembedded\b|\bfirmware\b|\brtos\b|\bverilog\b"),
    "algorithms": _r(r"\balgorithms?\b|\bdata structures\b"),
    "testing": _r(r"\bunit test|\bintegration test|\bjest\b|\bpytest\b"),
}

# Role families, matched against the title. Order is load-bearing: `game` goes first because a
# games posting names its domain in the title and means it ("Game AI Programmer" would
# otherwise read as ml).
ROLE_FAMILIES: list[tuple[str, re.Pattern]] = [
    ("game", _r(r"\bgames?\b|\bgaming\b|\bgameplay\b|\bunity\b|\bunreal\b|\bgodot\b|game engine|\bgamedev\b|graphics (?:engineer|programmer)")),
    ("fullstack", _r(r"full[\s-]?stack")),
    ("ml", _r(r"machine learning|\bml\b|\bai\b|deep learning|\bnlp\b|computer vision|research engineer")),
    ("data", _r(r"data (?:engineer|scien|analytic)|analytics")),
    ("security", _r(r"security|cryptograph|appsec|cyber|\bsoc\b|pentest|infosec")),
    ("mobile", _r(r"\bmobile\b|\bios\b|\bandroid\b")),
    ("embedded", _r(r"embedded|firmware")),
    ("infra", _r(r"infrastructure|platform|devops|\bsre\b|cloud|reliability|systems|network|sysadmin")),
    ("frontend", _r(r"front[\s-]?end|\bui\b|\bweb\b")),
    ("backend", _r(r"back[\s-]?end|server|\bapi\b|distributed")),
]
DEFAULT_ROLE_FAMILY = "swe"

# What a good internship says about itself. Presence is weak evidence; absence weaker still.
QUALITY_SIGNALS = {
    "return_offer": _r(r"\breturn offer\b|full[\s-]?time (?:offer|conversion)|convert(?:ing|ed)? to full[\s-]?time"),
    "mentorship": _r(r"\bmentor(?:ship|ed|s)?\b|\bbuddy\b|paired with (?:a|an)? ?(?:senior|engineer)"),
    "cohort": _r(r"intern (?:class|cohort|program)|\bcohort\b|summer program|intern events"),
    "relocation": _r(r"\brelocation\b|\bhousing\b|\bstipend\b"),
    "ship": _r(r"\bship\b|\bproduction\b|real (?:code|projects?|impact)|end[\s-]to[\s-]end|meaningful (?:work|projects?)"),
    "review": _r(r"\bcode reviews?\b|design (?:doc|review)|pull requests?|pair programming"),
}

# Narrow on purpose: a bare /unpaid/ also matches "unpaid leave" in a benefits section.
QUALITY_RED_FLAGS = {
    "unpaid": _r(r"\bunpaid (?:internship|position|role)\b|\bthis is an unpaid\b|\bno compensation\b"),
    "credit_only": _r(r"credit[\s-]only|for (?:course|academic|school) credit\b"),
}

HOURS_PER_MONTH = 173.33
HOURS_PER_YEAR = 2080
# "$45/hr", "$40 - $55 per hour", "$8,000/month", "$120k/year". A range takes its midpoint.
# Ashby writes Canadian rates as "CA$40 - CA$50 / hr", hence the optional letters before `$`.
PAY_PATTERN = _r(
    r"(?:[a-z]{1,3})?\$\s?([\d,]+(?:\.\d+)?)\s*(k\b)?"
    r"(?:\s*(?:-|–|—|to)\s*(?:[a-z]{1,3})?\$?\s?([\d,]+(?:\.\d+)?)\s*(k\b)?)?"
    r"\s*(?:/|\s+per\s+|\s+an?\s+)\s*(hour|hr|month|mo|year|yr|annum)"
)
# Hourly rate -> quality points, anchored on the intern market: ~$20/hr is the low end of
# paid, ~$50/hr is strong, big-tech tops out near $80/hr.
PAY_CURVE = [(15, 10), (20, 25), (25, 40), (30, 50), (40, 65), (50, 80), (65, 92), (80, 100)]
PAY_UNSTATED_SCORE = 55  # most postings never state pay, so silence is neutral

# Company prestige raises `quality` and raises `difficulty`: the same name that makes an
# internship worth having makes it harder to get. Keys are normalised ("Jane Street" -> "janestreet").
TOP_TIER_COMPANIES = {
    "google", "alphabet", "meta", "facebook", "apple", "amazon", "microsoft", "netflix", "nvidia",
    "openai", "anthropic", "deepmind", "googledeepmind", "xai", "ssi",
    "janestreet", "citadel", "citadelsecurities", "twosigma", "hudsonrivertrading", "hrt", "jumptrading",
    "optiver", "imc", "imctrading", "deshaw", "towerresearchcapital", "radixtrading", "sig", "susquehanna",
    "stripe", "databricks", "palantir", "snowflake", "figma", "ramp", "anduril", "scaleai",
    "spacex", "tesla", "waymo", "coinbase", "airbnb", "uber", "doordash", "linkedin", "roblox",
}
STRONG_TIER_COMPANIES = {
    "shopify", "atlassian", "salesforce", "adobe", "oracle", "ibm", "intel", "amd", "qualcomm",
    "cloudflare", "datadog", "mongodb", "hashicorp", "twilio", "dropbox", "block", "square",
    "robinhood", "instacart", "reddit", "pinterest", "snap", "discord", "plaid", "brex",
    "notion", "linear", "vercel", "retool", "asana", "lyft", "spotify", "squarespace",
    "perplexity", "cohere", "mistral", "mistralai", "huggingface", "anysphere", "cursor",
    "appliedintuition", "rippling", "gusto", "benchling", "affirm", "chime", "wealthsimple",
    "shopifyplus", "sonder", "cohereai", "element", "ideogram", "together", "togetherai",
    "ubisoft", "epicgames", "mongodb", "zscaler", "crowdstrike", "paloaltonetworks", "fortinet",
}

# --- résumé routing ----------------------------------------------------------------------------

DEFAULT_RESUME_VARIANT = "base"

# Which résumé each role family wants. Families with no mapping fall to base.
RESUME_FAMILY_VARIANT = {
    "swe": "base",
    "fullstack": "base",
    "embedded": "base",
    "backend": "backend",
    "infra": "devops",
    "frontend": "frontend",
    "mobile": "frontend",
    "ml": "ai",
    "data": "ai",
    "game": "game",
    "security": "security",
}
# A variant you haven't made degrades along this chain instead of failing.
RESUME_FALLBACK = {"devops": "backend", "security": "base", "game": "base", "ai": "base",
                   "frontend": "base", "backend": "base"}

# Evidence in the posting body, scored per variant. Not SKILL_LEXICON: that answers "does the
# candidate know this?", this answers "what shape of work is this posting?". `base` has no
# signals by design: it wins by being the fallback.
RESUME_SIGNALS: dict[str, list[tuple[str, re.Pattern, int]]] = {
    "base": [],
    "backend": [
        ("distributed systems", _r(r"\bdistributed systems?\b|\bmicroservices\b"), 2),
        ("databases", _r(r"\bpostgres(?:ql)?\b|\bmysql\b|\bdatabase schema\b|\bsql\b"), 2),
        ("queues/streaming", _r(r"\bkafka\b|\brabbitmq\b|\bcelery\b|\bmessage queue\b|\bredis\b"), 2),
        ("API design", _r(r"\bgrpc\b|\brest(?:ful)? apis?\b|\bapi design\b"), 1),
        ("scale/latency", _r(r"\bthroughput\b|\blatency\b|\bhigh availability\b|\bscalab"), 1),
    ],
    "frontend": [
        ("React/Vue/Angular", _r(r"\breact\b|\bnext\.?js\b|\bvue\b|\bangular\b|\bsvelte\b"), 2),
        ("CSS/design systems", _r(r"\bcss\b|\btailwind\b|\bdesign system\b|\bstyled-components\b"), 2),
        ("accessibility", _r(r"\baccessibility\b|\bwcag\b|\ba11y\b"), 2),
        ("browser/DOM", _r(r"\bbrowser\b|\bdom\b|\bsingle[\s-]page app"), 1),
        ("TypeScript", _r(r"\btypescript\b"), 1),
    ],
    "ai": [
        ("LLM work", _r(r"\bllms?\b|\blarge language model|\bprompt engineering\b|\bretrieval[\s-]augmented\b"), 2),
        ("ML frameworks", _r(r"\bpytorch\b|\btensorflow\b|\bscikit|\bjax\b"), 2),
        ("machine learning", _r(r"\bmachine learning\b|\bdeep learning\b|\bneural network"), 2),
        ("inference/serving", _r(r"\bmodel (?:serving|inference|training)\b|\bembeddings?\b|\bvector (?:database|search)\b"), 2),
        ("data pipelines", _r(r"\bairflow\b|\bspark\b|\betl\b|\bdata pipeline"), 1),
    ],
    "game": [
        ("Unity/Unreal", _r(r"\bunity\b|\bunreal\b|\bgodot\b"), 2),
        ("gameplay/engine", _r(r"\bgameplay\b|game engine|\bgamedev\b"), 2),
        ("graphics/rendering", _r(r"\bshaders?\b|\brendering\b|\brasteriz|\bgraphics pipeline\b"), 2),
        ("physics/simulation", _r(r"\bphysics (?:engine|simulation)\b|\bcollision detection\b"), 1),
        ("C++", _r(r"\bc\+\+"), 1),
    ],
    "devops": [
        ("containers/orchestration", _r(r"\bkubernetes\b|\bk8s\b|\bdocker\b|\bhelm\b"), 2),
        ("infrastructure as code", _r(r"\bterraform\b|\bansible\b|\bpulumi\b|\bcloudformation\b"), 2),
        ("CI/CD", _r(r"\bci/cd\b|\bgithub actions\b|\bjenkins\b|\bgitlab ci\b|\bargo ?cd\b"), 2),
        ("observability", _r(r"\bprometheus\b|\bgrafana\b|\bobservability\b|\bmonitoring\b|\bon[\s-]call\b"), 1),
        ("cloud", _r(r"\baws\b|\bazure\b|\bgcp\b|\bgoogle cloud\b"), 1),
    ],
    "security": [
        ("security operations", _r(r"\bsiem\b|\bsoc\b|\bincident response\b|\bthreat (?:hunting|detection|intel)"), 2),
        ("offensive security", _r(r"\bpenetration test|\bpentest|\bred team|\bexploit"), 2),
        ("vulnerability management", _r(r"\bvulnerabilit(?:y|ies)\b|\bcve\b|\bowasp\b|\bappsec\b"), 2),
        ("identity/crypto", _r(r"\bcryptograph|\bencryption\b|\biam\b|\bzero trust\b"), 1),
        ("compliance", _r(r"\bsoc ?2\b|\biso ?27001\b|\bgrc\b|\bcompliance\b"), 1),
    ],
}

# Weak priors from the employer's name. Weight 1 on purpose: a games studio hires backend,
# tools and IT engineers too. A hint can tip a posting that already leans somewhere, never
# carry one alone.
RESUME_COMPANY_HINTS: list[tuple[str, str, int, re.Pattern]] = [
    ("games studio", "game", 1, _r(
        r"\b(ubisoft|electronic arts|ea|behaviour|warner bros\.? games|wb games|eidos|gameloft|epic games|"
        r"riot games|activision|blizzard|rockstar|bungie|naughty dog|square enix|unity technologies|"
        r"bethesda|cd projekt|larian|haven studios|ludia|amplitude studios|2k)\b")),
    ("AI lab", "ai", 1, _r(r"\b(anthropic|openai|deepmind|cohere|mistral|hugging ?face|scale ai|databricks)\b")),
    ("security vendor", "security", 1, _r(r"\b(crowdstrike|palo alto networks|fortinet|zscaler|okta|cloudflare|rapid7|tenable)\b")),
]

RESUME_MAX_DESCRIPTION_CHARS = 20000
RESUME_TITLE_MULTIPLIER = 2  # a title names the role on purpose; a body mentions half the stack as background
RESUME_FAMILY_WEIGHT = 3  # what the title's role family alone is worth
RESUME_MIN_MARGIN = 2  # how far ahead the winner must be to override the title's own family
RESUME_MIN_SUPPORT = 2  # independent pieces of evidence a body-only decision needs
