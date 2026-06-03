"""Import seed documents (whitepaper, verified facts) from the knowledge/ folder
into the KB as source_type='document', tagged by category. No hallucination:
quiz questions are later grounded strictly on these stored chunks.
"""
import os
import re
import glob
import zipfile
import html

from . import categories

CHUNK_SIZE = 600
KNOWLEDGE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "knowledge"
)


def _read_docx(path: str) -> str:
    z = zipfile.ZipFile(path)
    x = z.read("word/document.xml").decode("utf-8", "ignore")
    x = re.sub(r"</w:p>", "\n", x)
    txt = html.unescape(re.sub(r"<[^>]+>", "", x)).replace("�", "-")
    return re.sub(r"\n{3,}", "\n\n", txt)


def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def _chunk(text: str):
    words, chunks, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > CHUNK_SIZE:
            if cur.strip():
                chunks.append(cur.strip())
            cur = w
        else:
            cur += " " + w
    if cur.strip():
        chunks.append(cur.strip())
    return chunks


def list_files():
    if not os.path.isdir(KNOWLEDGE_DIR):
        return []
    files = []
    for ext in ("*.md", "*.txt", "*.docx"):
        files.extend(glob.glob(os.path.join(KNOWLEDGE_DIR, ext)))
    return sorted(files)


async def import_all(pool):
    """Ingest every file in knowledge/ as a 'document' KB page. Returns summary."""
    files = list_files()
    pages, total_chunks = 0, 0
    for path in files:
        name = os.path.basename(path)
        try:
            text = _read_docx(path) if path.lower().endswith(".docx") else _read_text(path)
        except Exception:
            continue
        if len(text) < 80:
            continue
        # Synthetic URL keeps the citation honest: it points at the source document.
        url = f"document://{name}"
        async with pool.acquire() as con:
            page_id = await con.fetchval(
                """INSERT INTO knowledge_pages(url, title, source_type, category, fetched_at, last_updated)
                   VALUES($1,$2,'document','infrastructure', now(), now())
                   ON CONFLICT (url) DO UPDATE SET title=$2, source_type='document', last_updated=now()
                   RETURNING id""",
                url, name,
            )
            await con.execute("DELETE FROM knowledge_chunks WHERE page_id=$1", page_id)
            for i, c in enumerate(_chunk(text)):
                cat = categories.classify(c)
                await con.execute(
                    """INSERT INTO knowledge_chunks(page_id, chunk_index, content, category, source_type)
                       VALUES($1,$2,$3,$4,'document')""",
                    page_id, i, c, cat,
                )
                total_chunks += 1
        pages += 1
    return {"files": pages, "chunks": total_chunks, "names": [os.path.basename(f) for f in files]}
