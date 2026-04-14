import yfinance as yf
# Test if screener works
try:
    from yfinance import Sector
    print("Screener exists")
except:
    print("No screener")
