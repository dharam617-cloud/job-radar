"""Decide whether an employer is a Global Capability Centre (GCC) in India, and its sector.

A GCC here means a multinational's own India centre (technology, operations, analytics, R&D),
not an IT-services vendor, staffing agency or consultancy working for clients.

Matching is on whole words of the normalised company name. Extend the lists below when the
run log ("Skipped non-GCC employers") shows a real GCC that was missed.
"""
from __future__ import annotations

import re

SECTORS: dict[str, list[str]] = {
    "BFSI": [
        "jpmorgan", "jp morgan", "j p morgan", "jpmorgan chase", "chase", "goldman sachs", "morgan stanley", "wells fargo",
        "hsbc", "barclays", "citi", "citigroup", "citibank", "citicorp", "deutsche bank", "ubs", "credit suisse", "bny", "bny mellon",
        "state street", "northern trust", "standard chartered", "natwest", "lloyds", "lloyds technology centre", "anz",
        "commonwealth bank", "cba", "westpac", "nab", "national australia bank", "macquarie", "societe generale",
        "bnp paribas", "natixis", "nomura", "mizuho", "mufg", "smbc", "bank of america", "capital one", "american express", "amex",
        "mastercard", "visa", "paypal", "fiserv", "fis", "global payments", "synchrony", "discover financial", "us bank", "u s bank",
        "truist", "pnc", "fifth third", "citizens", "keybank", "ally", "charles schwab", "schwab", "fidelity", "fidelity international",
        "fmr", "vanguard", "blackrock", "invesco", "franklin templeton", "t rowe price", "principal", "principal financial group",
        "ameriprise", "m g global services", "prudential", "pgim", "metlife", "manulife", "john hancock", "sun life", "allianz",
        "allianz technology", "axa", "swiss re", "munich re", "zurich", "chubb", "aig", "travelers", "the hartford", "hartford",
        "liberty mutual", "nationwide", "the standard", "the standard india", "lincoln financial", "aon", "marsh mclennan", "marsh",
        "mercer", "oliver wyman", "wtw", "willis towers watson", "gallagher", "lseg", "london stock exchange group", "s p global",
        "moody s", "moodys", "msci", "morningstar", "nasdaq", "ice", "intercontinental exchange", "cme group", "broadridge",
        "ss c", "ss c technologies", "dtcc", "experian", "equifax", "transunion", "rabobank", "ing", "abn amro", "danske bank",
        "nordea", "euroclear", "deutsche borse", "commerzbank", "santander", "bbva", "brown brothers harriman", "edward jones",
        "lpl financial", "raymond james", "jefferies", "blackstone", "kkr", "apollo", "carlyle", "brookfield", "arcesium",
        "d e shaw", "de shaw", "tower research", "optiver", "wex", "worldline", "adyen", "stripe", "nuvei", "block", "intuit",
        "northern trust", "voya", "cigna", "evernorth", "the hanover", "acko", "deutsche telekom", "dws",
    ],
    "Technology": [
        "microsoft", "google", "alphabet", "amazon", "aws", "amazon web services", "apple", "meta", "oracle", "sap", "sap labs",
        "salesforce", "adobe", "servicenow", "workday", "vmware", "broadcom", "cisco", "dell", "dell technologies", "hp", "hp inc",
        "hewlett packard enterprise", "hpe", "intel", "qualcomm", "nvidia", "amd", "texas instruments", "micron", "analog devices",
        "nxp", "synopsys", "cadence", "atlassian", "autodesk", "ptc", "ansys", "dassault systemes", "nutanix", "netapp",
        "juniper", "arista", "palo alto networks", "fortinet", "zscaler", "crowdstrike", "okta", "check point", "trellix",
        "splunk", "elastic", "mongodb", "snowflake", "databricks", "confluent", "teradata", "informatica", "cloudera", "red hat",
        "citrix", "akamai", "uber", "linkedin", "expedia", "expedia group", "booking", "airbnb", "netflix", "sprinklr", "anaplan",
        "smartsheet", "quickbase", "blackbaud", "blackbaud india", "freshworks", "zoho", "rubrik", "cohesity", "commvault",
        "veeam", "sophos", "mcafee", "gen digital", "ukg", "kaseya", "alphasense", "chargepoint", "n able", "sonatype",
        "deepwatch", "coupang", "rakuten", "samsung", "sony", "lg", "panasonic", "western digital", "seagate", "keysight",
        "applied materials", "lam research", "kla", "marvell", "infineon", "stmicroelectronics", "renesas", "arm", "siemens eda",
        "electronic arts", "ea", "warner bros discovery", "disney", "nielsen", "nielsen sports", "thomson reuters", "relx",
        "wolters kluwer", "pearson", "gartner", "at t", "att", "verizon", "t mobile", "vodafone", "vois", "bt", "ericsson",
        "nokia", "comcast", "doordash", "lyft", "paypay", "imagine learning", "billtrust",
        "zebra technologies", "motorola solutions", "harman", "trimble", "bentley systems", "hexagon", "ibm software labs",
    ],
    "Retail & Consumer": [
        "walmart", "walmart global tech", "target", "lowe s", "lowes", "tesco", "tesco bengaluru", "sainsbury s", "marks spencer",
        "ahold delhaize", "84 51", "albertsons", "best buy", "home depot", "macy s", "nordstrom", "gap", "abercrombie",
        "abercrombie fitch", "levi strauss", "nike", "adidas", "h m", "ikea", "carrefour", "mcdonald s", "mcdonalds", "starbucks",
        "yum", "pepsico", "coca cola", "unilever", "procter gamble", "p g", "nestle", "nestle business services", "l oreal",
        "mondelez", "mars", "kellanova", "general mills", "diageo", "ab inbev", "heineken", "colgate", "colgate palmolive",
        "kimberly clark", "reckitt", "estee lauder", "mccormick", "mccormick company", "cargill", "adm", "bunge", "ferguson",
        "tjx", "the tjx companies", "kohl s", "ross stores", "dollar tree", "walgreens", "boots", "kraft heinz", "hershey",
        "mccain", "mccain foods", "philip morris", "british american tobacco", "bat", "lululemon", "williams sonoma", "wayfair",
        "ebay", "etsy", "shell retail",
    ],
    "Healthcare & Pharma": [
        "novartis", "novartis india", "sanofi", "opella", "astrazeneca", "pfizer", "merck", "msd", "eli lilly", "lilly", "amgen",
        "gsk", "roche", "bayer", "novo nordisk", "abbvie", "bristol myers squibb", "bms", "johnson johnson", "j j", "takeda",
        "teva", "regeneron", "gilead", "biogen", "medtronic", "abbott", "stryker", "zimmer biomet", "baxter", "bd",
        "becton dickinson", "boston scientific", "philips", "siemens healthineers", "ge healthcare", "optum", "unitedhealth",
        "unitedhealth group", "cvs health", "elevance", "elevance health", "humana", "mckesson", "cardinal health", "iqvia",
        "thermo fisher", "danaher", "agilent", "labcorp", "r1 rcm", "align technology", "edwards lifesciences", "hologic",
        "cerner", "oracle health", "change healthcare", "cotiviti", "evolent", "zelis", "gainwell", "alcon", "lonza", "ucb",
        "boehringer ingelheim", "merck kgaa", "fresenius", "solventum", "3m", "lexitas",
    ],
    "Manufacturing & Engineering": [
        "siemens", "ge", "ge aerospace", "ge vernova", "honeywell", "abb", "schneider electric", "emerson", "rockwell automation",
        "johnson controls", "carrier", "trane", "trane technologies", "eaton", "caterpillar", "john deere", "deere", "cnh",
        "cummins", "bosch", "continental", "zf", "mercedes benz", "mercedes benz research", "bmw", "volvo", "volvo group",
        "daimler truck", "ford", "ford business solutions", "general motors", "gm", "stellantis", "hyundai", "toyota", "boeing",
        "airbus", "rolls royce", "safran", "collins aerospace", "rtx", "pratt whitney", "lockheed martin", "shell", "bp",
        "exxonmobil", "chevron", "totalenergies", "baker hughes", "halliburton", "slb", "schlumberger", "weir", "maersk",
        "dhl", "fedex", "ups", "bridgestone", "bridgestone americas", "michelin", "goodyear", "3m", "dow", "basf", "linde",
        "air liquide", "parker hannifin", "otis", "whirlpool", "electrolux", "hitachi", "mitsubishi", "valeo", "magna",
        "aptiv", "visteon", "lear", "te connectivity", "amphenol", "danfoss", "grundfos", "alstom", "wabtec", "kone",
        "atlas copco", "sandvik", "skf", "volkswagen", "audi", "porsche", "renault", "nissan", "jaguar land rover",
        "landis gyr", "itron", "ametek", "fortive", "xylem", "dover", "ingersoll rand", "stanley black decker", "pall",
    ],
    "Professional services (captive)": [
        "deloitte shared services", "deloitte usi", "deloitte shared services india", "pwc acceleration center",
        "pwc ac", "ey gds", "ey global delivery services", "kpmg global services", "alvarez marsal", "mckinsey",
        "bain capability network", "bcg", "boston consulting group", "gartner", "zs associates",
    ],
}

# Names that look like a GCC even when the company isn't in the list above.
GCC_NAME = re.compile(
    r"global capability|\bgcc\b|global business services|\bgbs\b|global in house|captive|"
    r"india development cent(er|re)|technology cent(er|re)|innovation cent(er|re)|global technology|global tech\b|"
    r"shared services|capability cent(er|re)|global services india|technology services india|global solutions india",
    re.I)

# IT-services vendors, consultancies working for clients, staffing and recruiters: never a GCC.
NOT_GCC = re.compile(
    r"\b(tcs|tata consultancy|infosys|wipro|hcl|hcltech|tech mahindra|cognizant|accenture|capgemini|ltimindtree|"
    r"ltm|lti|mindtree|mphasis|hexaware|persistent|coforge|birlasoft|zensar|virtusa|cgi|epam|globallogic|nagarro|ust|"
    r"sonata|kpit|cyient|l t technology|ltts|tata elxsi|tata technologies|sasken|quest global|mastech|ntt data|dxc|"
    r"kyndryl|ibm|atos|eviden|sopra steria|fujitsu|luxoft|iris software|gspann|bounteous|quantiphi|tredence|mathco|"
    r"fractal|latentview|tiger analytics|sigmoid|c5i|acuity|valuelabs|happiest minds|dataart|altimetrik|publicis sapient|"
    r"thoughtworks|slalom|infovision|papigen|softobiz|dbiz|tachyon|quarks|aarvian|arohana|kapture|genpact|exl|wns|"
    r"firstsource|teleperformance|concentrix|hgs|randstad|adecco|teamlease|quess|manpower|careernet|ciel|xpheno|"
    r"apna|naukri|appit|heptarc|nexgile|antino|cloudsufi|r systems|3i infotech|in2it|ey|pwc india|pwc|kpmg|deloitte|"
    r"grant thornton|bdo)\b|"
    r"consultan(t|cy|ts)\b|immigration|recruit|staffing|placement|manpower|hr solutions|talent solutions|career company|"
    r"hiring for|confidential|stealth",
    re.I)

# Captive arms of firms whose plain name is excluded above (checked before NOT_GCC).
CAPTIVE_OVERRIDE = re.compile(
    r"deloitte (shared services|usi)|pwc (acceleration|ac\b)|ey (gds|global delivery)|kpmg global services|"
    r"ibm (software labs|india software lab)", re.I)

CURRENT_EMPLOYER = re.compile(r"commonwealth bank|\bcba\b", re.I)


def _norm(s: str) -> str:
    s = s.lower().replace("&", " ")
    s = re.sub(r"\b(private|pvt|ltd|limited|llp|inc|corp|corporation|plc|india|co)\b\.?", " ", s)
    return " " + re.sub(r"[^a-z0-9]+", " ", s).strip() + " "


_INDEX = sorted(((" " + re.sub(r"[^a-z0-9]+", " ", a.lower()).strip() + " ", sector)
                 for sector, names in SECTORS.items() for a in names), key=lambda x: -len(x[0]))


def classify(company: str) -> dict:
    """{'gcc': bool, 'sector': str, 'how': 'list'|'name'|'', 'own': bool}"""
    raw = company or ""
    own = bool(CURRENT_EMPLOYER.search(raw))
    if CAPTIVE_OVERRIDE.search(raw):
        return {"gcc": True, "sector": "Professional services (captive)", "how": "list", "own": own}
    if NOT_GCC.search(raw):
        return {"gcc": False, "sector": "", "how": "", "own": own}
    n = _norm(raw)
    for alias, sector in _INDEX:
        if alias in n:
            return {"gcc": True, "sector": sector, "how": "list", "own": own}
    if GCC_NAME.search(raw):
        return {"gcc": True, "sector": "Other GCC", "how": "name", "own": own}
    return {"gcc": False, "sector": "", "how": "", "own": own}
