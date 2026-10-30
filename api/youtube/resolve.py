import sys
import json
import re

def handler(request, response):
    from urllib.parse import urlparse, parse_qs
    
    parsed = urlparse(request.path)
    params = parse_qs(parsed.query)
    video_url = params.get('url', [''])[0]
    
    if not video_url:
        response.status_code = 400
        response.set_header('Content-Type', 'application/json')
        response.set_header('Access-Control-Allow-Origin', '*')
        return json.dumps({'status': 'error', 'error': 'Missing url parameter'})
    
    # Extract video ID
    video_id = None
    patterns = [
        r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})',
        r'^([a-zA-Z0-9_-]{11})$'
    ]
    
    for p in patterns:
        m = re.search(p, video_url)
        if m:
            video_id = m.group(1)
            break
    
    if not video_id:
        response.status_code = 400
        response.set_header('Content-Type', 'application/json')
        response.set_header('Access-Control-Allow-Origin', '*')
        return json.dumps({'status': 'error', 'error': 'Invalid YouTube URL or video ID'})
    
    try:
        import yt_dlp
        
        ydl_opts = {
            'quiet': True,
            'format': 'bestaudio/best',
            'skip_download': True,
            'retries': 2,
            'fragment_retries': 2,
            'extractor_retries': 2,
            'socket_timeout': 15,
            'nocheckcertificate': True,
            'geo_bypass': True,
            'concurrent_fragment_downloads': 16,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android_music']
                }
            },
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
                'Accept-Language': 'en-US,en;q=0.9'
            }
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info('https://www.youtube.com/watch?v=' + video_id, download=False)
            if not info:
                raise Exception('No video info returned')
            
            formats = info.get('formats', [])
            audio_format = None
            
            for f in formats:
                vcodec = f.get('vcodec', 'none')
                acodec = f.get('acodec', 'none')
                audio_url = f.get('url', '')
                
                if vcodec in ('none', None) and acodec not in ('none', None) and audio_url:
                    if audio_format is None or f.get('tbr', 0) > audio_format.get('tbr', 0):
                        audio_format = f
            
            if not audio_format:
                audio_format = info
            
            response.set_header('Content-Type', 'application/json')
            response.set_header('Access-Control-Allow-Origin', '*')
            return json.dumps({
                'status': 'ok',
                'stream_url': audio_format.get('url', ''),
                'title': info.get('title', ''),
                'duration': info.get('duration', 0),
                'video_id': video_id,
                'format': {
                    'itag': audio_format.get('format_id', ''),
                    'mime_type': audio_format.get('ext', 'unknown'),
                    'bitrate': audio_format.get('tbr', 0),
                    'quality': str(audio_format.get('abr', 0)),
                    'container': audio_format.get('ext', 'unknown')
                }
            })
    
    except Exception as error:
        error_msg = str(error).lower()
        is_bot_wall = any(m in error_msg for m in [
            'sign in', 'confirm', 'bot', 'not a bot', 
            'po token', 'unable to extract', 'requested format'
        ])
        
        response.status_code = 429 if is_bot_wall else 500
        response.set_header('Content-Type', 'application/json')
        response.set_header('Access-Control-Allow-Origin', '*')
        return json.dumps({
            'status': 'error',
            'error': str(error),
            'bot_wall': is_bot_wall
        })