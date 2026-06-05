"""Generates ~200 Zelion Intelligence puzzles (Morse, Binary, Cipher, Ecosystem,
Treasure Hunt) with hints + YouTube scripts + Telegram posts. Seeds them into the
DB (idempotent by slug) and exports JSON to /puzzles, /daily_hints, /youtube_scripts,
/telegram_hints. Answers live server-side only and are never sent to users.
"""
import os
import re
import json
import hashlib
import logging

log = logging.getLogger("zelion.puzzleseed")
BASE = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

REWARD = {"easy": 20, "medium": 50, "hard": 100, "legendary": 250}
PENALTY = {"easy": 2, "medium": 2, "hard": 2, "legendary": 5}
DIST = {"easy": 80, "medium": 60, "hard": 40, "legendary": 20}

MORSE = {
    'A': '.-', 'B': '-...', 'C': '-.-.', 'D': '-..', 'E': '.', 'F': '..-.', 'G': '--.',
    'H': '....', 'I': '..', 'J': '.---', 'K': '-.-', 'L': '.-..', 'M': '--', 'N': '-.',
    'O': '---', 'P': '.--.', 'Q': '--.-', 'R': '.-.', 'S': '...', 'T': '-', 'U': '..-',
    'V': '...-', 'W': '.--', 'X': '-..-', 'Y': '-.--', 'Z': '--..',
    '0': '-----', '1': '.----', '2': '..---', '3': '...--', '4': '....-',
    '5': '.....', '6': '-....', '7': '--...', '8': '---..', '9': '----.',
}

TERMS = ["ZELION", "ZEV", "VALIDATOR", "ENERGY", "PROOF", "BNB", "REACTOR", "COORDINATION",
         "HARDWARE", "VERIFICATION", "ORACLE", "BRIDGE", "RWA", "DEPIN", "ESG", "CARBON",
         "TOKENOMICS", "GRID", "SOLAR", "FUSION", "QUANTUM", "LAYER", "NETWORK", "PROTOCOL",
         "STAKE", "GOVERNANCE", "PHYSICAL", "TAMPER", "ATTESTATION", "SETTLEMENT", "RENEWABLE",
         "BATTERY", "PROVENANCE", "INFRASTRUCTURE", "INSTITUTIONAL", "DISCLOSURE", "CIPHER",
         "SEQUENCE", "MYSTERY", "OPERATOR"]

# Short-answer ecosystem facts (hard). (question, ANSWER, explanation)
ECO = [
    ("Which hardware device is Zelion's physical root of trust?", "ZEV",
     "The ZEV (Zelion Energy Validator) generates tamper-resistant proof at the energy source."),
    ("How many layers does the Zelion architecture have?", "THREE",
     "Physical Proof, Validation & Transmission, and Coordination & Record layers."),
    ("On which chain is the coordination & record layer built?", "BNB",
     "Layer 3 runs on BNB Chain–compatible infrastructure."),
    ("What is the fixed total supply of ZLN, in millions?", "500",
     "ZLN total supply is fixed at 500,000,000 with no further minting."),
    ("Trust in Zelion is anchored in software or hardware?", "HARDWARE",
     "Validation happens inside tamper-resistant hardware at the source."),
    ("Which token coordinates the Zelion network?", "ZLN",
     "The ZLN protocol token coordinates validator nodes, access, governance and settlement."),
    ("What kind of energy does Zelion focus on validating?", "RENEWABLE",
     "Zelion provides hardware-attested proof for renewable energy generation."),
    ("Real-world asset tokenization compatibility is abbreviated as?", "RWA",
     "Zelion supplies the physical evidence layer behind RWA tokenization."),
    ("Decentralized physical infrastructure networks are abbreviated as?", "DEPIN",
     "Zelion acts as the physical data-origin layer for DePIN networks."),
    ("Carbon credit markets rely on Zelion for credit ___ ?", "VERIFICATION",
     "Source-level proof strengthens carbon credit verification."),
    ("Reporting framework Zelion supports starting with C?", "CSRD",
     "Zelion supplies audit-grade data for CSRD and other ESG frameworks."),
    ("Validator node operators must hold and ___ ZLN?", "STAKE",
     "Staking ZLN aligns node operators with network integrity."),
    ("Governance in Zelion is binding or advisory?", "ADVISORY",
     "ZLN governance is advisory and grants no corporate control."),
    ("The trust flow in Zelion is one-way or two-way?", "ONEWAY",
     "Trust flows one way: from the physical device outward to the record."),
    ("ZEV processing happens at the cloud or the edge?", "EDGE",
     "All validation is edge-level; only validated data leaves the device."),
    ("Each ZEV has a unique cryptographic ___ ?", "IDENTITY",
     "A unique hardware identity roots every proof to a specific device."),
    ("Which sector needs 24/7 clean-energy matching from Zelion?", "DATACENTER",
     "Data centers / AI infrastructure need hourly clean-energy verification."),
    ("Zelion's blockchain choice is driven by low cost and high ___ ?", "THROUGHPUT",
     "BNB Chain offers throughput, low fees, adoption and DePIN tooling."),
    ("Team token vesting starts with a 6-month ___ ?", "LOCKUP",
     "Team tokens lock 6 months then vest linearly over 12–24 months."),
    ("Zelion's blockchain explorer is built with which JS framework?", "NEXTJS",
     "Zelion Explorer is built with TypeScript and Next.js."),
]


def _norm(s):
    return re.sub(r"[^A-Z0-9]", "", str(s).upper())


def _slug(title, answer):
    return hashlib.sha1(f"{title}|{answer}".encode()).hexdigest()[:20]


def _caesar(word, k=13):
    out = []
    for ch in word:
        if ch.isalpha():
            out.append(chr((ord(ch) - 65 + k) % 26 + 65))
        else:
            out.append(ch)
    return "".join(out)


def _wrap(answer, difficulty, category, title, question, explanation,
          yt_clue="a Morse flash", tg_clue="the latest Intelligence Drop"):
    ans = _norm(answer)
    yt_ts = f"0:{(hash(title) % 50) + 10:02d}"
    return {
        "slug": _slug(title, ans), "title": title, "question": question, "answer": ans,
        "accepted_variations": ans.lower(), "source_topic": category,
        "difficulty": difficulty, "reward": REWARD[difficulty], "penalty": PENALTY[difficulty],
        "category": category,
        "hint1": "The answer is a core Zelion ecosystem term.",
        "hint2": f"Decode the {category.lower()} carefully — letters map to a Zelion word.",
        "hint3": "Watch the YouTube clue and read the Telegram drop for the exact placement.",
        "source": "Zelion Whitepaper v3 / zeliontech.com",
        "youtube_instruction": f"Today's clue is hidden on 📺 YouTube as {yt_clue}.",
        "telegram_instruction": f"A hint is in 📢 {tg_clue} on the Telegram channel.",
        "explanation": explanation,
        "hints": {
            "daily_hint1": "Focus on Zelion's core vocabulary.",
            "daily_hint2": f"This is a {difficulty} {category}.",
            "daily_hint3": f"The decoded answer relates to: {explanation[:60]}…",
            "youtube_timestamp": yt_ts,
            "telegram_post_text": f"⚡ Reactor Intelligence Drop — today's mystery is a {category}. Decode and submit in the app.",
            "hidden_answer_placement": f"Answer flashes at {yt_ts} as Morse / overlay text.",
        },
        "script": {
            "youtube_title": f"⚡ Zelion Reactor Intelligence Briefing — {category}",
            "youtube_script": (
                "Operator, today's Reactor Mystery has been activated.\n"
                f"The answer is tied to Zelion's {category.lower()}. {explanation}\n"
                "Only true Reactors will discover it."),
            "clue_timestamp": yt_ts,
            "visual_clue": f"At {yt_ts}, flash the answer as Morse/overlay for 0.5s.",
            "audio_clue": "Optional: a short beep pattern spelling the first letter.",
            "caption_clue": "Hide the first letters of subtitle lines to spell a hint.",
            "cta": "Open Zelion Reactor and solve today's puzzle.",
            "telegram_post": (
                f"⚡ Reactor Intelligence Drop\n\nToday's mystery is a {category}.\n"
                "The answer is not Bitcoin. The answer is not Solana.\n"
                "Open the Reactor and submit your answer.\n\n#Zelion #ReactorChallenge"),
        },
    }


def generate():
    puzzles, used = [], set()

    def add(p):
        if p["slug"] in used:
            return
        used.add(p["slug"]); puzzles.append(p)

    counts = {k: 0 for k in DIST}

    # EASY: Morse + Binary + Reverse
    for t in TERMS[:30]:
        if counts["easy"] >= DIST["easy"]:
            break
        code = " ".join(MORSE[c] for c in t if c in MORSE)
        add(_wrap(t, "easy", "Morse Code Challenge", f"Reactor Morse: decode this",
                  f"Decode the Morse code:\n{code}", f"In Morse, this spells {t}.")); counts["easy"] += 1
    for t in TERMS[:30]:
        if counts["easy"] >= DIST["easy"]:
            break
        b = " ".join(format(ord(c), "08b") for c in t)
        add(_wrap(t, "easy", "Binary Challenge", "Reactor Binary: decode this",
                  f"Decode the 8-bit binary:\n{b}", f"Each byte is an ASCII letter spelling {t}.")); counts["easy"] += 1
    for t in TERMS:
        if counts["easy"] >= DIST["easy"]:
            break
        add(_wrap(t, "easy", "Reactor Cipher", "Reactor mirror cipher",
                  f"Reverse this to reveal a Zelion term:\n{t[::-1]}", f"Reversed, it spells {t}.")); counts["easy"] += 1

    # MEDIUM: Caesar cipher + sequence puzzles
    for t in TERMS:
        if counts["medium"] >= 40:
            break
        c = _caesar(t, 13)
        add(_wrap(t, "medium", "Reactor Cipher", "Reactor ROT13 cipher",
                  f"Apply ROT13 to decode:\n{c}", f"ROT13 of {c} is {t}.")); counts["medium"] += 1
    seqs = [([2, 4, 8, 16], 32), ([3, 6, 12, 24], 48), ([1, 1, 2, 3, 5], 8), ([5, 10, 20, 40], 80),
            ([1, 4, 9, 16], 25), ([2, 6, 18, 54], 162), ([10, 20, 40, 80], 160), ([1, 2, 4, 7, 11], 16),
            ([100, 50, 25], 12), ([7, 14, 28], 56), ([1, 3, 9, 27], 81), ([2, 5, 11, 23], 47),
            ([1, 8, 27, 64], 125), ([3, 5, 9, 17], 33), ([6, 12, 24, 48], 96), ([4, 9, 16, 25], 36),
            ([1, 2, 6, 24], 120), ([2, 3, 5, 8], 12), ([9, 18, 36], 72), ([11, 22, 44], 88)]
    for arr, ans in seqs:
        if counts["medium"] >= DIST["medium"]:
            break
        add(_wrap(str(ans), "medium", "Reactor Sequence Puzzle", "Reactor sequence",
                  f"Find the next number in the Reactor sequence:\n{', '.join(map(str, arr))}, ?",
                  f"The next value is {ans}.")); counts["medium"] += 1

    # HARD: ecosystem Q&A + multi-term ciphers
    for q, a, ex in ECO:
        if counts["hard"] >= 25:
            break
        add(_wrap(a, "hard", "Ecosystem Mystery", "Zelion Ecosystem Mystery", q, ex)); counts["hard"] += 1
    for t in TERMS:
        if counts["hard"] >= DIST["hard"]:
            break
        c = _caesar(t, 7)
        add(_wrap(t, "hard", "Reactor Cipher", "Reactor shift-7 cipher",
                  f"Shift each letter back by 7 to decode:\n{c}",
                  f"Caesar shift 7 reveals {t}.")); counts["hard"] += 1

    # LEGENDARY: multi-step treasure hunts
    for i, t in enumerate(TERMS[:DIST["legendary"]]):
        steps = (
            "Step 1: Find the clue in the pinned Telegram Intelligence Drop.\n"
            "Step 2: Watch the linked YouTube Short and note the flashed Morse at the timestamp.\n"
            "Step 3: Decode the Morse to a Zelion term.\n"
            "Step 4: Enter the final answer below.")
        morse = " ".join(MORSE[c] for c in t if c in MORSE)
        p = _wrap(t, "legendary", "Multi-Step Treasure Hunt",
                  f"⚡ Reactor Mystery Hunt #{i + 1}", steps,
                  f"The hidden Morse spells {t}.")
        p["hints"]["hidden_answer_placement"] = f"YouTube {p['hints']['youtube_timestamp']} Morse: {morse}"
        add(p); counts["legendary"] += 1

    return puzzles


def _write_files(puzzles):
    dirs = {d: os.path.join(BASE, "puzzles", d) for d in DIST}
    for d in (*dirs.values(), os.path.join(BASE, "daily_hints"),
              os.path.join(BASE, "youtube_scripts"), os.path.join(BASE, "telegram_hints")):
        os.makedirs(d, exist_ok=True)
    for p in puzzles:
        slug = p["slug"]
        # public-ish puzzle record (admin export — includes answer; not web-served)
        with open(os.path.join(dirs[p["difficulty"]], f"{slug}.json"), "w", encoding="utf-8") as f:
            json.dump({k: p[k] for k in p if k not in ("script", "hints")}, f, indent=2)
        with open(os.path.join(BASE, "daily_hints", f"{slug}.json"), "w", encoding="utf-8") as f:
            json.dump({"puzzle_id": slug, **p["hints"]}, f, indent=2)
        with open(os.path.join(BASE, "youtube_scripts", f"{slug}.json"), "w", encoding="utf-8") as f:
            json.dump({"puzzle_id": slug, **p["script"]}, f, indent=2)
        with open(os.path.join(BASE, "telegram_hints", f"{slug}.json"), "w", encoding="utf-8") as f:
            json.dump({"puzzle_id": slug, "post": p["script"]["telegram_post"],
                       "short_clue": p["hints"]["telegram_post_text"]}, f, indent=2)


async def count_active(pool):
    async with pool.acquire() as con:
        return await con.fetchval("SELECT count(*) FROM puzzles WHERE active=true") or 0


async def seed(pool, write_files=True):
    puzzles = generate()
    if write_files:
        try:
            _write_files(puzzles)
        except Exception as e:
            log.warning("puzzle file export failed: %s", e)
    inserted = 0
    async with pool.acquire() as con:
        for p in puzzles:
            pid = await con.fetchval(
                """INSERT INTO puzzles(slug,title,question,answer,accepted_variations,source_topic,
                       difficulty,reward,penalty,category,hint1,hint2,hint3,source,
                       youtube_instruction,telegram_instruction,explanation,active,status)
                   VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,true,'active')
                   ON CONFLICT (slug) DO NOTHING RETURNING id""",
                p["slug"], p["title"], p["question"], p["answer"], p["accepted_variations"],
                p["source_topic"], p["difficulty"], p["reward"], p["penalty"], p["category"],
                p["hint1"], p["hint2"], p["hint3"], p["source"],
                p["youtube_instruction"], p["telegram_instruction"], p["explanation"])
            if pid:
                inserted += 1
                h = p["hints"]
                await con.execute(
                    """INSERT INTO puzzle_hints(puzzle_id,daily_hint1,daily_hint2,daily_hint3,
                           youtube_timestamp,telegram_post_text,hidden_answer_placement)
                       VALUES($1,$2,$3,$4,$5,$6,$7) ON CONFLICT (puzzle_id) DO NOTHING""",
                    pid, h["daily_hint1"], h["daily_hint2"], h["daily_hint3"],
                    h["youtube_timestamp"], h["telegram_post_text"], h["hidden_answer_placement"])
                s = p["script"]
                await con.execute(
                    """INSERT INTO puzzle_scripts(puzzle_id,youtube_title,youtube_script,clue_timestamp,
                           visual_clue,audio_clue,caption_clue,cta,telegram_post)
                       VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9) ON CONFLICT (puzzle_id) DO NOTHING""",
                    pid, s["youtube_title"], s["youtube_script"], s["clue_timestamp"],
                    s["visual_clue"], s["audio_clue"], s["caption_clue"], s["cta"], s["telegram_post"])
    return {"generated": len(puzzles), "inserted": inserted, "active": await count_active(pool)}


async def ensure_min(pool, minimum=50):
    if await count_active(pool) >= minimum:
        return 0
    res = await seed(pool, write_files=False)
    return res["inserted"]
