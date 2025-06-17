"""
Google Places API integration for finding real medical clinics
"""
import requests
import os
from typing import Dict, List, Optional
import json

class GooglePlacesMedicalSearch:
    def __init__(self):
        self.api_key = os.environ.get('GOOGLE_PLACES_API_KEY')
        self.base_url = "https://maps.googleapis.com/maps/api/place"
        
    def search_medical_clinics_nearby(self, city: str, state: str, neighborhood: str, cep: str) -> Optional[Dict]:
        """
        Search for real medical clinics using Google Places API
        """
        try:
            if not self.api_key:
                print("ERROR: Google Places API key not configured")
                return None
                
            print(f"Searching for medical clinics in {neighborhood}, {city}, {state} using Google Places API")
                
            # First get coordinates for the location
            coordinates = self._get_coordinates(city, state, neighborhood, cep)
            if not coordinates:
                print(f"Could not get coordinates for {neighborhood}, {city}, trying direct text search")
                # Try direct text search without coordinates
                clinic = self._search_by_text(city, state, neighborhood)
                if clinic:
                    return clinic
                print("No coordinates and no text search results")
                return None
                
            # Search for medical clinics nearby
            clinic = self._search_nearby_clinics(coordinates, neighborhood)
            if clinic:
                return clinic
                
            # Fallback: search by text in the city
            return self._search_by_text(city, state, neighborhood)
            
        except Exception as e:
            print(f"ERROR in Google Places search: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    
    def _get_coordinates(self, city: str, state: str, neighborhood: str, cep: str) -> Optional[Dict]:
        """
        Get coordinates using Google Geocoding API
        """
        try:
            # Build address string
            address_parts = []
            if neighborhood and neighborhood.lower() != 'centro':
                address_parts.append(neighborhood)
            address_parts.extend([city, state, "Brazil"])
            
            if cep:
                address_parts.append(cep)
                
            address = ", ".join(address_parts)
            
            url = f"{self.base_url}/textsearch/json"
            params = {
                'query': address,
                'key': self.api_key,
                'language': 'pt-BR'
            }
            
            print(f"Getting coordinates for: {address}")
            response = requests.get(url, params=params, timeout=10)
            print(f"Coordinates API response status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"Coordinates API results: {len(data.get('results', []))}")
                if data.get('results'):
                    location = data['results'][0]['geometry']['location']
                    print(f"Found coordinates for {address}: {location['lat']}, {location['lng']}")
                    return {
                        'lat': location['lat'],
                        'lng': location['lng']
                    }
                else:
                    print(f"No results in coordinates response: {data}")
            else:
                print(f"Coordinates API error: {response.text}")
                    
        except Exception as e:
            print(f"Error getting coordinates: {e}")
            
        return None
    
    def _search_nearby_clinics(self, coordinates: Dict, neighborhood: str) -> Optional[Dict]:
        """
        Search for medical clinics near coordinates
        """
        try:
            url = f"{self.base_url}/nearbysearch/json"
            
            # Search terms for occupational health clinics
            search_types = [
                "medicina do trabalho",
                "saúde ocupacional", 
                "exames ocupacionais",
                "medicina ocupacional",
                "ASO"
            ]
            
            for search_term in search_types:
                params = {
                    'location': f"{coordinates['lat']},{coordinates['lng']}",
                    'radius': 15000,  # 15km radius
                    'keyword': search_term,
                    'type': 'hospital',
                    'key': self.api_key,
                    'language': 'pt-BR'
                }
                
                response = requests.get(url, params=params, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    
                    for place in data.get('results', []):
                        clinic = self._format_clinic_from_place(place)
                        if clinic and self._is_valid_medical_clinic(clinic):
                            print(f"Found clinic via nearby search: {clinic['nome']}")
                            return clinic
                            
        except Exception as e:
            print(f"Error in nearby search: {e}")
            
        return None
    
    def _search_by_text(self, city: str, state: str, neighborhood: str) -> Optional[Dict]:
        """
        Search by text query when nearby search fails
        """
        try:
            url = f"{self.base_url}/textsearch/json"
            
            # Build search queries
            queries = [
                f"clínica medicina do trabalho {city} {state}",
                f"saúde ocupacional {city}",
                f"exames ocupacionais {neighborhood} {city}",
                f"medicina ocupacional {city} {state}",
                f"ASO {city}"
            ]
            
            for query in queries:
                params = {
                    'query': query,
                    'key': self.api_key,
                    'language': 'pt-BR'
                }
                
                response = requests.get(url, params=params, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    
                    for place in data.get('results', []):
                        clinic = self._format_clinic_from_place(place)
                        if clinic and self._is_valid_medical_clinic(clinic):
                            print(f"Found clinic via text search: {clinic['nome']}")
                            return clinic
                            
        except Exception as e:
            print(f"Error in text search: {e}")
            
        return None
    
    def _format_clinic_from_place(self, place: Dict) -> Optional[Dict]:
        """
        Format Google Places result into clinic format
        """
        try:
            name = place.get('name', '')
            address = place.get('formatted_address', place.get('vicinity', ''))
            
            if not name or not address:
                return None
                
            # Extract city and neighborhood from address
            address_parts = address.split(', ')
            neighborhood = ""
            city = ""
            cep = ""
            
            # Try to extract CEP and city
            for part in address_parts:
                if '-' in part and len(part.replace('-', '').replace(' ', '')) == 8:
                    cep = part.strip()
                elif any(city_indicator in part.lower() for city_indicator in ['brasil', 'brazil']):
                    continue
                elif len(part.split()) <= 3 and part.strip():
                    if not city:
                        city = part.strip()
                    elif not neighborhood:
                        neighborhood = part.strip()
            
            # Get additional details if place_id available
            phone = ""
            if 'place_id' in place:
                details = self._get_place_details(place['place_id'])
                if details:
                    phone = details.get('formatted_phone_number', '')
            
            return {
                'nome': name,
                'endereco': address.split(',')[0].strip(),  # First part of address
                'bairro': neighborhood or "Centro",
                'cidade': city or "Cidade",
                'cep': cep or "00000-000",
                'telefone': phone or "(00) 0000-0000",
                'imagem': "https://images.unsplash.com/photo-1576091160399-112ba8d25d1f?w=400&h=300&fit=crop"
            }
            
        except Exception as e:
            print(f"Error formatting clinic: {e}")
            return None
    
    def _get_place_details(self, place_id: str) -> Optional[Dict]:
        """
        Get additional details for a place
        """
        try:
            url = f"{self.base_url}/details/json"
            params = {
                'place_id': place_id,
                'fields': 'formatted_phone_number,website',
                'key': self.api_key,
                'language': 'pt-BR'
            }
            
            response = requests.get(url, params=params, timeout=5)
            if response.status_code == 200:
                data = response.json()
                return data.get('result', {})
                
        except Exception as e:
            print(f"Error getting place details: {e}")
            
        return None
    
    def _is_valid_medical_clinic(self, clinic: Dict) -> bool:
        """
        Validate if the clinic is suitable for occupational health
        """
        name = clinic.get('nome', '').lower()
        address = clinic.get('endereco', '').lower()
        
        # Check for medical keywords
        medical_keywords = [
            'clínica', 'médic', 'saúde', 'hospital', 'centro', 
            'ambulatório', 'consultório', 'medicina', 'ocupacional',
            'trabalho', 'aso'
        ]
        
        has_medical_keyword = any(keyword in name for keyword in medical_keywords)
        
        # Exclude non-medical places
        exclude_keywords = [
            'farmácia', 'drogaria', 'laboratório', 'dentista',
            'veterinári', 'academia', 'hotel', 'restaurante'
        ]
        
        has_exclude_keyword = any(keyword in name for keyword in exclude_keywords)
        
        return has_medical_keyword and not has_exclude_keyword

def search_real_medical_clinics_google(city: str, state: str, neighborhood: str, cep: str) -> Optional[Dict]:
    """
    Main function to search for real medical clinics using Google Places
    """
    searcher = GooglePlacesMedicalSearch()
    return searcher.search_medical_clinics_nearby(city, state, neighborhood, cep)