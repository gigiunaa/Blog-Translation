import os, re, json
from typing import List, Tuple, Optional, Dict
from bs4 import BeautifulSoup, NavigableString, Comment
from openai import OpenAI

MAX_ITEMS_PER_REQUEST = 120

def _collect_translatable_nodes(soup: BeautifulSoup):
    items = []
    idx = 0
    for node in soup.descendants:
        if isinstance(node, Comment):
            continue
        if isinstance(node, NavigableString):
            parent = node.parent
            if parent and parent.name in {"script","style"}:
                continue
            text = str(node)
            if text and not text.isspace():
                key = f"[[[T{idx}]]]"
                node.replace_with(NavigableString(key))
                items.append((key, "text"))
                idx += 1
    attr_names = ["alt","title","placeholder","aria-label"]
    for tag in soup.find_all(True):
        for a in attr_names:
            if tag.has_attr(a):
                val = tag.get(a)
                if isinstance(val, str) and val.strip():
                    key = f"[[[T{idx}]]]"
                    tag[a] = key
                    items.append((key, f"attr:{a}"))
                    idx += 1
    return items

def _batched(seq, n):
    b=[]
    for x in seq:
        b.append(x)
        if len(b)>=n:
            yield b
            b=[]
    if b:
        yield b

def _call_openai(client: OpenAI, items: List[str], target_lang: str, source_lang: Optional[str]):
    system = (
        "You are a professional translator. Translate each string to the target language. "
        "Keep placeholders like [[[T0]]], HTML entities, numbers and punctuation unchanged. "
        "Return ONLY a JSON array of strings in the same order."
    )
    payload = {"target_lang": target_lang, "source_lang": source_lang or "auto", "items": items}
    resp = client.responses.create(
        model="gpt-4o-mini",
        input=[{"role":"system","content":system},{"role":"user","content":json.dumps(payload)}],
        temperature=0.2,
    )
    out = resp.output_text.strip()
    out = re.sub(r"^```(?:json)?\s*|\s*```$", "", out)
    try:
        data = json.loads(out)
        if not isinstance(data, list) or len(data)!=len(items):
            return items
        return [str(x) for x in data]
    except Exception:
        return items

def translate_html_document(html_input: str, target_lang: str, source_lang: Optional[str], openai_api_key: Optional[str]=None) -> str:
    if not openai_api_key:
        openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    client = OpenAI(api_key=openai_api_key)

    soup = BeautifulSoup(html_input, "html.parser")
    collected = _collect_translatable_nodes(soup)

    # Originals in the same order
    soup2 = BeautifulSoup(html_input, "html.parser")
    originals = []
    for node in soup2.descendants:
        if isinstance(node, Comment):
            continue
        if isinstance(node, NavigableString):
            parent = node.parent
            if parent and parent.name in {"script","style"}:
                continue
            text = str(node)
            if text and not text.isspace():
                originals.append(text)
    attr_names = ["alt","title","placeholder","aria-label"]
    for tag in soup2.find_all(True):
        for a in attr_names:
            if tag.has_attr(a):
                val = tag.get(a)
                if isinstance(val, str) and val.strip():
                    originals.append(val)

    if len(originals) != len(collected):
        return html_input

    translations = []
    for batch in _batched(originals, MAX_ITEMS_PER_REQUEST):
        translations.extend(_call_openai(client, batch, target_lang, source_lang))

    mapping = {}
    for (key,_), t in zip(collected, translations):
        mapping[key]=t

    html_with_keys = str(soup)
    final_html = re.sub(r"\[\[\[T\d+\]\]\]", lambda m: mapping.get(m.group(0), m.group(0)), html_with_keys)
    return final_html
