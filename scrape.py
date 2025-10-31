import requests
from bs4 import BeautifulSoup
import json
import sys
import time
from geopy.geocoders import Nominatim

def scrape_incidents():
    """
    Fetches the York County 911 incident page (ycdes.org) and scrapes the main table.
    Also geocodes the location of each incident.
    """
    URL = "https://www.ycdes.org/webcad/Default.aspx"
    
    # Initialize geocoder (Nominatim is free, requires a user agent)
    # We add a 1.1 second delay between queries to respect their terms of service.
    geolocator = Nominatim(user_agent="york_incident_mapper_v1")
    
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

        # Find the H2 tag with the text "Active Incidents"
        header = soup.find('h2', string='Active Incidents')

        if not header:
            print("Error: Could not find the 'Active Incidents' header (H2 tag).", file=sys.stderr)
            debug_filename = "debug_page.html"
            try:
                with open(debug_filename, "w", encoding="utf-8") as f:
                    f.write(response.text)
                print(f"--- DEBUG INFO: Saved HTML to '{debug_filename}' for inspection. ---", file=sys.stderr)
            except Exception as e:
                print(f"Could not write debug file: {e}", file=sys.stderr)
            return None

        # Find the *next* table tag immediately following the header
        table = header.find_next_sibling('table', class_='incidentList')

        if not table:
            print("Error: Found 'Active Incidents' header but could not find the 'incidentList' table immediately after it.", file=sys.stderr)
            debug_filename = "debug_page.html"
            try:
                with open(debug_filename, "w", encoding="utf-8") as f:
                    f.write(response.text)
                print(f"--- DEBUG INFO: Saved HTML to '{debug_filename}' for inspection. ---", file=sys.stderr)
            except Exception as e:
                print(f"Could not write debug file: {e}", file=sys.stderr)
            return None

        incidents = []
        
        # Find all table rows 'tr' in the table body
        # We skip the first row [1:] because it's the header
        for row in table.find_all('tr')[1:]:
            # Find all cells 'td' in the current row
            cells = row.find_all('td')
            
            # Ensure the row has the correct number of cells (at least 8)
            if len(cells) >= 8:
                incident = {
                    'type_general': cells[0].text.strip(),
                    'dispatch_time': cells[1].text.strip(),
                    'box_no': cells[2].text.strip(),
                    'type_specific': cells[3].text.strip(),
                    'street': cells[4].text.strip(),
                    'cross_street': cells[5].text.strip(),
                    'nearest_intersection': cells[6].text.strip(),
                    'location_township': cells[7].text.strip()
                }

                # --- Geocoding Step ---
                # Build a location string for the geocoder.
                # Use nearest_intersection if available, otherwise fall back to street.
                loc_str = incident['nearest_intersection']
                if not loc_str:
                    loc_str = incident['street']
                
                # Add township and state for better accuracy
                # NOTE: The data (YORK CITY, MANCHESTER TWP) indicates York County, PENNSYLVANIA, not Virginia.
                full_address = f"{loc_str}, {incident['location_township']}, York County, VA"
                
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

