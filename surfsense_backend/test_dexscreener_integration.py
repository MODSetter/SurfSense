#!/usr/bin/env python3
"""
Integration test script for DexScreener Connector API endpoints.
Tests the complete workflow: login → add connector → test endpoint → verify.
"""

import requests
import json
import sys

BASE_URL = "http://localhost:8000"

def login(email: str, password: str) -> str:
    """Login and return JWT access token."""
    print(f"🔐 Logging in as {email}...")
    response = requests.post(
        f"{BASE_URL}/auth/jwt/login",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    
    if response.status_code != 200:
        print(f"❌ Login failed: {response.status_code}")
        print(response.text)
        sys.exit(1)
    
    data = response.json()
    token = data.get("access_token")
    print(f"✅ Login successful! Token: {token[:50]}...")
    return token

def test_add_connector(token: str, space_id: int = 1) -> dict:
    """Test adding a DexScreener connector."""
    print(f"\n📝 Testing POST /api/v1/connectors/dexscreener/add...")
    
    payload = {
        "tokens": [
            {
                "chain": "ethereum",
                "address": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
                "name": "WETH"
            },
            {
                "chain": "ethereum",
                "address": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
                "name": "USDT"
            }
        ],
        "space_id": space_id
    }
    
    response = requests.post(
        f"{BASE_URL}/api/v1/connectors/dexscreener/add",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code in [200, 201]:
        print("✅ Add connector successful!")
    else:
        print(f"⚠️  Add connector returned {response.status_code}")
    
    return response.json()

def test_test_endpoint(token: str, space_id: int = 1) -> dict:
    """Test the test endpoint (fetches live data from DexScreener API)."""
    print(f"\n🧪 Testing GET /api/v1/connectors/dexscreener/test...")
    
    response = requests.get(
        f"{BASE_URL}/api/v1/connectors/dexscreener/test",
        params={"space_id": space_id},
        headers={"Authorization": f"Bearer {token}"}
    )
    
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Test endpoint successful!")
        print(f"Message: {data.get('message', 'N/A')}")
        print(f"Tokens configured: {data.get('tokens_count', 0)}")
        
        if data.get('sample_pair'):
            pair = data['sample_pair']
            print(f"\nSample Pair Data:")
            print(f"  - Base: {pair.get('baseToken', {}).get('symbol')}")
            print(f"  - Quote: {pair.get('quoteToken', {}).get('symbol')}")
            print(f"  - Price: ${pair.get('priceUsd', 'N/A')}")
            print(f"  - 24h Volume: ${pair.get('volume', {}).get('h24', 'N/A')}")
    else:
        print(f"⚠️  Test endpoint returned {response.status_code}")
        print(response.text)
    
    return response.json() if response.status_code == 200 else {}

def main():
    print("=" * 60)
    print("DexScreener Connector Integration Test")
    print("=" * 60)
    
    # Step 1: Login
    token = login("dextest@surfsense.dev", "TestPass123!")
    
    # Step 2: Test add connector
    add_result = test_add_connector(token)
    
    # Step 3: Test test endpoint (with space_id)
    test_result = test_test_endpoint(token, space_id=1)
    
    print("\n" + "=" * 60)
    print("✅ Integration Test Complete!")
    print("=" * 60)
    print("\nSummary:")
    print("  - Login: ✅")
    print("  - Add Connector: ✅" if add_result else "  - Add Connector: ⚠️")
    print("  - Test Endpoint: ✅" if test_result else "  - Test Endpoint: ⚠️")

if __name__ == "__main__":
    main()
