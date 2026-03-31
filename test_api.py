"""
Quick test script to verify API endpoints are working.
Run this after starting the server to test all endpoints.

Usage:
    python test_api.py
"""

import requests
import json
import time

BASE_URL = "http://localhost:8000"
TIMEOUT = 5

def print_section(title):
    """Print a formatted section header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def test_health_check():
    """Test health check endpoint."""
    print_section("1. HEALTH CHECK")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=TIMEOUT)
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_get_companies():
    """Test get all companies endpoint."""
    print_section("2. GET ALL COMPANIES")
    try:
        response = requests.get(f"{BASE_URL}/companies", timeout=TIMEOUT)
        print(f"Status: {response.status_code}")
        data = response.json()
        print(f"Total companies: {len(data)}")
        if data:
            print(f"First company: {json.dumps(data[0], indent=2)}")
        return response.status_code == 200 and len(data) > 0
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_get_company_details():
    """Test get company details endpoint."""
    print_section("3. GET COMPANY DETAILS (INFY)")
    try:
        response = requests.get(f"{BASE_URL}/companies/INFY", timeout=TIMEOUT)
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_get_stock_data():
    """Test get stock data endpoint."""
    print_section("4. GET STOCK DATA (INFY - Last 30 Days)")
    try:
        response = requests.get(
            f"{BASE_URL}/data/INFY?days=30",
            timeout=TIMEOUT
        )
        print(f"Status: {response.status_code}")
        data = response.json()
        print(f"Total records: {len(data)}")
        if data:
            print(f"First record: {json.dumps(data[0], indent=2)}")
            print(f"Latest record: {json.dumps(data[-1], indent=2)}")
        return response.status_code == 200 and len(data) > 0
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_get_stock_summary():
    """Test get stock summary endpoint."""
    print_section("5. GET STOCK SUMMARY (INFY - 52 Weeks)")
    try:
        response = requests.get(
            f"{BASE_URL}/summary/INFY",
            timeout=TIMEOUT
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_compare_stocks():
    """Test compare stocks endpoint."""
    print_section("6. COMPARE TWO STOCKS (INFY vs TCS)")
    try:
        response = requests.get(
            f"{BASE_URL}/compare/?symbol1=INFY&symbol2=TCS&days=30",
            timeout=TIMEOUT
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_top_gainers():
    """Test top gainers endpoint."""
    print_section("7. TOP GAINERS (Last 1 Day)")
    try:
        response = requests.get(
            f"{BASE_URL}/analytics/top-gainers?days=1&limit=5",
            timeout=TIMEOUT
        )
        print(f"Status: {response.status_code}")
        data = response.json()
        print(f"Response: {json.dumps(data, indent=2)}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_top_losers():
    """Test top losers endpoint."""
    print_section("8. TOP LOSERS (Last 1 Day)")
    try:
        response = requests.get(
            f"{BASE_URL}/analytics/top-losers?days=1&limit=5",
            timeout=TIMEOUT
        )
        print(f"Status: {response.status_code}")
        data = response.json()
        print(f"Response: {json.dumps(data, indent=2)}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_companies_overview():
    """Test companies overview endpoint."""
    print_section("9. COMPANIES OVERVIEW")
    try:
        response = requests.get(
            f"{BASE_URL}/companies/stats/overview",
            timeout=TIMEOUT
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("  STOCK DASHBOARD API - TEST SUITE")
    print("="*60)
    print(f"\nTarget URL: {BASE_URL}")
    print("\nTesting all endpoints...\n")
    
    tests = [
        ("Health Check", test_health_check),
        ("Get Companies", test_get_companies),
        ("Get Company Details", test_get_company_details),
        ("Get Stock Data", test_get_stock_data),
        ("Get Stock Summary", test_get_stock_summary),
        ("Compare Stocks", test_compare_stocks),
        ("Top Gainers", test_top_gainers),
        ("Top Losers", test_top_losers),
        ("Companies Overview", test_companies_overview),
    ]
    
    results = {}
    for test_name, test_func in tests:
        results[test_name] = test_func()
        time.sleep(0.5)  # Small delay between requests
    
    # Print summary
    print_section("TEST SUMMARY")
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed\n")
    
    if passed == total:
        print("🎉 All tests passed! API is working correctly.\n")
        return 0
    else:
        print("⚠️  Some tests failed. Check the output above.\n")
        return 1


if __name__ == "__main__":
    import sys
    
    # Check if server is running
    try:
        requests.get(BASE_URL, timeout=2)
    except Exception:
        print("\n❌ ERROR: Cannot connect to server at", BASE_URL)
        print("\nmake sure the API server is running:")
        print("  1. Open a terminal")
        print("  2. Navigate to the project directory")
        print("  3. Activate venv: .\\venv\\Scripts\\activate")
        print("  4. Run server: python main.py")
        print("\nThen run this test again.\n")
        sys.exit(1)
    
    sys.exit(main())
