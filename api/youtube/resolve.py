import sys
import json
import re
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        video_url = params.get('url', [''])[0]
        
        if not video_url:
            self.send_error(400, 'Missing url parameter')
            return
        
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
            self.send_error(400, 'Invalid YouTube URL or video ID')
            return
        
        # Try multiple clients - some work on datacenter IPs
        clients_to_try = [
            'android_music',
            'android', 
            'web_embedded',
            'tv_embedded',
            'mediaconnect',
            'android_vr'
        ]
        
        last_error = None
        
        for client in clients_to_try:
            try:
                result = self._extract(client, video_id)
                if result:
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps(result).encode())
                    return
            except Exception as e:
                last_error = e
                continue
        
        # All failed
        error_msg = str(last_error).lower() if last_error else 'unknown error'
        is_bot_wall = any(m in error_msg for m in [
            'sign in', 'confirm', 'bot', 'not a bot', 
            'po token', 'unable to extract', 'requested format',
            'login required'
        ])
        
        self.send_response(429 if is_bot_wall else 500)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps({
            'status': 'error',
            'error': str(last_error) if last_error else 'All clients failed',
            'bot_wall': is_bot_wall
        }).encode())
    
    def _extract(self, client, video_id):
        import yt_dlp
        
        ydl_opts = {
            'quiet': True,
            'format': 'bestaudio/best',
            'skip_download': True,
            'retries': 1,
            'fragment_retries': 1,
            'extractor_retries': 1,
            'socket_timeout': 10,
            'nocheckcertificate': True,
            'geo_bypass': True,
            'concurrent_fragment_downloads': 8,
            'extractor_args': {
                'youtube': {
                    'player_client': [client]
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
                raise Exception('No info')
            
            # Find audio URL
            stream_url = None
            
            # Try adaptive formats first (audio-only)
            for f in info.get('formats', []):
                vcodec = f.get('vcodec', 'none')
                acodec = f.get('acodec', 'none')
                if vcodec == 'none' and acodec != 'none' and f.get('url'):
                    if 'googlevideo.com' in f.get('url', ''):
                        stream_url = f['url']
                        break
            
            # Fallback to info url
            if not stream_url and info.get('url'):
                stream_url = info['url']
            
            if not stream_url:
                raise Exception('No stream URL found')
            
            return {
                'status': 'ok',
                'stream_url': stream_url,
                'title': info.get('title', ''),
                'duration': info.get('duration', 0),
                'video_id': video_id,
                'client_used': client,
                'format': {
                    'ext': info.get('ext', 'unknown'),
                    'quality': str(info.get('abr', info.get('tbr', 0)))
                }
            }
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()