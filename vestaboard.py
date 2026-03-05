import calendar
import requests
import time
import json
import logging
from datetime import datetime
from config import (
    VESTABOARD_API_KEY,
    WEATHER_API_KEY,
    WEATHER_LAT,
    WEATHER_LON,
    COUNTDOWN_TARGET_DATE,
    COUNTER_START_DATE,
    COUNTER_LABEL,
    COUNTER_USE_MONTHS
)

# Configure logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("vestaboard.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Constants
HEADERS = {
    'Content-Type': 'application/json',
    'X-Vestaboard-Read-Write-Key': VESTABOARD_API_KEY
}

VESTABOARD_URL = 'https://rw.vestaboard.com/'
WEATHER_CURRENT_URL = 'https://api.openweathermap.org/data/2.5/weather'
WEATHER_UV_URL = 'https://api.open-meteo.com/v1/forecast'
ENDPOINT_URL = 'https://nj3ho46btl.execute-api.us-west-2.amazonaws.com/default/checoRestEndpoint'

# Configuration
UPDATE_INTERVAL = 60 * 20  # 20 minutes
QUIET_HOURS_START = 23
QUIET_HOURS_END = 6
SLEEP_DURATION = 3600  # 1 hour

# Global state
updateCountdown = 0

def days_until(target_date, use_months=None):
    """Calculate time until a target date, handling year rollover"""
    if use_months is None:
        use_months = COUNTER_USE_MONTHS

    try:
        current_date = datetime.now()
        target = datetime.strptime(target_date, "%Y-%m-%d")

        # Handle year rollover for recurring dates
        if current_date > target:
            target = datetime(current_date.year + 1, target.month, target.day)

        if use_months:
            # Calculate months difference
            months = (target.year - current_date.year) * 12 + (target.month - current_date.month)
            days = target.day - current_date.day

            # Only show negative days when within 5 days of the monthly mark
            # Otherwise, show positive days since the last monthly mark
            if days < -5:
                months -= 1
                # Get days in previous month
                if current_date.month == 1:
                    prev_month_days = calendar.monthrange(current_date.year - 1, 12)[1]
                else:
                    prev_month_days = calendar.monthrange(current_date.year, current_date.month - 1)[1]
                days += prev_month_days

            return f"{months}m {days}d"
        else:
            # Calculate weeks and days
            days_diff = (target - current_date).days + 1
            weeks = days_diff // 7
            remaining_days = days_diff % 7
            return f"{weeks}w {remaining_days}d"
    except ValueError as e:
        logger.error(f"Invalid date format for target_date: {target_date}")
        return "0m 0d" if use_months else "0w 0d"

def days_since(start_date, use_months=None):
    """Calculate time since a given date"""
    if use_months is None:
        use_months = COUNTER_USE_MONTHS

    try:
        current_date = datetime.now()
        start = datetime.strptime(start_date, "%Y-%m-%d")

        if current_date < start:
            return "0m 0d" if use_months else "0w 0d"

        if use_months:
            # Calculate months difference
            months = (current_date.year - start.year) * 12 + (current_date.month - start.month)
            days = current_date.day - start.day

            # Only show negative days when within 5 days of the monthly anniversary
            # Otherwise, show positive days since the last anniversary
            if days < -5:
                months -= 1
                # Get days in previous month
                if current_date.month == 1:
                    prev_month_days = calendar.monthrange(current_date.year - 1, 12)[1]
                else:
                    prev_month_days = calendar.monthrange(current_date.year, current_date.month - 1)[1]
                days += prev_month_days

            return f"{months}m {days}d"
        else:
            # Calculate weeks and days
            days_diff = (current_date - start).days
            weeks = days_diff // 7
            remaining_days = days_diff % 7
            return f"{weeks}w {remaining_days}d"
    except ValueError as e:
        logger.error(f"Invalid date format for start_date: {start_date}")
        return "0m 0d" if use_months else "0w 0d"

def get_denver_weather():
    """Fetch and format current weather information from configured location"""
    temp = "N/A"
    uv_index = "N/A"

    # Fetch Temperature
    try:
        params = {
            'lat': WEATHER_LAT,
            'lon': WEATHER_LON,
            'appid': WEATHER_API_KEY,
            'units': 'imperial'
        }
        
        # Get current weather for accurate temperature
        current_response = requests.get(WEATHER_CURRENT_URL, params=params, timeout=10)
        current_response.raise_for_status()
        current_data = current_response.json()
        
        if current_data.get("cod") == 200:
            temp_val = current_data["main"]["temp"]
            temp = f"{round(temp_val, 1)}F"
        else:
            logger.warning(f"Current weather API returned unexpected data: {current_data.get('cod')}")
    except Exception as e:
        logger.error(f"Failed to fetch or parse temperature: {e}")

    # Fetch UV Index
    try:
        uv_params = {
            'latitude': WEATHER_LAT,
            'longitude': WEATHER_LON,
            'current': 'uv_index'
        }
        uv_response = requests.get(WEATHER_UV_URL, params=uv_params, timeout=10)
        uv_response.raise_for_status()
        uv_data = uv_response.json()

        # Extract UV index
        uv_val = uv_data.get("current", {}).get("uv_index", "N/A")
        if isinstance(uv_val, (float, int)):
            uv_index = round(uv_val, 1)
    except Exception as e:
        logger.error(f"Failed to fetch or parse UV index: {e}")

    return f"Temp: {temp}\nUV: {uv_index}"

def get_countdown():
    """Get countdown to target date"""
    days_until_val = days_until(COUNTDOWN_TARGET_DATE)
    return f"Due In {days_until_val}"

def get_ollie_counter():
    """Get counter since start date"""
    counter_days = days_since(COUNTER_START_DATE)
    return f"{COUNTER_LABEL}: {counter_days}"

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

