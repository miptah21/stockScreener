from bandarmology import get_broker_summary, calculate_bandar_flow
import json

ticker = "BBCA"
date = "2024-10-30" # Use the date we know has data from sample

print(f"Fetching data for {ticker} on {date}...")
data = get_broker_summary(ticker, date)

if data:
    print(f"Data fetched! {len(data)} records.")
    analysis = calculate_bandar_flow(data)
    print("Analysis Result:")
    print(json.dumps(analysis, indent=2))
else:
    print("Failed to fetch data.")
