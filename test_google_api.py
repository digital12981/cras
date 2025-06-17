"""
Test Google Places API directly
"""
import os
import requests

def test_google_places_api():
    api_key = os.environ.get('GOOGLE_PLACES_API_KEY')
    
    if not api_key:
        print("ERROR: No API key found")
        return
        
    print(f"Testing with API key: {api_key[:10]}...")
    
    # Test simple text search
    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params = {
        'query': 'clinica medicina do trabalho São Paulo',
        'key': api_key,
        'language': 'pt-BR'
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        print(f"Status code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Results found: {len(data.get('results', []))}")
            
            for i, place in enumerate(data.get('results', [])[:3]):
                print(f"Result {i+1}: {place.get('name')} at {place.get('formatted_address')}")
                
        else:
            print(f"Error response: {response.text}")
            
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    test_google_places_api()