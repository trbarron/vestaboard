import requests, time, json, random, html
import statsapi
from datetime import datetime
from config import VESTABOARD_API_KEY, WEATHER_API_KEY, WORD_API_KEY

HEADERS = {
    'Content-Type': 'application/json',
    'X-Vestaboard-Read-Write-Key': VESTABOARD_API_KEY
}

VESTABOARD_URL = 'https://rw.vestaboard.com/'
WEATHER_URL = 'https://api.openweathermap.org/data/2.5/forecast'
WORD_URL = 'https://api.wordnik.com/v4/words.json/wordOfTheDay'
OTD_URL = 'https://today.zenquotes.io/api'
BASEBALL_URL = f"http://lookup-service-prod.mlb.com/json/named.team_all_season.bam?sport_code='mlb'&all_star_sw='N'&sort_order=name_asc&season={datetime.now().year}"


# --------------


def getDenverWeather():
    params = {
        'lat': 39.76,
        'lon': -104.93,
        'appid': WEATHER_API_KEY
    }
    response = requests.get(WEATHER_URL, params=params)
    data = response.json()
    if data["cod"] == "200":
        weatherDesc = data["list"][0]["weather"][0]["main"]
        tempMax = data["list"][0]["main"]["temp_max"]
        temp = round((tempMax - 273.15) * (9/5) + 32, 1)
        return f"Weather:{weatherDesc}\nHigh:{temp}F"
    else:
        return "Error fetching weather"

def getOnThisDay():
    def cleanText(text):
        text = html.unescape(text)
        text = text.split('–', 1)[-1].strip()
        return text

    # Parse the JSON string to a Python dictionary
    apiResponse = requests.get(OTD_URL)
    data = apiResponse.json()

    # Extract the events, births, and deaths data
    events = data['data']['Events']
    births = data['data']['Births']
    deaths = data['data']['Deaths']

    # Combine all the text entries into a single list
    all_entries = events + births + deaths

    # Filter the entries to only include those with text under 120 characters
    short_entries = [cleanText(entry['text']) for entry in all_entries if len(entry['text']) < 119]

    # Pick a random entry from the filtered list
    if short_entries:
        random_entry = random.choice(short_entries)
        return(f"On this Day: {random_entry}")
    else:
        print("No entries found with text under 119 characters.")

def getWordOfTheDay():
    params = {'api_key': WORD_API_KEY}
    response = requests.get(WORD_URL, params=params)
    data = response.json()
    return f"{data['word']}:{data['definitions'][0]['text']}"[:40]

def getBaseballStats():
    teams = [111, 136, 115] # This is red sox, rockies & mariners
    team = random.choice(teams)
    most_recent_game_id = statsapi.last_game(team)
    bs_data = statsapi.boxscore_data(most_recent_game_id)

    homeTeam = bs_data["teamInfo"]["home"]["abbreviation"]
    awayTeam = bs_data["teamInfo"]["away"]["abbreviation"]
    homeScore = bs_data["homeBattingTotals"]["r"]
    awayScore = bs_data["awayBattingTotals"]["r"]
    
    return(f"{homeTeam} vs {awayTeam}\n {homeScore} to {awayScore}")

# --------------


def displayMessage(message):
    payload = json.dumps({'text': message})
    response = requests.post(VESTABOARD_URL, data=payload, headers=HEADERS)
    if response.status_code == 200:
        print(f"Displayed: {message}")
    else:
        print(f"Failed to display. Status code: {response.status_code}")

def getRandomDisplay():
    funcs = [
        getDenverWeather,
        # getWordOfTheDay,
        getOnThisDay,
        getBaseballStats
    ]
    selectedFunc = random.choice(funcs)
    displayMessage(selectedFunc())

if __name__ == "__main__":
    getRandomDisplay()
    while True:
        now = datetime.now()
        current_hour = now.hour

        # Check if the current time is within "quiet hours" (11pm to 6am)
        if current_hour >= 23 or current_hour < 6:
            time.sleep(3600)
        else:
            # Update at the top of each hour and at the 20 minute mark
            if now.minute == 0 or now.minute == 20 or now.minute == 40:
                getRandomDisplay()
                time.sleep(60)
            else:
                time.sleep(30)

