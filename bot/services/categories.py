"""ZelionTech knowledge taxonomy + keyword classifier for KB chunks."""

# The 14 required sections (canonical category keys -> display label).
CATEGORIES = {
    "infrastructure": "Zelion Infrastructure",
    "zev_device": "ZEV Device",
    "esg_verification": "ESG Verification",
    "bnb_coordination": "BNB Chain Coordination Layer",
    "depin": "DePIN Integration",
    "tokenomics": "Tokenomics",
    "enterprise": "Enterprise Deployment",
    "leadership": "Leadership / Team",
    "roadmap": "Roadmap",
    "security": "Security Architecture",
    "rwa": "RWA Compatibility",
    "carbon_markets": "Carbon Markets",
    "ai_energy_demand": "AI / Data-Center Energy Demand",
    "renewable_validation": "Renewable Energy Validation",
}

# Ordered keyword rules (first match wins). Lowercased substring matching.
_RULES = [
    ("zev_device", ["zev", "validation device", "hardware-rooted", "tamper-resistant", "iot device", "sensor"]),
    ("bnb_coordination", ["bnb", "binance smart chain", "bnb smart chain", "coordination layer",
                          "coordination protocol", "zln", "on-chain record", "record layer"]),
    ("tokenomics", ["token", "vesting", "distribution", "tokenomics", "zyl", "supply", "allocation", "commercial model"]),
    ("security", ["security", "intellectual property", "tamper", "cryptograph", "key", "attestation", "audit-ready"]),
    ("esg_verification", ["esg", "csrd", "sec climate", "disclosure", "greenwashing", "rec", "renewable energy certificate"]),
    ("carbon_markets", ["carbon", "carbon market", "carbon credit", "offset"]),
    ("ai_energy_demand", ["ai ", "data center", "data-center", "machine-verifiable", "compute demand"]),
    ("renewable_validation", ["renewable", "solar", "wind", "energy data", "validation infrastructure",
                              "physical proof", "energy verification"]),
    ("depin", ["depin", "decentralized physical", "physical infrastructure network"]),
    ("rwa", ["rwa", "real-world asset", "real world asset", "asset tokeniz"]),
    ("enterprise", ["enterprise", "deployment strategy", "use case", "commercial", "institutional"]),
    ("roadmap", ["roadmap", "milestone", "q1", "q2", "q3", "q4", "phase ", "development roadmap"]),
    ("leadership", ["team", "governance", "leadership", "founder", "advisor", "ceo", "cto"]),
    ("infrastructure", ["infrastructure", "architecture", "layer", "system", "network", "explorer", "bridge", "oracle"]),
]


def classify(text: str) -> str:
    t = (text or "").lower()
    for cat, kws in _RULES:
        if any(k in t for k in kws):
            return cat
    return "infrastructure"


def label(cat: str) -> str:
    return CATEGORIES.get(cat, "Zelion Infrastructure")
