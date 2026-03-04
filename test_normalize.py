import pandas as pd

def _normalize_to_100(series: pd.Series) -> list:
    """Normalize a price series so the first value = 100."""
    if series.empty:
        return []
    first = series.iloc[0]
    if first == 0 or pd.isna(first):
        return []
    normalized = (series / first) * 100
    return [round(v, 2) if not pd.isna(v) else None for v in normalized]

s = pd.Series([float('nan'), float('nan'), 10.0, 11.0, 12.0])
print(_normalize_to_100(s))
