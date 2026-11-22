import process from "node:process";

const TELEGRAM_API_TIMEOUT_MS = 5000;

function extractUserId(body) {
  if (!body || typeof body !== "object") return null;
  if (body.userId) return String(body.userId).trim();
  if (body.user_id) return String(body.user_id).trim();
  if (body.user && body.user.id) return String(body.user.id).trim();
  return null;
}

export default async function handler(req, res) {
  // CORS Configuration
  res.setHeader("Access-Control-Allow-Credentials", "true");
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET,OPTIONS,POST");
  res.setHeader(
    "Access-Control-Allow-Headers",
    "X-CSRF-Token, X-Requested-With, Accept, Accept-Version, Content-Length, Content-MD5, Content-Type, Date, X-Api-Version, X-Telegram-Init-Data"
  );

  // Handle Preflight OPTIONS Request
  if (req.method === "OPTIONS") {
    return res.status(200).end();
  }

  // Restrict to POST Requests Only
  if (req.method !== "POST") {
    return res.status(405).json({
      success: false,
      message: "Method not allowed",
    });
  }

  const botToken = process.env.BOT_TOKEN;
  if (!botToken) {
    return res.status(500).json({
      success: false,
      message: "BOT_TOKEN is missing in environment variables.",
    });
  }

  // Safely parse request body
  let body = req.body || {};
  if (typeof body === "string") {
    try {
      body = JSON.parse(body);
    } catch {
      return res.status(400).json({
        success: false,
        message: "Invalid JSON payload provided.",
      });
    }
  }

  const userId = extractUserId(body);
  if (!userId) {
    return res.status(400).json({
      success: false,
      message: "User ID missing from request payload.",
    });
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), TELEGRAM_API_TIMEOUT_MS);

  try {
    const telegramApiUrl = `https://api.telegram.org/bot${botToken}/sendMessage`;

    const telegramRes = await fetch(telegramApiUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      signal: controller.signal,
      body: JSON.stringify({
        chat_id: userId,
        text: "⚡ Thank you for your action on TMX-QUANTUM!",
      }),
    });

    clearTimeout(timeoutId);

    const data = await telegramRes.json().catch(() => ({}));

    if (!telegramRes.ok || data.ok === false) {
      return res.status(400).json({
        success: false,
        message: data.description || "Failed to dispatch Telegram notification.",
      });
    }

    return res.status(200).json({
      success: true,
      message: "Notification sent successfully.",
    });
  } catch (error) {
    clearTimeout(timeoutId);
    const isTimeout = error?.name === "AbortError";
    return res.status(isTimeout ? 504 : 500).json({
      success: false,
      message: isTimeout
        ? "Telegram API request timed out."
        : error?.message || "Internal server error occurred.",
    });
  }
}
