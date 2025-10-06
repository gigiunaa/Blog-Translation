from flask import Flask, request, jsonify
import openai
import os
import re
from bs4 import BeautifulSoup

app = Flask(__name__)

# OpenAI API Key
openai.api_key = os.getenv('OPENAI_API_KEY', 'your-key-here')

def split_html_intelligently(html_content, max_chunk_size=4000):
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
                    p = paragraphs[i] + (paragraphs[i+1] if i+1 < len(paragraphs) else '')
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

def translate_chunk_with_openai(html_chunk, model="gpt-4o-mini"):
    try:
        response = openai.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": """You are a professional HTML translator. Translate from English to Georgian while preserving ALL HTML tags, classes, and styles.

RULES:
1. Translate ONLY visible text
2. NEVER translate HTML tags, attributes, or CSS
3. Preserve exact HTML structure
4. Return ONLY translated HTML"""
                },
                {
                    "role": "user",
                    "content": f"Translate to Georgian:\n\n{html_chunk}"
                }
            ],
            temperature=0.3,
            max_tokens=8000
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error: {str(e)}")
        return html_chunk

@app.route('/translate-html', methods=['POST'])
def translate_html():
    try:
        data = request.get_json()
        
        if not data or 'html' not in data:
            return jsonify({'error': 'HTML required'}), 400
        
        html_content = data['html']
        model = data.get('model', 'gpt-4o-mini')
        
        print(f"Processing {len(html_content)} characters")
        
        head_content, body_chunks = split_html_intelligently(html_content)
        print(f"Split into {len(body_chunks)} chunks")
        
        translated_chunks = []
        for i, chunk in enumerate(body_chunks):
            print(f"Translating {i+1}/{len(body_chunks)}...")
            translated = translate_chunk_with_openai(chunk, model)
            translated_chunks.append(translated)
        
        body_content = ''.join(translated_chunks)
        
        soup = BeautifulSoup(html_content, 'html.parser')
        body_tag = soup.find('body')
        body_attrs = ''
        if body_tag:
            attrs = body_tag.attrs
            body_attrs = ' '.join([f'{k}="{v}"' if isinstance(v, str) else f'{k}="{" ".join(v)}"' for k, v in attrs.items()])
        
        final_html = f"""<html>
{head_content}
<body {body_attrs}>
{body_content}
</body>
</html>"""
        
        return jsonify({
            'success': True,
            'translated_html': final_html,
            'chunks_processed': len(body_chunks)
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
