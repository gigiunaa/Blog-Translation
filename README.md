# Blog Translator

Flask service that translates an entire HTML document using OpenAI while preserving structure and key attributes.

## Run
pip install -r requirements.txt
export OPENAI_API_KEY=your_key
python app.py

## Request
POST /translate
Content-Type: application/json
{
  "html": "<html>...</html>",
  "target_lang": "de"
}
