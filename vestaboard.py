import calendar
import re
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
    COUNTER_START_DATE,
    COUNTER_LABEL,
    COUNTER_USE_MONTHS
)

class RedactSecretsFilter(logging.Filter):
    """Mask API keys that requests embeds in exception messages (e.g. appid=...)"""
    _pattern = re.compile(r'(appid=)[^&\s\'")]+')

    def filter(self, record):
        record.msg = self._pattern.sub(r'\1REDACTED', record.getMessage())
        record.args = None
        return True

# Log to stderr only. monitor_script.sh redirects the process's output into
# vestaboard.log, so a FileHandler here would write every line twice.
_handler = logging.StreamHandler()
_handler.addFilter(RedactSecretsFilter())
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[_handler]
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

# Credit a single cat by name once total worked time exceeds this threshold
# and one cat accounts for at least WORK_TIME_NAME_SHARE of it.
WORK_TIME_NAME_THRESHOLD = 30 * 60  # 30 minutes, in seconds
WORK_TIME_NAME_SHARE = 0.8  # 80%

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

def get_weather():
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

def get_counter():
    """Get counter since start date"""
    counter_days = days_since(COUNTER_START_DATE)
    return f"{COUNTER_LABEL}: {counter_days}"

def parse_time_to_seconds(time_str):
    """Parse a 'H:MM:SS' or 'MM:SS' time string into total seconds"""
    try:
        parts = [int(p) for p in time_str.split(':')]
    except (ValueError, AttributeError):
        return 0

    if len(parts) == 3:
        hours, minutes, seconds = parts
    elif len(parts) == 2:
        hours, minutes, seconds = 0, parts[0], parts[1]
    else:
        return 0

    return hours * 3600 + minutes * 60 + seconds

def get_work_time_label(total_seconds, tuni_seconds, checo_seconds):
    """Return the display label for the work time line.

    Once the cats have worked more than 30 minutes and one cat accounts for
    80%+ of that time, credit that cat by name instead of the generic "Cats".
    """
    if total_seconds > WORK_TIME_NAME_THRESHOLD and total_seconds > 0:
        if tuni_seconds / total_seconds >= WORK_TIME_NAME_SHARE:
            return "Tuni"
        if checo_seconds / total_seconds >= WORK_TIME_NAME_SHARE:
            return "Checo"
    return "Cats"

def get_work_time():
    """Fetch and format work time from external API"""
    try:
        response = requests.get(ENDPOINT_URL, timeout=10)
        response.raise_for_status()

        data = response.json()
        body = data.get('body', '{}')
        # The endpoint wraps its payload as a JSON string, but accept an
        # already-decoded object too.
        if isinstance(body, str):
            body = json.loads(body)
        if not isinstance(body, dict):
            raise ValueError(f"Unexpected body type: {type(body).__name__}")
        work_time = str(body.get('work_time', '00:00'))

        # Extract hours and minutes
        time_parts = work_time.split(':')
        if len(time_parts) >= 2:
            work_time_hours = f"{time_parts[0]}:{time_parts[1]}"
        else:
            work_time_hours = "00:00"

        # Credit a single cat by name when they dominate the worked time
        label = get_work_time_label(
            parse_time_to_seconds(work_time),
            parse_time_to_seconds(body.get('tuni_time', '0:00:00')),
            parse_time_to_seconds(body.get('checo_time', '0:00:00')),
        )

        return f"{label}: {work_time_hours}"
    except requests.RequestException as e:
        logger.error(f"Failed to fetch work time: {e}")
        return "Cats: Unavailable"
    except (ValueError, KeyError, TypeError, AttributeError) as e:
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
    display_lines = [
        get_weather(),
        get_work_time(),
        get_counter(),
    ]
    return "\n".join(display_lines)

def is_quiet_hours():
    """Check if current time is during quiet hours"""
    current_hour = datetime.now().hour
    return current_hour >= QUIET_HOURS_START or current_hour < QUIET_HOURS_END

if __name__ == "__main__":
    logger.info("Starting Vestaboard display service")

    while True:
        try:
            if is_quiet_hours():
                logger.info("Quiet hours - pausing updates")
                time.sleep(SLEEP_DURATION)
            else:
                display_message(get_realtime_display())
                time.sleep(UPDATE_INTERVAL)
        except KeyboardInterrupt:
            logger.info("Shutting down Vestaboard display service")
            break
        except Exception as e:
            logger.error(f"Unexpected error in main loop: {e}")
            time.sleep(60)  # Wait a minute before retrying

