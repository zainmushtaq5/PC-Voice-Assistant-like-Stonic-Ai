import re
import urllib.parse
import webbrowser


def search_web(query: str) -> str:
    """Opens a browser and searches the web using Google."""
    try:
        url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
        webbrowser.open(url)
        return f"Successfully searched the web for: {query}"
    except Exception as e:
        return f"Error searching the web: {e}"


def open_website(url: str) -> str:
    """Opens a specific website/URL in the default browser."""
    try:
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        
        import platform
        import os
        if platform.system() == "Windows":
            os.startfile(url)
        else:
            webbrowser.open(url)
            
        return f"Opened {url} in your browser."
    except Exception as e:
        return f"Error opening website: {e}"


def web_search(query: str, max_results: int = 3) -> str:
    """Performs a live web search and returns readable text results, so the
    assistant can actually answer with current information instead of guessing."""
    try:
        from ddgs import DDGS
        results = list(DDGS().text(query, max_results=int(max_results or 3)))
        if not results:
            return "I couldn't find any web results for that."
        lines = []
        for i, r in enumerate(results[:5], 1):
            title = (r.get("title") or "").strip()
            body = (r.get("body") or "").strip()
            snippet = body or title
            snippet = re.sub(r"\s+", " ", snippet)
            lines.append(f"{i}. {snippet}")
        return "\n".join(lines)[:2500]
    except Exception as e:
        return f"Web search failed: {e}"


def play_youtube(query: str) -> str:
    """Search YouTube for `query` and actually play it: resolve the top result
    with yt-dlp and open that video's page (which autoplays in the browser). Falls
    back to opening the search page only if resolution fails."""
    query = (query or "").strip()
    if not query:
        return "I need a search term to play on YouTube."

    try:
        import yt_dlp  # installed; resolves real video URLs
    except Exception:
        yt_dlp = None

    if yt_dlp is not None:
        try:
            opts = {
                "quiet": True, "noplaylist": True, "skip_download": True,
                "format": "best",
            }
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(f"ytsearch1:{query}", download=False)
                entry = (info.get("entries") or [{}])[0]
                video_url = entry.get("webpage_url") or entry.get("url")
                title = entry.get("title") or "the first result"
            if video_url:
                open_website(video_url)
                return f"Playing '{title}' from YouTube in your browser."
        except Exception as exc:
            # Fall through to the search page fallback.
            print(f"[PlayYouTube] resolve failed: {exc}")

    # Last resort: open the search results page (can't autoplay without a URL).
    url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote(query)
    open_website(url)
    return (
        "I opened the YouTube results for that, but I couldn't auto-resolve the "
        "first video to start it directly. Please click the first result to play it."
    )


def get_weather(location: str = "") -> str:
    """Returns current weather for a location using the free wttr.in service."""
    try:
        import requests
        loc = urllib.parse.quote(location.strip() or "current location")
        url = f"https://wttr.in/{loc}?format=%l:+%t,+%C,+humidity+%h,+wind+%w"
        resp = requests.get(url, timeout=12)
        text = resp.text

        # Make it nice to read aloud: strip emojis/non-ascii, tidy whitespace.
        text = text.replace("°", " degrees")
        text = re.sub(r"[^\x20-\x7E]", " ", text)
        text = re.sub(r"\s+", " ", text).strip()

        if not text:
            return "I couldn't get the weather right now."
        return f"Weather: {text}."
    except Exception as e:
        return f"I couldn't get the weather: {e}"


