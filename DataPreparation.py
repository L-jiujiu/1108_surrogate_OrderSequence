import numpy as np
import pandas as pd
import os
import openpyxl

from Class import Sku

def init_sku_time(path_sku_time_map,num_sku,Mean,StandardDeviation):
    # 生成time随机数
    random_normal = np.random.normal(Mean, StandardDeviation, num_sku)
    sku_time = []
    for rdm in random_normal:
        if (rdm < 1):
            rdm = 1
        sku_time.append(round(rdm, 0))

    wb_file=path_sku_time_map
    data_time = pd.DataFrame(sku_time)
    data_time.columns = ['Time']
    book = openpyxl.load_workbook(wb_file)  # 读取你要写入的workbook
    writer = pd.ExcelWriter(wb_file, engine='openpyxl')
    writer.book = book
    writer.sheets = dict((ws.title, ws) for ws in book.worksheets)
    data_time.to_excel(writer, sheet_name="Part 1", index=False, startcol=4, startrow=0)
    writer.save()

def init_sku_time_1(path_sku_time_map,num_sku):
    # 生成time随机数
    sku_time=[1]*num_sku

    wb_file=path_sku_time_map
    data_time = pd.DataFrame(sku_time)
    data_time.columns = ['Time']
    book = openpyxl.load_workbook(wb_file)  # 读取你要写入的workbook
    writer = pd.ExcelWriter(wb_file, engine='openpyxl')
    writer.book = book
    writer.sheets = dict((ws.title, ws) for ws in book.worksheets)
    data_time.to_excel(writer, sheet_name="Part 1", index=False, startcol=4, startrow=0)
    writer.save()

def evaluation(vars,flag):
    cwd = os.getcwd()  # 读取当前文件夹路径

    path_order_sku_map = cwd + '/Fa_data/OrderPickDetail.xlsx'
    path_sku_time_map = cwd + '/Fa_data/PickLinePos_time.xlsx'

    # 初始化sku所在的分区：sku名称，sku处理所需时间、sku所在分区
    df = pd.read_excel(path_sku_time_map, sheet_name='Part 1', usecols='B,C,E')
    df.dropna(axis=0, how='any', inplace=True)
    df.reset_index(inplace=True,drop=True)
    data_count = df.values
    num_sku = len(data_count)
    print('所有Sku数量为：%d ' % num_sku)
    # print(vars)
    # print(df)

    # 重新读取更新后的SKU Time数据
    if(flag==1):
        df['Time']=pd.Series(vars)

    sku_list=[]
    data = df.values
    for i in range(0, num_sku):
        sku_input = {
            'name': str(int(data[i][1])),  # sku名称
            'num': i,  # sku序号
            'sectionID': str(int(data[i][0])),  # GroupID,sku所在分区
            'sku_time': vars[i],  # sku处理所需时间（默认为1）

            # 'sku_time': vars[i],  # sku处理所需时间（默认为1）
        }
        sku_list.append(Sku(sku_input))
    # ————————————————————————————
    # 初始化order，sku表dataframe叫df，order表dataframe叫data
    data = pd.read_excel(path_order_sku_map, sheet_name='Part 1', usecols='A,B,C,D',
                         names=['OrderID', 'CommodityID', 'Amount', 'PosGroupID'])
    # data[data['CommodityID']==329725618]['PosGroupID']=2101

    # 根据SKU的处理用时和订单包含的SKU个数计算单SKU的处理时间
    data_skuorder = pd.merge(data, df, on=['CommodityID', 'PosGroupID'], how='left')
    # data_skuorder.dropna(axis=0, how='any', inplace=True)
    print(data_skuorder[data_skuorder.isna().any(axis=1)])

    data_skuorder.insert(data_skuorder.shape[1], 'Time*Amount',
                         data_skuorder['Amount'] * data_skuorder['Time'])
    # data_num = data_skuorder['PosGroupID'].count()  # order拆散的sku信息总条数
    num_order = data_skuorder['PosGroupID'].groupby(data_skuorder['OrderID']).count().size  # 统计订单总个数

    # print(self.num_order)
    # print(data_skuorder)
    data_order_gb = data_skuorder.groupby(['OrderID', 'PosGroupID'])['Time*Amount'].sum()  # 统计order在各section的用时之和
    data_order = pd.DataFrame(data_order_gb)
    data_order.reset_index(inplace=True)
    data_order['id'] = data_order['OrderID'].rank(ascending=1, method='dense').astype(int)
    # print(data_order)

    order_array = np.zeros((num_order, 6))
    order_array_01 = np.zeros((num_order, 6))

    # 创建初始order-section矩阵[行数line:num_order,列数col:num_section[8个],按照012345，-1，-2]
    for index, row in data_order.iterrows():
        # 修改订单用时矩阵
        order_array[row['id'] - 1, int(row['PosGroupID'] / 100 - 17)] = row['Time*Amount']
        order_array_01[row['id'] - 1, int(row['PosGroupID'] / 100 - 17)] = 1

    # np.set_printoptions(threshold=np.sys.maxsize)
    # print(f'order_array 6:{self.order_array}')
    order_mainstream_workstep = np.ones((1, num_order))
    order_array = np.insert(order_array, 6, order_mainstream_workstep, axis=1)
    order_array = np.insert(order_array, 7, order_mainstream_workstep, axis=1)
    order_array_01 = np.insert(order_array_01, 6, np.zeros((1, num_order)), axis=1)
    order_array_01 = np.insert(order_array_01, 7, np.zeros((1, num_order)), axis=1)

    # print(
    #     f'所有SKU数量为:{num_sku},所有Order数量为:{num_order}')

    total_workload_array=order_array.sum(axis=0)
    total_workload_array01=order_array_01.sum(axis=0)

    print(list(order_array.sum(axis=0)))
    print(list(order_array_01.sum(axis=0)))
    # print(len(order_array.sum(axis=0)))
    # print(order_array.sum(axis=0))

    busy_sad=0
    for i in range(0,6):
        for j in range(i+1,6):
            buff=abs(total_workload_array[i] - total_workload_array[j])
            busy_sad = busy_sad + buff
            # print(f'{i}-{j}:{buff}')
    # print(busy_sad)
    # print('\n')

    busy_sad01 = 0
    for i in range(0, 6):
        for j in range(i + 1, 6):
            buf=abs(total_workload_array01[i] - total_workload_array01[j])
            busy_sad01 = busy_sad01 + buf
            # print(f'{i}-{j}:{buf}')
    # print(busy_sad01)
    return busy_sad

def test_sku_section_popularity():
    # 用于测试各[section,sku]的popularity
    cwd = os.getcwd()  # 读取当前文件夹路径

    path_order_sku_map = cwd + '/Fa_data/OrderPickDetail.xlsx'
    path_sku_time_map = cwd + '/Fa_data/PickLinePos_time.xlsx'

    data_order = pd.read_excel(path_order_sku_map, sheet_name='Part 1', usecols='A,B,C,D',
                         names=['OrderID', 'CommodityID', 'Amount', 'PosGroupID'])
    print('-------------')
    # print(data_order.groupby('PosGroupID')['OrderID'].apply(lambda x:len(x)))
    # print(data_order.groupby('CommodityID')['OrderID'].apply(lambda x:len(x)))

    df=data_order.groupby(['PosGroupID','CommodityID'])['OrderID'].apply(lambda x: len(x))
    data_order = pd.DataFrame(df)
    data_order.reset_index(inplace=True, drop=False)
    data_order=data_order.sort_values(by='OrderID',ascending=False)
    print(data_order.head(10))
    # print(data_order.groupby('PosGroupID')['OrderID'].apply(lambda x:len(x)))


def test_sku_amount_popularity():
    cwd = os.getcwd()  # 读取当前文件夹路径

    path_order_sku_map = cwd + '/Fa_data/OrderPickDetail.xlsx'

    data_order = pd.read_excel(path_order_sku_map, sheet_name='Part 1', usecols='A,B,C,D',
                               names=['OrderID', 'CommodityID', 'Amount', 'PosGroupID'])
    df=data_order.groupby(['CommodityID','PosGroupID'])['Amount'].apply(lambda x:sum(x))
    data_order = pd.DataFrame(df)
    print(data_order)
    data_order.reset_index(inplace=True, drop=False)
    data_order = data_order.sort_values(by='Amount', ascending=False)
    print(data_order.head(10))
    # print(data_order)
    dff=data_order.groupby('PosGroupID').apply(lambda x:x.sort_values('Amount',ascending=False))
    print(dff)
    # dff.to_excel('excel_1.xlsx',sheet_name='Sheet1',index=True)

def sku_all_used():
    # 用于测试sku表中的235个sku是否都被order list用到了
    cwd = os.getcwd()  # 读取当前文件夹路径
    path_order_sku_map = cwd + '/Fa_data/OrderPickDetail.xlsx'
    path_sku_time_map = cwd + '/Fa_data/PickLinePos_time.xlsx'

    # data_sku = pd.read_excel(path_sku_time_map, sheet_name='Part 1', usecols='B,C,E')

    data_sku = pd.read_excel(path_sku_time_map, sheet_name='Part 1', usecols='B,C')
    data_sku.dropna(axis=0, how='any', inplace=True)
    data_sku.reset_index(inplace=True, drop=True)
    data_sku=data_sku.astype('int')
    print(data_sku)

    data_order = pd.read_excel(path_order_sku_map, sheet_name='Part 1', usecols='B,D',
                         names=['CommodityID','PosGroupID'])
    ofo=['PosGroupID','CommodityID']
    data_order=data_order[ofo]

    wnc=list(data_order.groupby(['PosGroupID','CommodityID']).groups.keys())
    print(len(wnc))
    wnc_sku=list(data_sku.groupby(['PosGroupID','CommodityID']).groups.keys())
    # print(wnc_sku)
    print(len(wnc_sku))

    for i in wnc:
        if i not in wnc_sku:
            print(i)
    # ordersku_array=data_order.values
    # sku_array=data_sku.values
    # sku_array=data_sku['CommodityID'].to_list()
    #





    # 每个工区各40个sku

def combine_data():
    # 修改新的picklinepos
    cwd = os.getcwd()  # 读取当前文件夹路径

    # path_order_sku_map = cwd + '/Fa_data/OrderPickDetail.xlsx'
    path_sku_time_map = cwd + '/Fa_data/basedata/PickLinePos_time.xlsx'
    path_adjust=cwd+'/Fa_data/basedata/excel_1.xlsx' # 用来手动调整时间
    # 初始化sku所在的分区：sku名称，sku处理所需时间、sku所在分区
    df = pd.read_excel(path_sku_time_map, sheet_name='Part 1', usecols='A,B,C,D')
    df.dropna(axis=0, how='any', inplace=True)
    df.reset_index(inplace=True, drop=True)
    data_count = df.values

    num_sku = len(data_count)
    df_a = pd.read_excel(path_adjust, sheet_name='Sheet1', usecols='A,B,D')
    print('所有Sku数量为：%d ' % num_sku)
    print(df)
    print(df_a)

    dfm = pd.merge(df, df_a, on=['CommodityID', 'PosGroupID'], how='left')
    # dfm=dfm.drop('Time',axis=1)

    # data_skuorder.dropna(axis=0, how='any', inplace=True)
    # print(data_skuorder[data_skuorder.isna().any(axis=1)])
    print(dfm)
    print(len(dfm))
    dfm.to_excel(cwd+'/Fa_data/PickLinePos_time.xlsx',sheet_name='Part 1',index=False)


if __name__ == "__main__":
    vars=[1]*240 #list(np.ones(235))
    # flag=1：重新赋值，0：取表
    busy_sad=evaluation(vars,flag=0)
    # test_sku_section_popularity()
    # test_sku_amount_popularity()
    # sku_all_used()
    # combine_data()