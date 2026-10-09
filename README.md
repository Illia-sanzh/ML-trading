# ML-trading
A Machine Learning project for Algorithmic Trading, involving the use of LLM models for NLP.

The core of the project will hinge on the use of Machine Learning algorithms to predict the future price of stocks. The training will be done on 10 years of stock market data, starting in 2016 and ending 2026 to expand the amount of stock market trends for the model to consume(bearish, bullish, volatile, crisis markets). The training will involve 500 biggest companies stock prices and how they changed across a time. Eventually, when the model has been trained to deal with the market, including things such as fees, slippage, etc. it can be allowed to be tested on real-time stock market data(still paper trading though). Before that, a new kind of LLM model will be used, namely the Jev model by Typesafe AI. The model is not capable of real language output, like ChatGPT, claude, or gemini. It responds exlusively in numbers and has only three modes: Choice, Score, and Noul. It can, however, be used to interpret language and answer atomic questions, such as "Is this article positive?" and "Is this article about a product announcement/merger?" to which the model can respond in confidence, such as "happy: 0,98", meaning the article is 98% confidence happy. The model is incredibly fast, usually responding withing 10s of milliseconds on massive context, unlike other LLMs. It is also cheap, only taking $0,042 per 1M tokens of input and $0 per 1M tokens of output, making it perfect for real-time news articles analysis. A list of questions will be input in the Jev model, resulting in an array of many numbers of confidence, that the model will then have to learn to interpret to predict prices.

The final product will look like this:
1. A stream of news will be fed into a Jev model, then the output will be fed to the model
2. The model, trained on years of data, can predict the future stock prices with some confidence, drawing on its knowledge and the news sources
3. The model can place trades(shorts, longs) to make risk-adjusted decisions. Whether this will result in a net profit or loss, is hard to tell. Markets are unpredictable on such a minor scale, especially having little to no resources to work with.


Sources used up till now: 
