// tmxService.js
// Handles reward claim requests, input/state validation, timeouts, and structured error handling.

const DEFAULT_API_ENDPOINT = "https://tmxquantum-1.onrender.com";
const DEFAULT_TIMEOUT_MS = 6000;

class TMXQuantumService {
  constructor(apiEndpoint = DEFAULT_API_ENDPOINT, timeoutMs = DEFAULT_TIMEOUT_MS) {
    this.apiEndpoint = String(apiEndpoint || DEFAULT_API_ENDPOINT).replace(/\/+$/, "");
    this.timeoutMs = Number(timeoutMs) > 0 ? Number(timeoutMs) : DEFAULT_TIMEOUT_MS;
  }

  validateClaimInput(userId, adSessionToken, claimMeta = {}) {
    const normalizedUserId = userId !== undefined && userId !== null
      ? String(userId).trim()
      : "";

    if (!normalizedUserId) {
      return { valid: false, error: "Missing valid user ID for reward claim." };
    }

    if (adSessionToken !== undefined && adSessionToken !== null && String(adSessionToken).trim() === "") {
      return { valid: false, error: "Invalid empty ad session token." };
    }

    if (claimMeta.sessionPoints !== undefined) {
      const pts = Number(claimMeta.sessionPoints);
      if (!Number.isFinite(pts) || pts <= 0) {
        return { valid: false, error: "Invalid mining session points." };
      }
    }

    return { valid: true, userId: normalizedUserId };
  }

  extractBalance(data) {
    if (!data || typeof data !== "object") return null;
    const candidates = [
      data.newBalance,
      data.balance,
      data.tmx_balance,
      data.data?.newBalance,
      data.data?.balance
    ];
    for (const val of candidates) {
      if (typeof val === "number" && Number.isFinite(val)) return val;
      if (typeof val === "string" && val.trim() !== "" && Number.isFinite(Number(val))) {
        return Number(val);
      }
    }
    return null;
  }

  async claimMiningReward(userId, adSessionToken = null, options = {}) {
    const check = this.validateClaimInput(userId, adSessionToken, options);
    if (!check.valid) {
      return {
        success: false,
        error: check.error
      };
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeoutMs);

    try {
      const headers = {
        "Content-Type": "application/json"
      };

      if (adSessionToken) {
        headers["Authorization"] = `Bearer ${String(adSessionToken).trim()}`;
      }
      if (options.initData) {
        headers["X-Telegram-Init-Data"] = String(options.initData);
      }

      const payload = {
        userId: check.userId,
        user_id: check.userId,
        timestamp: Date.now(),
        ...(options.sessionPoints !== undefined ? { sessionPoints: Number(options.sessionPoints) } : {}),
        ...(options.multiplier !== undefined ? { multiplier: Number(options.multiplier) } : {}),
        ...(options.earned !== undefined ? { earned: Number(options.earned) } : {})
      };

      const response = await fetch(`${this.apiEndpoint}/api/claim`, {
        method: "POST",
        headers,
        signal: controller.signal,
        body: JSON.stringify(payload)
      });

      clearTimeout(timeoutId);

      const rawText = await response.text();
      let data = {};
      if (rawText) {
        try {
          data = JSON.parse(rawText);
        } catch {
          throw new Error("Server returned a non-JSON response.");
        }
      }

      if (!response.ok || data.success === false) {
        throw new Error(data.message || data.error || `Server responded with status ${response.status}`);
      }

      const balance = this.extractBalance(data);

      return {
        success: true,
        newBalance: balance,
        message: data.message || "TMX rewards claimed successfully!",
        raw: data
      };
    } catch (error) {
      clearTimeout(timeoutId);
      const isTimeout = error?.name === "AbortError";
      const message = isTimeout
        ? "Claim request timed out. Please check your connection and try again."
        : error?.message || "Network connection failed. Please check your internet and try again.";

      console.error("Mining Claim Error:", message);

      return {
        success: false,
        error: message
      };
    }
  }
}

export default TMXQuantumService;
