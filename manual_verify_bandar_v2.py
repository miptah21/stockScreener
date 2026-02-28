from bandarmology import get_broker_summary, calculate_bandar_flow
import json

ticker = "BBCA"
start_date = "2024-10-30"
end_date = "2024-10-31"

print(f"Fetching data for {ticker} from {start_date} to {end_date}...")
data = get_broker_summary(ticker, start_date, end_date)

if data:
    print(f"Data fetched! {len(data)} aggregated records.")
    
    # Check if 'avg' and 'lot' are present in raw data
    first_item = data[0]
    print("Sample Item Keys:", first_item.keys())
    
    analysis = calculate_bandar_flow(data)
    print("Analysis Result:")
    
    # Print Top 1 Buyer to check new fields
    top_buyer = analysis['top_buyers'][0]
    print(f"Top 1 Buyer: {top_buyer['code']} - Val: {top_buyer['formatted_value']} - Lot: {top_buyer['formatted_lot']} - Avg: {top_buyer['formatted_avg']}")
    
else:
    print("Failed to fetch data.")
