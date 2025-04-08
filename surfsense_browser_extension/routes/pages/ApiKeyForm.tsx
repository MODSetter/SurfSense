import React, { useState } from "react";
import { useNavigate } from "react-router-dom"
import icon from "data-base64:~assets/icon.png"
import { Storage } from "@plasmohq/storage"
import { Button } from "~/routes/ui/button"
import { ReloadIcon } from "@radix-ui/react-icons"

const ApiKeyForm = () => {
  const navigation = useNavigate()
  const [apiKey, setApiKey] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const storage = new Storage({ area: "local" })

  const validateForm = () => {
    if (!apiKey) {
      setError('API key is required');
      return false;
    }
    setError('');
    return true;
  };

  const handleSubmit = async (event: { preventDefault: () => void; }) => {
    event.preventDefault();
    if (!validateForm()) return;
    setLoading(true);

    try {
      // Verify token is valid by making a request to the API
      const response = await fetch(`${process.env.PLASMO_PUBLIC_BACKEND_URL}/verify-token`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${apiKey}`,
        }
      });

      setLoading(false);

      if (response.ok) {
        // Store the API key as the token
        await storage.set('token', apiKey);
        navigation("/")
      } else {
        setError('Invalid API key. Please check and try again.');
      }
    } catch (error) {
      setLoading(false);
      setError('An error occurred. Please try again later.');
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 to-gray-800 flex flex-col items-center justify-center p-6">
      <div className="w-full max-w-md mx-auto space-y-8">
        <div className="flex flex-col items-center space-y-2">
          <div className="bg-gray-800 p-3 rounded-full ring-2 ring-gray-700 shadow-lg">
            <img className="w-12 h-12" src={icon} alt="SurfSense" />
          </div>
          <h1 className="text-3xl font-semibold tracking-tight text-white mt-4">SurfSense</h1>
        </div>

        <div className="bg-gray-800/70 backdrop-blur-sm rounded-xl shadow-xl border border-gray-700 p-6">
          <div className="space-y-6">
            <h2 className="text-xl font-medium text-white">Enter your API Key</h2>
            <p className="text-gray-400 text-sm">
              Your API key connects this extension to the SurfSense.
            </p>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-2">
                <label htmlFor="apiKey" className="text-sm font-medium text-gray-300">
                  API Key
                </label>
                <input
                  type="text"
                  id="apiKey"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  className="w-full px-3 py-2 bg-gray-900/50 border border-gray-700 rounded-md focus:outline-none focus:ring-2 focus:ring-teal-500 text-white placeholder:text-gray-500"
                  placeholder="Enter your API key"
                />
                {error && (
                  <p className="text-red-400 text-sm mt-1">{error}</p>
                )}
              </div>

              <Button
                type="submit"
                disabled={loading}
                className="w-full bg-teal-600 hover:bg-teal-500 text-white py-2 px-4 rounded-md transition-colors"
              >
                {loading ? (
                  <>
                    <ReloadIcon className="mr-2 h-4 w-4 animate-spin" />
                    Verifying...
                  </>
                ) : (
                  "Connect"
                )}
              </Button>
            </form>

            <div className="text-center mt-4">
              <p className="text-sm text-gray-400">
                Need an API key?{" "}
                <a 
                  href="https://www.surfsense.net" 
                  target="_blank"
                  className="text-teal-400 hover:text-teal-300 hover:underline"
                >
                  Sign up
                </a>
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default ApiKeyForm
