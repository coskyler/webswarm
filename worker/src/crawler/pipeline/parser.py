from lxml import html
from lxml.html import HtmlElement
from lxml.etree import ParserError
from crawler.pipeline.types import FetchResult, ParseResult
import re
from urllib.parse import urljoin, urlparse, urlunparse, urlsplit, urlunsplit
from publicsuffix2 import get_sld


_INVISIBLE_TAGS = {
    "script",
    "style",
    "noscript",
    "template",
    "meta",
    "link",
    "head",
    "base",
    "iframe",
    "frame",
    "frameset",
    "object",
    "embed",
    "param",
    "source",
    "track",
    "audio",
    "video",
    "canvas",
    "svg",
    "path",
    "circle",
    "rect",
    "polygon",
    "g",
    "defs",
    "mask",
    "pattern",
    "picture",
    "portal",
    "slot",
    "-text",
    "#comment",
}
_INLINE_TAGS = {"span", "b", "i", "em", "strong", "a"}
_NAV_LINK_ATTRS = {"href", "action", "formaction", "data-href", "data-url"}

_URL_RE = re.compile(r'https?://[^\s"\'<>]+|/[^\s"\'<>]+')
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
import re

_PHONE_RE = re.compile(
    r"(?<!\d)"
    r"(?!\d{1,2}[\/\-.]\d{1,2}(?:[\/\-.]\d{2,4})\b)"   # reject dd/mm(/yyyy), dd-mm-yy, etc.
    r"(?:"
      r"(?:\+|00)\s*\d{1,3}"                           # +CC or 00CC
      r"(?:[ \-.\u00A0()]?\d){7,14}"                   # 8–17 digits total-ish (incl CC), must be digit-heavy
      r"|"
      r"\(?\d{1,4}\)?[ \-.\u00A0]"                     # national: requires a separator after area/group
      r"(?:\d{2,4}[ \-.\u00A0]?){2,6}\d{2,4}"          # 8–16 digits total, grouped
    r")"
    r"(?!\d)"
)

_SOCIAL_ORIGINS = {
    "facebook",
    "instagram",
    "tripadvisor",
    "youtube",
    "tiktok",
    "x"
}

def _chop_link(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))

def _add_link(link: str, links: dict[str, int]) -> int:
    link = _chop_link(link)
    
    if link in links:
        return links[link]

    links[link] = len(links)
    return len(links) - 1


def _extract_attrib_info(
    node: HtmlElement, url: str, links: dict[str, int], emails: dict[str, None]
) -> list[str]:
    found = set()

    # attributes
    for attr, val in node.attrib.items():
        attr = attr.lower()

        if not val:
            continue

        if not attr in _NAV_LINK_ATTRS:
            continue

        found.update(_URL_RE.findall(val))

        # also extract emails
        _extract_emails(val, emails)

    normalized = [
        urljoin(url, u) if url else u
        for u in found
        if not u.startswith(("javascript:", "mailto:", "tel:", "#"))
    ]

    return [f"[L{_add_link(link, links)}]" for link in normalized if link and len(link) < 256]


def _extract_emails(text: str, emails: dict[str, None]) -> None:
    if not text:
        return []
    found = _EMAIL_RE.findall(text)
    for email in found:
        emails[email] = None

def _extract_phones(text: str, phones: dict[str, None]) -> None:
    if not text:
        return
    found = _PHONE_RE.findall(text)
    for phone in found:
        digits = re.sub(r"\D+", "", phone)
        phones[digits] = None


def _walk(node, url, lines, links, emails, phones, indent=0, buf=None, bufIndent=0, top=True):
    if buf is None:
        buf = []

    if not isinstance(node.tag, str) or node.tag in _INVISIBLE_TAGS:
        return

    if node.text and node.text.strip():
        buf.append(node.text)
        _extract_emails(node.text, emails)
        _extract_phones(node.text, phones)

    for child in node:
        is_inline = child.tag in _INLINE_TAGS

        if is_inline:
            _walk(child, url, lines, links, emails, phones, indent, buf, bufIndent, False)
        else:
            if buf:
                lines.append("  " * bufIndent + "".join(buf).strip())
                buf.clear()
            _walk(child, url, lines, links, emails, phones, indent + 1, buf, indent + 1, True)

        if child.tail and child.tail.strip():
            buf.append(child.tail)
            _extract_emails(child.tail, emails)
            _extract_phones(node.text, phones)

        attrib_urls = _extract_attrib_info(child, url, links, emails)
        if attrib_urls:
            buf.append(", ".join(attrib_urls))

    if top and buf:
        lines.append("  " * bufIndent + "".join(buf).strip())
        buf.clear()


def _remove_whitespace(lines: list[str]) -> None:
    leadingSpaces = float("inf")
    for s in lines:
        spaces = len(s) - len(s.lstrip(" "))

        leadingSpaces = min(leadingSpaces, spaces)

    for i in range(len(lines)):
        lines[i] = lines[i][leadingSpaces:]


def parse(fetched: FetchResult, trace) -> ParseResult:
    root: HtmlElement | None = None

    try:
        root = html.fromstring(fetched.text)
    except ParserError:
        trace.add("parse", ok=False, message="Parse error")
        return ParseResult(ok=False, message="Parse error")

    lines = []
    links = {}
    emails = {}
    phones = {}

    _walk(root, fetched.url, lines, links, emails, phones)

    if not lines:
        trace.add("parse", ok=False, message="Parse error")
        return ParseResult(ok=False, message="Parse error")

    _remove_whitespace(lines)

    parsed_text = ("\n".join(lines))[:12000].rstrip()
    hyperlink_key_text = "\n".join(f"[L{v}] {k}" for k, v in links.items())

    # create socials dict from links
    socials = {}

    for link in links:
        p = urlparse(link)
        host = p.netloc.lower().split(":")[0]
        sld = get_sld(host)

        if not sld:
            continue

        sld_name = sld.split(".", 1)[0]

        if sld_name == "twitter":
            host = host[: -len("twitter.com")] + "x.com"
            p = p._replace(netloc=host)
            sld_name = "x"
        elif sld_name == "youtu":
            sld_name = "youtube"

        new_link = urlunparse(p)

        if sld_name in _SOCIAL_ORIGINS:
            socials.setdefault(sld_name, new_link)

    # print(f"\n\nparsed chars: {len(parsed_text)}\n\n{parsed_text}\n\nhypertext: {len(hyperlink_key_text)}\n\n{hyperlink_key_text}")

    trace.add("parse", ok=True)

    return ParseResult(
        ok=True,
        parsed_text=parsed_text,
        hyperlink_key_text=hyperlink_key_text,
        emails=list(emails),
        phones=list(phones),
        socials=socials
    )

    
