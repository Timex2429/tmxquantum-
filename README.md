# TMX Quantum

Backend server and frontend interface for TMX Quantum, featuring secure Telegram authentication, token mining, and rewarded ad verification.

## 🚀 Project Structure

* **`index.html`**: The frontend mining dashboard and user interface.
* **`tmxService.js`**: Frontend service handling secure API calls, token claims, and error management.
* **`app.js`**: Node.js backend server routing and request handling.
* **`main.py`**: Alternative Python backend integration script.
* **`build.sh`**: Deployment and build script configured for hosting platforms like Render.
* **`requirements.txt`**: Python dependencies list.

## 🛠️ Features

* **Cold-Start Prevention**: Integrated with automated keep-alive pings to keep instances active on free-tier hosting.
* **Secure Token Claiming**: Verifies user sessions and ad rewards before updating user balances.
* **Robust Error Handling**: Gracefully catches network interruptions and server timeouts on both client and server sides.

## 📄 Deployment

Hosted live via Render and linked with custom automation tools to ensure seamless uptime and instant responses.
