import requests
import time
import json
from datetime import datetime, timedelta
from config import VESTABOARD_API_KEY, WEATHER_API_KEY

HEADERS = {
    'Content-Type': 'application/json',
    'X-Vestaboard-Read-Write-Key': VESTABOARD_API_KEY
}

VESTABOARD_URL = 'https://rw.vestaboard.com/'
WEATHER_URL = 'https://api.openweathermap.org/data/2.5/forecast'
ENDPOINT_URL = 'https://nj3ho46btl.execute-api.us-west-2.amazonaws.com/default/checoRestEndpoint'

updateCountdown = 0

def days_until(target_date):
    current_date = datetime.now()
    target_date = datetime.strptime(target_date, "%Y-%m-%d")
    if current_date > target_date:
        target_date = datetime(current_date.year + 1, target_date.month, target_date.day)
    days_until = (target_date - current_date).days
    return days_until + 1

def get_denver_weather():
    params = {
        'lat': 39.76,
        'lon': -104.93,
        'appid': WEATHER_API_KEY
    }
    response = requests.get(WEATHER_URL, params=params)
    data = response.json()
    if data["cod"] == "200":
        weather_desc = data["list"][0]["weather"][0]["main"]
        temp_max = data["list"][0]["main"]["temp_max"]
        percip_chance = round(data["list"][0]["pop"] * 100,1)
        temp = round((temp_max - 273.15) * (9/5) + 32, 1)
        days_until_val = days_until("2025-07-24")
        return f"Temp: {temp}F\nPrecip: {percip_chance}%\nDue In {days_until_val}"
    else:
        return "Error fetching weather"

def display_message(message):
    payload = json.dumps({'text': message})
    response = requests.post(VESTABOARD_URL, data=payload, headers=HEADERS)
    if response.status_code == 200:
        print(f"Displayed: {message}")
    else:
        print(message)
        print(f"Failed to display. Status code: {response.status_code}")

def get_realtime_display():
    global updateCountdown
    updateCountdown = 60 * 20
    text = get_denver_weather()
    text += f"\n{get_work_time()}"
    return text

def get_work_time():
    response = requests.get(ENDPOINT_URL)
    if response.status_code == 200:
        try:
            data = response.json()
            body_str = data['body']
            body = json.loads(body_str)
            work_time = body['work_time']
            work_time_hours = work_time.split(':')[0] + ":" + work_time.split(':')[1]
            return f"Cats: {work_time_hours}"
        except json.JSONDecodeError as e:
            print("JSON decode error:", e)
            return "Failed to parse work time"
    else:
        return f"Failed to fetch work time. Status code: {response.status_code}"

def quiet_hours_sleep(sleeping):
    time.sleep(3600)
    sleeping = True
    return sleeping

def wake_up(sleeping):
    if sleeping:
        sleeping = False
    return sleeping

if __name__ == "__main__":
    target_date = "2025-07-24"
    sleeping = False
    while True:
        now = datetime.now()
        current_hour = now.hour

        if current_hour >= 23 or current_hour < 6:
            sleeping = quiet_hours_sleep(sleeping)
        else:
            sleeping = wake_up(sleeping)
            if updateCountdown == 0:
                display_message(get_realtime_display())
            time.sleep(1)
            updateCountdown -= 1

