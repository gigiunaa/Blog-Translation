from flask import Flask, request, jsonify
from openai import OpenAI
import os
import re
import time
from bs4 import BeautifulSoup
import traceback

app = Flask(__name__)

# Initialize OpenAI Client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# API key check
if not os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") == "your-key-here":
    print("⚠️ WARNING: OpenAI API key is not set!")

# ---------------------------
# Helper: split HTML logically
# ---------------------------
def split_html_intelligently(html_content, max_chunk_size=3000):
    """Split HTML into logical chunks without breaking structure."""
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        head = soup.find('head')
        body = soup.find('body')

        head_content = str(head) if head else ""
        chunks = []
        current_chunk = ""

        if body:
            for element in body.children:
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

        return head_content, chunks
    except Exception as e:
        print(f"❌ Error in split_html_intelligently: {e}")
        traceback.print_exc()
        raise


# ---------------------------
# Helper: translate one chunk
# ---------------------------
def translate_chunk_with_openai(html_chunk, model="gpt-4o-mini", target_lang="German"):
    """Translate HTML chunk with OpenAI."""
    try:
        print(f"🔄 Translating chunk ({len(html_chunk)} chars) to {target_lang}...")

        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": f"""You are a professional HTML translator. Translate from English to {target_lang} while preserving ALL HTML tags, classes, and styles.

RULES:
1. Translate ONLY visible text content
2. NEVER translate HTML tags, attributes, or CSS
3. Preserve exact HTML structure
4. Return ONLY translated HTML without any explanations"""
                    },
                    {"role": "user", "content": html_chunk}
                ],
                temperature=0.3,
                max_tokens=8000
            )
        except Exception as e:
            # fallback model if needed
            if "model_not_found" in str(e):
                print("⚠️ Model not found, retrying with gpt-4o")
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": f"Translate HTML to {target_lang} preserving all tags."},
                        {"role": "user", "content": html_chunk}
                    ],
                    temperature=0.3,
                    max_tokens=8000
                )
            else:
                raise

        result = response.choices[0].message.content.strip()
        print(f"✅ Chunk translated successfully ({len(result)} chars)")
        return result

    except Exception as e:
        error_msg = str(e)
        print(f"❌ Translation error: {error_msg}")
        traceback.print_exc()
        raise Exception(f"OpenAI API error: {error_msg}")


# ---------------------------
# Endpoint: /translate-html
# ---------------------------
@app.route('/translate-html', methods=['POST'])
def translate_html():
    try:
        print("\n" + "=" * 50)
        print("📥 New translation request received")

        data = request.get_json()
        if not data or 'html' not in data:
            return jsonify({'error': 'HTML content is required in request body'}), 400

        html_content = data['html']
        model = data.get('model', 'gpt-4o-mini')
        target_lang = data.get('target_lang', 'German')

        print(f"📊 HTML size: {len(html_content)} characters")
        print(f"🎯 Target language: {target_lang}")
        print(f"🤖 Model: {model}")

        print("✂️ Splitting HTML into chunks...")
        head_content, body_chunks = split_html_intelligently(html_content)
        print(f"✅ Split into {len(body_chunks)} chunks")

        translated_chunks = []
        for i, chunk in enumerate(body_chunks):
            print(f"\n📝 Processing chunk {i + 1}/{len(body_chunks)}...")
            translated = translate_chunk_with_openai(chunk, model, target_lang)
            translated_chunks.append(translated)

            # პაუზა მცირე მეხსიერების დასაცლელად
            time.sleep(1)

        print("\n🔨 Assembling final HTML...")
        body_content = ''.join(translated_chunks)

        soup = BeautifulSoup(html_content, 'html.parser')
        body_tag = soup.find('body')
        body_attrs = ''
        if body_tag:
            attrs = body_tag.attrs
            body_attrs = ' '.join(
                [f'{k}="{v}"' if isinstance(v, str) else f'{k}="{" ".join(v)}"' for k, v in attrs.items()]
            )

        final_html = f"""<html>
{head_content}
<body {body_attrs}>
{body_content}
</body>
</html>"""

        print(f"✅ Translation completed! Final size: {len(final_html)} chars")
        print("=" * 50 + "\n")

        return jsonify({
            'success': True,
            'translated_html': final_html,
            'chunks_processed': len(body_chunks),
            'target_language': target_lang
        })

    except Exception as e:
        error_msg = str(e)
        print(f"\n❌ ERROR: {error_msg}")
        traceback.print_exc()
        print("=" * 50 + "\n")

        return jsonify({
            'success': False,
            'error': error_msg,
            'details': traceback.format_exc()
        }), 500


# ---------------------------
# Health endpoints
# ---------------------------
@app.route('/health', methods=['GET'])
def health():
    api_key_status = "✅ Set" if os.getenv("OPENAI_API_KEY") and os.getenv("OPENAI_API_KEY") != 'your-key-here' else "❌ Missing"
    return jsonify({
        'status': 'healthy',
        'service': 'HTML Translator',
        'supported_languages': ['German', 'Georgian', 'Spanish', 'French', 'Russian'],
        'openai_api_key': api_key_status
    })


@app.route('/test', methods=['GET'])
def test():
    return jsonify({
        'message': 'Service is running!',
        'openai_configured': bool(os.getenv("OPENAI_API_KEY") and os.getenv("OPENAI_API_KEY") != 'your-key-here')
    })


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    print(f"\n🚀 Starting server on port {port}...")
    print(f"🔑 OpenAI API Key: {'✅ Configured' if os.getenv('OPENAI_API_KEY') else '❌ Not Set'}\n")
    app.run(host='0.0.0.0', port=port)
