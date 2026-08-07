export default async function handler(req, res) {
  // CORS Headers so Telegram WebApp can hit the endpoint without blocking
  res.setHeader('Access-Control-Allow-Credentials', true);
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET,OPTIONS,PATCH,DELETE,POST,PUT');
  res.setHeader(
    'Access-Control-Allow-Headers',
    'X-CSRF-Token, X-Requested-With, Accept, Accept-Version, Content-Length, Content-MD5, Content-Type, Date, X-Api-Version'
  );

  if (req.method === 'OPTIONS') {
    res.status(200).end();
    return;
  }

  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const BOT_TOKEN = process.env.BOT_TOKEN;
  const { userId } = req.body || {};

  if (!BOT_TOKEN) {
    return res.status(500).json({ success: false, message: 'BOT_TOKEN missing in Vercel Environment Variables.' });
  }

  try {
    const telegramApiUrl = `https://api.telegram.org/bot${BOT_TOKEN}/sendMessage`;

    const telegramRes = await fetch(telegramApiUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        chat_id: userId,
        text: "✅ Order successfully placed on TMX Quantum Shop!"
      })
    });

    const data = await telegramRes.json();

    if (!telegramRes.ok) {
      return res.status(400).json({ success: false, message: data.description || 'Telegram API Error' });
    }

    return res.status(200).json({ success: true, message: 'Purchase complete!' });
  } catch (error) {
    return res.status(500).json({ success: false, message: error.message });
  }
}
