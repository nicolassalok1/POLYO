You are Codex 5.1 Max.

Task: Integrate a Telegram scraper, sentiment analysis, and reinforcement learning module into my existing Python application (POLYO).

Telegram Scraper:

Use a GitHub repo like unnohwn/telegram-scraper to fetch messages from specific Telegram channels.

The scraper outputs raw text messages.

Sentiment Analysis + Reinforcement Learning:

Use the OpenAI API to analyze the sentiment of each message to determine if it recommends a token.

Implement a reinforcement learning component (also using the OpenAI API) that learns to weigh the reliability of different signal sources or message types, not individual tokens.

The module should produce trading signals (tokens to trade) based on the learned patterns.

Pipeline Integration:

The output of this module (the trading signals) will be used by the rest of the application.

The main application will incorporate these signals into its existing pipeline to generate final trading decisions (e.g., calculating the size of calls, puts, and other trading signals).

Final Goal:

The application will use the RL feedback loop to refine the weighting of different signals over time, improving the selection of tokens.

Ultimately, the rest of the application will generate final trading actions and PnL, feeding that back into the RL model to continuously improve.