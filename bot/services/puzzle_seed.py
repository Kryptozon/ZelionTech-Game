"""ZelionTech-specific puzzle bank. Every puzzle teaches ZelionTech (ZEV, Verified
Energy, BNB coordination layer, ESG verification, DePIN / RWA, the reactor system)
and/or REQUIRES watching the official YouTube / TikTok hint videos to solve — so they
cannot be answered by pasting the text into an AI.

Seeds are idempotent (by slug) and inserted as 'upcoming' + inactive: puzzles NEVER
auto-release; an admin releases one at a time. Answers/walkthroughs/scripts live in
the DB only and are NEVER sent to users (see services/puzzles.py:_public).
"""
import re
import hashlib
import logging

log = logging.getLogger("zelion.puzzleseed")

YT_CHANNEL = "https://www.youtube.com/@ZelionTech"
TT_CHANNEL = "https://www.tiktok.com/@zeliontech_zev"
REWARD = {"easy": 100, "medium": 130, "hard": 170, "legendary": 230}
PENALTY = {"easy": 10, "medium": 10, "hard": 10, "legendary": 10}


def _norm(s):
    return re.sub(r"[^A-Z0-9]", "", str(s).upper())


def _slug(key):
    return "zt-" + re.sub(r"[^a-z0-9]+", "-", str(key).lower()).strip("-")[:40]


# ---------------------------------------------------------------------------
# 1) ECOSYSTEM puzzles — ZelionTech project knowledge (teaches users about the
#    project; project-specific facts, not generic logic an AI can derive).
#    (question, ANSWER, accepted, difficulty, explanation/walkthrough)
# ---------------------------------------------------------------------------
ECO = [
    ("Which hardware device is ZelionTech's physical root of trust?", "ZEV", "zev,zelion energy validator",
     "easy", "The ZEV (Zelion Energy Validator) generates tamper-resistant proof at the energy source."),
    ("ZelionTech turns real renewable generation into what two-word, hardware-attested asset? (___ Energy)",
     "VERIFIED", "verified,verified energy", "easy",
     "Verified Energy is hardware-attested proof that clean energy was actually produced."),
    ("On which chain does ZelionTech's coordination & record layer run?", "BNB", "bnb,bnb chain",
     "easy", "The coordination layer runs on BNB Chain for low fees, throughput and DePIN tooling."),
    ("ZelionTech provides source-level proof to strengthen carbon credit ___ ?", "VERIFICATION",
     "verification,esg verification", "medium",
     "Source-level proof strengthens ESG / carbon-credit verification and disclosure."),
    ("Decentralized physical infrastructure networks are abbreviated as?", "DEPIN", "depin",
     "medium", "ZelionTech is the physical data-origin (DePIN) layer for clean-energy networks."),
    ("Real-world asset tokenization is abbreviated as?", "RWA", "rwa",
     "medium", "ZelionTech supplies the physical evidence layer behind RWA tokenization."),
    ("Trust in ZelionTech is anchored in software or hardware?", "HARDWARE", "hardware",
     "medium", "Validation happens inside tamper-resistant hardware at the energy source."),
    ("Which token coordinates the ZelionTech network (nodes, access, governance, settlement)?",
     "ZLN", "zln,zln token", "easy", "The ZLN protocol token coordinates the whole network."),
    ("In the ZelionTech flow 'Verified Energy -> ? -> Digital Proof', what is the missing layer?",
     "ORACLE", "oracle,zelion oracle", "hard",
     "The Zelion Oracle sits between Verified Energy and the final on-chain Digital Proof."),
    ("Validation in ZelionTech happens at the cloud or at the edge (on the device)?", "EDGE", "edge",
     "hard", "All validation is edge-level; only validated data ever leaves the ZEV device."),
]


# ---------------------------------------------------------------------------
# 2) VIDEO-DEPENDENT puzzles — AI-RESISTANT. The answer is only discoverable by
#    watching the exact published YouTube / TikTok clue.
#    (key, title, question, ANSWER, accepted, difficulty, ts, placement, walkthrough)
# ---------------------------------------------------------------------------
VIDEO = [
    ("timestamp-flash", "Flash Frame: Verified Energy",
     "A single word flashes for under a second in today's official YouTube Short. Enter that word.",
     "VERIFIED", "verified,verified energy", "medium", "00:07",
     "White-on-black frame flashes the word VERIFIED at ~0.4s.",
     "Pause the official YouTube Short at 0:07 — the flashed word is VERIFIED."),
    ("reactor-symbol", "The Symbol Behind the ZEV",
     "In today's official TikTok, a reactor symbol appears behind the ZEV device. Name that symbol.",
     "ATOM", "atom,atom symbol,nucleus", "medium", "00:04",
     "Atom/reactor emblem fades in behind the ZEV device between 0:03-0:06.",
     "The glowing emblem behind the ZEV in the TikTok is the atom/reactor mark."),
    ("missing-layer", "The Missing Layer",
     "Today's video shows 'Verified Energy -> ? -> Digital Proof'. Which Zelion layer is missing?",
     "ORACLE", "oracle,zelion oracle", "hard", "00:12",
     "Narrator names the middle layer 'Oracle' at ~0:12 while the diagram is on screen.",
     "The video narrates the middle layer as the Zelion Oracle."),
    ("multisource-combo", "Two-Source Cipher",
     "Combine the hidden word from today's YouTube hint with the symbol shown in today's TikTok, "
     "then enter the single Zelion term they form.",
     "ZEVBRIDGE", "zev bridge,zevbridge,bridge", "legendary", "YT 00:09 / TT 00:05",
     "YouTube flashes 'ZEV' at 0:09; TikTok shows the Bridge glyph at 0:05.",
     "YouTube reveals ZEV, TikTok reveals Bridge — together: ZEV Bridge."),
    ("daily-code", "Daily Reactor Code",
     "The answer is the hidden ZLN-#### code the admin places in today's official YouTube/TikTok video. "
     "Watch and enter the exact code.",
     "ZLN-0000", "zln0000,zln-0000", "easy", "00:15",
     "Admin overlays the daily ZLN-#### code near the end of the video.",
     "Read the on-screen ZLN-#### code from the official video and enter it exactly."),
    ("hidden-frame", "0.4-Second Code",
     "At second 6 of today's official ZelionTech YouTube Short, a code naming Zelion's physical "
     "infrastructure layer flashes for 0.4 seconds. Enter that code.",
     "DEPIN", "depin", "hard", "00:06",
     "A single frame at 0:06 flashes the DePIN code for ~0.4s.",
     "Step through 0:06 frame-by-frame: it shows DEPIN, Zelion's physical infrastructure (DePIN) layer."),
]


def _eco(q, ans, accepted, difficulty, explanation):
    ans_n = _norm(ans)
    return {
        "slug": _slug("eco-" + ans + "-" + q[:18]), "title": "ZelionTech Knowledge",
        "question": q, "answer": ans_n, "accepted_variations": accepted,
        "source_topic": "ZelionTech Ecosystem", "difficulty": difficulty,
        "reward": REWARD[difficulty], "penalty": PENALTY[difficulty],
        "category": "Ecosystem Knowledge",
        "hint1": "Hints are hidden in today's official YouTube/TikTok videos.",
        "hint2": "Watch the official ZelionTech videos to learn the answer.",
        "hint3": "No hints are shown in the app.",
        "source": "zeliontech.com / ZelionTech Whitepaper",
        "youtube_instruction": "Watch the official YouTube channel for context.",
        "telegram_instruction": "A new hint video is live on YouTube and TikTok.",
        "explanation": explanation, "walkthrough": explanation,
        "youtube_url": YT_CHANNEL, "tiktok_url": TT_CHANNEL,
        "hidden_clue_timestamp": "", "hidden_clue_description": "",
        "hints": {"daily_hint1": "", "daily_hint2": "", "daily_hint3": "",
                  "youtube_timestamp": "", "telegram_post_text": "New hint video is live.",
                  "hidden_answer_placement": explanation},
        "script": _script("ZelionTech Knowledge", q, "", explanation),
    }


def _video(key, title, q, ans, accepted, difficulty, ts, placement, walkthrough):
    ans_n = _norm(ans)
    return {
        "slug": _slug(key), "title": title, "question": q, "answer": ans_n,
        "accepted_variations": accepted, "source_topic": "Official Video Clue",
        "difficulty": difficulty, "reward": REWARD[difficulty], "penalty": PENALTY[difficulty],
        "category": "Video Clue",
        "hint1": "Hints are hidden in today's official YouTube/TikTok videos.",
        "hint2": "There are no hints in the app or on other platforms.",
        "hint3": "Watch YouTube and TikTok to decode.",
        "source": "ZelionTech YouTube / TikTok",
        "youtube_instruction": "The clue is hidden in today's official YouTube video.",
        "telegram_instruction": "A new hint video is live on YouTube and TikTok.",
        "explanation": walkthrough, "walkthrough": walkthrough,
        "youtube_url": YT_CHANNEL, "tiktok_url": TT_CHANNEL,
        "hidden_clue_timestamp": ts, "hidden_clue_description": placement,
        "hints": {"daily_hint1": "", "daily_hint2": "", "daily_hint3": "",
                  "youtube_timestamp": ts, "telegram_post_text": "New hint video is live.",
                  "hidden_answer_placement": placement},
        "script": _script(title, q, ts, placement),
    }


def _script(title, q, ts, placement):
    return {
        "youtube_title": f"⚡ Zelion Intelligence — {title}",
        "youtube_script": (f"INTRO: Welcome back, Operators. Today's Reactor Intelligence puzzle is "
                           f"\"{title}\".\nBODY: {q}\nThe clue is hidden at "
                           f"{ts or 'a key moment'} — {placement or '(set placement in dashboard)'}.\n"
                           f"OUTRO: Submit your answer in the Zelion Reactor app."),
        "tiktok_script": (f"Hook: \"Blink and you'll miss the Zelion clue 👀\". Show the clue at "
                         f"{ts or 'the drop'}. {placement or ''} End: Answer in the Zelion Reactor app."),
        "clue_timestamp": ts, "visual_clue": placement, "audio_clue": "",
        "caption_clue": "", "cta": "Open Zelion Reactor and submit today's puzzle.",
        "telegram_post": (f"⚡ New hint video is live on YouTube & TikTok. Watch, decode and submit "
                         f"\"{title}\" in the app."),
    }


def generate():
    """The curated ZelionTech puzzle bank (no generic AI-solvable puzzles)."""
    out = []
    for q, ans, accepted, diff, ex in ECO:
        out.append(_eco(q, ans, accepted, diff, ex))
    for row in VIDEO:
        out.append(_video(*row))
    # de-dupe by slug
    seen, uniq = set(), []
    for p in out:
        if p["slug"] in seen:
            continue
        seen.add(p["slug"]); uniq.append(p)
    return uniq


async def count_active(pool):
    async with pool.acquire() as con:
        return await con.fetchval("SELECT count(*) FROM puzzles WHERE active=true") or 0


async def count_bank(pool):
    async with pool.acquire() as con:
        return await con.fetchval("SELECT count(*) FROM puzzles") or 0


async def seed(pool):
    """Idempotently seed the ZelionTech bank. Puzzles are inserted as 'upcoming' +
    inactive — they NEVER auto-release; an admin releases one at a time."""
    puzzles = generate()
    inserted = 0
    async with pool.acquire() as con:
        for p in puzzles:
            pid = await con.fetchval(
                """INSERT INTO puzzles(slug,title,question,answer,accepted_variations,source_topic,
                       difficulty,reward,penalty,category,hint1,hint2,hint3,source,
                       youtube_instruction,telegram_instruction,explanation,walkthrough,
                       youtube_url,tiktok_url,hidden_clue_timestamp,hidden_clue_description,active,status)
                   VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,
                          $19,$20,$21,$22,false,'upcoming')
                   ON CONFLICT (slug) DO NOTHING RETURNING id""",
                p["slug"], p["title"], p["question"], p["answer"], p["accepted_variations"],
                p["source_topic"], p["difficulty"], p["reward"], p["penalty"], p["category"],
                p["hint1"], p["hint2"], p["hint3"], p["source"],
                p["youtube_instruction"], p["telegram_instruction"], p["explanation"], p["walkthrough"],
                p["youtube_url"], p["tiktok_url"], p["hidden_clue_timestamp"], p["hidden_clue_description"])
            if not pid:
                continue
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
                """INSERT INTO puzzle_scripts(puzzle_id,youtube_title,youtube_script,tiktok_script,
                       clue_timestamp,visual_clue,audio_clue,caption_clue,cta,telegram_post)
                   VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10) ON CONFLICT (puzzle_id) DO NOTHING""",
                pid, s["youtube_title"], s["youtube_script"], s["tiktok_script"], s["clue_timestamp"],
                s["visual_clue"], s["audio_clue"], s["caption_clue"], s["cta"], s["telegram_post"])
    return {"generated": len(puzzles), "inserted": inserted, "bank": await count_bank(pool)}


async def ensure_seed(pool):
    """Guarantee the curated ZelionTech bank exists (idempotent)."""
    return await seed(pool)
