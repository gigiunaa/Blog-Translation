# HTML Translator (Flask + GPT-4o-mini)

### Endpoint
POST /translate

#### Request JSON
{
  "html": "<html>...</html>",
  "target_lang": "de"
}

#### Response JSON
{
  "html": "<html>...translated...</html>",
  "stats": {"found": 1200, "translated": 1200, "model": "gpt-4o-mini"}
}

✅ Keeps all CSS, classes, and HTML structure intact  
✅ Translates only visible text nodes  
✅ Skips <script>, <style>, <code>, <svg>  
✅ Supports any target language  
✅ Runs perfectly on Render
