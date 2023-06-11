import pandas as pd
import os


cwd = os.getcwd()  # 读取当前文件夹路径

df = pd.read_excel(cwd + '/Fa_data/PickLinePos_time.xlsx', sheet_name='Part 1', usecols='B,C,E')
df.dropna(axis=0, how='any', inplace=True)

# print(df.groupby(1).count(0))
print(df)
# print(df.groupby('CommodityID')['PosGroupID'].count().filter(lambda x:x>1))
print(df.groupby('CommodityID')['PosGroupID'].filter(lambda x: len(x) >= 2))