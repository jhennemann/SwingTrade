# check_highmom.py
import pandas as pd
df = pd.read_csv('highmom_trades.csv')
subset = df[df['relative_strength'] > 50]
for year, group in subset.groupby('year'):
    wr = group['win'].mean() * 100
    avg = group['pnl'].mean() * 100
    print(f'{year}: {len(group)} trades, {wr:.1f}% WR, {avg:.2f}% avg return')
print(f"\nOverall: {len(subset)} trades, {subset['win'].mean()*100:.1f}% WR, {subset['pnl'].mean()*100:.2f}% avg return")