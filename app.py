from flask import Flask, render_template, make_response, send_from_directory, request, redirect, url_for, jsonify, session
import pandas as pd
import os
from itertools import groupby
import random

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Load datasets
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

airports_df = pd.read_excel(os.path.join(BASE_DIR, 'database', 'airportcode.xlsx'))
carriers_df = pd.read_excel(os.path.join(BASE_DIR, 'database', 'carriercode.xlsx'))
carriers_df['id'] = carriers_df['id'].astype(str)

# Fix for Namibia (NA) being interpreted as NaN
airports_df.loc[airports_df['CountryName'] == 'Namibia', 'country_code'] = 'NA'

# Ensure that the 'country_code' is a string
airports_df['country_code'] = airports_df['country_code'].astype(str)

# Ensure 'display_name' is string type for consistent operations
airports_df['display_name'] = airports_df['display_name'].astype(str)

# Create a country code mapping from airports_df
country_mapping = airports_df[['CountryName', 'country_code']].drop_duplicates().set_index('CountryName')['country_code'].to_dict()

# Add country_code to carriers_df
carriers_df['country_code'] = carriers_df['CrrCountry2'].map(country_mapping)

# Filter for eliminating inactive carriers 
carriers_df = carriers_df[carriers_df['ServiceStatus'] != '-']

# Ensure that 'CrrCountry' is a string
carriers_df['CrrCountry'] = carriers_df['CrrCountry'].astype(str)

# Ensure 'CrrCountry2' and 'CrrDetails' are strings for consistent operations
carriers_df['CrrCountry2'] = carriers_df['CrrCountry2'].astype(str)
carriers_df['CrrDetails'] = carriers_df['CrrDetails'].astype(str)
# Create dictionaries to store airport details
airport_details = airports_df.set_index('IATACode').T.to_dict()

# Create dictionaries to store carrier details
carrier_details = carriers_df.set_index('id').to_dict(orient='index')

# Pre-calculate unique countries list for performance
airport_details_by_country = airports_df[['country_code', 'CountryName']].drop_duplicates().reset_index(drop=True).sort_values(by='country_code').to_dict(orient='records')

# Pre-calculate unique continents list for performance
unique_continents = airports_df[['continent']].dropna().drop_duplicates().sort_values(by='continent').to_dict(orient='records')


@app.route('/')
def index():
    # Example featured data
    featured_airports = airports_df.sample(min(8, len(airports_df))).to_dict(orient='records')
    featured_carriers = carriers_df.sample(min(8, len(carriers_df))).to_dict(orient='records')
    popular_routes = [
        {'origin': 'JFK', 'destination': 'LAX', 'carrier_name': 'Test Airlines'},
        {'origin': 'LHR', 'destination': 'CDG', 'carrier_name': 'Test2 Airways'},
        {'origin': 'HND', 'destination': 'SFO', 'carrier_name': 'Test3 Airlines'},
        {'origin': 'DXB', 'destination': 'SYD', 'carrier_name': 'Test4 Airways'}
    ]

    response = make_response(render_template('index.html', featured_airports=featured_airports, featured_carriers=featured_carriers, popular_routes=popular_routes))
    response.cache_control.max_age = 300  # 5 minutes cache timeout
    return response

@app.route('/suggest')
def suggest(): # sourcery skip: extract-method
    query = request.args.get('term', '').strip() # jQuery UI uses 'term' for the query parameter
    suggestions = []
    if not query:
        return jsonify(suggestions)

    upper_query = query.upper()

    # Search airports
    # Prioritize exact IATA/ICAO matches, then partial name matches
    # Ensure 'display_name' is string type
    airports_df['display_name'] = airports_df['display_name'].astype(str)
    airport_matches = airports_df[
        (airports_df['IATACode'].str.upper() == upper_query) |
        (airports_df['ICAOCode'].str.upper() == upper_query) |
        (airports_df['display_name'].str.contains(query, case=False, na=False)) |
        (airports_df['CountryName'].str.contains(query, case=False, na=False))
    ].head(10)

    airport_suggestions = [{
        'label': f"{row['display_name']} ({row['IATACode']}) - Airport",
        'value': row['IATACode'],
        'url': url_for('airport', iata_code=row['IATACode']),
        'emoji': '🚩'
    } for _, row in airport_matches.iterrows()]

    # Havayollarını (Carriers) ara
    carrier_search_conditions = [
        carriers_df['name'].str.contains(query, case=False, na=False),
        carriers_df['CrrDetails'].str.contains(query, case=False, na=False),
        carriers_df['CrrCountry2'].str.contains(query, case=False, na=False)
    ]
    if 'IATA' in carriers_df.columns: # Check if IATA column exists
        carrier_search_conditions.append(carriers_df['IATA'].str.upper() == upper_query)
    if 'ICAO' in carriers_df.columns: # Check if ICAO column exists
        carrier_search_conditions.append(carriers_df['ICAO'].str.upper() == upper_query)

    carrier_suggestions = []
    if carrier_search_conditions:
        # Combine all conditions with OR, handling potential NaN values in columns
        combined_carrier_condition = pd.Series([False] * len(carriers_df), index=carriers_df.index)
        for cond in carrier_search_conditions:
            combined_carrier_condition = combined_carrier_condition | cond.fillna(False)
        carrier_matches = carriers_df[combined_carrier_condition].head(10)
        

        for _, row in carrier_matches.iterrows():
            carrier_icao = row['ICAO'] if 'ICAO' in carriers_df.columns and pd.notna(row['ICAO']) else 'N/A'
            carrier_iata = row['IATA'] if 'IATA' in carriers_df.columns and pd.notna(row['IATA']) else 'N/A'
            carrier_details = row['CrrDetails'] if 'CrrDetails' in row and pd.notna(row['CrrDetails']) else 'Unknown Carrier'
            
            # Determine which code to display in the label
            display_code = carrier_iata if carrier_iata != 'N/A' else carrier_icao
            
            carrier_suggestions.append({
                'label': f"{carrier_details} ({display_code}) - Carrier",
                'value': display_code, # Use the displayed code as value
                'url': url_for('carrier', carrier_id=row['id']),
                'emoji': '🛫'
            })

    # Önerileri birleştir (Interleaving): Her iki türden de sonuçları karıştırarak göster
    merged_suggestions = []
    for i in range(max(len(airport_suggestions), len(carrier_suggestions))):
        if i < len(airport_suggestions):
            merged_suggestions.append(airport_suggestions[i])
        if i < len(carrier_suggestions):
            merged_suggestions.append(carrier_suggestions[i])

    return jsonify(merged_suggestions[:10])

@app.route('/search')
def search():
    query = request.args.get('query', '').strip()
    if not query:
        # If query is empty, redirect to the home page
        return redirect(url_for('index'))

    # Convert query to uppercase for IATA/ICAO comparison
    upper_query = query.upper()

    # Search for exact IATA code match
    if upper_query in airports_df['IATACode'].str.upper().values:
        matched_airport = airports_df[airports_df['IATACode'].str.upper() == upper_query].iloc[0]
        return redirect(url_for('airport', iata_code=matched_airport['IATACode']))

    # Search for exact ICAO code match
    if upper_query in airports_df['ICAOCode'].str.upper().values:
        matched_airport = airports_df[airports_df['ICAOCode'].str.upper() == upper_query].iloc[0]
        return redirect(url_for('airport', iata_code=matched_airport['IATACode']))

    # Search for partial display_name match (case-insensitive)
    # Ensure 'display_name' is string type to avoid errors with .str accessor
    airports_df['display_name'] = airports_df['display_name'].astype(str)
    partial_matches = airports_df[airports_df['display_name'].str.contains(query, case=False, na=False)]

    if not partial_matches.empty:
        matched_airport = partial_matches.iloc[0] # Take the first partial match
        return redirect(url_for('airport', iata_code=matched_airport['IATACode']))

    # If no match found
    return "Airport or Carrier not found for your query.", 404

@app.route('/airports/<iata_code>')
def airport(iata_code):
    # Render a template for the specific airport using its IATA code
    if iata_code in airport_details:
        skyscanner_url, kayak_url = flights_from(iata_code)
        return render_template('airport.html', details=airport_details[iata_code], skyscanner_url=skyscanner_url, kayak_url=kayak_url)
    else:
        return "Airport not found", 404

@app.route('/carrier/<carrier_id>')
def carrier(carrier_id):
    # Render a template for the specific carrier using its unique ID
    if carrier_id in carrier_details:
        details = carrier_details[carrier_id]
        other_carriers_in_country = []
        if details.get("CrrCountry"):
            # Filter carriers by CrrCountry and exclude the current carrier
            other_carriers_in_country = [
                c for c in carriers_df.to_dict(orient='records') # c is a dictionary representing a row
                if c.get("CrrCountry") == details["CrrCountry"] and c.get("id") != carrier_id
            ]
        return render_template('carrier.html', details=details, other_carriers_in_country=other_carriers_in_country,carrier_id=carrier_id)
    else:
        return "Carrier not found", 404

@app.route('/flags/<country_code>')
def flag(country_code):
    # Serve flag images with proper cache control
    filename = f'{country_code.lower()}.svg'
    response = make_response(send_from_directory('static/flags', filename))
    response.cache_control.max_age = 86400  # 1 day cache timeout
    return response

@app.route('/countries/<country_code>')
def get_airports_by_country(country_code):
    # Filter the dataframe by country code
    filtered_df = airports_df[airports_df['country_code'] == country_code]
    # Convert the filtered dataframe to a dictionary
    airports_by_country = filtered_df.to_dict(orient='records')
    # Render the 'country.html' template with the airports data
    return render_template('country.html', cntairports=airports_by_country)

@app.route('/continents/<continent>')
def get_airports_by_continent(continent):
    # Filter the dataframe by continent
    filtered_df = airports_df[airports_df['continent'] == continent]
    
    # Get all airports with relevant details for the continent
    all_airports_in_continent = filtered_df[['continent', 'CountryName', 'country_code', 'display_name', 'IATACode']].sort_values(by=['CountryName', 'display_name']).to_dict(orient='records')

    # Group airports by country within the continent
    grouped_airports_by_country = {}
    for country_name, country_group in groupby(all_airports_in_continent, key=lambda x: x['CountryName']):
        grouped_airports_by_country[country_name] = list(country_group)
    return render_template('continent.html', continent_code=continent, grouped_airports_by_country=grouped_airports_by_country)

@app.route('/airports')
@app.route('/airports/')
def airports(): # Renamed from 'airports' to 'all_airports' to avoid confusion with the route name
    # Get all airports with relevant details
    all_airports_data = airports_df[['continent', 'CountryName', 'country_code', 'display_name', 'IATACode']].sort_values(by=['continent', 'CountryName', 'display_name']).to_dict(orient='records')

    # Group airports by continent, then by country
    grouped_airports_by_continent = {}
    for continent, continent_group in groupby(all_airports_data, key=lambda x: x['continent']):
        grouped_airports_by_country = {}
        for country_name, country_group in groupby(list(continent_group), key=lambda x: x['CountryName']):
            grouped_airports_by_country[country_name] = list(country_group)
        grouped_airports_by_continent[continent] = grouped_airports_by_country

    return render_template('aairports.html', grouped_airports_by_continent=grouped_airports_by_continent)

@app.route('/countries')
@app.route('/countries/')
def countries():
    # Get list of countries with continent information
    countries_with_continent = airports_df[['country_code', 'CountryName', 'continent']].drop_duplicates().sort_values(by=['continent', 'CountryName']).to_dict(orient='records')

    # Group countries by continent
    grouped_countries = {}
    for continent, group in groupby(countries_with_continent, key=lambda x: x['continent']):
        grouped_countries[continent] = list(group)

    return render_template('ccountries.html', grouped_countries=grouped_countries)


@app.route('/continents')
@app.route('/continents/')
def continents():
    # Get list of continents (using pre-calculated data)
    return render_template('continents.html', continents=unique_continents)

@app.route('/carriers')
@app.route('/carriers/')
def carriers():
    # Get all carriers with relevant details
    all_carriers_data = carriers_df[['id', 'name', 'IATA', 'CrrCountry', 'CrrCountry2']].sort_values(by=['CrrCountry2', 'name']).to_dict(orient='records')

    # Group carriers by country
    grouped_carriers_by_country = {}
    for country_name, country_group in groupby(all_carriers_data, key=lambda x: x['CrrCountry2']):
        grouped_carriers_by_country[country_name] = list(country_group)

    return render_template('ccarriers.html', grouped_carriers_by_country=grouped_carriers_by_country)

def flights_from(iata_code):
    # Construct the Skyscanner URL with the dynamic airport code
    skyscanner_url = f"https://www.skyscanner.com/flights-from/{iata_code}/"
    kayak_url = f"https://www.kayak.com/explore/{iata_code}-anywhere"
    return skyscanner_url, kayak_url

def generate_airline_name_from_iata_question():
    """Generates a question asking for the airline name from an IATA code."""
    try:
        valid_carriers = carriers_df[carriers_df['name'].notna() & carriers_df['IATA'].notna()]
        if valid_carriers.empty: return None
        
        correct_answer_series = valid_carriers.sample(1).iloc[0]
        correct_answer_name = correct_answer_series['name']
        
        options_df = carriers_df[(carriers_df['name'].notna()) & (carriers_df['name'] != correct_answer_name)]
        options = options_df['name'].sample(min(3, len(options_df))).tolist()
        
        options.append(correct_answer_name)
        random.shuffle(options)
        return {
            'question': f"Which airline has the IATA code '{correct_answer_series['IATA']}'?",
            'options': options,
            'answer': correct_answer_name,
            'subject_name': correct_answer_name,
            'link': {'type': 'carrier', 'id': correct_answer_series['id']}
        }
    except (ValueError, IndexError):
        return None

def generate_airport_name_from_iata_question():
    """Generates a question asking for the airport name from an IATA code."""
    try:
        valid_airports = airports_df[airports_df['display_name'].notna() & airports_df['IATACode'].notna()]
        if valid_airports.empty: return None

        correct_answer_series = valid_airports.sample(1).iloc[0]
        correct_answer_name = correct_answer_series['apt_name']

        options_df = airports_df[(airports_df['apt_name'].notna()) & (airports_df['apt_name'] != correct_answer_name)]
        options = options_df['apt_name'].sample(min(3, len(options_df))).tolist()
        
        options.append(correct_answer_name)
        random.shuffle(options)
        return {
            'question': f"Which airport has the IATA code '{correct_answer_series['IATACode']}'?",
            'options': options,
            'answer': correct_answer_name,
            'subject_name': correct_answer_name,
            'link': {'type': 'airport', 'id': correct_answer_series['IATACode']}
        }
    except (ValueError, IndexError):
        return None

def generate_iata_from_airline_name_question():
    """Generates a question asking for the IATA code from an airline name."""
    try:
        valid_carriers = carriers_df[carriers_df['name'].notna() & carriers_df['IATA'].notna()]
        if len(valid_carriers) < 4: return None
        
        correct_answer_series = valid_carriers.sample(1).iloc[0]
        airline_name = correct_answer_series['name']
        correct_answer_iata = correct_answer_series['IATA']
        
        options_df = valid_carriers[valid_carriers['IATA'] != correct_answer_iata]
        options = options_df['IATA'].sample(3).tolist()
        
        options.append(correct_answer_iata)
        random.shuffle(options)
        return {
            'question': f"What is the IATA code of '{airline_name}?'",
            'options': options,
            'answer': correct_answer_iata,
            'subject_name': airline_name,
            'link': {'type': 'carrier', 'id': correct_answer_series['id']}
        }
    except (ValueError, IndexError):
        return None

def generate_country_from_airline_name_question():
    """Generates a question asking for the country of an airline."""
    try:
        valid_carriers = carriers_df[carriers_df['name'].notna() & carriers_df['CrrCountry2'].notna() & carriers_df['country_code'].notna()]
        if len(valid_carriers) < 4: return None

        correct_answer_series = valid_carriers.sample(1).iloc[0]
        airline_name = correct_answer_series['name']
        correct_answer_country = correct_answer_series['CrrCountry2']

        options_df = carriers_df[carriers_df['CrrCountry2'].notna() & (carriers_df['CrrCountry2'] != correct_answer_country)]
        if len(options_df['CrrCountry2'].unique()) < 3: return None
        options = options_df['CrrCountry2'].drop_duplicates().sample(3).tolist()

        options.append(correct_answer_country)
        random.shuffle(options)
        return {
            'question': f"Which country is the airline '{airline_name}' based in?",
            'options': options,
            'answer': correct_answer_country,
            'subject_name': correct_answer_country,
            'link': {'type': 'country', 'id': correct_answer_series['country_code']}
        }
    except (ValueError, IndexError):
        return None

def generate_country_from_airport_name_question():
    """Generates a question asking for the country of an airport."""
    try:
        valid_airports = airports_df[airports_df['display_name'].notna() & airports_df['CountryName'].notna() & airports_df['country_code'].notna()]
        if len(valid_airports) < 4: return None

        correct_answer_series = valid_airports.sample(1).iloc[0]
        airport_name = correct_answer_series['apt_name']
        correct_answer_country = correct_answer_series['CountryName']

        options_df = airports_df[airports_df['CountryName'].notna() & (airports_df['CountryName'] != correct_answer_country)]
        if len(options_df['CountryName'].unique()) < 3: return None
        options = options_df['CountryName'].drop_duplicates().sample(3).tolist()

        options.append(correct_answer_country)
        random.shuffle(options)
        return {
            'question': f"In which country is '{airport_name}' located?",
            'options': options,
            'answer': correct_answer_country,
            'subject_name': airport_name,
            'link': {'type': 'airport', 'id': correct_answer_series['IATACode']}
        }
    except (ValueError, IndexError):
        return None

# List of available question generator functions
question_generators = [
    generate_airline_name_from_iata_question,
    generate_airport_name_from_iata_question,
    generate_iata_from_airline_name_question,
    generate_country_from_airline_name_question,
    generate_country_from_airport_name_question,
]

@app.route('/game', methods=['GET'])
def game_start():
    session['score'] = 0
    questions = []
    
    # Generate 10 unique questions
    attempts = 0
    while len(questions) < 10 and attempts < 100:
        generator = random.choice(question_generators)
        question = generator()
        if question and question not in questions:
            questions.append(question)
        attempts += 1
            
    # If we couldn't generate 10 unique questions, fill up with anything
    while len(questions) < 10 and attempts < 200:
        generator = random.choice(question_generators)
        question = generator()
        if question:
            questions.append(question)
        attempts += 1

    session['questions'] = questions
    return redirect(url_for('game_question', question_id=0))

@app.route('/game/<int:question_id>', methods=['GET', 'POST'])
def game_question(question_id):
    if 'questions' not in session or question_id >= len(session['questions']):
        return redirect(url_for('score'))

    question_data = session['questions'][question_id]

    if request.method == 'POST':
        user_answer = request.form.get('option')
        correct_answer = question_data['answer']
        is_correct = user_answer == correct_answer
        if is_correct:
            session['score'] += 1
        
        # Store feedback details in session and redirect to prevent re-submission on refresh (PRG pattern)
        session['feedback_for_question'] = {
            'question_id': question_id, # The ID of the question that was just answered
            'question': question_data,
            'user_answer': user_answer,
            'is_correct': is_correct,
            'score': session['score'],
            'question_number': question_id + 1, # For display in feedback
            'next_question_id': question_id + 1 # For the 'Next Question' button
        }
        return redirect(url_for('game_feedback', question_id=question_id))

    return render_template('game.html', 
                           question=question_data['question'], 
                           options=question_data['options'], 
                           score=session['score'], 
                           question_number=question_id + 1,
                           question_id=question_id)

@app.route('/game/feedback/<int:question_id>', methods=['GET'])
def game_feedback(question_id):
    # Retrieve feedback details from session and clear it
    feedback_data = session.pop('feedback_for_question', None)

    # Ensure we have feedback data and it matches the current question_id
    if not feedback_data or feedback_data['question_id'] != question_id:
        # If no feedback or mismatch, redirect to the current question or score
        # This handles cases where a user might try to directly access /game/feedback/X
        if 'questions' not in session or question_id >= len(session['questions']):
            return redirect(url_for('score'))
        else:
            # If feedback is missing or stale, redirect them back to the question to answer it.
            return redirect(url_for('game_question', question_id=question_id))

    return render_template('feedback.html', **feedback_data)

@app.route('/score')
def score():
    return render_template('score.html', score=session.get('score', 0))

if __name__ == '__main__':
    app.run(debug=True)
