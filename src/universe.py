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


if __name__ == "__main__":
    universe = SP500UniverseStockAnalysis()
    print(f"Loaded {len(universe.tickers)} tickers")
    print(universe.tickers[:20])
