import process from "node:process";

const TELEGRAM_API_TIMEOUT_MS = 5000;
const DEFAULT_CHANNEL_ID = "3905270338";

function extractUserId(body) {
  if (!body || typeof body !== "object") return null;
  if (body.userId) return String(body.userId).trim();
  if (body.user_id) return String(body.user_id).trim();
  if (body.user && body.user.id) return String(body.user.id).trim();
  return null;
}

function normalizeChannelChatId(rawId) {
  if (!rawId) return null;
  const cleaned = String(rawId).trim();
  if (!cleaned) return null;
  if (cleaned.startsWith("@") || cleaned.startsWith("-100")) {
    return cleaned;
  }
  if (/^\d+$/.test(cleaned)) {
    return `-100${cleaned}`;
  }
  return cleaned;
}

function extractChannelChatId(body) {
  if (body && typeof body === "object") {
    if (body.channelId) return normalizeChannelChatId(body.channelId);
    if (body.channel_id) return normalizeChannelChatId(body.channel_id);
    if (body.chatId) return normalizeChannelChatId(body.chatId);
  }
  const envId = process.env.CHANNEL_CHAT_ID || process.env.TMX_CHANNEL_CHAT_ID;
  if (envId) return normalizeChannelChatId(envId);
  return normalizeChannelChatId(DEFAULT_CHANNEL_ID);
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

  const botToken = process.env.BOT_TOKEN || process.env.TELEGRAM_BOT_TOKEN;
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

  const isChannelPost = body.target === "channel" || body.action === "channel";
  let chatId = null;
  let messageText = "⚡ Thank you for your action on TMX-QUANTUM!";

  if (isChannelPost) {
    chatId = extractChannelChatId(body);
    if (!chatId) {
      return res.status(400).json({
        success: false,
        message: "Channel chat ID missing.",
      });
    }

    const rawMessage = body.message || body.text || body.announcement;
    if (!rawMessage || typeof rawMessage !== "string" || !rawMessage.trim()) {
      return res.status(400).json({
        success: false,
        message: "Announcement or reminder message text is required for channel posts.",
      });
    }
    messageText = rawMessage.trim();
  } else {
    chatId = extractUserId(body);
    if (!chatId) {
      return res.status(400).json({
        success: false,
        message: "User ID missing from request payload.",
      });
    }
    if (typeof body.text === "string" && body.text.trim()) {
      messageText = body.text.trim();
    }
  }

  const payload = {
    chat_id: chatId,
    text: messageText,
    parse_mode: body.parseMode || body.parse_mode || "HTML",
    disable_notification: Boolean(body.silent),
  };

  if (body.buttonText && body.buttonUrl) {
    payload.reply_markup = {
      inline_keyboard: [[{ text: String(body.buttonText), url: String(body.buttonUrl) }]],
    };
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), TELEGRAM_API_TIMEOUT_MS);

  try {
    const telegramApiUrl = `https://api.telegram.org/bot${botToken}/sendMessage`;

    const telegramRes = await fetch(telegramApiUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      signal: controller.signal,
      body: JSON.stringify(payload),
    });

    clearTimeout(timeoutId);

    const data = await telegramRes.json().catch(() => ({}));

    if (!telegramRes.ok || data.ok === false) {
      return res.status(400).json({
        success: false,
        message: data.description || "Failed to dispatch Telegram message.",
      });
    }

    return res.status(200).json({
      success: true,
      message: isChannelPost
        ? "Channel announcement/reminder sent successfully."
        : "Notification sent successfully.",
      chat_id: chatId,
      message_id: data.result?.message_id ?? null,
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
