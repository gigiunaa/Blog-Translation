from flask import Flask, request, jsonify
from openai import OpenAI
import os
import re
import time
import gc
import psutil
from bs4 import BeautifulSoup
import traceback

app = Flask(__name__)

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Check key
if not os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") == "your-key-here":
    print("⚠️ WARNING: OpenAI API key is not set!")

# ------------------------------------------
# Memory-safe cleanup helper
# ------------------------------------------
def cleanup_memory(force=False):
    gc.collect()
    process = psutil.Process(os.getpid())
    mem = process.memory_info().rss / 1024 / 1024
    print(f"🧠 Memory usage: {mem:.2f} MB")
    if mem > 400 or force:
        print("⚠️ High memory usage — forcing cleanup...")
        gc.collect()
        time.sleep(2)
    return mem

# ------------------------------------------
# Splitter
# ------------------------------------------
def split_html_intelligently(html_content, max_chunk_size=900):
    """Split HTML into manageable chunks without breaking tags."""
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        head = soup.find("head")
        body = soup.find("body")

        head_content = str(head) if head else ""
        chunks, current_chunk = [], ""

        if body:
            for element in body.children:
                element_str = str(element)
                if len(element_str) > max_chunk_size:
                    parts = re.split(r"(</p>|</div>|</li>|</tr>)", element_str)
                    for i in range(0, len(parts), 2):
                        p = parts[i] + (parts[i + 1] if i + 1 < len(parts) else "")
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
        print(f"❌ Split error: {e}")
        traceback.print_exc()
        raise

# ------------------------------------------
# Translator
# ------------------------------------------
def translate_chunk_with_openai(html_chunk, model="gpt-4o-mini", target_lang="German"):
    """Translate HTML chunk safely with retries and memory cleanup."""
    try:
        print(f"🔄 Translating chunk ({len(html_chunk)} chars) → {target_lang} ...")

        prompt = f"""
You are a professional HTML translator. Translate from English to {target_lang} while preserving ALL HTML tags, classes, and styles.
Rules:
1. Translate ONLY visible text.
2. NEVER translate HTML tags, attributes, or CSS.
3. Preserve exact HTML structure.
4. Return ONLY translated HTML.
"""
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": prompt.strip()},
                {"role": "user", "content": html_chunk},
            ],
            temperature=0.3,
            max_tokens=4096,
        )
        result = response.choices[0].message.content.strip()
        print(f"✅ Chunk translated ({len(result)} chars)")
        return result

    except Exception as e:
        print(f"⚠️ Translation error: {e}")
        traceback.print_exc()
        print("♻️ Retrying with smaller model...")
        time.sleep(3)
        # Retry fallback
        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": f"Translate HTML to {target_lang}, keep structure."},
                    {"role": "user", "content": html_chunk},
                ],
                temperature=0.3,
                max_tokens=4096,
            )
            result = response.choices[0].message.content.strip()
            print(f"✅ Fallback success ({len(result)} chars)")
            return result
        except Exception as e2:
            raise Exception(f"Retry failed: {e2}")

# ------------------------------------------
# Endpoint
# ------------------------------------------
@app.route("/translate-html", methods=["POST"])
def translate_html():
    try:
        print("\n" + "=" * 60)
        print("📥 New translation request received")

        data = request.get_json()
        if not data or "html" not in data:
            return jsonify({"error": "HTML content required"}), 400

        html_content = data["html"]
        model = data.get("model", "gpt-4o-mini")
        target_lang = data.get("target_lang", "German")

        print(f"📊 HTML size: {len(html_content)} chars")
        print(f"🎯 Target: {target_lang}")
        print(f"🤖 Model: {model}")

        print("✂️ Splitting...")
        head_content, body_chunks = split_html_intelligently(html_content)
        print(f"✅ Split into {len(body_chunks)} chunks")

        translated_chunks = []
        for i, chunk in enumerate(body_chunks):
            print(f"\n📝 Processing chunk {i+1}/{len(body_chunks)} ...")
            translated = translate_chunk_with_openai(chunk, model, target_lang)
            translated_chunks.append(translated)
            mem = cleanup_memory()
            if mem > 500:
                print("💤 Cooling down (memory spike)...")
                time.sleep(8)
            else:
                time.sleep(1)

        print("\n🔨 Assembling final HTML...")
        body_content = "".join(translated_chunks)

        soup = BeautifulSoup(html_content, "html.parser")
        body_tag = soup.find("body")
        body_attrs = ""
        if body_tag:
            attrs = body_tag.attrs
            body_attrs = " ".join(
                [f'{k}="{v}"' if isinstance(v, str) else f'{k}="{" ".join(v)}"' for k, v in attrs.items()]
            )

        final_html = f"<html>\n{head_content}\n<body {body_attrs}>\n{body_content}\n</body>\n</html>"
        print(f"✅ Done! Final size: {len(final_html)} chars")
        cleanup_memory(force=True)

        return jsonify(
            {
                "success": True,
                "translated_html": final_html,
                "chunks_processed": len(body_chunks),
                "target_language": target_lang,
            }
        )

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        traceback.print_exc()
        cleanup_memory(force=True)
        return jsonify({"success": False, "error": str(e)}), 500

# ------------------------------------------
# Health/test
# ------------------------------------------
@app.route("/health", methods=["GET"])
def health():
    return jsonify(
        {
            "status": "healthy",
            "service": "HTML Translator Optimized",
            "ram_mb": psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024,
        }
    )

@app.route("/test", methods=["GET"])
def test():
    return jsonify({"message": "Service is running!"})

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print(f"\n🚀 Starting server on port {port} ...")
    app.run(host="0.0.0.0", port=port)
