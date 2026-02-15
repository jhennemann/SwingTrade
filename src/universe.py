import requests
from bs4 import BeautifulSoup


class SP500UniverseStockAnalysis:
    def __init__(self):
        self.url = "https://stockanalysis.com/list/sp-500-stocks/"
        self.tickers = self._load()

    def _load(self) -> list[str]:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }

        response = requests.get(self.url, headers=headers, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "lxml")

        # The table rows contain <tr>, ticker symbol is in the first <td>
        table = soup.find("table")
        rows = table.find_all("tr")[1:]  # skip header row

        tickers = []
        for row in rows:
            cols = row.find_all("td")
            if not cols:
                continue

            symbol = cols[1].text.strip()  # "Symbol" column
            tickers.append(symbol.replace(".", "-"))  # BRK.B -> BRK-B

        return tickers


class Nasdaq100Universe:
    def __init__(self):
        self.url = "https://stockanalysis.com/list/nasdaq-100-stocks/"
        self.tickers = self._load()

    def _load(self) -> list[str]:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }

        response = requests.get(self.url, headers=headers, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "lxml")

        table = soup.find("table")
        rows = table.find_all("tr")[1:]  # skip header row

        tickers = []
        for row in rows:
            cols = row.find_all("td")
            if not cols:
                continue

            symbol = cols[1].text.strip()  # "Symbol" column
            tickers.append(symbol.replace(".", "-"))

        return tickers


if __name__ == "__main__":
    sp500 = SP500UniverseStockAnalysis()
    print(f"S&P 500: {len(sp500.tickers)} tickers")
    print(sp500.tickers[:10])
    
    nasdaq100 = Nasdaq100Universe()
    print(f"\nNASDAQ 100: {len(nasdaq100.tickers)} tickers")
    print(nasdaq100.tickers[:10])
    
    # Show overlap
    overlap = set(sp500.tickers) & set(nasdaq100.tickers)
    print(f"\nOverlap: {len(overlap)} stocks in both")
    
    # Combined universe
    combined = list(set(sp500.tickers + nasdaq100.tickers))
    print(f"Combined (deduplicated): {len(combined)} stocks")