export default async function handler(req, res) {
  // CORS configuration
  res.setHeader('Access-Control-Allow-Credentials', true);
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET,OPTIONS,POST');
  res.setHeader(
    'Access-Control-Allow-Headers',
    'X-CSRF-Token, X-Requested-With, Accept, Accept-Version, Content-Length, Content-MD5, Content-Type, Date, X-Api-Version'
  );

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  if (req.method !== 'POST') {
    return res.status(405).json({ success: false, message: 'Method not allowed' });
  }

  const BOT_TOKEN = process.env.BOT_TOKEN;
  const { userId } = req.body || {};

  if (!BOT_TOKEN) {
    return res.status(500).json({ 
      success: false, 
      message: 'BOT_TOKEN is missing in Vercel Environment Variables.' 
    });
  }

  if (!userId) {
    return res.status(400).json({ 
      success: false, 
      message: 'User ID missing from Telegram WebApp payload.' 
    });
  }

  try {
    const telegramApiUrl = `https://api.telegram.org/bot${BOT_TOKEN}/sendMessage`;

    const telegramRes = await fetch(telegramApiUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        chat_id: userId,
        text: "⚡ Thank you for your order on TMX-QUANTUM!"
      })
    });

    const data = await telegramRes.json();

    if (!telegramRes.ok) {
      return res.status(400).json({ 
        success: false, 
        message: data.description || 'Failed to dispatch Telegram notification.' 
      });
    }

    return res.status(200).json({ success: true, message: 'Purchase successful!' });
  } catch (error) {
    return res.status(500).json({ success: false, message: error.message });
  }
}
