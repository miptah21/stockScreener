from services.sentiment_service import get_sentiment_analysis
import json

try:
    print("Testing BBCA.JK...")
    r = get_sentiment_analysis('BBCA.JK')
    print("Success:", r.get('success'))
    print("Total Articles:", r.get('total_articles'))
    print("Model:", r.get('model_used'))
    s = r.get('sentiment_summary', {})
    print("Score:", s.get('overall_score'), "Label:", s.get('overall_label'))
    b = r.get('source_breakdown', {})
    for k, v in b.items():
        print(f"  {k}: {v}")
    
    # Also test an index
    print("\nTesting IHSG...")
    r2 = get_sentiment_analysis('IHSG')
    print("Success:", r2.get('success'))
    print("Total Articles:", r2.get('total_articles'))
    
except Exception as e:
    print(f"Test failed: {e}")
