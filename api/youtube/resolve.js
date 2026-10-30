const { getInfo, chooseFormat } = require('@distube/ytdl-core');

module.exports = async function handler(req, res) {
  // CORS
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  
  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  const videoUrl = req.query.url;
  
  if (!videoUrl) {
    return res.status(400).json({ status: 'error', error: 'Missing url parameter' });
  }

  // Extract video ID
  let videoId = null;
  const patterns = [
    /(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})/,
    /^([a-zA-Z0-9_-]{11})$/
  ];
  
  for (const p of patterns) {
    const m = videoUrl.match(p);
    if (m) { videoId = m[1]; break; }
  }
  
  if (!videoId) {
    return res.status(400).json({ status: 'error', error: 'Invalid YouTube URL or video ID' });
  }

  try {
    const info = await getInfo('https://www.youtube.com/watch?v=' + videoId, {
      playerClients: ['ANDROID_MUSIC', 'ANDROID', 'ANDROID_VR', 'IOS'],
      requestOptions: {
        headers: { 
          'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
          'Accept-Language': 'en-US,en;q=0.9'
        },
        timeout: 25000
      }
    });

    let format = chooseFormat(info.formats, { 
      quality: 'highestaudio',
      filter: 'audioonly'
    });

    if (!format) {
      format = chooseFormat(info.formats, { quality: 'highest' });
    }

    if (!format || !format.url) {
      throw new Error('No playable format found');
    }

    return res.status(200).json({
      status: 'ok',
      stream_url: format.url,
      title: info.videoDetails.title,
      duration: parseInt(info.videoDetails.lengthSeconds) || 0,
      video_id: videoId,
      format: {
        itag: format.itag,
        mime_type: format.mimeType,
        bitrate: format.bitrate,
        quality: format.quality,
        container: format.container
      }
    });

  } catch (error) {
    const isBotWall = /sign in|confirm|bot|not a bot|po token|unable to extract|requested format/i.test(error.message);
    
    return res.status(isBotWall ? 429 : 500).json({
      status: 'error',
      error: error.message,
      bot_wall: isBotWall
    });
  }
};