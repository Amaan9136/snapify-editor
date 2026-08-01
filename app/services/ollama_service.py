import json
import re
import requests
DEFAULT_TIMEOUT = 60
PROMPT_TEMPLATE = """You are a social media assistant helping to prepare a YouTube Shorts upload.
Context about the clip:
{context}
Generate the following, and respond with ONLY valid JSON (no markdown fences, no commentary), matching this exact schema:
{{
  "title": "a catchy, click-worthy YouTube Shorts title, under 90 characters",
  "description": "a 2-4 sentence engaging description for the video, include a call to action",
  "hashtags": ["#example1", "#example2", "... 8-15 relevant hashtags including #Shorts"]
}}
"""
class OllamaError(RuntimeError):
    pass
def _headers(app_config):
    headers = {"Content-Type": "application/json"}
    api_key = app_config.get("OLLAMA_API_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers
def _extract_json(text):
    text = text.strip()
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1)
    else:
        brace_match = re.search(r"\{.*\}", text, re.DOTALL)
        if brace_match:
            text = brace_match.group(0)
    return json.loads(text)
def generate_metadata(app_config, context_description, extra_instructions=None):
    host = app_config.get("OLLAMA_HOST", "https://ollama.com").rstrip("/")
    model = app_config.get("OLLAMA_MODEL", "gpt-oss:20b-cloud")
    prompt = PROMPT_TEMPLATE.format(context=context_description)
    if extra_instructions:
        prompt += f"\nAdditional instructions from the user: {extra_instructions}\n"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "format": "json",
    }
    try:
        resp = requests.post(
            f"{host}/api/chat",
            headers=_headers(app_config),
            json=payload,
            timeout=DEFAULT_TIMEOUT,
        )
    except requests.RequestException as e:
        raise OllamaError(f"Could not reach Ollama host at {host}: {e}") from e
    if resp.status_code != 200:
        raise OllamaError(f"Ollama returned HTTP {resp.status_code}: {resp.text[:500]}")
    data = resp.json()
    raw_content = (data.get("message") or {}).get("content", "")
    try:
        parsed = _extract_json(raw_content)
    except (json.JSONDecodeError, TypeError) as e:
        raise OllamaError(f"Could not parse Ollama's response as JSON: {e}. Raw: {raw_content[:500]}") from e
    title = str(parsed.get("title", "")).strip()
    description = str(parsed.get("description", "")).strip()
    hashtags = parsed.get("hashtags", [])
    if isinstance(hashtags, str):
        hashtags = [h.strip() for h in hashtags.split() if h.strip()]
    hashtags = [h if h.startswith("#") else f"#{h}" for h in hashtags]
    return {
        "title": title or "Untitled Short",
        "description": description,
        "hashtags": hashtags,
        "raw": raw_content,
    }
def check_connection(app_config):
    host = app_config.get("OLLAMA_HOST", "https://ollama.com").rstrip("/")
    try:
        resp = requests.get(f"{host}/api/tags", headers=_headers(app_config), timeout=10)
        if resp.status_code == 200:
            return True, "connected"
        return False, f"HTTP {resp.status_code}: {resp.text[:200]}"
    except requests.RequestException as e:
        return False, str(e)