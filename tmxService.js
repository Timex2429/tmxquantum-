// tmxQuantumService.js
// Handles secure token claims, network error catching, and state validation

class TMXQuantumService {
  constructor(apiEndpoint) {
    this.apiEndpoint = apiEndpoint || 'https://tmxquantum-1.onrender.com';
  }

  async claimMiningReward(userId, adSessionToken) {
    try {
      const response = await fetch(`${this.apiEndpoint}/api/claim`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${adSessionToken}`
        },
        body: JSON.stringify({ userId, timestamp: Date.now() })
      });

      // Handle HTTP-level errors gracefully
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.message || `Server responded with status: ${response.status}`);
      }

      const data = await response.json();
      
      return {
        success: true,
        newBalance: data.newBalance,
        message: 'TMX tokens claimed successfully!'
      };

    } catch (error) {
      console.error('Mining Claim Error:', error.message);
      
      // Return a structured error response for the frontend UI to display
      return {
        success: false,
        error: error.message || 'Network connection failed. Please check your internet and try again.'
      };
    }
  }
}

export default TMXQuantumService;
