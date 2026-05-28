"""Verificação automática de correspondência entre título, URL, tags e texto de normas."""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from .legal_text import pick_display_title, pick_verbatim_body

# ---------------------------------------------------------------------------
# Identidade normativa (tipo + número)
# ---------------------------------------------------------------------------

_ACT_ALIASES: dict[str, str] = {
    "lei": "lei",
    "leis": "lei",
    "lei complementar": "lei_complementar",
    "lc": "lei_complementar",
    "decreto": "decreto",
    "decreto-lei": "decreto_lei",
    "decreto lei": "decreto_lei",
    "medida provisoria": "medida_provisoria",
    "medida provisória": "medida_provisoria",
    "mpv": "medida_provisoria",
    "emenda constitucional": "emenda_constitucional",
}

_HEADER_RE = re.compile(
    r"(?is)"
    r"(?:^|\n)\s*"
    r"(?P<act>lei(?:\s+complementar)?|decreto(?:-lei)?|medida\s+provis[oó]ria|emenda\s+constitucional)"
    r"\s+n[º°\.o\s]*"
    r"(?P<num>[\d][\d\.\s,]*(?:-\d+)?)",
    re.MULTILINE,
)

_LEXML_TITLE_RE = re.compile(
    r"(?is)Título\s+(.+?)(?:\n\nData|\n\nApelido|\n\nEmenta|\Z)",
)
_LEXML_EMENTA_RE = re.compile(
    r"(?is)Ementa\s+(.+?)(?:\n\n(?:Nome Uniforme|Mais detalhes|Publicação|Projeto)|\Z)",
)
_AGU_TAG_RE = re.compile(r"^agu:(?P<slug>[a-z0-9_]+)$", re.I)
_PLANALTO_PATH_RE = re.compile(
    r"(?i)/(?:decreto|decreto-lei|mpv|mp)/(?:[a-z]*)?(\d[\d]+)",
)
_PLANALTO_LEI_RE = re.compile(r"(?i)/leis(?:/\d{4})?/l([\d\.]+?)(?:consol|comp|\.htm)",)
_PLANALTO_LEI_SIMPLE_RE = re.compile(r"(?i)/leis/l(\d{4,5})(?:\.htm|comp)",)
_LEXML_URN_RE = re.compile(
    r"(?i)urn:lex:br:(?:federal|estadual)?:(?P<act>lei|decreto|medida\.provisoria|decreto-lei)"
    r"(?::\d{4}-\d{2}-\d{2})?;(?P<num>[\d]+(?:-\d+)?)",
)


@dataclass(frozen=True)
class NormIdentity:
    act_type: str
    number_digits: str
    number_suffix: str | None = None

    def key(self) -> tuple[str, str, str | None]:
        return (self.act_type, self.number_digits, self.number_suffix)

    def label(self) -> str:
        if self.number_suffix:
            base = f"{self.number_digits[:-len(self.number_suffix)]}.{self.number_suffix}"
            if self.number_digits.endswith(self.number_suffix.replace("-", "")):
                base = self.number_digits
            parts = self._format_number()
            return f"{self._act_label()} nº {parts}"
        return f"{self._act_label()} nº {self._format_number()}"

    def _act_label(self) -> str:
        return {
            "lei": "Lei",
            "lei_complementar": "Lei Complementar",
            "decreto": "Decreto",
            "decreto_lei": "Decreto-Lei",
            "medida_provisoria": "Medida Provisória",
            "emenda_constitucional": "Emenda Constitucional",
            "constituicao": "Constituição Federal",
        }.get(self.act_type, self.act_type)

    def _format_number(self) -> str:
        d = self.number_digits
        if self.act_type == "medida_provisoria" and self.number_suffix:
            main = d[: -len(self.number_suffix)] if d.endswith(self.number_suffix.replace("-", "")) else d
            if len(main) >= 4:
                return f"{main[:-2]}.{main[-2:]}-{self.number_suffix}"
            return f"{d}-{self.number_suffix}"
        if len(d) > 4 and d.isdigit():
            return f"{d[:-3]}.{d[-3:]}" if len(d) >= 5 else d
        if len(d) == 4:
            return f"{d[0]}.{d[1:]}"
        return d


def _strip_accents(s: str) -> str:
    nfd = unicodedata.normalize("NFD", s)
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn")


def _normalize_act(act_raw: str) -> str:
    key = _strip_accents(act_raw.lower().strip())
    key = re.sub(r"\s+", " ", key)
    return _ACT_ALIASES.get(key, key.replace(" ", "_"))


def _parse_number_token(raw: str) -> tuple[str, str | None]:
    cleaned = re.sub(r"[\s\.]", "", raw.strip())
    m = re.match(r"^(\d+)(?:-(\d+))?$", cleaned)
    if not m:
        digits = re.sub(r"\D", "", cleaned)
        return digits, None
    return m.group(1), m.group(2)


def identity_from_title(title: str) -> NormIdentity | None:
    if not title or not str(title).strip():
        return None
    t = _strip_accents(str(title).strip())
    if re.search(r"constituicao\s+federal", t, re.I):
        return NormIdentity(act_type="constituicao", number_digits="1988")
    m = re.match(
        r"^(?P<act>lei complementar|lei|decreto-lei|decreto|medida provisoria|mpv|emenda constitucional)"
        r"\s+(?P<num>[\d][\d\.]*(?:-\d+)?)(?:/\d{4})?(?:\s+—|\s+-|\s*$)",
        t,
        re.I,
    )
    if not m:
        m2 = re.match(r"^(?P<act>lei|decreto)\s+(?P<num>\d+)$", t, re.I)
        if not m2:
            return None
        m = m2
    act = _normalize_act(m.group("act"))
    digits, suffix = _parse_number_token(m.group("num"))
    if not digits:
        return None
    return NormIdentity(act_type=act, number_digits=digits, number_suffix=suffix)


def identity_from_url(url: str) -> NormIdentity | None:
    if not url:
        return None
    u = str(url).strip()
    m = _LEXML_URN_RE.search(u)
    if m:
        act = _normalize_act(m.group("act").replace(".", " "))
        digits, suffix = _parse_number_token(m.group("num"))
        return NormIdentity(act_type=act, number_digits=digits, number_suffix=suffix)
    if "constituicao" in u.lower():
        return NormIdentity(act_type="constituicao", number_digits="1988")
    m = _PLANALTO_LEI_RE.search(u) or _PLANALTO_LEI_SIMPLE_RE.search(u)
    if m:
        digits = re.sub(r"\D", "", m.group(1))
        return NormIdentity(act_type="lei", number_digits=digits)
    m = _PLANALTO_PATH_RE.search(u)
    if m:
        digits = re.sub(r"\D", "", m.group(1))
        act = "decreto"
        if "decreto-lei" in u.lower() or "/del" in u.lower():
            act = "decreto_lei"
        if "/mpv" in u.lower() or "/mp" in u.lower():
            act = "medida_provisoria"
        return NormIdentity(act_type=act, number_digits=digits)
    m = re.search(r"(?i)/l(\d{4,5})(?:\.htm|/)", u)
    if m:
        return NormIdentity(act_type="lei", number_digits=m.group(1))
    return None


def identity_from_body(text: str, *, max_chars: int = 4000) -> NormIdentity | None:
    if not text:
        return None
    sample = text[:max_chars]
    m = _HEADER_RE.search(sample)
    if not m:
        return None
    act = _normalize_act(m.group("act"))
    raw_num = re.sub(r"\s+", "", m.group("num"))
    digits, suffix = _parse_number_token(raw_num)
    if not digits:
        return None
    return NormIdentity(act_type=act, number_digits=digits, number_suffix=suffix)


def identity_from_agu_tag(tags: list[Any]) -> NormIdentity | None:
    for t in tags or []:
        if not isinstance(t, str):
            continue
        m = _AGU_TAG_RE.match(t.strip())
        if not m:
            continue
        slug = m.group("slug")
        if slug.startswith("dec_"):
            return NormIdentity("decreto", slug[4:])
        if slug.startswith("lei_"):
            return NormIdentity("lei", slug[4:])
        if slug.startswith("lc_"):
            return NormIdentity("lei_complementar", slug[3:])
        if slug.startswith("mpv_"):
            parts = slug[4:].split("_", 1)
            if len(parts) == 2:
                return NormIdentity("medida_provisoria", parts[0], parts[1])
            return NormIdentity("medida_provisoria", slug[4:])
    return None


def parse_lexml_metadata(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    if not text:
        return out
    m = _LEXML_TITLE_RE.search(text)
    if m:
        out["titulo_lexml"] = re.sub(r"\s+", " ", m.group(1).strip())
    m = _LEXML_EMENTA_RE.search(text)
    if m:
        out["ementa"] = re.sub(r"\s+", " ", m.group(1).strip())
    return out


def _normalize_ementa(s: str) -> str:
    s = _strip_accents(s.lower())
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def ementa_matches_body(ementa: str, body: str, *, min_prefix: int = 40) -> bool:
    if not ementa or not body:
        return True
    e = _normalize_ementa(ementa)
    b = _normalize_ementa(body)
    if len(e) < 20:
        return e in b
    prefix = e[:min_prefix]
    return prefix in b


def _same_identity(a: NormIdentity | None, b: NormIdentity | None) -> bool:
    if a is None or b is None:
        return True
    return a.key() == b.key()


def _compatible_identity(a: NormIdentity | None, b: NormIdentity | None) -> bool:
    """Aceita equivalências de formatação (ex.: 14230 vs 14.230)."""
    if a is None or b is None:
        return True
    if a.act_type != b.act_type:
        return False
    if a.number_suffix != b.number_suffix:
        return False
    return a.number_digits == b.number_digits


# ---------------------------------------------------------------------------
# Resultado da verificação
# ---------------------------------------------------------------------------

@dataclass
class CorrespondenceIssue:
    code: str
    severity: str
    message: str
    field: str | None = None


@dataclass
class CorrespondenceReport:
    url: str
    title: str
    ok: bool
    skipped: bool = False
    skip_reason: str | None = None
    identities: dict[str, str] = field(default_factory=dict)
    issues: list[CorrespondenceIssue] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "ok": self.ok,
            "skipped": self.skipped,
            "skip_reason": self.skip_reason,
            "identities": self.identities,
            "issues": [
                {"code": i.code, "severity": i.severity, "message": i.message, "field": i.field}
                for i in self.issues
            ],
        }


def verify_record(record: dict[str, Any]) -> CorrespondenceReport:
    url = str(record.get("url") or "").strip()
    title = str(pick_display_title(record) or record.get("title") or "").strip()
    body = str(pick_verbatim_body(record) or record.get("content") or "")
    summary = str(record.get("summary") or "")
    tags = record.get("tags") or []
    legal_act_type = str(record.get("legal_act_type") or "").strip().lower()

    report = CorrespondenceReport(url=url, title=title, ok=True)

    encoding_corrupt = "\ufffd" in body or "\ufffd" in summary
    if encoding_corrupt:
        report.skipped = True
        report.skip_reason = "encoding_corrupt"
        report.issues.append(
            CorrespondenceIssue(
                code="ENCODING_CORRUPT",
                severity="warn",
                message="Texto com caractere de substituição (U+FFFD); verificação texto/ementa limitada.",
                field="content",
            )
        )

    id_title = identity_from_title(title)
    id_url = identity_from_url(url)
    id_body = None if encoding_corrupt else (identity_from_body(body) or identity_from_body(summary))
    id_tag = identity_from_agu_tag(tags)
    lexml = parse_lexml_metadata(body) or parse_lexml_metadata(summary)
    id_lexml_title = identity_from_title(lexml.get("titulo_lexml", "")) if lexml.get("titulo_lexml") else None

    for label, ident in (
        ("title", id_title),
        ("url", id_url),
        ("body", id_body),
        ("tag", id_tag),
        ("lexml_titulo", id_lexml_title),
    ):
        if ident:
            report.identities[label] = ident.label()

    pairs = [
        ("NUMBER_TITLE_URL", id_title, id_url, "title", "url"),
        ("NUMBER_TITLE_BODY", id_title, id_body, "title", "content"),
        ("NUMBER_URL_BODY", id_url, id_body, "url", "content"),
        ("NUMBER_TAG_URL", id_tag, id_url, "tag", "url"),
        ("NUMBER_LEXML_TITLE", id_title, id_lexml_title, "title", "lexml_titulo"),
    ]
    for code, a, b, fa, fb in pairs:
        if not _compatible_identity(a, b):
            report.issues.append(
                CorrespondenceIssue(
                    code=code,
                    severity="error",
                    message=(
                        f"Incompatibilidade entre {fa} ({a.label() if a else '?'}) "
                        f"e {fb} ({b.label() if b else '?'})."
                    ),
                    field=fb,
                )
            )
            report.ok = False

    if not encoding_corrupt and legal_act_type and id_body:
        expected = legal_act_type.replace("-", "_")
        if id_body.act_type != expected and not (
            expected == "decreto" and id_body.act_type == "decreto_lei"
        ):
            report.issues.append(
                CorrespondenceIssue(
                    code="ACT_TYPE_METADATA_BODY",
                    severity="error",
                    message=(
                        f"legal_act_type={legal_act_type!r} não corresponde ao cabeçalho "
                        f"do texto ({id_body.act_type!r})."
                    ),
                    field="legal_act_type",
                )
            )
            report.ok = False

    ementa = lexml.get("ementa") or ""
    if not ementa and summary and "planalto" in url.lower():
        sm = re.search(r"(?is)(?:Aprova|Regulamenta|Dispõe|Altera|Revoga|Institui)(.+?)(?:\n\n|Art\.)", summary)
        if sm:
            ementa = re.sub(r"\s+", " ", sm.group(0).strip())[:240]

    if not encoding_corrupt and ementa and body and not ementa_matches_body(ementa, body):
        report.issues.append(
            CorrespondenceIssue(
                code="EMENTA_BODY_MISMATCH",
                severity="error",
                message="Ementa/descrição não encontrada no início do texto integral.",
                field="content",
            )
        )
        report.ok = False

    if lexml.get("titulo_lexml") and title:
        if id_lexml_title and id_title and not _compatible_identity(id_lexml_title, id_title):
            report.issues.append(
                CorrespondenceIssue(
                    code="EMENTA_TITLE_MISMATCH",
                    severity="error",
                    message=(
                        f"Título curto ({title!r}) diverge do campo Título LexML "
                        f"({lexml['titulo_lexml']!r})."
                    ),
                    field="title",
                )
            )
            report.ok = False

    if not id_title and not id_url:
        report.issues.append(
            CorrespondenceIssue(
                code="IDENTITY_UNKNOWN",
                severity="warn",
                message="Não foi possível extrair tipo/número do título ou da URL.",
            )
        )
        report.ok = False

    if encoding_corrupt and not any(i.severity == "error" for i in report.issues):
        report.ok = True

    return report


def iter_jsonl_records(input_dir: Path) -> Iterator[tuple[dict[str, Any], str]]:
    for fp in sorted(input_dir.glob("*.jsonl")):
        with fp.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, dict):
                    yield obj, fp.name


def load_catalog_records(catalog_path: Path) -> list[dict[str, Any]]:
    if not catalog_path.is_file():
        return []
    data = json.loads(catalog_path.read_text(encoding="utf-8"))
    docs = data.get("documents") or []
    out: list[dict[str, Any]] = []
    for doc in docs:
        if not isinstance(doc, dict):
            continue
        out.append(
            {
                "url": doc.get("url") or doc.get("doc_key"),
                "title": doc.get("title"),
                "summary": doc.get("resumo"),
                "content": "",
                "legal_act_type": (doc.get("meta") or {}).get("legal_act_type"),
                "tags": [],
                "_source": "catalog",
            }
        )
    return out


def verify_all(
    *,
    input_dir: Path,
    catalog_path: Path | None = None,
    dedupe_by_url: bool = True,
) -> list[CorrespondenceReport]:
    by_url: dict[str, dict[str, Any]] = {}
    for rec, _ in iter_jsonl_records(input_dir):
        key = str(rec.get("url") or rec.get("id") or "")
        if key:
            by_url[key] = rec

    if catalog_path:
        for rec in load_catalog_records(catalog_path):
            key = str(rec.get("url") or "")
            if key and key not in by_url:
                by_url[key] = rec

    reports: list[CorrespondenceReport] = []
    seen: set[str] = set()
    for url, rec in sorted(by_url.items(), key=lambda x: x[1].get("title") or x[0]):
        if dedupe_by_url and url in seen:
            continue
        seen.add(url)
        reports.append(verify_record(rec))
    return reports


def summarize_reports(reports: list[CorrespondenceReport]) -> dict[str, Any]:
    skipped = sum(1 for r in reports if r.skipped)
    ok = sum(1 for r in reports if r.ok)
    errors = sum(1 for r in reports if not r.ok and not r.skipped)
    encoding_only = sum(
        1
        for r in reports
        if r.skipped and r.ok is False and all(i.code == "ENCODING_CORRUPT" for i in r.issues)
    )
    by_code: dict[str, int] = {}
    for r in reports:
        for i in r.issues:
            by_code[i.code] = by_code.get(i.code, 0) + 1
    return {
        "total": len(reports),
        "ok": ok,
        "failed": errors,
        "skipped_encoding": skipped,
        "encoding_only_fail": encoding_only,
        "issues_by_code": dict(sorted(by_code.items())),
    }
