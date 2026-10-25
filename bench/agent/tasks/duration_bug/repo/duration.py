import re


def parse_duration(text):
    """Parse durations such as '1h30m', '45s', '2h' or '1h5m10s' into seconds."""
    total = 0
    for value, unit in re.findall(r'(\d+)([hms])', text):
        total += int(value) * {'h': 3600, 'm': 60, 's': 1}[unit]
    return total
