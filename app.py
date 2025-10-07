from flask import Flask, request, jsonify, Response
from openai import OpenAI
import os
import re
import time
import gc
from bs4 import BeautifulSoup
import traceback

app = Flask(__name__)

# Initialize OpenAI Client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Warn if no API key
if not os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") == "your-key-here":
    print("⚠️ WARNING: OpenAI API key is not set!")


# ------------------------------------------
# Helper: split only <body> HTML logically
# ------------------------------------------
def split_html_intelligently(html_content, max_chunk_size=1800):
    """Split <body> HTML safely without breaking tags."""
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        body = soup.find('body')

        # თუ body არ არის, მთლიანად ამუშავოს მოცემული
        html_to_split = str(body) if body else html_content
        chunks, current_chunk = [], ""

        # მხოლოდ body-ის შიგთავსის children ელემენტები
        soup2 = BeautifulSoup(html_to_split, 'html.parser')
        elements = soup2.body.contents if soup2.body else soup2.contents

        for element in elements:
            element_str = str(element)
            if len(element_str) > max_chunk_size:
                paragraphs = re.split(r'(</p>|</div>|</li>|</tr>)', element_str)
                for i in range(0, len(paragraphs), 2):
                    p = paragraphs[i] + (paragraphs[i + 1] if i + 1 < len(paragraphs) else '')
                    if len(current_chunk) + len(p) > max_chunk_size:
                        if current_chunk:
                            chunks.append(current_chunk)
                        current_chunk = p
                    else:
                        current_chunk += p
            else:
                if len(current_chunk) + len(element_str) > max_chunk_size:
                    chunks.append(current_chunk)
                    current_chunk = element_str
                else:
                    current_chunk += element_str

        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    except Exception as e:
        print(f"❌ Error in split_html_intelligently: {e}")
        traceback.print_exc()
        raise


# ------------------------------------------
# Helper: translate one chunk
# ------------------------------------------
def translate_chunk_with_openai(html_chunk, model="gpt-4o-mini", target_lang="German"):
    """Translate one HTML chunk while preserving structure."""
    try:
        print(f"🔄 Translating chunk ({len(html_chunk)} chars) → {target_lang} ...")

        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": f"""You are a professional HTML translator. 
Translate from English to {target_lang} while preserving ALL HTML tags, classes, and inline styles.

RULES:
1. Translate ONLY visible text, never tags or CSS
2. Preserve full HTML structure
3. Output valid HTML only (no explanations)"""
                },
                {"role": "user", "content": html_chunk}
            ],
            temperature=0.3
        )

        result = response.choices[0].message.content.strip()
        print(f"✅ Translated ({len(result)} chars)")
        return result

    except Exception as e:
        print("❌ OpenAI Translation Error:", e)
        traceback.print_exc()
        raise


# ------------------------------------------
# Endpoint: translate-body
# ------------------------------------------
@app.route('/translate-body', methods=['POST'])
def translate_body():
    """Receives HTML (body or full HTML), translates only <body> contents."""
    try:
        print("\n" + "=" * 50)
        print("📥 New /translate-body request")

        data = request.get_json(force=True)
        if not data or 'html' not in data:
            return jsonify({'error': 'Missing "html" field'}), 400

        html_content = data['html']
        target_lang = data.get('target_lang', 'German')
        model = data.get('model', 'gpt-4o-mini')

        print(f"📊 HTML size: {len(html_content)} chars | Target: {target_lang}")

        chunks = split_html_intelligently(html_content)
        print(f"✅ Split into {len(chunks)} chunks")

        translated_chunks = []
        for i, chunk in enumerate(chunks):
            print(f"📝 Translating chunk {i + 1}/{len(chunks)} ...")
            translated = translate_chunk_with_openai(chunk, model, target_lang)
            translated_chunks.append(translated)

            gc.collect()
            time.sleep(0.5)  # avoids rate limit

        translated_body = ''.join(translated_chunks)

        # მხოლოდ body დავაბრუნოთ (რაც user-მა მოგვცა)
        soup = BeautifulSoup(html_content, 'html.parser')
        body_tag = soup.find('body')
        body_attrs = ''
        if body_tag:
            attrs = body_tag.attrs
            body_attrs = ' '.join(
                [f'{k}="{v}"' if isinstance(v, str) else f'{k}="{" ".join(v)}"' for k, v in attrs.items()]
            )

        # ✅ ზუსტად იგივე <body> სტრუქტურა დააბრუნოს, თარგმნილი შიგთავსით
        final_html = f"<body {body_attrs}>{translated_body}</body>"

        print("✅ Translation completed successfully!")
        return Response(final_html, mimetype='text/html')

    except Exception as e:
        print(f"❌ ERROR: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# ------------------------------------------
# Healthcheck endpoints
# ------------------------------------------
@app.route('/healthz', methods=['GET'])
def healthz():
    return jsonify({'status': 'ok', 'service': 'translate-body'})


if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    print(f"\n🚀 Starting Translate Service on port {port}")
    app.run(host="0.0.0.0", port=port)
