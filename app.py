import os
import json
from urllib.parse import unquote
from flask import Flask, request, jsonify
from bs4 import BeautifulSoup, NavigableString
from openai import OpenAI

# === Flask Setup ===
app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB max

# === OpenAI Setup ===
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# === Helpers ===
def extract_text_nodes(soup):
    """Collect all visible text nodes except code/style/script/svg."""
    nodes = []

    def walk(node):
        for child in node.children:
            if isinstance(child, NavigableString):
                text = str(child).strip()
                if text and child.parent.name not in ["script", "style", "code", "pre", "svg"]:
                    nodes.append((child, text))
            elif hasattr(child, "children"):
                walk(child)

    walk(soup)
    return nodes


def translate_chunk(texts, target_lang="de"):
    """Send chunked text to GPT model for translation."""
    CHUNK_SIZE = 20
    results = []

    for i in range(0, len(texts), CHUNK_SIZE):
        chunk = texts[i:i + CHUNK_SIZE]
        data = {"items": [{"i": j, "t": t} for j, t in enumerate(chunk)]}

        prompt = (
            f"You are a professional translator. Translate all JSON text values below into {target_lang}. "
            "Preserve punctuation, whitespace, HTML entities, and order. "
            "Return only valid JSON with translated values.\n\n"
            f"{json.dumps(data, ensure_ascii=False)}"
        )

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            messages=[
                {"role": "system", "content": "Translate text only, do not alter JSON or HTML."},
                {"role": "user", "content": prompt},
            ],
        )

        output = response.choices[0].message.content.strip()

        try:
            parsed = json.loads(output)
            for item in parsed.get("items", []):
                results.append(item.get("t", ""))
        except Exception:
            # fallback: return same texts
            results.extend(chunk)

    return results


# === Route ===
@app.route("/translate", methods=["POST"])
def translate_html():
    try:
        raw_body = request.data.decode("utf-8")
        print("RAW BODY >>>", raw_body)  # debug log

        data = request.get_json(force=True)
        html = unquote(data.get("html", ""))
        target_lang = data.get("target_lang", "de")

        if not html.strip():
            return jsonify({"error": "Missing or empty 'html' field"}), 400

        soup = BeautifulSoup(html, "html.parser")
        nodes = extract_text_nodes(soup)
        texts = [t for _, t in nodes]

        translated = translate_chunk(texts, target_lang)

        for (node, _), new_text in zip(nodes, translated):
            node.replace_with(new_text)

        return jsonify({
            "html": str(soup),
            "stats": {"found": len(nodes), "translated": len(translated)},
            "lang": target_lang,
            "model": "gpt-4o-mini"
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
