from datetime import datetime, timedelta, timezone


# start_time = f"{2026-08-10T17:22}:00Z"
dt_obj = datetime.fromisoformat("2026-08-10T17:22")
new_dt_obj = dt_obj + timedelta(minutes=1)
end_time = new_dt_obj.strftime('%Y-%m-%dT%H:%M:%SZ')

print(end_time)