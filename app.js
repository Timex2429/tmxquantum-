import process from "node:process";

const TELEGRAM_API_TIMEOUT_MS = 5000;
const DEFAULT_CHANNEL_ID = "3905270338";

const REMINDER_PRESETS = {
  mining:
    "⚡ <b>TMX-QUANTUM Mining Reminder</b>\nYour quantum mining round is ready! Open the Mini App to claim your 💎 rewards and keep your momentum going.",
  streak:
    "🔥 <b>Daily Check-In Streak Reminder</b>\nDon't break your 7-day check-in streak on TMX-QUANTUM—claim today's bonus before the clock resets!",
  spin:
    "🎡 <b>Quantum Spin Ready</b>\nYour daily Quantum Spin is available on TMX-QUANTUM! Spin now for a chance at extra 💎 drops.",
};

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

function getCandidateChannelIds(body) {
  let raw = DEFAULT_CHANNEL_ID;
  if (body && typeof body === "object") {
    raw = body.channelId || body.channel_id || body.chatId || raw;
  }
  const envId = process.env.CHANNEL_CHAT_ID || process.env.TMX_CHANNEL_CHAT_ID;
  if (!body?.channelId && !body?.channel_id && !body?.chatId && envId) {
    raw = envId;
  }

  const cleaned = String(raw || "").trim();
  const normalized = normalizeChannelChatId(cleaned);
  const candidates = [];

  if (normalized) candidates.push(normalized);
  if (cleaned && !candidates.includes(cleaned)) candidates.push(cleaned);

  return candidates;
}

async function sendTelegramMessage(botToken, payload) {
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
    return { ok: telegramRes.ok && data.ok !== false, status: telegramRes.status, data };
  } catch (error) {
    clearTimeout(timeoutId);
    throw error;
  }
}

export default async function handler(req, res) {
  // CORS Configuration
  res.setHeader("Access-Control-Allow-Credentials", "true");
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET,OPTIONS,POST");
  res.setHeader(
    "Access-Control-Allow-Headers",
    "X-CSRF-Token, X-Requested-With, Accept, Accept-Version, Content-Length, Content-MD5, Content-Type, Date, X-Api-Version, X-Telegram-Init-Data, X-Admin-Secret"
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

  const botToken = process.env.BOT_TOKEN || process.env.bot_token || process.env.TELEGRAM_BOT_TOKEN;
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

  if (isChannelPost) {
    const requiredSecret = process.env.CHANNEL_ADMIN_SECRET;
    if (requiredSecret) {
      const providedSecret = req.headers["x-admin-secret"] || body.secret;
      if (providedSecret !== requiredSecret) {
        return res.status(401).json({
          success: false,
          message: "Unauthorized channel post request.",
        });
      }
    }

    const candidates = getCandidateChannelIds(body);
    if (!candidates.length) {
      return res.status(400).json({
        success: false,
        message: "Channel chat ID missing.",
      });
    }

    const presetKey = typeof body.reminderType === "string" ? body.reminderType.trim().toLowerCase() : "";
    const rawMessage =
      body.message ||
      body.text ||
      body.announcement ||
      (presetKey && REMINDER_PRESETS[presetKey]) ||
      (body.type === "reminder" ? REMINDER_PRESETS.mining : "");

    if (!rawMessage || typeof rawMessage !== "string" || !rawMessage.trim()) {
      return res.status(400).json({
        success: false,
        message: "Announcement or reminder message text is required for channel posts.",
      });
    }

    const basePayload = {
      text: rawMessage.trim(),
      parse_mode: body.parseMode || body.parse_mode || "HTML",
      disable_notification: Boolean(body.silent),
    };

    if (body.buttonText && body.buttonUrl) {
      basePayload.reply_markup = {
        inline_keyboard: [[{ text: String(body.buttonText), url: String(body.buttonUrl) }]],
      };
    }

    try {
      let lastFailure = null;
      for (const candidateChatId of candidates) {
        const result = await sendTelegramMessage(botToken, {
          ...basePayload,
          chat_id: candidateChatId,
        });

        if (result.ok) {
          return res.status(200).json({
            success: true,
            message: "Channel announcement/reminder sent successfully.",
            chat_id: candidateChatId,
            message_id: result.data.result?.message_id ?? null,
          });
        }

        lastFailure = result.data?.description || "Failed to dispatch Telegram channel message.";
      }

      return res.status(400).json({
        success: false,
        message: lastFailure,
      });
    } catch (error) {
      const isTimeout = error?.name === "AbortError";
      return res.status(isTimeout ? 504 : 500).json({
        success: false,
        message: isTimeout
          ? "Telegram API request timed out."
          : error?.message || "Internal server error occurred.",
      });
    }
  }

  // Default: user notification
  const userId = extractUserId(body);
  if (!userId) {
    return res.status(400).json({
      success: false,
      message: "User ID missing from request payload.",
    });
  }

  const userText =
    typeof body.text === "string" && body.text.trim()
      ? body.text.trim()
      : "⚡ Thank you for your action on TMX-QUANTUM!";

  try {
    const result = await sendTelegramMessage(botToken, {
      chat_id: userId,
      text: userText,
      parse_mode: body.parseMode || body.parse_mode || "HTML",
      disable_notification: Boolean(body.silent),
    });

    if (!result.ok) {
      return res.status(400).json({
        success: false,
        message: result.data?.description || "Failed to dispatch Telegram notification.",
      });
    }

    return res.status(200).json({
      success: true,
      message: "Notification sent successfully.",
      message_id: result.data.result?.message_id ?? null,
    });
  } catch (error) {
    const isTimeout = error?.name === "AbortError";
    return res.status(isTimeout ? 504 : 500).json({
      success: false,
      message: isTimeout
        ? "Telegram API request timed out."
        : error?.message || "Internal server error occurred.",
    });
  }
    }
