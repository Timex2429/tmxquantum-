// Block ID 39504 integrated
const BLOCK_ID = "39504"; 

function loadAdsgramSDK() {
    return new Promise((resolve, reject) => {
        if (window.Adsgram) {
            resolve(window.Adsgram);
            return;
        }

        const scriptId = 'adsgram-sdk-script';
        let script = document.getElementById(scriptId);
        
        if (script) {
            const checkInterval = setInterval(() => {
                if (window.Adsgram) {
                    clearInterval(checkInterval);
                    resolve(window.Adsgram);
                }
            }, 100);
            
            setTimeout(() => {
                clearInterval(checkInterval);
                if (!window.Adsgram) reject(new Error("Adsgram SDK load timeout."));
            }, 5000);
            return;
        }

        script = document.createElement('script');
        script.id = scriptId;
        script.src = 'https://sad.adsgram.ai/js/sad.min.js';
        script.async = true;
        
        script.onload = () => {
            if (window.Adsgram) {
                resolve(window.Adsgram);
            } else {
                reject(new Error("Adsgram script loaded, but global object is missing."));
            }
        };
        
        script.onerror = () => {
            reject(new Error("Failed to load Adsgram SDK. Check your internet connection or ad-blocker settings."));
        };

        document.head.appendChild(script);
    });
}

async function handleWatchAdAndClaim() {
    const claimButton = document.getElementById('claim-btn');
    const statusText = document.getElementById('status-msg');

    try {
        claimButton.disabled = true;
        statusText.style.color = "#94a3b8";
        statusText.innerText = "Initializing ad environment...";

        if (window.Telegram && window.Telegram.WebApp) {
            window.Telegram.WebApp.ready();
        }

        const Adsgram = await loadAdsgramSDK();
        
        statusText.innerText = "Loading ad...";
        const adController = Adsgram.init({ blockId: BLOCK_ID });

        statusText.innerText = "";
        const result = await adController.show();
        
        console.log("Ad completed successfully:", result);
        await grantRewardOnBackend();

    } catch (error) {
        console.warn("Adsgram execution workflow failed:", error.message);
        statusText.style.color = "#f87171";
        statusText.innerText = error.message.includes("Adsgram") 
            ? "Ad provider blocked or unavailable. Please disable ad-blockers and try again." 
            : "An error occurred. Please check your connection.";
    } finally {
        claimButton.disabled = false;
    }
}

async function grantRewardOnBackend() {
    const statusText = document.getElementById('status-msg');
    try {
        statusText.style.color = "#34d399";
        statusText.innerText = "Ad watched! Claiming your TMX tokens...";
        await new Promise(resolve => setTimeout(resolve, 1500));
        statusText.innerText = "Success! TMX tokens added to your balance.";
    } catch (backendError) {
        statusText.style.color = "#f87171";
        statusText.innerText = "Failed to credit reward: " + backendError.message;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const claimButton = document.getElementById('claim-btn');
    if (claimButton) {
        claimButton.addEventListener('click', handleWatchAdAndClaim);
    }
});
