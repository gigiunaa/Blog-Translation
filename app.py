import os
from flask import Flask, request, jsonify
from werkzeug.exceptions import BadRequest
from translator import translate_html_document

app = Flask(__name__)

@app.get("/")
def health():
    return jsonify({"ok": True, "service": "blog-translator", "version": "1.0.0"})

@app.post("/translate")
def translate():
    try:
        if not request.is_json:
            raise BadRequest("Content-Type must be application/json")
        data = request.get_json(silent=False)
        if not isinstance(data, dict):
            raise BadRequest("JSON body must be an object")

        html = data.get("html")
        target_lang = data.get("target_lang")
        source_lang = data.get("source_lang")

        if not isinstance(html, str) or not html.strip():
            raise BadRequest("Field 'html' is required and must be a non-empty string")
        if not isinstance(target_lang, str) or not target_lang.strip():
            raise BadRequest("Field 'target_lang' is required (e.g., 'de', 'fr')")

        translated_html = translate_html_document(
            html_input=html,
            target_lang=target_lang.strip(),
            source_lang=(source_lang.strip() if isinstance(source_lang, str) else None),
            openai_api_key=os.getenv("OPENAI_API_KEY"),
        )
        return jsonify({"ok": True, "html": translated_html})

    except BadRequest as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception as e:
        app.logger.exception("Unhandled error in /translate")
        return jsonify({"ok": False, "error": "Internal Server Error"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
