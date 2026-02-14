import yfinance as yf

# Initialize ticker
aapl = yf.Ticker("AAPL")

# Get all expiration dates
exps = aapl.options

# Get options for the first expiration date
opt = aapl.option_chain(exps[0])

# Access calls and puts DataFrames
calls = opt.calls
puts = opt.puts

breakpoint()
