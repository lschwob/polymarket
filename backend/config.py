"""
Configuration for alert thresholds and detection rules.
Can be overridden via environment variables.
"""
import os

# Alert Detection Thresholds
ABSOLUTE_DELTA_THRESHOLD = float(os.getenv("ABSOLUTE_DELTA_THRESHOLD", "0.05"))  # 5% absolute change
RELATIVE_DELTA_THRESHOLD = float(os.getenv("RELATIVE_DELTA_THRESHOLD", "0.20"))  # 20% relative change
MIN_VOLUME_THRESHOLD = float(os.getenv("MIN_VOLUME_THRESHOLD", "100"))  # Minimum volume to avoid noise
ALERT_COOLDOWN_MINUTES = int(os.getenv("ALERT_COOLDOWN_MINUTES", "15"))  # Cooldown between alerts

# Snapshot window for shift detection
SHIFT_DETECTION_WINDOW_HOURS = int(os.getenv("SHIFT_DETECTION_WINDOW_HOURS", "1"))  # Look back 1 hour

# Trending Categories
TRENDING_CATEGORIES_TOP_K = int(os.getenv("TRENDING_CATEGORIES_TOP_K", "20"))
TRENDING_MIN_SCORE = float(os.getenv("TRENDING_MIN_SCORE", "1000"))
TRENDING_MIN_OCCURRENCES = int(os.getenv("TRENDING_MIN_OCCURRENCES", "2"))

# Job Intervals
TRENDING_REFRESH_INTERVAL_MINUTES = int(os.getenv("TRENDING_REFRESH_INTERVAL_MINUTES", "10"))
MARKETS_REFRESH_INTERVAL_MINUTES = int(os.getenv("MARKETS_REFRESH_INTERVAL_MINUTES", "5"))
