import os
import json
import re
from flask import Flask, request, jsonify
from bs4 import BeautifulSoup, NavigableString
from openai import OpenAI

app = Flask(__name__)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def extract_text_nodes(soup):
    texts = []

    def traverse(node):
        for child in node.children:
            if isinstance(child, NavigableString):
                text = str(child).strip()
                if text and not isinstance(child, (BeautifulSoup,)):
                    if child.parent.name not in [
                        "script", "style", "code", "pre", "svg"
                    ]:
                        texts.append((child, text))
            elif child.name:
                traverse(child)

    traverse(soup)
    return texts

def translate_texts(texts, target_lang="de"):
    results = []
    CHUNK_SIZE = 20

    for i in range(0, len(texts), CHUNK_SIZE):
        chunk = texts[i:i+CHUNK_SIZE]
        items = [{"i": j, "t": t} for j, (_, t) in enumerate(chunk)]
        prompt = (
            f"You are a professional translator. Translate the following JSON text values into {target_lang}. "
            "Keep punctuation, line breaks, HTML entities, and order exactly. "
            "Return only JSON with translated values.\n\n"
            f"{json.dumps({'items': items}, ensure_ascii=False)}"
        )

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            messages=[
                {"role": "system", "content": "You translate text only, not code or HTML."},
                {"role": "user", "content": prompt}
            ],
        )

        data = response.choices[0].message.content.strip()

        try:
            parsed = json.loads(re.search(r"\{.*\}", data, re.DOTALL).group(0))
            for idx, item in enumerate(parsed.get("items", [])):
                results.append(item["t"])
        except Exception:
            for _, t in chunk:
                results.append(t)

    return results

@app.route("/translate", methods=["POST"])
def translate_html():
    try:
        data = request.get_json(force=True)
        html = data.get("html")
        target_lang = data.get("target_lang", "de")

        if not html:
            return jsonify({"error": "Missing 'html' field"}), 400

        soup = BeautifulSoup(html, "html.parser")
        nodes = extract_text_nodes(soup)

        translated_texts = translate_texts(nodes, target_lang)

        for (node, _), new_text in zip(nodes, translated_texts):
            node.replace_with(new_text)

        output_html = str(soup)
        stats = {
            "found": len(nodes),
            "translated": len(translated_texts),
            "model": "gpt-4o-mini",
        }

        return jsonify({"html": output_html, "stats": stats})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))