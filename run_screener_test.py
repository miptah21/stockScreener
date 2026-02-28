from screener import screen_stocks
import sys

def test_screener_run():
    print("Testing screen_stocks('idx_lq45') ...")
    try:
        result = screen_stocks('idx_lq45')
        if result['success']:
            print(f"Success! Scanned {result['total_scanned']} stocks.")
            print(f"With Report: {result['with_report_count']}")
            print(f"Without Report: {result['without_report_count']}")
            print(f"Errors: {result['error_count']}")
            
            # Print sample
            if result['results']:
                sample = result['results'][0]
                print(f"Sample Result: {sample}")
        else:
            print(f"Failed: {result.get('error')}")
    except Exception as e:
        print(f"CRASHED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_screener_run()
