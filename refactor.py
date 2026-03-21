import os

# Path to the file
path = r"C:\Users\Sanskar Bhoir\Project\Stock-Market-Predictor\backend\agents\coordinator_agent.py"

with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Make sure asyncio is imported
if "import asyncio" not in content:
    content = content.replace("from typing import Any, Dict, List, Tuple\n", "from typing import Any, Dict, List, Tuple\nimport asyncio\n")

start_token = '    def process_ticker(self, ticker: str, horizon: str = "1d", current_price: float | None = None) -> Dict[str, Any]:'
end_token = '        missing_data: List[str] = []'

start_idx = content.find(start_token)
end_idx = content.find(end_token, start_idx)

if start_idx != -1 and end_idx != -1:
    target = content[start_idx:end_idx]
    replacement = '''    async def process_ticker(self, ticker: str, horizon: str = "1d", current_price: float | None = None) -> Dict[str, Any]:
        """
        Execute full multi-agent orchestration concurrently using asyncio, returning one fused decision object.
        """
        current_price, market_ts = await asyncio.to_thread(self._get_current_price, ticker, current_price)

        async def fetch_sentiment_and_macro():
            sentiment = await asyncio.to_thread(self.sentiment_agent.analyze, ticker)
            headlines = [h["title"] for h in sentiment.get("top_headlines", [])]
            macro = await asyncio.to_thread(self.macro_agent.analyze, headlines)
            return sentiment, macro
            
        coros = [
            asyncio.to_thread(self.commodities_agent.analyze),
            asyncio.to_thread(self.technical_agent.analyze, ticker),
            asyncio.to_thread(self.fundamentals_agent.analyze, ticker),
            fetch_sentiment_and_macro()
        ]
        
        results = await asyncio.gather(*coros)
        commodities_result, technical_result, fundamentals_result, (sentiment_result, macro_result) = results

        core_results = [macro_result, commodities_result, sentiment_result, technical_result, fundamentals_result]
        risk_result = await asyncio.to_thread(self.risk_agent.synthesize, ticker, current_price, horizon, core_results)

'''
    new_content = content[:start_idx] + replacement + content[end_idx:]
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_content)
    print("Agent parallelization refactored successfully.")
else:
    print("Tokens not found.")
