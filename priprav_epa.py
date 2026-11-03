import re

import pandas as pd

MILES_TO_KM = 1.609344

df = pd.read_csv('data/epa/vehicles.csv', low_memory=False)
ev = df[df['atvType'] == 'EV'].copy()


def motor_kw(text):
    # napr. "127 and 200 kW PMSM" -> 327, "150 kW AC PMSM" -> 150
    if not isinstance(text, str) or 'kw' not in text.lower():
        return None
    before_kw = text.lower().split('kw')[0]
    nums = [float(n) for n in re.findall(r'\d+(?:\.\d+)?', before_kw)]
    return sum(nums) if nums else None


ev['motor_kw'] = ev['evMotor'].map(motor_kw)
ev['n_motors'] = ev['evMotor'].str.count(r'\band\b').fillna(0).astype(int) + 1
ev['charge240'] = ev['charge240'].replace(0, float('nan'))  # 0 = údaj chýba
ev['range_km'] =(ev['range'] * MILES_TO_KM).round()
ev['kwh_per_100km'] = (ev['combE'] / MILES_TO_KM).round(2)

clean = ev.rename(columns={
    'VClass': 'vehicle_class',
    'charge240': 'charge_time_240v_hr',
})[[
    'year', 'make', 'model', 'vehicle_class', 'drive',
    'motor_kw', 'n_motors', 'charge_time_240v_hr', 'kwh_per_100km', 'range_km',
]]

clean.to_csv('data/ev_epa.csv', index=False)
print(clean.shape)
