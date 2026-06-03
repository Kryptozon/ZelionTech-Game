"""AI quiz generator — grounded ONLY in the ZelionTech KB (document + website).

Safety: every question is built from a single verified KB chunk and stores that
chunk's source_url. If the excerpt is insufficient the model must return
{"skip": true} (no invented facts). With no AI_API_KEY a deterministic, fully
grounded source-attribution fallback is used.
"""
import json
import random
import aiohttp

from ..config import settings
from . import kb, categories

TIER_BY_DIFF = {1: "beginner", 2: "intermediate", 3: "advanced", 4: "expert"}

QTYPE_INSTRUCTION = {
    "mcq": "a multiple-choice question with exactly 4 options",
    "true_false": "a True/False question; options MUST be exactly [\"True\",\"False\"]",
    "scenario": "a real-world scenario/application question with 4 options",
    "architecture": "a question about Zelion's system architecture/layers with 4 options",
    "tokenomics": "a question about Zelion tokenomics/distribution/vesting with 4 options",
}

DIFF_HINT = {1: "basic factual recall", 2: "simple understanding",
             3: "comparison/analysis", 4: "expert ecosystem application"}

SYSTEM_PROMPT = (
    "You write quiz questions for ZelionTech. You may ONLY use facts contained in the "
    "provided excerpt. NEVER invent facts, numbers, partners, or specs. If the excerpt is "
    "insufficient to write a correct, unambiguous question, return {\"skip\": true}. "
    "Otherwise return STRICT JSON: {question, options[], correct_index, explanation}. "
    "The correct answer must be directly verifiable from the excerpt."
)


async def _call_llm(excerpt, qtype, difficulty):
    user = (
        f"ZelionTech excerpt:\n\"\"\"\n{excerpt}\n\"\"\"\n\n"
        f"Write {QTYPE_INSTRUCTION[qtype]}, difficulty: {DIFF_HINT[difficulty]} "
        f"(level {difficulty}). Return STRICT JSON only."
    )
    payload = {
        "model": settings.AI_MODEL,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                     {"role": "user", "content": user}],
        "temperature": 0.3,
        "response_format": {"type": "json_object"},
    }
    headers = {"Authorization": f"Bearer {settings.AI_API_KEY}", "Content-Type": "application/json"}
    async with aiohttp.ClientSession() as s:
        async with s.post(f"{settings.AI_API_BASE}/chat/completions", json=payload,
                          headers=headers, timeout=aiohttp.ClientTimeout(total=60)) as r:
            data = await r.json()
    return json.loads(data["choices"][0]["message"]["content"])


def _valid(q, qtype):
    n = 2 if qtype == "true_false" else 4
    return (isinstance(q.get("question"), str)
            and isinstance(q.get("options"), list) and len(q["options"]) == n
            and isinstance(q.get("correct_index"), int) and 0 <= q["correct_index"] < n)


def _fallback(chunk_text, title, all_titles):
    """Grounded MCQ: which document/section does this verbatim statement come from?"""
    snippet = chunk_text[:150].rsplit(" ", 1)[0]
    distractors = [t for t in all_titles if t and t != title]
    random.shuffle(distractors)
    options = [title] + distractors[:3]
    while len(options) < 4:
        options.append("None of the above")
    random.shuffle(options)
    return {
        "question": f"According to the ZelionTech knowledge base, which source states: “{snippet}…”?",
        "options": options,
        "correct_index": options.index(title),
        "explanation": "This statement is taken verbatim from the cited ZelionTech source.",
    }, "mcq"


async def generate(pool, count=5, difficulty=1, qtype="mcq", category=None, auto_approve=False):
    rows = await kb.sample_chunks(pool, n=max(count * 2, 8), category=category)
    if not rows:
        return {"inserted": 0, "reason": "knowledge base empty — run /kbrefresh first"}

    all_titles = list({r["title"] for r in rows if r["title"]})
    use_ai = bool(settings.AI_API_KEY)
    tier = TIER_BY_DIFF.get(difficulty, "beginner")
    status = "approved" if auto_approve else "pending"
    inserted = []

    for row in rows:
        if len(inserted) >= count:
            break
        q, used_type = None, qtype
        if use_ai:
            try:
                cand = await _call_llm(row["content"], qtype, difficulty)
                if not cand.get("skip") and _valid(cand, qtype):
                    q = cand
            except Exception:
                q = None
        if q is None and not use_ai:
            q, used_type = _fallback(row["content"], row["title"], all_titles)
        if q is None or not _valid(q, used_type):
            continue

        cat = row["category"] or categories.classify(row["content"])
        async with pool.acquire() as con:
            qid = await con.fetchval(
                """INSERT INTO quiz_questions
                   (question, options, correct_index, explanation, difficulty, tier, qtype,
                    category, source_url, source_type, chunk_id, status, created_by)
                   VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,'ai') RETURNING id""",
                q["question"], json.dumps(q["options"]), int(q["correct_index"]),
                q.get("explanation", ""), difficulty, tier, used_type, cat,
                row["url"], row["source_type"], row["id"], status,
            )
        inserted.append(qid)

    return {"inserted": len(inserted), "ids": inserted,
            "mode": "ai" if use_ai else "fallback", "tier": tier,
            "status": status, "qtype": qtype}
