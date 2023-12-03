import requests, time, json, re
from datetime import datetime, timezone, timedelta
from config import VESTABOARD_API_KEY, WEATHER_API_KEY, RAPID_API_KEY

HEADERS = {
    'Content-Type': 'application/json',
    'X-Vestaboard-Read-Write-Key': VESTABOARD_API_KEY
}

VESTABOARD_URL = 'https://rw.vestaboard.com/'
WEATHER_URL = 'https://api.openweathermap.org/data/2.5/forecast'
WORD_URL = 'https://api.wordnik.com/v4/words.json/wordOfTheDay'
OTD_URL = 'https://today.zenquotes.io/api'
BASEBALL_URL = f"http://lookup-service-prod.mlb.com/json/named.team_all_season.bam?sport_code='mlb'&all_star_sw='N'&sort_order=name_asc&season={datetime.now().year}"
BASKETBALL_URL = f"https://api-basketball.p.rapidapi.com/games"

sleeping = False
basketballSchedule = False
updateCountdown = 0
basketballScheduleCountdown = 0
gameOn = False

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
        percipChance = data["list"][0]["pop"]
        temp = round((tempMax - 273.15) * (9/5) + 32, 1)
        daysUntil = days_until_christmas()
        return f"Weather: {weatherDesc}\nTemp: {temp}F\nPercip %: {percipChance*100}\nDays until xmas: {daysUntil}"
        # return f"Weather: {weatherDesc}\nTemp: {temp}F\nPercip %: {percipChance}"
    else:
        return "Error fetching weather"

def getBasketballRealtime(gameId):
    global updateCountdown

    url = f"https://api-basketball.p.rapidapi.com/games/{gameId}"

    headers = {
        'x-rapidapi-host': "api-basketball.p.rapidapi.com",
        'x-rapidapi-key': RAPID_API_KEY
    }

    response = requests.request("GET", url, headers=headers)
    data = response.json()

    homeTeam = data['api']['games'][0]['teams']['home']['team_name']
    awayTeam = data['api']['games'][0]['teams']['away']['team_name']
    homeScore = data['api']['games'][0]['scores']['home']['total']
    awayScore = data['api']['games'][0]['scores']['away']['total']
    status = data['api']['games'][0]['status']['long']
    statusCleaned = re.sub(r"\s*\(.*?\)", "", status)

    
    updateCountdown = int(60 * 4) # Update every 4 minutes
    return f"{homeTeam} vs {awayTeam}\n{statusCleaned}\n{homeScore} to {awayScore}"

# --------------


def displayMessage(message):
    payload = json.dumps({'text': message})
    response = requests.post(VESTABOARD_URL, data=payload, headers=HEADERS)
    if response.status_code == 200:
        print(f"Displayed: {message}")
    else:
        print(message)
        print(f"Failed to display. Status code: {response.status_code}")

def days_until_christmas():
    # Get the current date
    current_date = datetime.now()
    christmas_date = datetime(current_date.year, 12, 25)
    if current_date > christmas_date:
        christmas_date = datetime(current_date.year + 1, 12, 25)
    days_until = (christmas_date - current_date).days
    return days_until

def getRealtimeDisplay():
    global basketballSchedule, updateCountdown, gameOn
    # Check basketball to see if it's live

    if basketballSchedule or gameOn:
        mst = timezone(timedelta(hours=-7))

        # Get the current time in MST
        now = datetime.now(mst)

        for game_time, game_id, homeTeam, awayTeam in basketballSchedule:
            # Check if current time is within 3 hours of the game
            game_start_time = datetime.strptime(game_time, "%Y-%m-%dT%H:%M:%S%z")
            time_difference = game_start_time - now
            time_difference_seconds = time_difference.total_seconds()

            if 60 * 10 >= time_difference_seconds >= 0 and not gameOn:  # 10 minutes in seconds
                minutes, seconds = divmod(abs(int(time_difference_seconds)), 60)

                if minutes == 1: gameOn = {"timeStart": now, "game_id": game_id}

                updateCountdown = 60
                return f"{homeTeam} vs {awayTeam} starting in {minutes} mins"
                
            elif gameOn and game_id == gameOn.game_id:
                gameOnDifference = now - gameOn.timeStart
                if gameOnDifference.total_seconds() >= 10800: gameOn = False
                return getBasketballRealtime(game_id)
    
    updateCountdown = 60 * 20
    return getDenverWeather()
    
def quietHoursSleep():
    global sleeping

    time.sleep(3600)
    sleeping = True

def checkBasketballSchedule():
    global basketballScheduleCountdown

    teams = ["Denver Nuggets", "Boston Celtics"]
    leagueId = "12"  # NBA League ID

    today = datetime.now().strftime('%Y-%m-%d')
    url = "https://api-basketball.p.rapidapi.com/games"

    headers = {
        'x-rapidapi-host': "api-basketball.p.rapidapi.com",
        'x-rapidapi-key': RAPID_API_KEY
    }

    querystring = {"date": today, "league": leagueId, "season": "2023-2024", "timezone": "America/Denver"}
    response = requests.request("GET", url, headers=headers, params=querystring)
    data = response.json()
    result = []
    for game in data['response']:
        # Check if either team is playing
        homeTeam = game['teams']['home']['name'].split()[1]
        awayTeam = game['teams']['away']['name'].split()[1]
        if homeTeam in teams or awayTeam in teams:
            # Save the time of the game, game ID, and team names
            result.append([game['date'], game['id'], homeTeam, awayTeam])
    
    basketballScheduleCountdown = 60 * 60

    if result == []:
        return False
    else:
        return result

def wakeUp():
    global sleeping, basketballSchedule

    if sleeping:
        basketballSchedule = checkBasketballSchedule()
        sleeping = False

if __name__ == "__main__":

    basketballSchedule = checkBasketballSchedule()
    
    while True:
        now = datetime.now()
        current_hour = now.hour

        if current_hour >= 23 or current_hour < 6:
            quietHoursSleep()

        else:
            if sleeping: wakeUp()

            if updateCountdown == 0:
                displayMessage(getRealtimeDisplay())
            
            if basketballScheduleCountdown == 0:
                basketballSchedule = checkBasketballSchedule()
            
            time.sleep(1)
            updateCountdown -= 1
            basketballScheduleCountdown -= 1