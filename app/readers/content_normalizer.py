"""Normalize extracted text and HTML content."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup


def normalize_plain_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def strip_scripts_and_normalize_html(html: str, base_href: str | None = None) -> str:
    soup = BeautifulSoup(html or "", "lxml")
    for tag in soup(["script", "iframe", "object", "embed"]):
        tag.decompose()
    # Remove event handlers
    for tag in soup.find_all(True):
        attrs = dict(tag.attrs)
        for attr in attrs:
            if str(attr).lower().startswith("on"):
                del tag.attrs[attr]
    body = soup.body or soup
    content = "".join(str(child) for child in body.children)
    if base_href:
        return f'<div data-base="{base_href}">{content}</div>'
    return content
