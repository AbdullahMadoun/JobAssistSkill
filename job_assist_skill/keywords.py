"""
Search Keywords Dictionary for Career Assistant.

Provides comprehensive job search keywords organized by:
- Roles (by seniority, field, technology)
- Companies (tech, finance, healthcare, etc.)
- Locations (cities, countries, regions)
- Work Types (Remote, Hybrid, On-site)
- Benefits (Visa, Relocation, Equity, etc.)

Usage:
    from keywords import ROLES, COMPANIES, LOCATIONS, WORK_TYPES
    keywords = ROLES["software"] + COMPANIES["tech"]
"""

ROLES = {
    # Software / Engineering
    "software_engineer": [
        "software engineer",
        "software developer",
        "backend engineer",
        "frontend engineer",
        "full stack developer",
        "fullstack engineer",
        "python developer",
        "java developer",
        "javascript developer",
        "golang developer",
        "rust developer",
        "c++ developer",
        "csharp developer",
        ".net developer",
    ],
    "senior_software": [
        "senior software engineer",
        "senior software developer",
        "staff engineer",
        "principal engineer",
        "lead developer",
        "engineering manager",
        "senior backend engineer",
        "senior frontend engineer",
    ],
    "devops_sre": [
        "devops engineer",
        "site reliability engineer",
        "sre",
        "platform engineer",
        "infrastructure engineer",
        "cloud engineer",
        "aws engineer",
        "azure engineer",
        "gcp engineer",
    ],
    "data_ml": [
        "data scientist",
        "machine learning engineer",
        "ml engineer",
        "deep learning engineer",
        "ai engineer",
        "data engineer",
        "analytics engineer",
        "data analyst",
        "business intelligence",
        "big data engineer",
        "spark engineer",
    ],
    "mobile": [
        "mobile developer",
        "ios developer",
        "android developer",
        "flutter developer",
        "react native developer",
        "swift developer",
        "kotlin developer",
    ],
    "qa_testing": [
        "qa engineer",
        "test engineer",
        "automation engineer",
        "quality assurance",
        "sdET",
        "manual tester",
    ],
    "security": [
        "security engineer",
        "cybersecurity engineer",
        "application security engineer",
        "infosec engineer",
        "penetration tester",
        "security analyst",
    ],
    "product": [
        "product manager",
        "product owner",
        "technical program manager",
        "program manager",
        "project manager",
        "scrum master",
    ],
    "design": [
        "ux designer",
        "ui designer",
        "product designer",
        "ux researcher",
        "visual designer",
        "graphic designer",
    ],
    "data_related": [
        "database administrator",
        "dba",
        "data architect",
        "etl developer",
        "reporting analyst",
    ],
    "cloud_infra": [
        "cloud architect",
        "solutions architect",
        "technical architect",
        "infrastructure architect",
        "network engineer",
        "systems engineer",
    ],
    "entry_level": [
        "junior software engineer",
        "new grad software engineer",
        "graduate software engineer",
        "intern software engineer",
        "entry level software developer",
        "graduate developer",
        "jr software engineer",
    ],
}

COMPANIES = {
    # Tech Giants
    "big_tech": [
        "Google",
        "Microsoft",
        "Amazon",
        "Apple",
        "Meta",
        "Facebook",
        "Netflix",
        "Adobe",
        "Oracle",
        "IBM",
        "Intel",
        "Cisco",
        "Salesforce",
        "VMware",
    ],
    # Search & Advertising
    "search_ad": [
        "Google",
        "Microsoft Bing",
        "Yahoo",
        "Baidu",
        "Yandex",
    ],
    # Social Media
    "social_media": [
        "Meta",
        "Facebook",
        "Instagram",
        "Twitter",
        "X",
        "LinkedIn",
        "Snapchat",
        "TikTok",
        "Reddit",
        "Pinterest",
    ],
    # Cloud Providers
    "cloud": [
        "Amazon Web Services",
        "AWS",
        "Microsoft Azure",
        "Google Cloud",
        "GCP",
        "Oracle Cloud",
        "IBM Cloud",
    ],
    # Streaming & Entertainment
    "streaming": [
        "Netflix",
        "Disney",
        "Hulu",
        "Amazon Prime Video",
        "Spotify",
        "Apple Music",
        "YouTube",
        "Twitch",
    ],
    # Finance & Fintech
    "finance": [
        "JPMorgan Chase",
        "Goldman Sachs",
        "Morgan Stanley",
        "Bank of America",
        "Citigroup",
        "Wells Fargo",
        "American Express",
        "Capital One",
        "PayPal",
        "Stripe",
        "Square",
        "Coinbase",
        "Robinhood",
        "Klarna",
        "Revolut",
    ],
    # Healthcare Tech
    "healthcare": [
        "Epic Systems",
        "Cerner",
        "Optum",
        "UnitedHealth Group",
        "CVS Health",
        "Anthem",
        "Humana",
        "McKesson",
        "Cigna",
    ],
    # Consulting
    "consulting": [
        "McKinsey",
        "Boston Consulting Group",
        "Bain",
        "Deloitte",
        "PwC",
        "KPMG",
        "EY",
        "Accenture",
        "Capco",
    ],
    # E-commerce
    "ecommerce": [
        "Amazon",
        "Alibaba",
        "eBay",
        "Shopify",
        "Walmart",
        "Target",
        "Etsy",
        "Wayfair",
        "Zappos",
    ],
    # Gaming
    "gaming": [
        "Electronic Arts",
        "EA",
        "Activision Blizzard",
        "Ubisoft",
        "Electronic Arts",
        "Take-Two Interactive",
        "Epic Games",
        "Riot Games",
        "Valve",
    ],
    # Regional Tech Hubs
    "saudi_tech": [
        "Stc",
        "Mobily",
        "Zain",
        " Aramco",
        "Halliburton",
        "Baker Hughes",
        "Schlumberger",
        "Huawei Saudi",
        "Microsoft Saudi",
        "Amazon Saudi",
    ],
    "uae_tech": [
        "Noon",
        "Talabat",
        "Careem",
        "Swvl",
        "Dubizzle",
        "Namshi",
        "Mumzworld",
        "Fetchr",
        "Ecma",
    ],
    "gulf_tech": [
        "OQ",
        "Ooredoo",
        "Etisalat",
        "du",
        "Qatar Airways",
        "Emirates",
        "flydubai",
    ],
}

LOCATIONS = {
    # GCC / Middle East
    "gcc": [
        "Saudi Arabia",
        "UAE",
        "Dubai",
        "Abu Dhabi",
        "Qatar",
        "Doha",
        "Kuwait",
        "Bahrain",
        "Oman",
    ],
    "saudi": [
        "Riyadh",
        "Jeddah",
        "Dammam",
        "Mecca",
        "Medina",
        "Khobar",
        "Al Khobar",
        "Saudi Arabia",
    ],
    "uae": [
        "Dubai",
        "Abu Dhabi",
        "Sharjah",
        "Ajman",
        "UAE",
        "United Arab Emirates",
    ],
    "qatar": [
        "Doha",
        "Qatar",
    ],
    # USA
    "usa": [
        "United States",
        "USA",
        "US",
    ],
    "usa_major": [
        "New York",
        "San Francisco",
        "Los Angeles",
        "Seattle",
        "Boston",
        "Chicago",
        "Austin",
        "Denver",
    ],
    "usa_tech": [
        "San Francisco Bay Area",
        "Silicon Valley",
        "Seattle",
        "Austin",
        "Boston",
        "New York City",
        "Los Angeles",
    ],
    # Europe
    "uk": [
        "London",
        "Manchester",
        "Edinburgh",
        "Birmingham",
        "UK",
        "United Kingdom",
        "England",
    ],
    "europe": [
        "Germany",
        "Berlin",
        "Munich",
        "Frankfurt",
        "Hamburg",
        "France",
        "Paris",
        "Lyon",
        "Netherlands",
        "Amsterdam",
        "Spain",
        "Madrid",
        "Barcelona",
        "Italy",
        "Milan",
        "Rome",
        "Switzerland",
        "Zurich",
        "Geneva",
        "Sweden",
        "Stockholm",
        "Norway",
        "Oslo",
        "Denmark",
        "Copenhagen",
        "Finland",
        "Helsinki",
    ],
    # Asia Pacific
    "asia": [
        "Singapore",
        "Hong Kong",
        "Tokyo",
        "Seoul",
        "Shanghai",
        "Beijing",
        "Bangalore",
        "Mumbai",
        "Delhi",
        "Sydney",
        "Melbourne",
        "Auckland",
    ],
    "apac": [
        "Singapore",
        "Hong Kong",
        "Tokyo",
        "Seoul",
        "Sydney",
        "Melbourne",
        "Mumbai",
        "Bangalore",
    ],
    # Remote
    "remote": [
        "Remote",
        "Remote - US",
        "Remote - Europe",
        "Remote - Global",
        "Work from Home",
        "WFH",
        "Anywhere",
        "100% Remote",
    ],
    "hybrid": [
        "Hybrid",
        "Hybrid - Remote",
        "Flexible",
        "Hybrid Work",
        "Partially Remote",
    ],
}

WORK_TYPES = {
    "remote": [
        "remote",
        "work from home",
        "wfh",
        "anywhere",
        "distributed",
    ],
    "hybrid": [
        "hybrid",
        "flexible",
        "partially remote",
    ],
    "onsite": [
        "on-site",
        "on site",
        "office",
        "onsite",
    ],
}

BENEFITS = {
    "sponsorship": [
        "visa sponsorship",
        "visa sponsor",
        "work visa",
        "h1b",
        "work permit",
        "relocation assistance",
        "relocation package",
        " immigration support",
    ],
    "equity": [
        "equity",
        "stock options",
        "rsu",
        "espp",
        "employee stock purchase",
    ],
    "compensation": [
        "competitive salary",
        "bonus",
        "annual bonus",
        "performance bonus",
        " signing bonus",
    ],
    "health": [
        "health insurance",
        "dental",
        "vision",
        "medical",
        "life insurance",
        "wellness",
    ],
    "retirement": [
        "401k",
        "pension",
        "retirement plan",
        "espp",
    ],
    "pto": [
        "unlimited pto",
        "generous pto",
        "paid vacation",
        "paid time off",
        "pto",
        "leave",
    ],
    "learning": [
        "learning budget",
        "education budget",
        "conference",
        "training",
        "certification",
        "career development",
    ],
}

HIRING_KEYWORDS = [
    # Direct hiring language
    "we're hiring",
    "we are hiring",
    "now hiring",
    "join our team",
    "looking for",
    "open position",
    "job opening",
    "hiring soon",
    "career opportunity",
    "recruiting",
    "vacancy",
    "#hiring",
    "urgent hiring",
    "immediate opening",
    # Modern/Startup
    "come build with us",
    "let's build",
    "building the future",
    "join us",
    "be part of our team",
    "We're growing",
    "expanding our team",
    "team is growing",
    "hiring multiple",
    "multiple openings",
    "several positions",
]

SENIORITY = {
    "entry": [
        "junior",
        "jr",
        "entry level",
        "graduate",
        "intern",
        "new grad",
        "entry-level",
        "associate",
        "early career",
    ],
    "mid": [
        "mid-level",
        "mid level",
        "intermediate",
        "2+ years",
        "3+ years",
        "5 years",
        "software engineer ii",
        "developer ii",
    ],
    "senior": [
        "senior",
        "sr",
        "sr.",
        "staff",
        "principal",
        "lead",
        "6+ years",
        "7+ years",
        "8+ years",
        "10+ years",
        "senior engineer",
        "senior developer",
    ],
    "manager": [
        "manager",
        "director",
        "head of",
        "vp",
        "vice president",
        "chief",
        "principal",
    ],
}

def build_search_queries(
    roles: list = None,
    companies: list = None,
    locations: list = None,
    work_type: str = None,
    include_hiring: bool = True,
    seniority: str = None,
) -> list:
    """
    Build LinkedIn search queries from keywords.

    Args:
        roles: List of role keywords (from ROLES dict)
        companies: List of company keywords (from COMPANIES dict)
        locations: List of location keywords (from LOCATIONS dict)
        work_type: 'remote', 'hybrid', or 'onsite'
        include_hiring: Include 'hiring' keyword
        seniority: 'entry', 'mid', 'senior', or 'manager'

    Returns:
        List of search query strings

    Example:
        queries = build_search_queries(
            roles=["software_engineer", "data_ml"],
            locations=["usa_major", "remote"],
            work_type="remote",
        )
    """
    queries = []
    seen = set()

    def add_query(q):
        q = q.strip().lower()
        if q and q not in seen:
            seen.add(q)
            queries.append(q)

    role_keywords = []
    if roles:
        for r in roles:
            if isinstance(r, str) and r in ROLES:
                role_keywords.extend(ROLES[r])
            else:
                role_keywords.append(r)

    location_keywords = []
    if locations:
        for l in locations:
            if isinstance(l, str) and l in LOCATIONS:
                location_keywords.extend(LOCATIONS[l])
            else:
                location_keywords.append(l)

    if work_type and work_type in WORK_TYPES:
        location_keywords.extend(WORK_TYPES[work_type])

    seniority_keywords = []
    if seniority and seniority in SENIORITY:
        seniority_keywords = SENIORITY[seniority]

    # Build queries: role + location combinations
    for role in role_keywords[:5]:
        for loc in location_keywords[:3]:
            query = f"{role} {loc}"
            if include_hiring:
                query += " hiring"
            add_query(query)

            if seniority_keywords:
                for sen in seniority_keywords[:2]:
                    query = f"{sen} {role} {loc}"
                    if include_hiring:
                        query += " hiring"
                    add_query(query)

    # Company-focused queries
    if companies:
        for c in companies[:5]:
            if isinstance(c, str) and c in COMPANIES:
                for co in COMPANIES[c][:3]:
                    query = f"{co} careers"
                    add_query(query)
                    query = f"{co} join our team"
                    add_query(query)
            else:
                query = f"{c} careers"
                add_query(query)
                query = f"{c} join our team"
                add_query(query)

    # Pure hiring keywords
    if include_hiring and not roles:
        for kw in HIRING_KEYWORDS[:10]:
            add_query(kw)

    return queries


# Convenience dictionaries for common searches
QUICK_SEARCHES = {
    "remote_software": {
        "roles": ["software_engineer", "senior_software"],
        "locations": ["remote"],
        "work_type": "remote",
    },
    "us_tech": {
        "roles": ["software_engineer", "data_ml", "cloud_infra"],
        "locations": ["usa_tech"],
    },
    "gulf_tech": {
        "roles": ["software_engineer", "senior_software"],
        "locations": ["gcc", "saudi", "uae"],
    },
    "europe_tech": {
        "roles": ["software_engineer", "data_ml"],
        "locations": ["europe", "uk"],
    },
    "asia_tech": {
        "roles": ["software_engineer", "data_ml", "mobile"],
        "locations": ["asia", "singapore"],
    },
    "entry_level": {
        "roles": ["entry_level"],
        "locations": ["usa", "uk", "remote"],
    },
    "data_science": {
        "roles": ["data_ml"],
        "locations": ["usa_tech", "remote"],
    },
    "devops": {
        "roles": ["devops_sre"],
        "locations": ["remote", "usa"],
    },
}


if __name__ == "__main__":
    # Demo: print some search queries
    print("=== Remote Software Engineer Queries ===")
    for q in build_search_queries(
        roles=["software_engineer"],
        locations=["remote"],
        work_type="remote",
    ):
        print(f"  • {q}")

    print("\n=== US Tech Hub Queries ===")
    for q in build_search_queries(
        roles=["software_engineer", "senior_software"],
        locations=["usa_tech"],
    ):
        print(f"  • {q}")

    print("\n=== Gulf Region Queries ===")
    for q in build_search_queries(
        roles=["software_engineer"],
        locations=["gcc"],
    ):
        print(f"  • {q}")
