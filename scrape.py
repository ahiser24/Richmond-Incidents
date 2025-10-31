import requests
from bs4 import BeautifulSoup
import json
import sys
import time
from geopy.geocoders import Nominatim

def scrape_incidents():
    """
    Fetches the Richmond, VA active calls page and scrapes the main table.
    Also geocodes the location of each incident.
    """
    URL = "https://apps.richmondgov.com/applications/activecalls/Home/ActiveCalls"
    
    # Initialize geocoder (Nominatim is free, requires a user agent)
    # We add a 1.1 second delay between queries to respect their terms of service.
    geolocator = Nominatim(user_agent="richmond_incident_mapper_v1")
    
    # Set headers to mimic a real browser request
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    print(f"Attempting to fetch data from {URL}...", file=sys.stderr)

    try:
        # Fetch the page content
        response = requests.get(URL, headers=headers, timeout=10)
        
        # Check for HTTP errors
        response.raise_for_status() 
        print("Successfully fetched page.", file=sys.stderr)

        # Parse the HTML content
        soup = BeautifulSoup(response.text, 'html.parser')

        table = soup.find('table')

        if not table:
            print("Error: Could not find the data table.", file=sys.stderr)
            return None

        incidents = []
        
        for row in table.find_all('tr')[1:]:
            cells = row.find_all('td')
            
            if len(cells) >= 7:
                incident = {
                    'type_general': cells[1].text.strip(),
                    'dispatch_time': cells[0].text.strip(),
                    'box_no': cells[2].text.strip(),
                    'type_specific': cells[4].text.strip(),
                    'street': cells[5].text.strip(),
                    'cross_street': '',
                    'nearest_intersection': '',
                    'location_township': cells[2].text.strip()
                }

                # --- Geocoding Step ---
                cleaned_street = incident['street'].replace('-BLK', '00').strip()
                full_address = f"{cleaned_street}, Richmond, VA"
                
                print(f"Geocoding: {full_address}", file=sys.stderr)
                
                try:
                    location = geolocator.geocode(full_address, timeout=5)
                    if location:
                        incident['lat'] = location.latitude
                        incident['lng'] = location.longitude
                        print(f"-> Found: ({location.latitude}, {location.longitude})", file=sys.stderr)
                    else:
                        incident['lat'] = None
                        incident['lng'] = None
                        print(f"-> Warning: Could not geocode address: {full_address}", file=sys.stderr)
                except Exception as e:
                    print(f"-> Geocoding Error: {e}", file=sys.stderr)
                    incident['lat'] = None
                    incident['lng'] = None

                incidents.append(incident)
                
                # --- Rate Limiting ---
                # IMPORTANT: Pause for 1.1s to respect Nominatim's (1 req/sec) free usage policy.
                time.sleep(1.1) 
        
        print(f"Found and geocoded {len(incidents)} incidents.", file=sys.stderr)
        return incidents

    except requests.exceptions.HTTPError as errh:
        print(f"Http Error: {errh}", file=sys.stderr)
    except requests.exceptions.ConnectionError as errc:
        print(f"Error Connecting: {errc}", file=sys.stderr)
    except requests.exceptions.Timeout as errt:
        print(f"Timeout Error: {errt}", file=sys.stderr)
    except requests.exceptions.RequestException as err:
        print(f"An unexpected error occurred: {err}", file=sys.stderr)
    
    return None

if __name__ == "__main__":
    incident_data = scrape_incidents()
    
    if incident_data:
        # Convert the list of incidents to a JSON string and print it
        json_output = json.dumps(incident_data, indent=2)
        print(json_output)

        # ---- Write to incidents.json ----
        output_file = "incidents.json"
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(json_output)
            print(f"--- INFO: Incident data written to '{output_file}'. ---", file=sys.stderr)
        except Exception as e:
            print(f"Could not write to '{output_file}': {e}", file=sys.stderr)
    else:
        print("No incident data was scraped.", file=sys.stderr)

