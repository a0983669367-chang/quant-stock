import yfinance as yf
UNIVERSE = ['NQ=F', 'ES=F', 'YM=F', 'NKD=F', 'FTW=F']
df_all = yf.download(UNIVERSE, period='1y', progress=False, group_by='ticker', threads=True)
print("Columns:", df_all.columns)
print("Levels 0:", df_all.columns.levels[0] if hasattr(df_all.columns, 'levels') else 'No levels')
