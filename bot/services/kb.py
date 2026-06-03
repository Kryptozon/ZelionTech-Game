"""ZelionTech knowledge base: crawl zeliontech.com, extract text, store chunks."""
import asyncio
import re
from urllib.parse import urljoin, urlparse

import aiohttp
from bs4 import BeautifulSoup

from ..config import settings
from . import categories

CHUNK_SIZE = 600          # ~chars per chunk
HEADERS = {"User-Agent": "ZelionReactorBot/1.0 (+https://zeliontech.com)"}


def _same_domain(url: str, root: str) -> bool:
    return urlparse(url).netloc.replace("www.", "") == urlparse(root).netloc.replace("www.", "")


def _clean_text(html: str):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "svg"]):
        tag.decompose()
    title = (soup.title.string.strip() if soup.title and soup.title.string else "")
    text = re.sub(r"\s+", " ", soup.get_text(" ")).strip()
    links = [a.get("href") for a in soup.find_all("a", href=True)]
    return title, text, links


def _chunk(text: str):
    words, chunks, cur = text.split(" "), [], ""
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


async def _fetch(session, url):
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as r:
            if r.status == 200 and "text/html" in r.headers.get("content-type", ""):
                return await r.text()
    except Exception:
        return None
    return None


async def refresh(pool, max_pages: int | None = None):
    """Crawl the site (BFS, same-domain), store pages + chunks. Returns a summary dict."""
    root = settings.WEBSITE_URL.rstrip("/")
    limit = max_pages or settings.KB_MAX_PAGES
    seen, queue, saved_pages, saved_chunks = set(), [root], 0, 0

    async with aiohttp.ClientSession(headers=HEADERS) as session:
        while queue and len(seen) < limit:
            url = queue.pop(0).split("#")[0].rstrip("/")
            if url in seen:
                continue
            seen.add(url)
            html = await _fetch(session, url)
            if not html:
                continue
            title, text, links = _clean_text(html)
            if len(text) < 80:
                continue

            async with pool.acquire() as con:
                page_id = await con.fetchval(
                    """INSERT INTO knowledge_pages(url, title, source_type, fetched_at, last_updated)
                       VALUES($1,$2,'website', now(), now())
                       ON CONFLICT (url) DO UPDATE SET title=$2, source_type='website', last_updated=now()
                       RETURNING id""",
                    url, title or url,
                )
                await con.execute("DELETE FROM knowledge_chunks WHERE page_id=$1", page_id)
                chunks = _chunk(text)
                for i, c in enumerate(chunks):
                    await con.execute(
                        """INSERT INTO knowledge_chunks(page_id, chunk_index, content, category, source_type)
                           VALUES($1,$2,$3,$4,'website')""",
                        page_id, i, c, categories.classify(c),
                    )
                saved_chunks += len(chunks)
            saved_pages += 1

            for href in links:
                nxt = urljoin(url + "/", href).split("#")[0].rstrip("/")
                if _same_domain(nxt, root) and nxt not in seen and nxt not in queue:
                    queue.append(nxt)
            await asyncio.sleep(0.3)  # be polite

    return {"pages": saved_pages, "chunks": saved_chunks, "visited": len(seen)}


async def stats(pool):
    async with pool.acquire() as con:
        pages = await con.fetchval("SELECT count(*) FROM knowledge_pages")
        chunks = await con.fetchval("SELECT count(*) FROM knowledge_chunks")
        last = await con.fetchval("SELECT max(last_updated) FROM knowledge_pages")
    return {"pages": pages, "chunks": chunks, "last_updated": last}


async def sample_chunks(pool, n=8, category=None):
    """Sample substantive chunks from BOTH document and website sources."""
    async with pool.acquire() as con:
        if category:
            return await con.fetch(
                """SELECT c.id, c.content, c.category, c.source_type, p.url, p.title
                   FROM knowledge_chunks c JOIN knowledge_pages p ON p.id=c.page_id
                   WHERE length(c.content) > 120 AND c.category=$2
                   ORDER BY random() LIMIT $1""",
                n, category,
            )
        return await con.fetch(
            """SELECT c.id, c.content, c.category, c.source_type, p.url, p.title
               FROM knowledge_chunks c JOIN knowledge_pages p ON p.id=c.page_id
               WHERE length(c.content) > 120
               ORDER BY random() LIMIT $1""",
            n,
        )


async def stats_by_category(pool):
    async with pool.acquire() as con:
        return await con.fetch(
            "SELECT category, source_type, count(*) c FROM knowledge_chunks "
            "GROUP BY category, source_type ORDER BY c DESC"
        )
