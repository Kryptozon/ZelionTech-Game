"""AI quiz generator — grounded ONLY in zeliontech.com knowledge base.

If AI_API_KEY is set, calls an OpenAI-compatible chat API with a strict grounded
prompt. Otherwise falls back to a deterministic, source-cited generator that builds
simple title-attribution questions from real chunks (never invents facts).
Every generated question is stored as status='pending' for admin review and
always carries a source_url.
"""
import json
import random
import aiohttp

from ..config import settings
from . import kb

SYSTEM_PROMPT = (
    "You are a quiz writer for ZelionTech. You may ONLY use facts contained in the "
    "provided ZelionTech website excerpt. Never invent facts. If the excerpt does not "
    "contain enough information to write a correct, unambiguous question, reply with "
    '{"skip": true}. Otherwise output STRICT JSON with keys: question, options (array of '
    "exactly 4 strings), correct_index (0-3), explanation (1 sentence), difficulty (1-5 "
    "matching the requested level). The correct answer must be verifiable from the excerpt."
)

DIFFICULTY_HINT = {
    1: "a basic factual recall question",
    2: "a simple understanding question",
    3: "a comparison question between two concepts",
    4: "a scenario / application question",
    5: "an expert ecosystem question",
}


async def _call_llm(excerpt: str, difficulty: int):
    user = (
        f"ZelionTech website excerpt:\n\"\"\"\n{excerpt}\n\"\"\"\n\n"
        f"Write {DIFFICULTY_HINT.get(difficulty, 'a question')} (difficulty {difficulty}). "
        f"Return STRICT JSON only."
    )
    payload = {
        "model": settings.AI_MODEL,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                     {"role": "user", "content": user}],
        "temperature": 0.4,
        "response_format": {"type": "json_object"},
    }
    headers = {"Authorization": f"Bearer {settings.AI_API_KEY}", "Content-Type": "application/json"}
    async with aiohttp.ClientSession() as s:
        async with s.post(f"{settings.AI_API_BASE}/chat/completions", json=payload,
                          headers=headers, timeout=aiohttp.ClientTimeout(total=60)) as r:
            data = await r.json()
    content = data["choices"][0]["message"]["content"]
    return json.loads(content)


def _valid(q: dict) -> bool:
    return (
        isinstance(q.get("question"), str)
        and isinstance(q.get("options"), list) and len(q["options"]) == 4
        and isinstance(q.get("correct_index"), int) and 0 <= q["correct_index"] <= 3
    )


def _fallback_question(chunk_text: str, title: str, difficulty: int, all_titles):
    """Grounded, source-cited fallback: which page does this statement come from?"""
    snippet = chunk_text[:160].rsplit(" ", 1)[0]
    distractors = [t for t in all_titles if t and t != title]
    random.shuffle(distractors)
    options = [title] + distractors[:3]
    while len(options) < 4:
        options.append("None of the above")
    random.shuffle(options)
    return {
        "question": f"On the ZelionTech website, which page states: “{snippet}…”?",
        "options": options,
        "correct_index": options.index(title),
        "explanation": "This statement appears on the cited ZelionTech page.",
        "difficulty": difficulty,
    }


async def generate(pool, count=5, difficulty=1):
    """Generate `count` pending questions grounded in the KB. Returns inserted ids."""
    rows = await kb.sample_chunks(pool, n=max(count * 2, 8))
    if not rows:
        return {"inserted": 0, "reason": "knowledge base empty — run /kbrefresh first"}

    all_titles = list({r["title"] for r in rows if r["title"]})
    inserted = []
    use_ai = bool(settings.AI_API_KEY)

    for row in rows:
        if len(inserted) >= count:
            break
        q = None
        if use_ai:
            try:
                q = await _call_llm(row["content"], difficulty)
                if q.get("skip") or not _valid(q):
                    q = None
            except Exception:
                q = None
        if q is None and not use_ai:
            q = _fallback_question(row["content"], row["title"], difficulty, all_titles)
        if q is None or not _valid(q):
            continue

        async with pool.acquire() as con:
            qid = await con.fetchval(
                """INSERT INTO quiz_questions
                   (question, options, correct_index, explanation, difficulty, source_url, chunk_id, status, created_by)
                   VALUES($1,$2,$3,$4,$5,$6,$7,'pending','ai') RETURNING id""",
                q["question"], json.dumps(q["options"]), int(q["correct_index"]),
                q.get("explanation", ""), int(q.get("difficulty", difficulty)),
                row["url"], row["id"],
            )
        inserted.append(qid)

    return {"inserted": len(inserted), "ids": inserted, "mode": "ai" if use_ai else "fallback"}
