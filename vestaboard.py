import requests
import time
import json
import logging
from datetime import datetime
from config import VESTABOARD_API_KEY, WEATHER_API_KEY

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants
HEADERS = {
    'Content-Type': 'application/json',
    'X-Vestaboard-Read-Write-Key': VESTABOARD_API_KEY
}

VESTABOARD_URL = 'https://rw.vestaboard.com/'
WEATHER_URL = 'https://api.openweathermap.org/data/2.5/forecast'
ENDPOINT_URL = 'https://nj3ho46btl.execute-api.us-west-2.amazonaws.com/default/checoRestEndpoint'

# Configuration
UPDATE_INTERVAL = 60 * 20  # 20 minutes
QUIET_HOURS_START = 23
QUIET_HOURS_END = 6
SLEEP_DURATION = 3600  # 1 hour

# Global state
updateCountdown = 0

def days_until(target_date):
    """Calculate days until a target date, handling year rollover"""
    try:
        current_date = datetime.now()
        target_date = datetime.strptime(target_date, "%Y-%m-%d")
        if current_date > target_date:
            target_date = datetime(current_date.year + 1, target_date.month, target_date.day)
        days_until = (target_date - current_date).days
        return days_until + 1
    except ValueError as e:
        logger.error(f"Invalid date format for target_date: {target_date}")
        return 0

def days_since(start_date):
    """Calculate weeks and days since a given date"""
    try:
        current_date = datetime.now()
        start_date = datetime.strptime(start_date, "%Y-%m-%d")
        
        if current_date < start_date:
            return "0w 0d"
        
        days_diff = (current_date - start_date).days
        weeks = days_diff // 7
        remaining_days = days_diff % 7
        
        return f"{weeks}w {remaining_days}d"
    except ValueError as e:
        logger.error(f"Invalid date format for start_date: {start_date}")
        return "0w 0d"

def get_denver_weather():
    """Fetch and format Denver weather information"""
    try:
        params = {
            'lat': 39.76,
            'lon': -104.93,
            'appid': WEATHER_API_KEY
        }
        response = requests.get(WEATHER_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get("cod") == "200" and data.get("list"):
            weather_data = data["list"][0]
            temp_max = weather_data["main"]["temp_max"]
            percip_chance = round(weather_data["pop"] * 100, 1)
            temp = round((temp_max - 273.15) * (9/5) + 32, 1)
            return f"Temp: {temp}F\nPrecip: {percip_chance}%"
        else:
            logger.warning(f"Weather API returned unexpected data: {data.get('cod')}")
            return "Weather: Unavailable"
    except requests.RequestException as e:
        logger.error(f"Failed to fetch weather: {e}")
        return "Weather: Error"
    except (KeyError, IndexError) as e:
        logger.error(f"Failed to parse weather data: {e}")
        return "Weather: Parse Error"

def get_countdown():
    """Get countdown to target date"""
    days_until_val = days_until("2025-07-24")
    return f"Due In {days_until_val}"

def get_ollie_counter():
    """Get Ollie's age counter"""
    ollie_days = days_since("2025-07-18")
    return f"Ollie: {ollie_days}"

def get_work_time():
    """Fetch and format work time from external API"""
    try:
        response = requests.get(ENDPOINT_URL, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        body_str = data.get('body', '{}')
        body = json.loads(body_str)
        work_time = body.get('work_time', '00:00')
        
        # Extract hours and minutes
        time_parts = work_time.split(':')
        if len(time_parts) >= 2:
            work_time_hours = f"{time_parts[0]}:{time_parts[1]}"
        else:
            work_time_hours = "00:00"
            
        return f"Cats: {work_time_hours}"
    except requests.RequestException as e:
        logger.error(f"Failed to fetch work time: {e}")
        return "Cats: Unavailable"
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"Failed to parse work time data: {e}")
        return "Cats: Parse Error"

def display_message(message):
    """Display message on Vestaboard"""
    try:
        payload = json.dumps({'text': message})
        response = requests.post(VESTABOARD_URL, data=payload, headers=HEADERS, timeout=10)
        response.raise_for_status()
        logger.info(f"Successfully displayed message on Vestaboard")
    except requests.RequestException as e:
        logger.error(f"Failed to display message on Vestaboard: {e}")
    except Exception as e:
        logger.error(f"Unexpected error displaying message: {e}")

def get_realtime_display():
    """Build the complete display message"""
    global updateCountdown
    updateCountdown = UPDATE_INTERVAL
    
    display_lines = []
    
    # Weather information
    weather_info = get_denver_weather()
    display_lines.append(weather_info)
    
    # Countdown
    # countdown_info = get_countdown()
    # display_lines.append(countdown_info)
    
    # Work time
    work_time_info = get_work_time()
    display_lines.append(work_time_info)
    
    # Ollie counter
    ollie_info = get_ollie_counter()
    display_lines.append(ollie_info)
    
    return "\n".join(display_lines)

def quiet_hours_sleep(sleeping):
    """Handle quiet hours sleep mode"""
    logger.info("Entering quiet hours sleep mode")
    time.sleep(SLEEP_DURATION)
    return True

def wake_up(sleeping):
    """Handle wake up from sleep mode"""
    if sleeping:
        logger.info("Waking up from sleep mode")
        return False
    return sleeping

def is_quiet_hours():
    """Check if current time is during quiet hours"""
    current_hour = datetime.now().hour
    return current_hour >= QUIET_HOURS_START or current_hour < QUIET_HOURS_END

if __name__ == "__main__":
    logger.info("Starting Vestaboard display service")
    sleeping = False
    
    while True:
        try:
            if is_quiet_hours():
                sleeping = quiet_hours_sleep(sleeping)
            else:
                sleeping = wake_up(sleeping)
                if updateCountdown == 0:
                    display_message(get_realtime_display())
                time.sleep(1)
                updateCountdown -= 1
        except KeyboardInterrupt:
            logger.info("Shutting down Vestaboard display service")
            break
        except Exception as e:
            logger.error(f"Unexpected error in main loop: {e}")
            time.sleep(60)  # Wait a minute before retrying

