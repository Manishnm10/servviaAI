"""
Objective 2 Verification — Passive Chronobiological Inference
=============================================================

Tests ChronobiologyEngine with three scenarios:
    1. Morning query (08:30, winter, Northern Hemisphere — New York)
    2. Late-night query (03:00, winter, Northern Hemisphere — insomnia)
    3. Mid-summer query (15:00, July, Southern Hemisphere — Sydney)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime
from chronobiology.inference import ChronobiologyEngine

engine = ChronobiologyEngine()

DIVIDER = "=" * 70

# ────────────────────────────────────────────────
# SCENARIO 1: Morning query — 08:30, Jan, New York (40.71°N)
# ────────────────────────────────────────────────
print(f"\n{DIVIDER}")
print("SCENARIO 1: Morning Query — 08:30, January, New York")
print(DIVIDER)

state1 = engine.infer_state(
    local_time=datetime(2026, 1, 15, 8, 30),
    coordinates=(40.71, -74.01),
)

print(f"  Local Time:      {state1.local_time}")
print(f"  Circadian Phase: {state1.circadian_phase.value}")
print(f"  Season:          {state1.seasonal_influence.value}")
print(f"  Sleep Pressure:  {state1.sleep_pressure_estimate.value}")
print(f"  Misaligned:      {state1.is_misaligned}")
print(f"  Hemisphere:      {state1.hemisphere}")
print(f"  Advisory:        {state1.advisory}")

assert state1.circadian_phase.value == "morning_activation", f"Expected morning_activation, got {state1.circadian_phase.value}"
assert state1.seasonal_influence.value == "winter_accumulation", f"Expected winter_accumulation, got {state1.seasonal_influence.value}"
assert state1.sleep_pressure_estimate.value == "low", f"Expected low, got {state1.sleep_pressure_estimate.value}"
assert not state1.is_misaligned, "Should NOT be misaligned at 08:30"
assert state1.hemisphere == "northern"
print("\n✅ SCENARIO 1 PASSED")

# ────────────────────────────────────────────────
# SCENARIO 2: Late-night query — 03:00, Feb, Mumbai (19.07°N)
# ────────────────────────────────────────────────
print(f"\n{DIVIDER}")
print("SCENARIO 2: Late-Night Query — 03:00, February, Mumbai (insomnia)")
print(DIVIDER)

state2 = engine.infer_state(
    local_time=datetime(2026, 2, 26, 3, 0),
    coordinates=(19.07, 72.87),
)

print(f"  Local Time:      {state2.local_time}")
print(f"  Circadian Phase: {state2.circadian_phase.value}")
print(f"  Season:          {state2.seasonal_influence.value}")
print(f"  Sleep Pressure:  {state2.sleep_pressure_estimate.value}")
print(f"  Misaligned:      {state2.is_misaligned}")
print(f"  Hemisphere:      {state2.hemisphere}")
print(f"  Advisory:        {state2.advisory}")

assert state2.circadian_phase.value == "deep_sleep", f"Expected deep_sleep, got {state2.circadian_phase.value}"
assert state2.is_misaligned, "Should BE misaligned at 03:00"
assert state2.sleep_pressure_estimate.value == "high", f"Expected high, got {state2.sleep_pressure_estimate.value}"
print("\n✅ SCENARIO 2 PASSED")

# ────────────────────────────────────────────────
# SCENARIO 3: Mid-summer afternoon — 15:00, July, Sydney (33.87°S)
# ────────────────────────────────────────────────
print(f"\n{DIVIDER}")
print("SCENARIO 3: Mid-Summer Afternoon — 15:00, July, Sydney (Southern Hemisphere)")
print(DIVIDER)

state3 = engine.infer_state(
    local_time=datetime(2026, 7, 15, 15, 0),
    coordinates=(-33.87, 151.21),
)

print(f"  Local Time:      {state3.local_time}")
print(f"  Circadian Phase: {state3.circadian_phase.value}")
print(f"  Season:          {state3.seasonal_influence.value}")
print(f"  Sleep Pressure:  {state3.sleep_pressure_estimate.value}")
print(f"  Misaligned:      {state3.is_misaligned}")
print(f"  Hemisphere:      {state3.hemisphere}")
print(f"  Advisory:        {state3.advisory}")

assert state3.circadian_phase.value == "afternoon_slump", f"Expected afternoon_slump, got {state3.circadian_phase.value}"
# July in Southern Hemisphere = NH January → winter_accumulation
assert state3.seasonal_influence.value == "winter_accumulation", f"Expected winter_accumulation (SH July=NH Jan), got {state3.seasonal_influence.value}"
assert state3.sleep_pressure_estimate.value == "moderate", f"Expected moderate, got {state3.sleep_pressure_estimate.value}"
assert not state3.is_misaligned, "Should NOT be misaligned at 15:00"
assert state3.hemisphere == "southern"
print("\n✅ SCENARIO 3 PASSED")

# ────────────────────────────────────────────────
# BONUS: Equatorial query — 12:00, August, Nairobi (1.29°S)
# ────────────────────────────────────────────────
print(f"\n{DIVIDER}")
print("BONUS: Equatorial Query — 12:00, August, Nairobi")
print(DIVIDER)

state4 = engine.infer_state(
    local_time=datetime(2026, 8, 10, 12, 0),
    coordinates=(-1.29, 36.82),
)

print(f"  Local Time:      {state4.local_time}")
print(f"  Circadian Phase: {state4.circadian_phase.value}")
print(f"  Season:          {state4.seasonal_influence.value}")
print(f"  Sleep Pressure:  {state4.sleep_pressure_estimate.value}")
print(f"  Misaligned:      {state4.is_misaligned}")
print(f"  Hemisphere:      {state4.hemisphere}")
print(f"  Advisory:        {state4.advisory}")

assert state4.hemisphere == "equatorial"
assert state4.seasonal_influence.value == "monsoon_dampness"  # Aug = equatorial wet season
assert state4.circadian_phase.value == "afternoon_peak"
print("\n✅ BONUS PASSED")


print(f"\n{DIVIDER}")
print("🎉 ALL SCENARIOS PASSED — ChronobiologyEngine verified!")
print(DIVIDER)
