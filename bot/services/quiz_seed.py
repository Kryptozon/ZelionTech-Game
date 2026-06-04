"""Quiz question bank: curated fact-checked questions from the Zelion knowledge base
+ a grounded generator that tops the pool up to a target (default 300).

All seeded questions are approved + active by default, so the daily quiz works
immediately with no manual approval. Idempotent via a per-question slug (sha1).
"""
import re
import hashlib
import json
import logging

from . import kb, kb_doc, categories

log = logging.getLogger("zelion.quizseed")

REWARD = {1: 5, 2: 10, 3: 20, 4: 35}
WP = "Zelion Institutional Whitepaper v3"

# (question, [opt0..3], correct_index, explanation, difficulty 1-4, category, source_section)
CURATED = [
    ("What does ZEV stand for in the Zelion system?",
     ["Zelion Energy Validator", "Zelion Electric Vehicle", "Zero Emission Vault", "Zelion Edge Verifier"],
     0, "The ZEV (Zelion Energy Validator) is the main hardware device and physical root of trust.",
     1, "zev_device", "06 · Core Product: The ZEV"),
    ("ZelionTech is best described as a…",
     ["Decentralized Energy Network", "Social media app", "Centralized utility company", "Gaming studio"],
     0, "ZelionTech is a Decentralized Energy Network for verifiable energy data.",
     1, "infrastructure", "Overview"),
    ("On which blockchain is Zelion's coordination & record layer built?",
     ["BNB Chain", "Bitcoin", "Solana", "Cardano"],
     0, "Layer 3 runs on BNB Chain–compatible infrastructure.",
     1, "bnb_coordination", "07 · System Architecture"),
    ("The ZEV is primarily a…",
     ["Tamper-resistant hardware device", "Mobile app", "Cloud API", "Spreadsheet"],
     0, "Validation happens inside a tamper-resistant hardware device at the energy source.",
     1, "zev_device", "05 · The Zelion Solution"),
    ("Where is the ZEV installed?",
     ["At or near where energy is produced or consumed", "In a data center only", "On a phone", "At a bank"],
     0, "Source-level capture: the ZEV sits at the energy source.",
     1, "renewable_validation", "06 · Core Product: The ZEV"),
    ("How many layers does the Zelion system architecture have?",
     ["Three", "One", "Five", "Ten"],
     0, "Physical Proof, Validation & Transmission, and Coordination & Record layers.",
     1, "infrastructure", "07 · System Architecture"),
    ("Which layer records validated proofs on-chain?",
     ["Coordination & Record Layer", "Physical Proof Layer", "Marketing Layer", "Sensor Layer"],
     0, "Layer 3, the Coordination & Record Layer, writes immutable on-chain entries.",
     2, "bnb_coordination", "07 · System Architecture"),
    ("What is the fixed total supply of ZLN?",
     ["500,000,000", "1,000,000,000", "21,000,000", "100,000,000"],
     0, "ZLN total supply is fixed at 500,000,000 with no ongoing minting.",
     1, "tokenomics", "14 · Token Distribution & Vesting"),
    ("Is there ongoing minting of ZLN beyond the initial allocation?",
     ["No", "Yes, 2% yearly", "Yes, unlimited", "Only on weekends"],
     0, "Supply is fixed; there is no ongoing issuance or minting mechanism.",
     2, "tokenomics", "14 · Token Distribution & Vesting"),
    ("Which allocation is the largest in ZLN distribution?",
     ["Ecosystem & Infrastructure Development (30%)", "Founding Team (20%)",
      "Liquidity Reserve (15%)", "Strategic Partnerships (10%)"],
     0, "Ecosystem & Infrastructure Development receives 150M ZLN (30%).",
     2, "tokenomics", "14 · Token Distribution & Vesting"),
    ("Core Contributors & Founding Team allocation is what share of supply?",
     ["20%", "5%", "40%", "50%"],
     0, "The team allocation is 100,000,000 ZLN, or 20%.",
     3, "tokenomics", "14 · Token Distribution & Vesting"),
    ("Team token vesting follows…",
     ["A 6-month lock-up, then 12–24 months linear vesting", "Immediate unlock",
      "10-year cliff", "No vesting"],
     0, "Founding team tokens lock for 6 months then vest linearly over 12–24 months.",
     3, "tokenomics", "14 · Token Distribution & Vesting"),
    ("The ZLN token is described as…",
     ["A purely operational coordination component, not an investment",
      "A guaranteed-yield security", "A meme coin", "Company equity"],
     0, "ZLN is operational; it is not an investment product and grants no equity.",
     2, "tokenomics", "13 · ZLN Coordination Protocol"),
    ("Which is NOT a function of the ZLN token?",
     ["Guaranteed dividends", "Validator node participation",
      "Ecosystem service access", "Governance signaling"],
     0, "ZLN functions are node staking, service access, governance, and settlement — not dividends.",
     2, "tokenomics", "13 · ZLN Coordination Protocol"),
    ("Validator node operators are required to…",
     ["Hold and stake ZLN", "Buy hardware monthly", "Post on social media", "Run a bank"],
     0, "Node operators must hold and stake ZLN to align incentives with network integrity.",
     3, "bnb_coordination", "13 · ZLN Coordination Protocol"),
    ("ZLN governance participation is…",
     ["Advisory in nature", "Full corporate control", "Equity ownership", "Profit entitlement"],
     0, "Governance is advisory; it gives no control over corporate operations or assets.",
     3, "tokenomics", "13 · ZLN Coordination Protocol"),
    ("Zelion anchors trust at…",
     ["The physical hardware source", "A central database", "A marketing team", "An audit firm"],
     0, "Trust is placed at the physical source via tamper-resistant hardware.",
     1, "security", "05 · The Zelion Solution"),
    ("'Proof is separate from record' means…",
     ["The blockchain only stores what hardware already validated",
      "Records are deleted daily", "Hardware copies the blockchain", "Proof is optional"],
     0, "The chain stores hardware-validated data; it never generates or modifies it.",
     2, "security", "05 · The Zelion Solution"),
    ("The architecture's trust flow is…",
     ["One-way, from device outward to the record layer", "Two-way and editable",
      "Top-down from the blockchain", "Random"],
     0, "Trust is established at the source and carried forward; records can't be changed after the fact.",
     3, "infrastructure", "07 · System Architecture"),
    ("Each ZEV unit has…",
     ["A unique hardware-based cryptographic identity", "A shared password",
      "No identity", "A printed serial sticker only"],
     0, "A unique device identity is assigned at manufacturing and roots all proofs.",
     2, "security", "06 · Core Product: The ZEV"),
    ("Where does ZEV validation processing happen?",
     ["Locally on the device (edge); only validated data leaves",
      "In a public cloud", "On the user's phone", "Nowhere"],
     0, "Edge-level processing: raw sensor data never leaves the device.",
     2, "zev_device", "06 · Core Product: The ZEV"),
    ("Which ESG frameworks does Zelion support reporting for?",
     ["CSRD, SFDR, SEC climate rules, TCFD", "Only GDPR", "Only PCI-DSS", "None"],
     0, "Zelion provides audit-grade data for CSRD, SFDR, SEC climate rules and TCFD.",
     2, "esg_verification", "09 · Use Cases"),
    ("How does Zelion help carbon markets?",
     ["Source-level proof for credit issuance and offset validation",
      "By minting carbon randomly", "By ignoring audits", "By printing certificates"],
     0, "Zelion-attested data is a stronger evidence base for carbon credit verification.",
     2, "carbon_markets", "09 · Use Cases"),
    ("For data centers, Zelion enables…",
     ["24/7 / hourly clean-energy matching", "Annual estimates only",
      "No reporting", "Manual spreadsheets"],
     0, "Continuous, source-level verification supports credible 24/7 clean energy claims.",
     3, "ai_energy_demand", "09 · Use Cases"),
    ("Zelion's role in RWA (real-world assets) is to provide…",
     ["The physical evidence layer for tokenized energy assets",
      "Token price predictions", "Legal ownership deeds", "Insurance"],
     0, "Hardware-attested outputs tie tokenized representations to real infrastructure.",
     3, "rwa", "12 · Strategic Ecosystem Alignment"),
    ("For DePIN networks, Zelion functions as…",
     ["A physical proof / data origin layer", "A token exchange",
      "A social network", "A wallet app"],
     0, "Zelion supplies device-level trust as the physical data origin for DePIN systems.",
     2, "depin", "12 · Strategic Ecosystem Alignment"),
    ("Why did Zelion choose BNB Chain–compatible infrastructure?",
     ["Throughput, low cost, institutional adoption, DeFi/DePIN tooling",
      "It is the only blockchain", "Lowest security", "No reason given"],
     0, "BNB Chain offers throughput, low fees, adoption, and mature DeFi/DePIN tooling.",
     3, "bnb_coordination", "12 · Strategic Ecosystem Alignment"),
    ("Zelion's tamper resistance is described as…",
     ["Structural (at the source)", "None", "Purely procedural", "Password-based"],
     0, "Unlike legacy/oracle systems, Zelion's tamper resistance is structural at the source.",
     3, "competitive", "08 · Competitive Positioning"),
    ("Compared with software oracles, Zelion's source-level capture is…",
     ["Yes — oracles have none", "Identical", "Worse", "Not applicable"],
     0, "Zelion provides source-level capture; software oracles do not.",
     3, "competitive", "08 · Competitive Positioning"),
    ("Which is NOT a Zelion commercial revenue stream?",
     ["Token price speculation", "Hardware deployment",
      "Enterprise subscriptions", "API & data access"],
     0, "Revenue comes from hardware, subscriptions, licensing and data access — not token speculation.",
     2, "commercial", "11 · Commercial Model"),
    ("Does Zelion rely on token issuance or price for revenue?",
     ["No", "Yes, primarily", "Only in Phase 1", "Yes, 50%"],
     0, "Zelion does not rely on token issuance, price movements, or secondary markets for revenue.",
     3, "commercial", "11 · Commercial Model"),
    ("Roadmap Phase 1 is named…",
     ["Foundation", "Scale", "Integration", "Sunset"],
     0, "Phase 1 Foundation covers hardware finalization, initial deployment and protocol launch.",
     1, "roadmap", "15 · Development Roadmap"),
    ("Roadmap Phase 2 is named…",
     ["Integration", "Foundation", "Scale", "Maintenance"],
     0, "Phase 2 Integration covers ecosystem activation, enterprise onboarding, data platform launch.",
     2, "roadmap", "15 · Development Roadmap"),
    ("Roadmap Phase 3 is named…",
     ["Scale", "Integration", "Foundation", "Wind-down"],
     0, "Phase 3 Scale covers geographic expansion, partner network and full governance.",
     2, "roadmap", "15 · Development Roadmap"),
    ("Zelion's device design and attestation methods are protected by…",
     ["Filed patent applications", "Open-source MIT license",
      "No protection", "A trademark only"],
     0, "Core architecture and methods are covered by filed patent applications.",
     2, "security", "16 · Intellectual Property & Security"),
    ("A core Zelion security principle is…",
     ["Hardware-rooted trust", "Trust the user input", "No monitoring", "Single shared key"],
     0, "Security is anchored at the hardware level, reducing software-based attack classes.",
     2, "security", "16 · Intellectual Property & Security"),
    ("'Minimal attack surface' refers to…",
     ["Narrow, purpose-built firmware with no general-purpose interfaces",
      "A small office", "Few employees", "A short whitepaper"],
     0, "Firmware is intentionally narrow with no unnecessary features or interfaces.",
     3, "security", "16 · Intellectual Property & Security"),
    ("Why are the three layers decoupled?",
     ["So disruption in one layer doesn't affect validation integrity in others",
      "To save money", "For marketing", "By accident"],
     0, "Decoupling means no single point of failure compromises validation integrity.",
     3, "infrastructure", "07 · System Architecture"),
    ("The ZEV continues operating when…",
     ["Network connectivity is limited or temporarily unavailable",
      "The token price drops", "An admin logs out", "It is unplugged"],
     0, "The device keeps validating at the source even without constant connectivity.",
     2, "zev_device", "07 · System Architecture"),
    ("Enterprise deployment is structured as…",
     ["Hardware provisioning plus an ongoing service agreement",
      "A one-time app download", "A token airdrop", "A free trial only"],
     0, "Setup is by Zelion field engineering plus continuous monitoring/firmware management.",
     3, "enterprise", "10 · Enterprise Deployment Strategy"),
    ("Zelion's channel partner program includes…",
     ["Energy integrators, EPC contractors, grid technology providers",
      "Only retail influencers", "Only banks", "Only exchanges"],
     0, "The channel program scales deployment via infrastructure integrators and EPC/grid partners.",
     4, "enterprise", "10 · Enterprise Deployment Strategy"),
    ("Renewable energy validation replaces self-reported figures with…",
     ["Independently verifiable device data", "Estimates", "Marketing claims", "Annual averages"],
     0, "ZEV outputs replace self-reported figures with hardware-attested, verifiable data.",
     2, "renewable_validation", "09 · Use Cases"),
    ("REC stands for…",
     ["Renewable Energy Certificate", "Reactor Energy Coin",
      "Remote Edge Compute", "Regulated Electric Current"],
     0, "RECs (Renewable Energy Certificates) are a market Zelion data can substantiate.",
     1, "esg_verification", "Overview"),
    ("Layer 2 (Validation & Transmission) does NOT…",
     ["Change or reinterpret the data", "Verify device identities",
      "Preserve provenance", "Prepare data for on-chain submission"],
     0, "Layer 2 moves validated proofs without altering them, preserving provenance.",
     4, "infrastructure", "07 · System Architecture"),
    ("Carbon registries appear in Zelion's partner map for…",
     ["Credit substantiation", "Marketing", "Token listing", "Payroll"],
     0, "Carbon registries integrate for source-level proof behind offset verification.",
     4, "carbon_markets", "12 · Strategic Ecosystem Alignment"),
    ("Crypto mining operators use Zelion to…",
     ["Substantiate renewable energy claims to lenders and regulators",
      "Mine ZLN faster", "Avoid all reporting", "Hide energy use"],
     0, "Hardware-based verification helps miners prove renewable sourcing credibly.",
     3, "enterprise", "09 · Use Cases"),
    ("The ZLN liquidity reserve (15%) is intended for…",
     ["Supporting orderly market conditions, not speculation",
      "Team bonuses", "Buybacks for profit", "Random giveaways"],
     0, "The reserve is managed for orderly conditions, not discretionary or speculative use.",
     4, "tokenomics", "14 · Token Distribution & Vesting"),
    ("Strategic partnership token allocations are released…",
     ["In stages tied to milestones", "All at launch", "Never", "Daily"],
     0, "Partnership/ecosystem allocations unlock with deployment and partnership milestones.",
     4, "tokenomics", "14 · Token Distribution & Vesting"),
    ("ZLN does NOT represent…",
     ["Equity, ownership, or entitlement to profits", "A coordination unit",
      "A governance signal", "A settlement unit"],
     0, "ZLN grants no equity, ownership, or profit claims on Zelion or affiliates.",
     3, "tokenomics", "13 · ZLN Coordination Protocol"),
    ("Independent auditability of the Zelion ZEV is rated…",
     ["Full cryptographic", "Limited", "None", "Manual only"],
     0, "ZEV offers full cryptographic auditability vs limited/moderate for legacy systems.",
     4, "competitive", "08 · Competitive Positioning"),
    ("Zelion's outputs are most valuable to which buyers?",
     ["Institutions under disclosure and compliance requirements",
      "Anonymous traders", "Gamers", "Retail shoppers"],
     0, "Hardware-rooted, audit-grade data is built for institutional compliance use.",
     2, "enterprise", "08 · Competitive Positioning"),
    ("The defining feature of Zelion's architecture is…",
     ["A one-way trust flow from the physical device outward",
      "A central admin override", "Editable history", "Manual data entry"],
     0, "The record layer cannot change proof after the fact; trust flows one direction.",
     3, "infrastructure", "07 · System Architecture"),
]


def _slug(text: str) -> str:
    norm = re.sub(r"\s+", " ", text.strip().lower())
    return hashlib.sha1(norm.encode("utf-8")).hexdigest()


async def _insert(con, q, opts, correct, expl, diff, category, section, source_type, source_url, created_by):
    slug = _slug(q)
    return await con.fetchval(
        """INSERT INTO quiz_questions
           (question, options, correct_index, explanation, difficulty, tier, qtype,
            category, source_section, source_url, source_type, reward, status, active, created_by, slug)
           VALUES($1,$2,$3,$4,$5,$6,'mcq',$7,$8,$9,$10,$11,'approved',true,$12,$13)
           ON CONFLICT (slug) DO NOTHING RETURNING id""",
        q, json.dumps(opts), correct, expl, diff,
        {1: "beginner", 2: "intermediate", 3: "advanced", 4: "expert"}[diff],
        category, section, source_url, source_type, REWARD[diff], created_by, slug,
    )


async def count_active(pool):
    async with pool.acquire() as con:
        return await con.fetchval(
            "SELECT count(*) FROM quiz_questions WHERE status='approved' AND active=true"
        )


async def seed_curated(pool):
    inserted = 0
    async with pool.acquire() as con:
        for (q, opts, correct, expl, diff, cat, section) in CURATED:
            r = await _insert(con, q, opts, correct, expl, diff, cat, section,
                              "document", f"document://{WP}", "curated")
            if r:
                inserted += 1
        await con.execute(
            "INSERT INTO question_generation_logs(source, count_generated, status, detail) "
            "VALUES('curated',$1,'ok',$2)",
            inserted, f"{len(CURATED)} curated questions processed",
        )
    return inserted


async def generate_from_kb(pool, target):
    """Top the bank up to `target` using grounded source-attribution MCQs from KB chunks."""
    have = await count_active(pool)
    if have >= target:
        return 0
    rows = await kb.sample_chunks(pool, n=(target - have) * 2 or 50)
    if not rows:
        return 0
    titles = list({r["title"] for r in rows if r["title"]}) or ["ZelionTech"]
    inserted = 0
    import random
    async with pool.acquire() as con:
        for row in rows:
            if await count_active(pool) >= target and inserted > 0:
                break
            snippet = (row["content"][:150].rsplit(" ", 1)[0]).strip()
            if len(snippet) < 40:
                continue
            cat = row["category"] or categories.classify(row["content"])
            section = categories.label(cat)
            distractors = [c for c in categories.CATEGORIES.values() if c != section]
            random.shuffle(distractors)
            opts = [section] + distractors[:3]
            random.shuffle(opts)
            diff = random.choice([1, 1, 2, 2, 3])
            q = f"Which Zelion topic does this statement relate to?  “{snippet}…”"
            r = await _insert(con, q, opts, opts.index(section),
                              "This statement comes from the cited Zelion source.",
                              diff, cat, section, row["source_type"], row["url"], "kb_generated")
            if r:
                inserted += 1
        await con.execute(
            "INSERT INTO question_generation_logs(source, count_generated, status, detail) "
            "VALUES('kb_generated',$1,'ok',$2)",
            inserted, f"target={target}",
        )
    return inserted


async def ensure_min(pool, minimum=25):
    """Guarantee a playable bank on boot (curated only — no KB needed)."""
    if await count_active(pool) >= minimum:
        return 0
    n = await seed_curated(pool)
    log.info("quiz ensure_min seeded %s curated questions", n)
    return n


async def seed(pool, target=300):
    """Full seed: import docs if needed, curated, then generate to target."""
    chunks = 0
    async with pool.acquire() as con:
        chunks = await con.fetchval("SELECT count(*) FROM knowledge_chunks") or 0
    if chunks == 0:
        try:
            await kb_doc.import_all(pool)
        except Exception as e:
            log.warning("kb import during seed failed: %s", e)
    cur = await seed_curated(pool)
    gen = await generate_from_kb(pool, target)
    total = await count_active(pool)
    return {"curated": cur, "generated": gen, "active_total": total, "target": target}
