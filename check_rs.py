import pandas as pd
df = pd.read_csv('highmom_trades.csv')

subset = df[df['relative_strength'] >= 50]
for year, group in subset.groupby('year'):
    print(f"{int(year)}: {len(group)} trades")