# -*- coding:utf-8 -*-
"""
作者：l_jiujiu
日期：2021.11.17
"""
import copy

import numpy as np
import pandas as pd
import time as tm
import os

from Class import Sku, Section, Order, Time, Data_Analysis
from Other_Functions import Find_Section_now_num, Check_jam, \
    display_order_list_simple, display_order_list
    # Func_Cost_sequence_simple, \
    # Func_Cost_sequence,


class Simulation:
    def __init__(self, simulation_config):
        self.T = simulation_config['T'] # 最高仿真时长
        self.path_order_sku_map = simulation_config['path_order_sku_map'] # order-sku图
        self.path_sku_time_map = simulation_config['path_sku_time_map'] # sku-section图

        self.type = simulation_config['type_order']
        self.pace = simulation_config['pace']

        # 1、初始化section
        self.num_section = simulation_config['num_section']
        self.num_section_main = simulation_config['num_section_main']
        self.section_list = []
        # 2、初始化sku
        self.num_sku = 0
        self.sku_list = []
        # 是否初始化分区/SKU/订单的用时
        self.new_sku_time = simulation_config['new_sku_time']
        self.normal_info = simulation_config['normal_info']
        # 3、初始化订单
        self.num_order = 0
        self.order_notstart = []  # 未发出的order
        self.order_start = []  # 已经开始流转的order
        self.order_finish = []  # 已经流转结束的order
        self.order_before_section = -1

        # 初始化画图工具
        self.data_analysis = Data_Analysis()

        # 初始化sku、订单信息，生成订单在各分区的用时矩阵order_array
        self.init_section()
        self.init_skuorder()

        # + surrogate
        self.busy_section = [0, 0, 0, 0, 0, 0]  # 工站繁忙的总次数
        self.busy_variance_sum = 0
        self.op_method = simulation_config['optimization_method']

        # 导入GA的排序
        self.order_list_GA = simulation_config['order_list_GA']


    def init_section(self):
        # 初始化6个section信息：分区名称、正在等待的订单数量、处理订单列表
        # print('所有Section个数为：%d' % self.num_section,'主干道中转站个数为：%d'%self.num_section_main)
        for i in range(0, (self.num_section), 1):
            section_input = {
                'name': str(i + 17) + '01',  # 分区名称
                'num': i,  # 分区序号
                'max_order_num': 6  # 最多停滞order数量
            }
            self.section_list.append(Section(section_input))

        for j in range(-(self.num_section_main), 0, 1):
            section_input = {
                'name': 'section_{}'.format(j),  # 分区名称
                'num': j,  # 分区序号
                'max_order_num': 1  # 最多停滞order数量

            }
            self.section_list.append(Section(section_input))
        self.section_list_copy=copy.deepcopy(self.section_list)
            # self.section_list.copy()
    def init_skuorder(self):
        # 初始化sku所在的分区：sku名称，sku处理所需时间、sku所在分区
        df = pd.read_excel(self.path_sku_time_map, sheet_name='Part 1', usecols='B,C,E')
        df.dropna(axis=0, how='any', inplace=True)
        data_count = df.values
        self.num_sku = len(data_count)
        # print('所有Sku数量为：%d ' % self.num_sku)
        # 是否按正态分布随机生成SKU处理用时
        if (self.new_sku_time == '1'):
            # print('正在更新sku时间……')
            self.data_analysis.init_sku_time(path_sku_time_map=self.path_sku_time_map, num_sku=self.num_sku,
                                             Mean=self.normal_info[0], StandardDeviation=self.normal_info[1])
            # print('sku时间已更新')
            df = pd.read_excel(self.path_sku_time_map, sheet_name='Part 1', usecols='B,C,E')
            df.dropna(axis=0, how='any', inplace=True)
        elif (self.new_sku_time == '111'):
            # print('正在更新sku时间……')
            self.data_analysis.init_sku_time_1(path_sku_time_map=self.path_sku_time_map, num_sku=self.num_sku)
            # print('sku时间已全部更新为1')
            df = pd.read_excel(self.path_sku_time_map, sheet_name='Part 1', usecols='B,C,E')
            df.dropna(axis=0, how='any', inplace=True)
        else:
            pass
            # print('sku时间未更新')
        # 重新读取更新后的SKU Time数据
        data = df.values
        for i in range(0, self.num_sku):
            sku_input = {
                'name': str(int(data[i][1])),  # sku名称
                'num': i,  # sku序号
                'sectionID': str(int(data[i][0])),  # GroupID,sku所在分区
                'sku_time': int(data[i][2]),  # sku处理所需时间（默认为1）
            }
            self.sku_list.append(Sku(sku_input))
            self.sku_list_copy=copy.deepcopy(self.sku_list)
        # ————————————————————————————
        # 初始化order，sku表dataframe叫df，order表dataframe叫data
        data = pd.read_excel(self.path_order_sku_map, sheet_name='Part 1', usecols='A,B,C,D',
                             names=['OrderID', 'CommodityID', 'Amount', 'PosGroupID'])
        # 根据SKU的处理用时和订单包含的SKU个数计算单SKU的处理时间
        data_skuorder=pd.merge(data,df,on=['CommodityID','PosGroupID'],how='left')
        data_skuorder.dropna(axis=0, how='any', inplace=True)
        data_skuorder.insert(data_skuorder.shape[1], 'Time*Amount',
                             data_skuorder['Amount']*data_skuorder['Time'])
        # data_num = data_skuorder['PosGroupID'].count()  # order拆散的sku信息总条数
        self.num_order = data_skuorder['PosGroupID'].groupby(data_skuorder['OrderID']).count().size # 统计订单总个数

        # 用于保存所有订单是否派发的情况，如果派发了，则对应order_id位置的矩阵改成1
        self.order_notstart_array=np.zeros((self.num_order,1))

        # print(self.num_order)
        # print(data_skuorder)
        data_order_gb=data_skuorder.groupby(['OrderID','PosGroupID'])['Time*Amount'].sum() # 统计order在各section的用时之和
        data_order=pd.DataFrame(data_order_gb)
        data_order.reset_index(inplace=True)
        data_order['id']=data_order['OrderID'].rank(ascending=1,method='dense').astype(int)
        # print(data_order)
        self.order_array = np.zeros((self.num_order, self.num_section))

        # 创建初始order-section矩阵[行数line:num_order,列数col:num_section[6个]]
        for index,row in data_order.iterrows():
            # 修改订单用时矩阵
            self.order_array[row['id']-1,int(row['PosGroupID']/100-17)]=row['Time*Amount']
        # print(self.order_array)

        for i in range(0, self.num_order):
            # 根据订单组成计算各工序用时，并加入主干道节点信息，生成工序表work_schedule
            work_schedule_dic = {'0': 0, '1': 0, '-1': 0, '2': 0, '3': 0, '-2': 0, '4': 0, '5': 0}
            for j in range(0,6):
                if(self.order_array[i,j]!=0):
                    work_schedule_dic[str(j)]=self.order_array[i,j]
                else:
                    work_schedule_dic.pop(str(j))
            work_schedule = [[k, v] for k, v in work_schedule_dic.items()]  # 将字典转化为列表
            # print(work_schedule)
            order_name=data_order[data_order['id']-1 == i]['OrderID'].unique()[0]
        # 初始化订单运行时间数据
            time_input = {'order_name': order_name,
                          # 'now_section_list': [],
                          'time_enter_section': 0,
                          'time_start_process': 0,
                          'period_process': 0,
                          'time_leave_section': 0}

            order_input = {'name': order_name,  # 订单名称
                           'num': i,  # 订单序号
                           'work_schedule': work_schedule,
                           'time': Time(time_input)}
            self.order_notstart.append(Order(order_input))

        self.order_notstart_copy=copy.deepcopy(self.order_notstart)
            # self.order_notstart.deepcopy() # 存一个副本，用于下次调用
        # 统计只去往一个分区的简单订单的个数和比例 simple_rate
        simple_num = 0
        for order in self.order_notstart:
            if (len(order.work_schedule) == 3):
                simple_num = simple_num + 1
        self.simple_rate=simple_num/self.num_order
        print(f'所有SKU数量为:{self.num_sku},所有Order数量为:{self.num_order},去往一个分区的Order占比:{self.simple_rate}')

    def recycle_initial(self):
        # 重复调用仿真时的初始化设置
        # print(self.order_notstart_origin)
        self.sku_list=copy.deepcopy(self.sku_list_copy)
        self.section_list=copy.deepcopy(self.section_list_copy)

        self.order_notstart=copy.deepcopy(self.order_notstart_copy)
        self.order_notstart_array=np.zeros((self.num_order,1))
        self.order_start = []  # 已经开始流转的order
        self.order_finish = []  # 已经流转结束的order
        self.order_before_section = -1

        self.busy_section = [0, 0, 0, 0, 0, 0]  # 工站繁忙的总次数
        self.busy_variance_sum = 0
        self.op_method = simulation_config['optimization_method']
        self.data_analysis = Data_Analysis()

    # 订单派发算法
    def Func_Assign_Order_Tools(self, order_now,time):
        # print(f'当前派发的订单为:order_{order_now.num}')

        # 3\赋予section_now为order_now第一个不为负的section，得到第一个不为负section的编号和当前order所处的工序
        order_now.now_section_num, order_now.now_schedule_num = Find_Section_now_num(order_now)
        # print('当前派发的订单为%s'%order_now.name,',地点为%s'%self.section_list[order_now.now_section_num].name,"对应工序序号为%d"%order_now.now_schedule_num,'工序为:%s'%order_now.work_schedule)

        # 4\在section等待队列中加入订单信息(订单序号，订单在该区用时)
        self.section_list[order_now.now_section_num].Add_to_waiting_order_list(order_now, time)

        # 5\更新order_before_section：上一个派发订单第一个取得非主路section
        self.order_before_section = order_now.now_section_num

        # 6\修改订单时间信息
        order_now.time.time_enter_section = time

        # 7\在未发出订单信息中删除order_now
        for i in range(len(self.order_notstart)):
            if (self.order_notstart[i].name == order_now.name):
                # print(f'num:{self.order_notstart[i].num},')
                self.order_notstart_array[(self.order_notstart[i].num,0)] = 100000
                self.order_start.append(self.order_notstart[i])
                self.order_notstart.pop(i)
                break

    def rule_process_weight(self,weight):
        # 用于获得订单-工站 次序权重矩阵
        # 按照去到工站的顺序依次分配权重:把weight结合到订单需要拜访工站的先后顺序上
        order_array_nonzero = np.nonzero(self.order_array)
        order_array_weight = np.zeros((self.num_order, self.num_section))
        weight_flag = 0
        # 生成先后要去的不同工区各自的权重
        for i in range(0, len(order_array_nonzero[0])):
            if (i == 0):
                weight_flag = 0
            elif (order_array_nonzero[0][i] == order_array_nonzero[0][i - 1]):
                weight_flag = weight_flag + 1
            else:
                weight_flag = 0
            order_array_weight[order_array_nonzero[0][i], order_array_nonzero[1][i]] = weight[weight_flag]
        return order_array_weight

    # cost_cal_rule为各个决策规则，返回的是order的排序，也就是order num
    def cost_cal_rule1(self):
        # 决策规则1：多项式 𝒄𝒐𝒔𝒕=𝒂×𝑷_𝟎+𝒃×𝑷_𝟏+𝒄×𝑷_𝟐，多个最小就选第1个
        cost_all = np.dot(self.order_array_weight_all, self.section_busyness_array) # 订单次序权重 点乘 工站实时工作状态
        cost=cost_all+self.order_notstart_array # 将已经完成派发的订单赋极大值
        min = np.argmin(cost) # 取cost最小的订单进行派发
        line,col = np.where(cost == np.min(cost)) # line就是当前最小的order序号，对于已经派发的订单，他的order array weight是极大的数10000
        # print(line)

        # print(f'cost最小的行是：{line},派发的订单是:{order_costmin.num}-{order_costmin.name}')
        return line[0]
    def cost_cal_rule2(self):
        # 决策规则2：多项式 𝒄𝒐𝒔𝒕=𝒂×𝑷_𝟎+𝒃×𝑷_𝟏+𝒄×𝑷_𝟐 + 多个最小就选去的工区与上一个不同的
        cost_all = np.dot(self.order_array_weight_all, self.section_busyness_array) # 订单次序权重 点乘 工站实时工作状态
        cost=cost_all+self.order_notstart_array # 将已经完成派发的订单赋极大值
        min = np.argmin(cost) # 取cost最小的订单进行派发
        line,col = np.where(cost == np.min(cost)) # line就是当前最小的order序号，对于已经派发的订单，他的order array weight是极大的数10000
        # print(line)
        # print(f'cost最小的行是：{line},派发的订单是:{order_costmin.num}-{order_costmin.name}')
        return line[0]

    # 配合Rules,Order_Select
    def Order_Select_Rules(self, time):
        order_num=self.cost_cal_rule1()
        for order in self.order_notstart:
            if order.num==order_num:
                order_pick=order
                break
        # 检测该派发的订单是否会在第一个主路上被堵住
        order_now = Check_jam(order_pick, self.section_list)

        if order_now == 'error':
            # print('error')
            return 0
        else:
            self.Func_Assign_Order_Tools(order_now,time)
            return 1

    # 配合GA的订单派发算法
    def Order_Select_OriginGA(self, time, order_num):
        order_now = None
        for i in range(0, len(self.order_notstart)):
            if self.order_notstart[i].num == order_num:
                order_now = self.order_notstart[i]
                break
            else:
                continue
        order_now = Check_jam(order_now, self.section_list)
        if order_now == 'error':
            # print('error')
            return 0
        else:
            self.Func_Assign_Order_Tools(order_now,time)
            return 1

    # 移动到下一个分区
    def Func_Move_To_Next_Schedule(self, order_now, section_list, time):
        while (int(order_now.now_schedule_num) + 1 < len(order_now.work_schedule)):
            # 当前order的下一个目标分区
            section_next = section_list[int(order_now.work_schedule[order_now.now_schedule_num + 1][0])]
            if ((len(section_next.waiting_order_list) + len(section_next.process_order_list) + len(
                    section_next.finish_order_list)) >= section_next.max_order_num):
                # 堵了：now_schedule_num不变，将order加入到now_schedule_num的finish_list中，break
                section_list[int(order_now.work_schedule[order_now.now_schedule_num][0])].Add_to_finish_order_list(
                    order_now)
                break
            else:
                # 不堵：看now_schedule_num + 1是main还是section
                if (section_next.num < 0):  # 是main
                    order_now.now_schedule_num = order_now.now_schedule_num + 1
                else:  # 是section
                    order_now.now_schedule_num = order_now.now_schedule_num + 1
                    section_list[int(order_now.work_schedule[order_now.now_schedule_num][0])].Add_to_waiting_order_list(
                        order_now, time + 1)
                    break
        else:
            return 0
        return 1


    # 仿真主函数
    def run(self,rule):
        order_count_GA = 0
        self.order_array_weight_all = self.rule_process_weight(weight=rule)
        # print(self.order_notstart)
        # print(self.order_finish)
        # print(self.order_start)
        for t in range(1, self.T):
            # print("\n")
            # print(
            #     "--------------------------\n     当前时刻为%d\n--------------------------" %
            #     t)

            # 记录当前时刻的系统的繁忙情况
            # 创建初始section-busyness矩阵[行数line:num_section,列数col:num_section[6个]]
            self.section_busyness_array = np.zeros((self.num_section, 1))
            for i in range(0, self.num_section):
                # print(self.section_list[i].name)
                self.section_busyness_array[i, 0] = len(self.section_list[i].waiting_order_list) \
                                                    + len(self.section_list[i].process_order_list) \
                                                    + len(self.section_list[i].finish_order_list)

            # step1：下发新的订单
            # print(len(self.order_notstart))
            if ((t + 1) % self.pace == 0):
                # print('pace is OK')
                if (len(self.order_notstart) != 0):
                    if (self.type == 'GA_origin'):
                        # print(f'接下来该派发第{order_count_GA}个订单：order_{self.order_list_GA[order_count_GA]}')
                        # print(f'接下来该派发第{self.order_list_GA[order_count_GA]}个订单')
                        flag = self.Order_Select_OriginGA(time=t, order_num=self.order_list_GA[order_count_GA])
                        if flag == 1:
                            order_count_GA = order_count_GA + 1

                    elif (self.type == 'rules_simple'):
                        # print(f'接下来该派发第{order_count_GA}个订单：order_{self.order_list_GA[order_count_GA]}')
                        # print(f'接下来该派发第{self.order_list_GA[order_count_GA]}个订单')
                        self.Order_Select_Rules(time=t)

                else:
                    # print('*********无order可派发*********\n')
                    pass
            # step2：储存绘图数据
            self.data_analysis.save_y_t(time=t, section_list=self.section_list, plot=self.data_analysis)
            # print('各section初始情况：')
            # display_order_list(self.section_list, type='main')
            # display_order_list(self.section_list,type='all')

            # step3：对每个section进行正序遍历，依次完成当前section中的任务
            #     print('\n*********对各section中订单进行遍历，依次完成*********')
            for i in range(0, 6):
                self.section_list[i].Process_order(time=t)
            # # 测试数据
            # print('各section完成初始订单后：')
            # display_order_list(self.section_list,type='all')

            # step4：对每个section+mainstream进行倒序遍历，依次对section中finish的订单进行移动
            list_test = [5, 4, -2, 3, 2, -1, 1, 0]
            for list_num in list_test:
                section_now = self.section_list[list_num]
                count = len(section_now.finish_order_list)

                while (count > 0):
                    order_now = section_now.finish_order_list[0]
                    section_now.finish_order_list.pop(0)
                    count = count - 1
                    # print('%s'%section_now.name,'中的%s'%order_now.name,'移动')

                    key = self.Func_Move_To_Next_Schedule(order_now=order_now, section_list=self.section_list, time=t)
                    if (key == 0):
                        # print('%s' % order_now.name, '已完成全部任务')
                        self.order_finish.append(order_now)

            # 展示数据
            # print('\nt=%d' % t, '时刻结束：', end='\n')
            # display_order_list(self.section_list, type='main')
            # print('\norder_start%d:'%len(self.order_start), end='')
            # display_order_list_simple(self.order_start)
            # print('order_finish%d:'%len(self.order_finish), end='')
            # display_order_list_simple(self.order_finish)

            # 记录主路拥堵订单情况
            if (len(self.section_list[7].finish_order_list) != 0):
                self.data_analysis.main_jam_1 = self.data_analysis.main_jam_1 + 1  # 主路的拥堵情况
            if (len(self.section_list[6].finish_order_list) != 0):
                self.data_analysis.main_jam_2 = self.data_analysis.main_jam_2 + 1  # 主路的拥堵情况

            # todo:记录各工位工作情况，目前有array！
            busy_scene = [0, 0, 0, 0, 0, 0]
            for i in range(0, 6):
                if ((len(self.section_list[i].process_order_list) + len(self.section_list[i].waiting_order_list)) > 0):
                    self.busy_section[i] = self.busy_section[i] + 1
                    busy_scene[i] = len(self.section_list[i].process_order_list) + len(
                        self.section_list[i].waiting_order_list)
            self.busy_variance_sum = self.busy_variance_sum + np.var(busy_scene)
            # print(self.busy_section)

            # 订单全部完成，退出循环
            if (len(self.order_finish) == self.num_order):
                T_last = t
                break

        # 展示数据（总结）
        if ((self.op_method == 'surrogate') and (self.type == 'new')) or (
                (self.op_method == 'surrogate') and (self.type == 'rules_simple')):
            print('[Order：%d ' % self.num_order,'Sku：%d]' % self.num_sku,',type:%s'%self.type,',pace:%d'%self.pace)
            # print('[Order：%d ' % self.num_order,'Sku：%d]' % self.num_sku,',type:%s'%self.type,',pace:%d'%self.pace,'\nsku_time信息:%s'%self.sku_time_num)
            print('完成全部订单共计循环次数：%d' % T_last)
            print('主路-1拥堵情况：%d' % self.data_analysis.main_jam_1,
                  '主路-2拥堵情况：%d' % self.data_analysis.main_jam_2)
            # # 计算忙碌的方差：
            print(
                f'各section忙碌情况的方差为：{np.var(self.busy_section)},平均值为：{np.mean(self.busy_section)},busy_section:{self.busy_section}')
            print(f'工时方差为：{self.busy_variance_sum}')

        order_start_list = []
        for order in self.order_start:
            order_start_list.append(order.num)

        self.data_analysis.xls_output(self.order_start, self.type)

        results = {
            'T_last': T_last,
            'jam_1': self.data_analysis.main_jam_1,
            'jam_2': self.data_analysis.main_jam_2,
            'busy_variance': self.busy_variance_sum,
            'order_start_list':order_start_list
        }
        return results


if __name__ == "__main__":
    start = tm.perf_counter()  # 记录当前时刻
    import os
    import warnings
    warnings.filterwarnings('ignore')

    cwd = os.getcwd()  # 读取当前文件夹路径

    weight_list=[
        [1, 0.5, 0.3],
        [1,0,0],
                 ]
    from simulation_config import simulation_config
    simulation_1 = Simulation(simulation_config)  # 初始化仿真实例

    for i in range(0,len(weight_list)):
        if i>0:
            simulation_1.recycle_initial() # 第二次仿真需要重启部分设置
        print(f"\nweight:{weight_list[i]}")
        results = simulation_1.run(rule=weight_list[i])  # 运行仿真
        T_last = results['T_last']
        jam_1 = results['jam_1']
        jam_2 = results['jam_2']
        busy_variance = results['busy_variance']
        sum_result = T_last / 6.944 + (jam_1 + jam_2) / 0.88 + busy_variance / 22.728

        # print(f"订单派发列表:{results['order_start_list']}")
        print(T_last, jam_1, jam_2, jam_1 + jam_2, busy_variance, sum_result)
        # simulation_1.data_analysis.plot_results_plotly() #绘图

    end = tm.perf_counter()
    print("程序共计用时 : %s Seconds " % (end - start))
