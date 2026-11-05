"""Phase 3 Live Open-Meteo Hydrodynamics Verification Script.

Allows manual execution and verification of:
1. Reaching out to Open-Meteo Marine REST API.
2. Applying Cubic Delta (psi_3) kernel smoothing.
3. Fallback circuit breaker engaging on failure.

Author: Nigerian Navy officer with 20+ years of operational experience
ORCID: 0009-0008-0112-9273
"""

import json
import urllib.request


def cubic_delta_kernel(x, h=1.0):
    """Evaluate cubic delta kernel."""
    abs_x = abs(x)
    q = abs_x / h
    if q < 1.0:
        return (1 / (6 * h)) * (4 - 6 * (q**2) + 3 * (q**3))
    elif q < 2.0:
        return (1 / (6 * h)) * ((2 - q) ** 3)
    else:
        return 0.0


def smooth_wave_heights(raw_heights):
    """Convolve discrete wave heights with cubic delta kernel."""
    if len(raw_heights) < 3:
        return sum(raw_heights) / len(raw_heights) if raw_heights else 0.0
    weights = [cubic_delta_kernel(-1.0), cubic_delta_kernel(0.0), cubic_delta_kernel(1.0)]
    norm = sum(weights)
    smoothed = sum(h_val * w for h_val, w in zip(raw_heights[-3:], weights)) / norm
    return smoothed


def fetch_and_smooth_hs():
    """Fetch live wave heights from Open-Meteo or engage circuit breaker fallback."""
    url = (
        "https://marine-api.open-meteo.com/v1/marine"
        "?latitude=4.25&longitude=7.75&hourly=wave_height&timezone=Africa%2FLagos&forecast_days=1"
    )
    print(f"[NETWORK] Reaching out to Open-Meteo API...")
    print(f"[NETWORK] Endpoint: {url}")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MTRE-Metocean-Adapter/1.0"})
        with urllib.request.urlopen(req, timeout=5.0) as response:
            if response.status != 200:
                raise Exception(f"HTTP Error {response.status}")
            payload = json.loads(response.read().decode("utf-8"))
            hourly_data = payload.get("hourly", {})
            wave_heights = hourly_data.get("wave_height", [])
            valid_heights = [h for h in wave_heights if h is not None]
            if not valid_heights:
                raise ValueError("Payload returned empty wave heights.")
            last_3_hours = valid_heights[:3]
            smoothed_hs = smooth_wave_heights(last_3_hours)
            print(f"[SUCCESS] Raw Hs array (meters): {last_3_hours}")
            print(f"[MATH]    Applied Cubic Delta (psi_3) kernel convolution.")
            print(f"[RESULT]  Smoothed Live Hs: {smoothed_hs:.4f} meters")
            return smoothed_hs, False
    except Exception as e:
        print(f"[CIRCUIT BREAKER TRIPPED] Network or Parsing Failure: {e}")
        print(f"[FALLBACK] Engaging historical 90th percentile baseline (1.85m).")
        return 1.85, True


if __name__ == "__main__":
    print("================================================================")
    print("PHASE 3: LIVE OSINT - OPEN-METEO HYDRODYNAMICS VERIFICATION")
    print("================================================================")
    hs, is_estimated = fetch_and_smooth_hs()
    print("================================================================")
    if is_estimated:
        print("STATUS: DEGRADED [ESTIMATED_HYDRODYNAMICS]")
    else:
        print("STATUS: LIVE VERIFIED")
