"""Cliente LEXML: busca HTML, resolução URN e ingestão JSONL (naintegra-crawl)."""

from __future__ import annotations

import html as html_lib
import json
import logging
import re
import subprocess
import time
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

LEXML_BASE = "https://www.lexml.gov.br"
SEARCH_PATH = "/busca/search"
DEFAULT_UA = "Mozilla/5.0 (compatible; NaIntegraLex/1.0; +https://naintegracursos.com.br/lex)"

_DOC_HIT_RE = re.compile(
    r'<div[^>]+class="docHit"[^>]*>(.*?)</div>\s*(?=<div[^>]+class="docHit"|<!--|$)',
    re.I | re.S,
)
_FIELD_RE = re.compile(
    r'<td[^>]*>\s*<b>\s*([^<]+?)\s*</b>\s*</td>\s*<td[^>]*>(.*?)</td>',
    re.I | re.S,
)
_URN_HREF_RE = re.compile(r'href="(/urn/urn:lex:[^"]+)"', re.I)
_PLANALTO_URL_RE = re.compile(
    r'https?://(?:www\.)?(?:legislacao\.)?planalto\.gov\.br[^"\'<>\s]+',
    re.I,
)
_DATE_BR_RE = re.compile(r"(\d{2})/(\d{2})/(\d{4})")


@dataclass
class LexmlHit:
    urn: str
    title: str = ""
    ementa: str = ""
    date: date | None = None
    autoridade: str = ""
    tipo: str = ""
    url: str = ""
    planalto_urls: list[str] = field(default_factory=list)
    source: str = "lexml_search"

    def as_dict(self) -> dict[str, Any]:
        return {
            "urn": self.urn,
            "title": self.title,
            "titulo": self.title,
            "ementa": self.ementa,
            "date": self.date.isoformat() if self.date else None,
            "autoridade": self.autoridade,
            "tipo": self.tipo,
            "url": self.url or f"{LEXML_BASE}/urn/{self.urn}",
            "planalto_urls": self.planalto_urls,
            "source": self.source,
        }


def _strip_html(fragment: str) -> str:
    text = re.sub(r"<[^>]+>", " ", fragment or "")
    text = html_lib.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def parse_br_date(raw: str) -> date | None:
    m = _DATE_BR_RE.search(raw or "")
    if not m:
        return None
    dd, mm, yyyy = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        return date(yyyy, mm, dd)
    except ValueError:
        return None


def parse_search_html(html: str) -> list[LexmlHit]:
    hits: list[LexmlHit] = []
    for block in _DOC_HIT_RE.findall(html or ""):
        fields: dict[str, str] = {}
        urn = ""
        title = ""
        for label_raw, value_raw in _FIELD_RE.findall(block):
            label = _strip_html(label_raw).lower().rstrip(":")
            value = _strip_html(value_raw)
            fields[label] = value
            if label in ("urn",):
                urn = value
            if label in ("título", "titulo") and value:
                title = value
        if not urn:
            m = _URN_HREF_RE.search(block)
            if m:
                urn = m.group(1).removeprefix("/urn/")
        if not urn:
            continue
        if urn.startswith("/urn/"):
            urn = urn.removeprefix("/urn/")
        if not title:
            title = fields.get("título") or fields.get("titulo") or urn
        hit = LexmlHit(
            urn=urn,
            title=title,
            ementa=fields.get("ementa", ""),
            date=parse_br_date(fields.get("data", "")),
            autoridade=fields.get("autoridade", ""),
            tipo=fields.get("tipo documento", "") or fields.get("tipo", ""),
            url=f"{LEXML_BASE}/urn/{urn}",
            source="lexml_search",
        )
        hits.append(hit)
    return hits


def search_federal_legislation(
    keyword: str,
    *,
    client: httpx.Client | None = None,
    timeout: float = 60.0,
) -> list[LexmlHit]:
    params = {
        "keyword": keyword,
        "smode": "simple",
        "f1-tipoDocumento": "Legislação",
        "f1-autoridade": "Federal",
    }
    own = client is None
    if own:
        client = httpx.Client(timeout=timeout, follow_redirects=True, headers={"User-Agent": DEFAULT_UA})
    try:
        r = client.get(f"{LEXML_BASE}{SEARCH_PATH}", params=params)
        r.raise_for_status()
        return parse_search_html(r.text)
    finally:
        if own:
            client.close()


def resolve_urn(
    urn: str,
    *,
    client: httpx.Client | None = None,
    timeout: float = 60.0,
    fetch_planalto_links: bool = True,
) -> LexmlHit:
    urn = (urn or "").strip()
    if urn.startswith("/urn/"):
        urn = urn.removeprefix("/urn/")
    page_url = f"{LEXML_BASE}/urn/{urn}"
    own = client is None
    if own:
        client = httpx.Client(timeout=timeout, follow_redirects=True, headers={"User-Agent": DEFAULT_UA})
    try:
        r = client.get(page_url)
        r.raise_for_status()
        html = r.text
        title_m = re.search(r"<title>([^<]+)</title>", html, re.I)
        title = _strip_html(title_m.group(1)) if title_m else urn
        ementa_m = re.search(
            r"<td[^>]*>\s*<b>\s*Ementa\s*</b>\s*</td>\s*<td[^>]*>(.*?)</td>",
            html,
            re.I | re.S,
        )
        ementa = _strip_html(ementa_m.group(1)) if ementa_m else ""
        planalto_urls: list[str] = []
        if fetch_planalto_links:
            seen: set[str] = set()
            for raw in _PLANALTO_URL_RE.findall(html):
                u = html_lib.unescape(raw).replace("&amp;", "&")
                if u not in seen:
                    seen.add(u)
                    planalto_urls.append(u)
        return LexmlHit(
            urn=urn,
            title=title,
            ementa=ementa,
            url=page_url,
            planalto_urls=planalto_urls,
            source="lexml_urn",
        )
    finally:
        if own:
            client.close()


def run_external_crawl_command(command: str, *, timeout: int = 3600) -> tuple[int, str]:
    cmd = (command or "").strip()
    if not cmd:
        return 0, "comando vazio"
    try:
        proc = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=float(timeout),
        )
        tail = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
        if len(tail) > 900:
            tail = tail[-900:]
        return proc.returncode, f"exit={proc.returncode} {tail}".strip()
    except subprocess.TimeoutExpired:
        return 124, "timeout no comando shell"


def iter_crawl_jsonl(paths: list[Path]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in paths:
        if not path.is_file():
            continue
        with path.open(encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                raw = line.strip()
                if not raw or raw.startswith("#"):
                    continue
                try:
                    obj = json.loads(raw)
                except json.JSONDecodeError as exc:
                    logger.warning("JSONL inválido %s:%s: %s", path, line_no, exc)
                    continue
                if isinstance(obj, dict):
                    obj["_source_file"] = str(path)
                    obj["_source_line"] = line_no
                    records.append(obj)
    return records


def hit_from_crawl_record(record: dict[str, Any]) -> LexmlHit | None:
    doc_type = str(record.get("doc_type") or record.get("type") or "").lower()
    source = str(record.get("source") or record.get("source_system") or "").lower()
    if doc_type and doc_type not in ("legislacao", "legislação", "lei"):
        if source not in ("lexml",):
            return None
    urn = str(record.get("urn") or record.get("metadata", {}).get("urn") or "").strip()
    if urn.startswith("/urn/"):
        urn = urn.removeprefix("/urn/")
    url = str(record.get("url") or "").strip()
    title = str(record.get("titulo") or record.get("title") or urn or url)
    ementa = str(record.get("ementa") or record.get("description") or "")
    meta = record.get("metadata") or {}
    raw_date = meta.get("data") or record.get("date")
    parsed_date: date | None = None
    if isinstance(raw_date, str):
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw_date):
            parsed_date = date.fromisoformat(raw_date)
        else:
            parsed_date = parse_br_date(raw_date)
    planalto_urls = list(meta.get("planalto_urls") or [])
    if url and "planalto.gov.br" in url.lower() and url not in planalto_urls:
        planalto_urls.insert(0, url)
    if not urn and not url:
        return None
    if not urn and url:
        urn = f"planalto::{url}"
    return LexmlHit(
        urn=urn,
        title=title,
        ementa=ementa,
        date=parsed_date,
        autoridade=str(meta.get("autoridade") or "Federal"),
        tipo=str(meta.get("tipo_documento") or "Legislação"),
        url=url or (f"{LEXML_BASE}/urn/{urn}" if not urn.startswith("planalto::") else url),
        planalto_urls=planalto_urls,
        source="crawl_inbox",
    )


def discover_hits_for_law_numbers(
    law_numbers: list[str],
    *,
    since: date | None = None,
    sleep_seconds: float = 0.25,
    max_searches: int | None = None,
) -> list[LexmlHit]:
    """Busca no LEXML por número de lei e filtra por data mínima."""
    deduped: list[str] = []
    seen: set[str] = set()
    keywords: list[str] = []
    seen_kw: set[str] = set()
    for raw in law_numbers:
        num = re.sub(r"[^\d/]", "", raw or "")
        if not num or num in seen:
            continue
        seen.add(num)
        deduped.append(num)
        kw = num.split("/")[0]
        if kw not in seen_kw:
            seen_kw.add(kw)
            keywords.append(kw)
    if max_searches is not None:
        keywords = keywords[: max(0, max_searches)]

    by_urn: dict[str, LexmlHit] = {}
    with httpx.Client(timeout=60.0, follow_redirects=True, headers={"User-Agent": DEFAULT_UA}) as client:
        for num in keywords:
            keyword = num
            try:
                hits = search_federal_legislation(keyword, client=client)
            except Exception as exc:
                logger.warning("LEXML search %s falhou: %s", keyword, exc)
                continue
            for hit in hits:
                if since and hit.date and hit.date < since:
                    continue
                prev = by_urn.get(hit.urn)
                if prev is None or (hit.date and (not prev.date or hit.date > prev.date)):
                    by_urn[hit.urn] = hit
            if sleep_seconds > 0:
                time.sleep(sleep_seconds)
    return list(by_urn.values())


def write_crawl_inbox(
    inbox: Path,
    records: list[dict[str, Any]],
    *,
    batch_name: str | None = None,
) -> Path:
    inbox.mkdir(parents=True, exist_ok=True)
    stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    fname = batch_name or f"lexml_weekly_{stamp}.jsonl"
    out = inbox / fname
    with out.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return out


def merge_hits(*groups: list[LexmlHit]) -> list[LexmlHit]:
    by_urn: dict[str, LexmlHit] = {}
    for group in groups:
        for hit in group:
            prev = by_urn.get(hit.urn)
            if prev is None:
                by_urn[hit.urn] = hit
                continue
            if hit.ementa and not prev.ementa:
                prev.ementa = hit.ementa
            if hit.date and (not prev.date or hit.date > prev.date):
                prev.date = hit.date
            if hit.planalto_urls:
                for u in hit.planalto_urls:
                    if u not in prev.planalto_urls:
                        prev.planalto_urls.append(u)
    return list(by_urn.values())
