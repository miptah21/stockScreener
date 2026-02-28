import requests
from datetime import datetime, timedelta

import os
from dotenv import load_dotenv

load_dotenv()
load_dotenv()

def get_broker_summary(ticker, start_date, end_date=None):
    """
    Fetches broker summary data from GoAPI.
    Supports single date or date range (by aggregation).
    
    Args:
        ticker (str): Stock ticker (e.g., 'BBCA').
        start_date (str): Start date in YYYY-MM-DD format.
        end_date (str): End date in YYYY-MM-DD format. If None, same as start_date.
        
    Returns:
        list: List of broker summary dictionaries (aggregated), or None if failed.
    """
    if not end_date:
        end_date = start_date
        
    # Convert to datetime objects for iteration
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        print("Invalid date format")
        return None
        
    # Limit range to 30 days
    if (end_dt - start_dt).days > 30:
        return {'error': 'Rentang tanggal maksimal 30 hari'}
        
    current_dt = start_dt
    aggregated_data = {} # broker_code -> {buy_val, buy_lot, sell_val, sell_lot, name}
    
    fetching_active = True
    has_data = False
    
    while current_dt <= end_dt:
        date_str = current_dt.strftime("%Y-%m-%d")
        print(f"Fetching for {date_str}...")
        
        # Try fetching for this date
        # Assuming the endpoint is the one we found before
        # We'll use a helper to try endpoints
        daily_res = _fetch_single_day(ticker, date_str)
        
        if isinstance(daily_res, dict) and 'error' in daily_res:
            print(f"Error fetching {date_str}: {daily_res['error']}")
            return daily_res
            
        if daily_res:
            has_data = True
            for item in daily_res:
                broker = item.get('broker') or {}
                code = broker.get('code')
                if not code: continue
                
                if code not in aggregated_data:
                    aggregated_data[code] = {
                        'name': broker.get('name', 'Unknown'),
                        'buy_val': 0, 'buy_lot': 0,
                        'sell_val': 0, 'sell_lot': 0
                    }
                
                side = item.get('side', '').upper()
                val = float(item.get('value', 0))
                lot = int(item.get('lot', 0))
                
                if side == 'BUY':
                    aggregated_data[code]['buy_val'] += val
                    aggregated_data[code]['buy_lot'] += lot
                elif side == 'SELL':
                    aggregated_data[code]['sell_val'] += val
                    aggregated_data[code]['sell_lot'] += lot
                    
        current_dt += timedelta(days=1)
        
    if not has_data:
        return None
        
    # Convert aggregation back to list format expected by calculator
    # We need to net off based on the original structure?
    # Actually, the original structure had 'side': 'BUY' or 'SELL'. 
    # But for a range, a broker might be Net Buy overall or Net Sell.
    # We should return a list where each broker has a net position?
    # Or return raw aggregated dict and let calculator handle it?
    
    # To keep calculator simple, let's normalize to a list of dicts.
    # However, a broker acts as both Buyer and Seller usually. 
    # The API returns separate rows for BUY and SELL (or NET?). 
    # The sample showed "transaction_type": "NET". 
    # If API gives NET per day, we sum NETs?
    # Sample broker_sample.json showed: "side": "BUY", "transaction_type": "NET".
    # This implies for that day, ZP was Net Buyer.
    
    # If ZP is Net Buy 100 on Day 1 and Net Sell 50 on Day 2 -> Total Net Buy 50.
    # If ZP is Net Buy 100 on Day 1 and Net Buy 50 on Day 2 -> Total Net Buy 150.
    
    # So we sum the Net Values.
    # If side=BUY, val is positive. If side=SELL, val is effectively negative flow (but positive scalar).
    
    final_list = []
    for code, data in aggregated_data.items():
        net_buy_val = data['buy_val'] - data['sell_val']
        net_buy_lot = data['buy_lot'] - data['sell_lot']
        
        # We need to reconstruct the "item" for calculate_bandar_flow
        # but calculate_bandar_flow expects 'value' and 'side'.
        
        if net_buy_val > 0:
            side = 'BUY'
            value = net_buy_val
            lot = net_buy_lot # Generally positive if val is positive, but not always (avg price diff)
        else:
            side = 'SELL'
            value = abs(net_buy_val)
            lot = abs(net_buy_lot) # Flip sign
            
        # Avg Price = Total Value / Total Lot (Gross or Net?)
        # Usually Bandarmology users want Average Buying Price for Accumulation, Avg Selling for Dist.
        # But if we aggregate NETs, the Avg Price is tricky.
        # "Avg Price" implies the price at which they accumulated.
        # Implied Avg = Net Value / Net Lot.
        
        # Avg Price = Value / (Lot * 100) because 1 Lot = 100 Shares
            
        # Avg Price = Total Buy Val / Total Buy Lot (if Net Buy)
        #           = Total Sell Val / Total Sell Lot (if Net Sell)
        # This represents the average price they ACCUMULATED at or DISTRIBUTED at.
        avg_price = 0
        if net_buy_val > 0:
             # Net Buyer -> Use Gross Buy Avg
             if data['buy_lot'] > 0:
                 avg_price = data['buy_val'] / (data['buy_lot'] * 100)
        else:
             # Net Seller -> Use Gross Sell Avg
             if data['sell_lot'] > 0:
                 avg_price = data['sell_val'] / (data['sell_lot'] * 100)
            
        final_list.append({
            'broker': {'code': code, 'name': data['name']},
            'code': code,
            'side': side,
            'value': value,
            'lot': lot, # Net Lot
            'avg': avg_price
        })
        
    return final_list

def _fetch_single_day(ticker, date):
    # Reload keys to ensure updates are picked up
    # Note: load_dotenv doesn't override by default, so we might need strict reload if env changed
    # But usually restarting app is best. We'll try to read os.getenv directly assuming it might be set.
    # To be safe, let's re-call load_dotenv with override=True for this critical section if needed, 
    # but that might be expensive. Let's just trust os.getenv if the app reloaded.
    
    k1 = os.getenv("GOAPI_API_KEY")
    k2 = os.getenv("GOAPI_API_KEY_2")
    keys = [k for k in [k1, k2] if k]
    
    if not keys:
        print("DEBUG: No API Keys found!")
        return []
        
    last_error = None
    
    for i, key in enumerate(keys):
        mask = f"...{key[-4:]}" if len(key) > 4 else key
        print(f"DEBUG: Trying Key {i+1} ({mask}) for {date}...")
        
        endpoints = [
            f"https://api.goapi.io/stock/idx/{ticker}/broker_summary?api_key={key}&date={date}",
            f"https://api.goapi.io/stock/idx/broker_summary?api_key={key}&symbol={ticker}&date={date}",
        ]
        
        for url in endpoints:
            try:
                response = requests.get(url, timeout=5)
                
                if response.status_code == 429:
                    print(f"DEBUG: Key {i+1} Rate Limited (429)")
                    last_error = {'error': 'Rate Limit Exceeded'}
                    break # Try next key
                    
                if response.status_code == 200:
                    data = response.json()
                    status = data.get('status')
                    if status == 'success' and data.get('data'):
                        print(f"DEBUG: Key {i+1} Success!")
                        return data['data'].get('results', [])
                    else:
                        print(f"DEBUG: Key {i+1} Returned {status}")
                        
            except Exception as e:
                print(f"DEBUG: Key {i+1} Error: {e}")
                pass
                
    if last_error:
        print("DEBUG: All keys failed/rate limited.")
        return last_error
        
    return []

def calculate_bandar_flow(broker_data):
    """
    Calculates Bandarmology status and returns list with Lot and Avg Price.
    """
    if not broker_data:
        return {
            "status": "No Data",
            "top_buyers": [],
            "top_sellers": [],
            "summary": {}
        }
        
    buyers = []
    sellers = []
    
    for item in broker_data:
        broker_info = item.get('broker') or {}
        code = broker_info.get('code')
        name = broker_info.get('name')
        value = float(item.get('value', 0))
        lot = int(item.get('lot', 0))
        avg = float(item.get('avg', 0))
        side = item.get('side', '').upper()
        
        entry = {
            "code": code,
            "name": name,
            "value": value,
            "lot": lot,
            "avg": avg,
            "formatted_value": f"{value:,.0f}",
            "formatted_lot": f"{lot:,.0f}",
            "formatted_avg": f"{avg:,.0f}"
        }
        
        if side == 'BUY':
            buyers.append(entry)
        elif side == 'SELL':
            sellers.append(entry)
            
    # Sort
    buyers.sort(key=lambda x: x['value'], reverse=True)
    sellers.sort(key=lambda x: x['value'], reverse=True)
    
    # Calculate Sums
    top_1_buy = sum(x['value'] for x in buyers[:1])
    top_3_buy = sum(x['value'] for x in buyers[:3])
    top_5_buy = sum(x['value'] for x in buyers[:5])
    
    top_1_sell = sum(x['value'] for x in sellers[:1])
    top_3_sell = sum(x['value'] for x in sellers[:3])
    top_5_sell = sum(x['value'] for x in sellers[:5])
    
    net_1 = top_1_buy - top_1_sell
    net_3 = top_3_buy - top_3_sell
    net_5 = top_5_buy - top_5_sell
    
    # Determine Status
    status = "Neutral"
    if top_1_buy > top_1_sell * 1.5:
        status = "Big Accumulation"
    elif top_1_sell > top_1_buy * 1.5:
        status = "Big Distribution"
    elif top_3_buy > top_3_sell:
        status = "Accumulation"
    elif top_3_sell > top_3_buy:
        status = "Distribution"

    return {
        "status": status,
        "top_buyers": buyers[:5],
        "top_sellers": sellers[:5],
        "summary": {
            "top_1_net": net_1,
            "top_3_net": net_3,
            "top_5_net": net_5,
        }
    }
