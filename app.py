import os
import base64
import openai
from flask import Flask, request, jsonify
from flask_cors import CORS

# ===================== CONFIG =====================
app = Flask(__name__)
CORS(app)

# OpenAI API Key
openai.api_key = os.getenv("OPENAI_API_KEY", "PUT_YOUR_KEY_HERE")

# ===================== ROUTES =====================
@app.route("/", methods=["GET"])
def home():
    return jsonify({"ok": True, "message": "Blog translation API is running ✅"})

@app.route("/translate", methods=["POST"])
def translate_html():
    try:
        data = request.get_json(force=True)
        html_b64 = data.get("html_b64")
        target_lang = data.get("target_lang", "de")

        if not html_b64:
            return jsonify({"ok": False, "error": "Missing html_b64"}), 400

        # Decode HTML from Base64
        html = base64.b64decode(html_b64).decode("utf-8")

        # ===================== TRANSLATION =====================
        prompt = f"""
        Translate the following HTML document to {target_lang}.
        Keep all HTML tags, attributes, and structure exactly the same.
        Translate only visible text content (no code, no URLs, no numbers).
        HTML to translate:
        {html}
        """

        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )

        translated_html = response.choices[0].message["content"]

        # Return success
        return jsonify({
            "ok": True,
            "target_lang": target_lang,
            "translated_html": translated_html
        })

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ===================== START SERVER =====================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
