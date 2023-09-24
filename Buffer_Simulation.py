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
import random

from Buffer_Class import Sku, Section, Order, Time, Data_Analysis
from a_Other_Functions import Find_Section_now_num, Check_jam, Check_jam_all, \
    display_order_list_simple, display_order_list
from Buffer_Fast_track import find_shorted_path

from Tool_Gantt import DrawGantt
from itertools import chain


# import warnings
# warnings.filterwarnings('ignore')
class Simulation:
    def __init__(self, simulation_config):
        self.T = simulation_config['T']  # 最高仿真时长
        self.step = simulation_config['step']  # 时序仿真节奏
        self.path_order_sku_map = simulation_config['path_order_sku_map']  # order-sku图
        self.path_sku_time_map = simulation_config['path_sku_time_map']  # sku-section图

        self.type = simulation_config['schedule_type']
        self.rule = simulation_config['rule']
        self.pace = simulation_config['pace']

        # 1、初始化section
        self.num_section = simulation_config['num_section']
        self.num_section_main = simulation_config['num_section_main']
        self.section_list = []
        # 2、初始化sku
        self.num_sku = 0
        self.sku_list = []
        # 3、初始化订单
        self.num_order = 0
        self.order_notstart = []  # 未发出的order
        self.order_start = []  # 已经开始流转的order
        self.order_start_num = []  # 已经开始流转的order
        self.order_finish = []  # 已经流转结束的order
        self.order_before_section = -99
        self.buffer_num = simulation_config['buffer_num']

        # 初始化画图工具
        self.data_analysis = Data_Analysis()

        # 初始化sku、订单信息，生成订单在各分区的用时矩阵order_array
        self.init_section()
        self.init_skuorder()

        # + surrogate
        self.busy_variance_sum = 0
        self.op_method = simulation_config['optimization_method']

        # 导入GA的排序
        self.order_list_GA = simulation_config['order_list_GA']
        # 初始化recorder
        self.init_workload_recorder()
        print('init 了')
        self.order_du = 0
        # self.weight_buffer=simulation_config['rule_buffer']
        self.weight_buffer=[]

    def init_section(self):
        # 初始化6个section信息：分区名称、正在等待的订单数量、处理订单列表
        # print('所有Section个数为：%d' % self.num_section,'主干道中转站个数为：%d'%self.num_section_main)
        for i in range(0, (self.num_section), 1):
            section_input = {
                'name': str(i + 17) + '01',  # 分区名称
                'num': i,  # 分区序号
                'max_order_num': 1 + self.buffer_num  # 最多停滞order数量
            }
            self.section_list.append(Section(section_input))

        # main
        for j in range(-(self.num_section_main), 0, 1):
            section_input = {
                'name': 'section_{}'.format(j),  # 分区名称
                'num': j,  # 分区序号
                'max_order_num': 1  # 最多停滞order数量
            }
            self.section_list.append(Section(section_input))
        self.section_list_copy = copy.deepcopy(self.section_list)
        # self.section_list.copy()

    def init_skuorder(self):
        # 初始化sku所在的分区：sku名称，sku处理所需时间、sku所在分区
        df = pd.read_excel(self.path_sku_time_map, sheet_name='Part 1', usecols='B,C,E')
        df.dropna(axis=0, how='any', inplace=True)
        data_count = df.values
        self.num_sku = len(data_count)
        # print('所有Sku数量为：%d ' % self.num_sku)

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
            self.sku_list_copy = copy.deepcopy(self.sku_list)
        # ————————————————————————————
        # 初始化order，sku表dataframe叫df，order表dataframe叫data
        data = pd.read_excel(self.path_order_sku_map, sheet_name='Part 1', usecols='A,B,C,D',
                             names=['OrderID', 'CommodityID', 'Amount', 'PosGroupID'])
        # 根据SKU的处理用时和订单包含的SKU个数计算单SKU的处理时间
        data_skuorder = pd.merge(data, df, on=['CommodityID', 'PosGroupID'], how='left')
        data_skuorder.dropna(axis=0, how='any', inplace=True)
        data_skuorder.insert(data_skuorder.shape[1], 'Time*Amount',
                             data_skuorder['Amount'] * data_skuorder['Time'])
        # data_num = data_skuorder['PosGroupID'].count()  # order拆散的sku信息总条数
        self.num_order = data_skuorder['PosGroupID'].groupby(data_skuorder['OrderID']).count().size  # 统计订单总个数

        # 用于保存所有订单是否派发的情况，如果派发了，则对应order_id位置的矩阵改成1
        self.order_notstart_array = np.zeros((self.num_order, 1))
        # self.order_start_array = np.zeros((self.num_order, 0))

        # print(self.num_order)
        # print(data_skuorder)
        data_order_gb = data_skuorder.groupby(['OrderID', 'PosGroupID'])['Time*Amount'].sum()  # 统计order在各section的用时之和
        data_order = pd.DataFrame(data_order_gb)
        data_order.reset_index(inplace=True)
        data_order['id'] = data_order['OrderID'].rank(ascending=1, method='dense').astype(int)
        # print(data_order)
        self.order_array = np.zeros((self.num_order, self.num_section))
        self.order_array_main0 = np.zeros((self.num_order, self.num_section))
        self.order_array_01 = np.zeros((self.num_order, self.num_section))

        # 创建初始order-section矩阵[行数line:num_order,列数col:num_section[8个],按照012345，-1，-2]
        for index, row in data_order.iterrows():
            # 修改订单用时矩阵
            self.order_array[int(row['id']) - 1, int(row['PosGroupID'] / 100 - 17)] = row['Time*Amount']
            self.order_array_01[int(row['id']) - 1, int(row['PosGroupID'] / 100 - 17)] = 1
            self.order_array_main0[int(row['id']) - 1, int(row['PosGroupID'] / 100 - 17)] = 1
        # np.set_printoptions(threshold=np.sys.maxsize)
        # print(f'order_array 6:{self.order_array}')
        order_mainstream_workstep = np.ones((1, self.num_order))

        self.order_array = np.insert(self.order_array, 6, order_mainstream_workstep, axis=1)
        self.order_array = np.insert(self.order_array, 7, order_mainstream_workstep, axis=1)

        self.order_array_main0 = np.insert(self.order_array_main0, 6, np.zeros((1, self.num_order)), axis=1)
        self.order_array_main0 = np.insert(self.order_array_main0, 7, np.zeros((1, self.num_order)), axis=1)

        self.order_array_01 = np.insert(self.order_array_01, 6, np.zeros((1, self.num_order)), axis=1)
        self.order_array_01 = np.insert(self.order_array_01, 7, np.zeros((1, self.num_order)), axis=1)
        # print(f'self.order_array_01:{self.order_array_01}')

        # print(f'ssss:{self.order_array_main0}')
        # np.set_printoptions(threshold=np.sys.maxsize)
        # print(f'order_array 7:{self.order_array}')

        for i in range(0, self.num_order):
            # 根据订单组成计算各工序用时，并加入主干道节点信息，生成工序表work_schedule
            work_schedule_dic = {'0': 0, '1': 0, '-1': 0, '2': 0, '3': 0, '-2': 0, '4': 0, '5': 0}
            for j in range(0, 6):
                if (self.order_array[i, j] != 0):
                    work_schedule_dic[str(j)] = self.order_array[i, j]
                else:
                    work_schedule_dic.pop(str(j))
            work_schedule = [[k, v] for k, v in work_schedule_dic.items()]  # 将字典转化为列表
            # print(work_schedule)
            order_name = data_order[data_order['id'] - 1 == i]['OrderID'].unique()[0]
            # 初始化订单运行时间数据
            time_input = {'order_name': order_name,
                          # 'now_section_list': [],
                          'time_enter_section': [0, 0, 0, 0, 0, 0, 0, 0],
                          'time_start_process': [0, 0, 0, 0, 0, 0, 0, 0],
                          'period_process': 0,
                          'time_leave_section': [0, 0, 0, 0, 0, 0, 0, 0]}

            order_input = {'name': order_name,  # 订单名称
                           'num': i,  # 订单序号
                           'work_schedule': work_schedule,
                           'time': Time(time_input)}
            self.order_notstart.append(Order(order_input))

        self.order_notstart_copy = copy.deepcopy(self.order_notstart)
        # self.order_notstart.deepcopy() # 存一个副本，用于下次调用
        # 统计只去往一个分区的简单订单的个数和比例 simple_rate
        simple_num = 0
        for order in self.order_notstart:
            if (len(order.work_schedule) == 3):
                simple_num = simple_num + 1
        self.simple_rate = simple_num / self.num_order
        print(
            f'所有SKU数量为:{self.num_sku},所有Order数量为:{self.num_order},去往一个分区的Order占比:{self.simple_rate}')
        # total_workload_array=self.order_array.sum(axis=0)
        # print(len(self.order_array.sum(axis=0)))
        # print(self.order_array.sum(axis=0))
        #
        # busy_sad=0
        # for i in range(0,6):
        #     for j in range(i+1,6):
        #         busy_sad = busy_sad + abs(total_workload_array[i] - total_workload_array[j])
        # print(busy_sad)
        self.order_array_first = np.zeros((self.num_order, self.num_section))
        self.order_array_second = np.zeros((self.num_order, self.num_section))
        self.order_array_third = np.zeros((self.num_order, self.num_section))

    def recycle_initial(self):
        # 重复调用仿真时的初始化设置
        # print(self.order_notstart_origin)
        self.sku_list = copy.deepcopy(self.sku_list_copy)
        self.section_list = copy.deepcopy(self.section_list_copy)

        self.order_notstart = copy.deepcopy(self.order_notstart_copy)
        self.order_notstart_array = np.zeros((self.num_order, 1))
        self.order_start = []  # 已经开始流转的order
        self.order_start_num = []  # 已经开始流转的order
        self.order_finish = []  # 已经流转结束的order
        self.order_before_section = -1

        self.busy_variance_sum = 0
        # self.op_method = simulation_config['optimization_method']
        self.data_analysis = Data_Analysis()
        # print('recycle了')

    def recycle_initial_GA(self, GA):
        # 重复调用仿真时的初始化设置,需要更新order顺序表时
        # print(self.order_notstart_origin)
        self.sku_list = copy.deepcopy(self.sku_list_copy)
        self.section_list = copy.deepcopy(self.section_list_copy)

        self.order_notstart = copy.deepcopy(self.order_notstart_copy)
        self.order_notstart_array = np.zeros((self.num_order, 1))
        self.order_start = []  # 已经开始流转的order
        self.order_start_num = []  # 已经开始流转的order
        self.order_finish = []  # 已经流转结束的order
        self.order_before_section = -1

        self.busy_variance_sum = 0
        # self.op_method = simulation_config['optimization_method']
        self.data_analysis = Data_Analysis()

        self.order_list_GA = GA
        # print(GA)
        # print('recycle了')

    # 订单派发算法
    def Func_Assign_Order_Tools(self, order_now, time):
        # print(f'当前派发的订单为:order_{order_now.num}')

        # 3\赋予section_now为order_now第一个不为负的section，得到第一个不为负section的编号和当前order所处的工序
        order_now.now_section_num, order_now.now_schedule_num = Find_Section_now_num(order_now)
        # print('当前派发的订单为%s'%order_now.name,',地点为%s'%self.section_list[order_now.now_section_num].name,"对应工序序号为%d"%order_now.now_schedule_num,'工序为:%s'%order_now.work_schedule)

        # 4\在section等待队列中加入订单信息(订单序号，订单在该区用时)
        self.section_list[order_now.now_section_num].Add_to_waiting_order_list(order_now, time)
        # print(order_now.num, order_now.now_section_num)

        # 5\更新order_before_section：上一个派发订单第一个去的非主路section
        self.order_before_section = order_now.now_section_num

        # 6\修改订单时间信息
        # order_now.time.time_enter_section[order_now.now_section_num] = time

        # 7\在未发出订单信息中删除order_now
        for i in range(len(self.order_notstart)):
            if (self.order_notstart[i].name == order_now.name):
                # print(f'num:{self.order_notstart[i].num},')
                self.order_notstart_array[(self.order_notstart[i].num, 0)] = 10000
                self.order_start.append(self.order_notstart[i])
                self.order_notstart.pop(i)
                break

    def rule_process_weight(self, rule):
        # 用于获得订单-工站 次序权重矩阵
        # 按照去到工站的顺序依次分配权重:把weight结合到订单需要拜访工站的先后顺序上
        order_array_ori = copy.deepcopy(self.order_array)
        # print('ori')
        # print(order_array_ori)
        order_array_ori = np.delete(order_array_ori, obj=7, axis=1)
        order_array_ori = np.delete(order_array_ori, obj=6, axis=1)
        # print('del')
        # print(order_array_ori)

        order_array_nonzero = np.nonzero(order_array_ori)
        order_array_weight = np.zeros((self.num_order, self.num_section))

        weight_flag = 0
        # 生成先后要去的不同工区各自的权重
        # print(len(order_array_nonzero[0]))
        self.order_first_section = []
        for i in range(0, len(order_array_nonzero[0])):
            if (i == 0):
                weight_flag = 0
            elif (order_array_nonzero[0][i] == order_array_nonzero[0][i - 1]):
                weight_flag = weight_flag + 1
            else:
                weight_flag = 0
            order_array_weight[order_array_nonzero[0][i], order_array_nonzero[1][i]] = rule[weight_flag]
            if (weight_flag == 0):
                self.order_first_section.append(order_array_nonzero[1][i])
                self.order_array_first[order_array_nonzero[0][i], order_array_nonzero[1][i]] = 1
            elif (weight_flag == 1):
                self.order_array_second[order_array_nonzero[0][i], order_array_nonzero[1][i]] = 1
            elif (weight_flag == 2):
                self.order_array_third[order_array_nonzero[0][i], order_array_nonzero[1][i]] = 1

        # print(self.order_array)
        # print(f'self.order_array_first:{self.order_array_first}')
        # print(f'self.order_array_second:{self.order_array_second}')
        # print(f'self.order_array_third:{self.order_array_third}')
        # print(f'order_first_section({len(self.order_first_section)}):{self.order_first_section})')

        # self.order_first_section

        # 加上主路，都是必经之路
        order_mainstream_workstep = np.zeros((1, self.num_order))
        order_array_weight = np.insert(order_array_weight, 6, order_mainstream_workstep, axis=1)
        order_array_weight = np.insert(order_array_weight, 7, order_mainstream_workstep, axis=1)
        # np.set_printoptions(threshold=np.sys.maxsize)
        # print(f'order_array 7:{order_array_weight}')

        # print(order_total_time_rank)

        return order_array_weight

    # # cost_cal_rule为各个决策规则，返回的是order的排序，也就是order num
    def cost_cal_rule(self):
        if self.rule == 'Fa_origin':
            order_id = None
            for order in self.order_notstart:
                jam_check = Check_jam(order, self.section_busyness_array, max=self.section_list[0].max_order_num)
                if jam_check == 'error':
                    continue
                for i in range(len(order.work_schedule)):
                    if (int(order.work_schedule[i][0]) < 0):  # 如果第i步为mainstream，跳过这一步判断下一步是否还为mainstream
                        continue
                    else:
                        section_waiting_num = \
                            len(self.section_list[int(order.work_schedule[i][0])].waiting_order_list) \
                            + len(self.section_list[int(order.work_schedule[i][0])].process_order_list) \
                            + len(self.section_list[int(order.work_schedule[i][0])].finish_order_list)
                        break
                if section_waiting_num == 0:
                    order_id = order.num
                    break
                else:
                    continue
            return order_id

        elif self.rule == 'random':
            rand = random.randint(0, len(self.order_notstart) - 1)
            order_id = self.order_notstart[rand].num
            return order_id

        elif self.rule == 'sequentially':
            order_id = self.order_notstart[0].num
            return order_id

        elif self.rule == 'T':
            cost_all = np.dot(self.order_array_weight_all, self.section_busyness_time_array)  # 订单次序权重 点乘 工站实时工作状态
            cost = cost_all + self.order_notstart_array  # 将已经完成派发的订单赋极大值
            line, col = np.where(cost == np.min(cost))  # line就是当前最小的order序号，对于已经派发的订单，他的order array weight是极大的数10000
            return line[0]

        elif self.rule == 'N':
            # print(self.section_busyness_array)
            cost_all = np.dot(self.order_array_weight_all, self.section_busyness_array)  # 订单次序权重 点乘 工站实时工作状态
            cost = cost_all + self.order_notstart_array  # 将已经完成派发的订单赋极大值
            line, col = np.where(cost == np.min(cost))  # line就是当前最小的order序号，对于已经派发的订单，他的order array weight是极大的数10000
            return line[0]

        elif self.rule == 'Npro':
            # 决策规则1pro：多项式 𝒄𝒐𝒔𝒕=𝒂×N_𝟎+𝒃×N_𝟏+𝒄×N_𝟐，多个最小就选第1个，N代表工区缓冲区+工作区（当前+即将到达的）订单数量
            cost_all = np.dot(self.order_array_weight_all, self.section_busyness_array_pro)  # 订单次序权重 点乘 工站实时工作状态
            cost = cost_all + self.order_notstart_array  # 将已经完成派发的订单赋极大值
            line, col = np.where(cost == np.min(cost))  # line就是当前最小的order序号，对于已经派发的订单，他的order array weight是极大的数10000
            return line[0]

        elif self.rule == 'Tpro':
            # 决策规则2pro：多项式 𝒄𝒐𝒔𝒕=𝒂×T_𝟎+𝒃×T_𝟏+𝒄×T_𝟐，多个最小就选第1个，T代表工区缓冲区+工作区（当前+即将到达的）订单待加工时间
            cost_all = np.dot(self.order_array_weight_all, self.section_busyness_time_array_pro)  # 订单次序权重 点乘 工站实时工作状态
            cost = cost_all + self.order_notstart_array  # 将已经完成派发的订单赋极大值
            line, col = np.where(cost == np.min(cost))  # line就是当前最小的order序号，对于已经派发的订单，他的order array weight是极大的数10000
            return line[0]

        elif self.rule == 'LPT':
            # 最短的订单先发
            order_return = None
            busy_section = np.where(self.section_process_array[:6, 0] != 0)
            jam_array = np.zeros(6)
            if self.section_busyness_array[6, 0] != 0:
                jam_array[2] = 1
                jam_array[3] = 1
                jam_array[4] = 1
                jam_array[5] = 1
            elif self.section_busyness_array[7, 0] != 0:
                jam_array[4] = 1
                jam_array[5] = 1
            busy_array = [0, 0, 0, 0, 0, 0]
            for i in busy_section[0]:
                busy_array[i] = 1
            cost_checkjam = np.dot(self.order_array_first, jam_array + busy_array)
            cost_checkjam = cost_checkjam + self.order_notstart_array[:, 0] / 100
            order_notjam_num = np.where(
                cost_checkjam == 0)  # line就是当前最小的order序号，对于已经派发的订单，他的order array weight是极大的数10000
            # 目前可以发的订单集合
            order_notjam_num_list = list(order_notjam_num[0])
            if len(order_notjam_num_list) == 0:
                return None
            order_cannot_array = np.ones((self.num_order, 1))
            for order in order_notjam_num_list:
                order_cannot_array[order, 0] = 0

            # 如果当前所有工区都不忙，则发一个耗时最长的订单:
            # if np.sum(busy_array) == 0:
            for i in range(0, len(self.order_total_time_rank)):
                if self.order_total_time_rank[i] in order_notjam_num_list:
                    order_return = self.order_total_time_rank[i]
                    break
            return order_return

        elif self.rule == 'SPT':
            order_list=[]
            for order in self.order_notstart:
                order_list.append(order.num)
            for i in range(len(self.order_total_time_rank) - 1, -1, -1):
                if self.order_total_time_rank[i] in order_list:
                    order_return = self.order_total_time_rank[i]
                    break
            return order_return

        elif self.rule == 'LPT':
            order_list=[]
            for order in self.order_notstart:
                order_list.append(order.num)
            for i in range(0,len(self.order_total_time_rank)):
                if self.order_total_time_rank[i] in order_list:
                    order_return = self.order_total_time_rank[i]
                    break
            return order_return

        # elif self.rule=='Buffer':
        #     # 当前系统中订单 如果完成需要花费的时间
        #     print(self.section_busyness_array_pro)
        #     max_section_now=np.max(self.section_busyness_array_pro)
        #     line_max_section, col_max_section = np.where(self.section_busyness_array_pro == np.max(self.section_busyness_array_pro))  # line就是当前最小的order序号，对于已经派发的订单，他的order array weight是极大的数10000
        #     print(line_max_section[0])
        #     if(max_section_now!=0):
        #         # print(f'max_section_now:{max_section_now}')
        #         # 当前分区的busy状态，从1*8变为6557*8
        #         b = np.transpose(np.tile(self.section_busyness_array_pro, (1, self.num_order)))
        #         # 决策规则2pro：多项式 𝒄𝒐𝒔𝒕=𝒂×T_𝟎+𝒃×T_𝟏+𝒄×T_𝟐，多个最小就选第1个，T代表工区缓冲区+工作区（当前+即将到达的）订单待加工时间
        #         # print(f'self.order_array_main0:{self.order_array_main0}')
        #         # print(self.order_notstart_array)
        #         not_start_1000 = np.tile(self.order_notstart_array/100, (1, 8))
        #         # print(f'not_start_1000:{not_start_1000}\nb:{b}')
        #         prepare=b+not_start_1000
        #         cost=prepare+self.order_array_main0  # 订单即将完成时间+系统累计用时,也就是新加入了这个订单后，会对系统产生的影响
        #         # cost=cost+self.order_notstart_array
        #         # print(f'cost:{cost}')
        #         order_cost_max=np.max(cost,axis=1)
        #         # print(order_cost_max)
        #         order_can=[i for i,x in enumerate(order_cost_max) if x<=line_max_section[0]]
        #         # print(order_can)
        #
        #         if len(order_can)>0:
        #             order_rank=[self.order_total_time_rank[i] for i in order_can]
        #             # print(order_rank)
        #             # print(min(order_rank))
        #             order_return=self.order_total_time_rank.index(min(order_rank))
        #             # print(order_return)
        #             return order_return
        #         else:
        #             cost_max_section=cost[:,line_max_section[0]]
        #             # print(f'cost_max_section:{cost_max_section}')
        #             line_order_pick=np.where(cost_max_section==np.min(cost_max_section))
        #             # print(line_order_pick[0][0])
        #             return line_order_pick[0][0]
        #     else:
        #         # print(self.order_notstart_array)
        #         # print(self.order_total_time_rank)
        #         order_notstart_array_count = np.reshape(self.order_notstart_array, (self.num_order))
        #         print(order_notstart_array_count)
        #         cost_max_section = self.order_total_time_rank + order_notstart_array_count
        #         line_order_pick=np.where(cost_max_section==np.min(cost_max_section))
        #         print(line_order_pick)
        #         print(line_order_pick[0][0])
        #         return line_order_pick[0][0]
        #     # order_array_nonzero = np.nonzero(order_array_ori)
        #
        #     # # max_order_all=np.min(cost[:,line_max_section[0]])
        #     # # line_order_pick, col_order_pick = np.where()  # line就是当前最小的order序号，对于已经派发的订单，他的order array weight是极大的数10000
        #     #
        #     # # order_pick=
        #     # # print(f'max_order_all:{max_order_all}')
        #     # # 订单发出去后 对各个工区 工作的 影响
        #     # cost=np.sum(cost,axis=1)
        #     # print(f'costtt:{cost}')
        #     # # print(self.order_notstart_array)
        #     # cost = np.transpose(cost).reshape(self.num_order,1) + self.order_notstart_array  # 将已经完成派发的订单赋极大值
        #     # # print('kaolv:',cost)
        #     # line, col = np.where(cost == np.min(cost))  # line就是当前最小的order序号，对于已经派发的订单，他的order array weight是极大的数10000
        #     # return line[0]
        #     # # return 0

        elif self.rule == 'TT':
            order_return = None
            busy_section = np.where(self.section_process_array[:6, 0] != 0)
            jam_array = np.zeros(6)
            if self.section_busyness_array[6, 0] != 0:
                jam_array[2] = 1
                jam_array[3] = 1
                jam_array[4] = 1
                jam_array[5] = 1
            elif self.section_busyness_array[7, 0] != 0:
                jam_array[4] = 1
                jam_array[5] = 1
            busy_array = [0, 0, 0, 0, 0, 0]
            for i in busy_section[0]:
                busy_array[i] = 1
            cost_checkjam = np.dot(self.order_array_first, jam_array + busy_array)
            cost_checkjam = cost_checkjam + self.order_notstart_array[:, 0] / 100
            order_notjam_num = np.where(
                cost_checkjam == 0)  # line就是当前最小的order序号，对于已经派发的订单，他的order array weight是极大的数10000
            # 目前可以发的订单集合
            order_notjam_num_list = list(order_notjam_num[0])
            if len(order_notjam_num_list)==0:
                return None
            order_cannot_array = np.ones((self.num_order, 1))
            for order in order_notjam_num_list:
                order_cannot_array[order, 0] = 0

            # 如果当前所有工区都不忙，则发一个耗时最长的订单:
            if np.sum(busy_array) == 0:
                for i in range(0, len(self.order_total_time_rank)):
                    if self.order_total_time_rank[i] in order_notjam_num_list:
                        order_return = self.order_total_time_rank[i]
                        break
                return order_return
            else:
                cost_all = np.dot(self.order_array_weight_all, self.section_busyness_time_array)  # 订单次序权重 点乘 工站实时工作状态
                cost = cost_all + order_cannot_array*100  # 将已经完成派发的订单赋极大值
                line, col = np.where(
                    cost == np.min(cost))  # line就是当前最小的order序号，对于已经派发的订单，他的order array weight是极大的数10000
                return line[0]

                # order_id_list = []
                # order_timecal_list = []
                # for order in self.order_notstart:
                #     order_id_list.append(order.num)
                #
                # order_return = order_id_list[order_timecal_list.index(max(order_timecal_list))]
                # return order_return

        elif self.rule == 'Buffer':
            order_return = None
            # 【可发订单筛选】
            # 派发的时候不能堵：如果main-1堵了，则不发第一个分区是section2345的订单，elif如果main-2堵了，则不发第一个分区是section45的订单
            # 派发的时候工区得有空：识别各工区的工况，如果有分区当前正在处理的订单是空的，则筛选第一个分区去这些空分区的订单
            # print(f'busyness:{self.section_busyness_array[:,0]}')
            # print(f'process:{self.section_process_array[:,0]}')
            busy_section = np.where(self.section_process_array[:6, 0] != 0)
            # print(busy_section[0])
            # 主路main堵了
            jam_array = np.zeros(6)
            # print(f'jam_array:{jam_array}')
            if self.section_busyness_array[6, 0] != 0:
                jam_array[2] = 1
                jam_array[3] = 1
                jam_array[4] = 1
                jam_array[5] = 1
            elif self.section_busyness_array[7, 0] != 0:
                jam_array[4] = 1
                jam_array[5] = 1
            # print(f'jam_array:{jam_array}')
            busy_array = [0, 0, 0, 0, 0, 0]
            for i in busy_section[0]:
                busy_array[i] = 1
            # print(f'busy_array:{busy_array}')

            cost_checkjam = np.dot(self.order_array_first, jam_array + busy_array)
            # print(f'cost_checkjam jam&busy:{cost_checkjam}')
            cost_checkjam = cost_checkjam + self.order_notstart_array[:, 0] / 100
            # print(cost_checkjam)
            order_notjam_num = np.where(
                cost_checkjam == 0)  # line就是当前最小的order序号，对于已经派发的订单，他的order array weight是极大的数10000

            # 目前可以发的订单集合
            order_notjam_num_list = list(order_notjam_num[0])
            # print(f'当前时刻可以派发的订单id:{order_notjam_num_list}')

            if len(order_notjam_num_list)==0:
                # print('都不能发')
                return None

            # 如果当前所有工区都不忙，则发一个耗时最长的订单:
            if np.sum(busy_array) == 0:
                for i in range(0, len(self.order_total_time_rank)):
                    if self.order_total_time_rank[i] in order_notjam_num_list:
                        order_return = self.order_total_time_rank[i]
                        break
                # print('都不忙，发耗时的订单')
                return order_return
            else:
                # 如果有有工区在忙，需要计算各分区实时可用时间
                max_time, section_list_lefttime, section_list_lefttime_pre = self.Cal_Available_time_in_Gantt()

                print(f'关键路径用时：{max_time}')
                # print(f'【后面的空余】各点从最早完成到关键路径间的剩余时间:{section_list_lefttime}')
                # print(f'【前面的空余】各点从现在到最迟开始时间的剩余时间：{section_list_lefttime_pre}')

                order_id_list=[]
                order_timecal_list=[]
                # 第1个工序(本来就是空的)，考虑｜time-前空余｜的绝对值，好的订单cost是少的，尽量填满 1
                # 第2、3个工序，考虑｜time-后空余｜，好的订单cost相加起来是最少的，干扰最少 1，1
                for order in self.order_notstart:
                    if order.num not in order_notjam_num_list:
                        continue
                    order_id_list.append(order.num)
                    # print(self.order_array)
                    # print(order.num,order.work_schedule)
                    weight=self.weight_buffer

                    # 第一个目标工区
                    order_section_first=self.order_array_first[order.num,:]
                    order_time_first=np.sum(np.multiply(self.order_array[order.num,:6],order_section_first))
                    # 前面的空余：
                    section_list_lefttime_pre_1=np.sum(np.multiply(section_list_lefttime_pre,order_section_first))
                    # 后面的空余：
                    section_list_lefttime_1 = np.sum(np.multiply(section_list_lefttime, order_section_first))
                    # weight=[5,3,1,10,5,3]

                    # 如果order time少于区间冗余空间，则计order time；如果多于区间冗余空间，则计多出去的值，所以选一个最大的
                    first_dif_pre=order_time_first*weight[0] if section_list_lefttime_pre_1-order_time_first>=0 else (section_list_lefttime_pre_1-order_time_first)*weight[1]
                    first_dif=first_dif_pre


                    # 第二个目标工区
                    order_section_second = self.order_array_second[order.num, :]
                    order_time_second = np.sum(np.multiply(self.order_array[order.num, :6], order_section_second))
                    section_list_lefttime_2 = np.sum(np.multiply(section_list_lefttime, order_section_second))
                    section_list_lefttime_pre_2 = np.sum(np.multiply(section_list_lefttime_pre, order_section_second))

                    section_list_lefttime_2_real=max(section_list_lefttime_2,section_list_lefttime_pre_2)

                    # second_dif_aft=order_time_second*weight[2] if section_list_lefttime_2-order_time_second>=0 else (section_list_lefttime_2-order_time_second)*weight[3]
                    # second_dif_pre=order_time_second*weight[2] if section_list_lefttime_pre_2-order_time_second>=0 else (section_list_lefttime_pre_2-order_time_second)*weight[3]

                    # second_dif=abs(second_dif_pre-second_dif_aft)

                    # section_list_lefttime_2_re = min(section_list_lefttime_2, max_time - order_time_first)
                    # section_list_lefttime_2_re=min(section_list_lefttime_2,section_list_lefttime_2-(order_time_first+section_list_lefttime_2-max_time)/2)
                    # section_list_lefttime_2_re_pre=min(section_list_lefttime_pre_2,section_list_lefttime_pre_2-(order_time_first+section_list_lefttime_pre_2-max_time)/2)
                    # section_list_lefttime_2_re=section_list_lefttime_2_re_pre
                    # second_dif_re = order_time_second * weight[2] if section_list_lefttime_2_re - order_time_second >= 0 else (section_list_lefttime_2_re - order_time_second) * weight[3]
                    second_dif_re = order_time_second * weight[2] if section_list_lefttime_2_real - order_time_second >= 0 else (section_list_lefttime_2_real - order_time_second) * weight[3]
                    second_dif=second_dif_re


                    order_section_third = self.order_array_third[order.num, :]
                    order_time_third = np.sum(np.multiply(self.order_array[order.num, :6], order_section_third))
                    section_list_lefttime_3 = np.sum(np.multiply(section_list_lefttime, order_section_third))
                    section_list_lefttime_pre_3 = np.sum(np.multiply(section_list_lefttime_pre, order_section_third))
                    section_list_lefttime_3_real = section_list_lefttime_pre_3-(max_time-section_list_lefttime_2+order_time_second)

                    third_dif_re=order_time_third*weight[4] if section_list_lefttime_3_real-order_time_third>=0 else (section_list_lefttime_3_real-order_time_third)*weight[5]


                    # third_dif_aft=order_time_third*weight[4] if section_list_lefttime_3-order_time_third>=0 else (section_list_lefttime_3-order_time_third)*weight[5]
                    # third_dif_pre=order_time_third*weight[4] if section_list_lefttime_pre_3-order_time_third>=0 else (section_list_lefttime_pre_3-order_time_third)*weight[5]
                    # third_dif=abs(third_dif_aft-third_dif_pre)
                    # third_dif=third_dif_aft
                    # third_dif=third_dif_pre

                    # section_list_lefttime_3_re=min(section_list_lefttime_3,section_list_lefttime_3-(order_time_first+order_time_second+section_list_lefttime_3-max_time)/2)
                    # section_list_lefttime_3_re_pre=min(section_list_lefttime_pre_3,section_list_lefttime_pre_3-(order_time_first+order_time_second+section_list_lefttime_pre_3-max_time)/2)
                    # section_list_lefttime_3_re=min(section_list_lefttime_3_re_pre,section_list_lefttime_3_re)

                    third_dif=third_dif_re

                    time_cal=np.sum(first_dif)+\
                             np.sum(second_dif)+\
                             np.sum(third_dif)
                    # print(time_cal)
                    order_timecal_list.append(time_cal)

                order_return=order_id_list[order_timecal_list.index(max(order_timecal_list))]
                # print(f'index:{order_id_list[order_timecal_list.index(max(order_timecal_list))]}')
                print(f'决定派发订单order_{order_return}:cost={max(order_timecal_list)}')
                return order_return


    def Cal_Available_time_in_Gantt(self):
        node_list = []
        edge_list = []
        all_order_insection = [[], [], [], [], [], [], ]
        section_process_available = [0, 0, 0, 0, 0, 0]

        for section in self.section_list:
            # print(section.name)
            if (len(section.process_order_list) > 0):
                section_process_available[section.num] = 1
            for process in section.process_order_list:
                # print(f'process:{process.name}{process.work_schedule}')
                # 过滤掉工时为0的工序
                work_schedule_copy = copy.deepcopy(process.work_schedule)
                work_schedule_filter = list(filter(lambda x: x[1] != 0, work_schedule_copy))
                # print(f'w:{work_schedule_filter}')

                # 1\将所有工序以：[本工序，'D',本工序时间]：['E1', 'D', 1]的形式加入
                for i in range(0, len(work_schedule_filter)):
                    edge_list.append([str(process.name) + str(i), 'D', work_schedule_filter[i][1]])
                    node_list.append(str(process.name) + str(i))
                    all_order_insection[int(work_schedule_filter[i][0])].append(
                        [str(process.name) + str(i), work_schedule_filter[i][1]])

                # 2\[如果一个订单有2个及以上的工序，同一个订单工序的前一，后一，前一的时间]：['E1', 'E2', 1],
                len_schedule = len(work_schedule_filter)
                if len_schedule > 1:
                    for ii in range(0, len_schedule):
                        if ii + 1 < len_schedule:
                            edge_list.append([str(process.name) + str(ii), str(process.name) + str(ii + 1),
                                              work_schedule_filter[ii][1]])
            for wait in section.waiting_order_list:
                # print(f'wait:{wait.name}{wait.work_schedule}')
                # all_order_insection.append(wait.name)
                # 过滤掉工时为0的工序
                work_schedule_copy = copy.deepcopy(wait.work_schedule)
                work_schedule_filter = list(filter(lambda x: x[1]!= 0, work_schedule_copy))
                # print(f'w:{work_schedule_filter}')

                # 1\将所有工序以：[本工序，'D',本工序时间]：['E1', 'D', 1]的形式加入
                for i in range(0, len(work_schedule_filter)):
                    edge_list.append([str(wait.name) + str(i), 'D', work_schedule_filter[i][1]])
                    node_list.append(str(wait.name) + str(i))
                    all_order_insection[int(work_schedule_filter[i][0])].append(
                        [str(wait.name) + str(i), work_schedule_filter[i][1]])
                # {'0': [['E0', 1.0]], '1': [['E1', 1.0]], '2': [['A0', 2.0]], '3': [], '4': [['B0', 1.0], ['C0', 1.0]],
                #  '5': [['A1', 1.0]]}

                # 2\[如果一个订单有2个及以上的工序，同一个订单工序的前一，后一，前一的时间]：['E1', 'E2', 1],
                len_schedule = len(work_schedule_filter)
                if len_schedule > 1:
                    for ii in range(0, len_schedule):
                        if ii + 1 < len_schedule:
                            edge_list.append([str(wait.name) + str(ii), str(wait.name) + str(ii + 1),
                                              work_schedule_filter[ii][1]])
        # [['E1'], ['E2'], ['A1'], [], ['B1', 'C1'], ['A2']]
        # 3\[同一个工区订单的前一，后一，前一的时间]
        # print(f'all_order_insection:{all_order_insection}')
        for order_insection in all_order_insection:
            len_order_insection = len(order_insection)
            if (len_order_insection > 1):
                for ii in range(0, len_order_insection):
                    if ii + 1 < len_order_insection:
                        edge_list.append(
                            [order_insection[ii][0], order_insection[ii + 1][0], order_insection[ii][1]])
        node_list.append('D')
        # print(f'\nedge{len(edge_list)}:{edge_list}')
        # print(f'node{len(node_list)}:{node_list}')

        section_list_lefttime, section_list_lefttime_pre, max_time = find_shorted_path(node_list, edge_list,
                                                                                       all_order_insection)
        # 如果section process里面有订单，则前面的空余为0
        # print(section_process_available)
        for i in range(0, len(section_list_lefttime_pre)):
            if section_process_available[i] == 1:
                section_list_lefttime_pre[i] = 0

        # print(f'关键路径用时：{max_time}')
        # print(f'【后面的空余】各点从最早完成到关键路径间的剩余时间:\n{section_list_lefttime}')
        # print(f'【前面的空余】各点从现在到最迟开始时间的剩余时间：\n{section_list_lefttime_pre}')
        #
        return max_time, section_list_lefttime, section_list_lefttime_pre

    # 配合Rules,Order_Select
    def Order_Select_Rules(self, time):
        order_num = self.cost_cal_rule()
        if order_num is not None:
            for order in self.order_notstart:
                if order.num == order_num:
                    order_pick = order
                    break
        else:
            # self.order_du=self.order_du+1
            return 0
        # print(f'order_pick:{order_pick.num},{order_pick.work_schedule}')
        # print(np.transpose(self.section_waiting_array))

        order_now = Check_jam(order_pick, self.section_busyness_array, self.section_list[0].max_order_num)

        if order_now == 'error':
            # print('堵了，当前轮无法派发')
            # print(np.transpose(self.section_waiting_array))
            self.order_du = self.order_du + 1
            return 0
        else:
            self.Func_Assign_Order_Tools(order_now, time)
            self.order_start_num.append(order_now.num)
            self.order_insystem_array[order_now.num, :] = self.order_array_01[order_now.num, :]
            # print(f'befor:{self.order_insystem_array}')
            print(f'派发的订单是:order_{order_now.num}:{order_now.name},工序是:{order_now.work_schedule}')
            return 1

    # 已知订单排序的-配合GA的订单派发算法
    def Order_Select_OriginGA(self, time, order_num):
        # print(order_num)
        # if len(self.order_notstart)==0:
        #     return 0
        # print(self.order_notstart)
        # print(order_num)
        for order in self.order_notstart:
            if order.num == order_num:
                order_pick = order
                break
        # print(order_pick.num)
        # 检测该派发的订单是否会因为被堵住而无法派发
        order_now = Check_jam(order_pick, self.section_busyness_array, self.section_list[0].max_order_num)

        if order_now == 'error':
            # print('堵了，当前轮无法派发')
            # print(np.transpose(self.section_waiting_array))
            self.order_du = self.order_du + 1

            return 0
        else:  # 成功发出
            self.Func_Assign_Order_Tools(order_now, time)
            self.order_start_num.append(order_now.num)
            # print(f'成功发出{order_now.num}')
            return 1

    # 移动到下一个分区
    def Func_Move_To_Next_Schedule(self, order_now, section_list, time):
        while (int(order_now.now_schedule_num) + 1 < len(order_now.work_schedule)):
            # 当前order的下一个目标分区
            # print()
            section_next = section_list[int(order_now.work_schedule[order_now.now_schedule_num + 1][0])]
            # print(f'{order_now.num}section_next.num:{section_next.num}')
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
                    order_now.time.time_leave_section[order_now.now_schedule_num] = time + 1

                    break
        else:
            return 0
        return 1

    def init_workload_recorder(self):
        # [par1 工区缓冲区+工作区当前订单数量]section-busyness矩阵，表示各工区和主路等待订单的数量 [行数line:num_section,列数col:num_section[8个],顺序：012345，-1，-2]
        self.section_busyness_array = np.zeros((self.num_section + self.num_section_main, 1))
        self.section_waiting_array = np.zeros((self.num_section + self.num_section_main, 1))
        self.section_process_array = np.zeros((self.num_section + self.num_section_main, 1))
        self.section_finish_array = np.zeros((self.num_section + self.num_section_main, 1))

        # [par1-pro 工区缓冲区+工作区 即将到达+缓冲区 订单数量]section-busyness矩阵，表示各工区和主路等待订单的数量 [行数line:num_section,列数col:num_section[8个],顺序：012345，-1，-2]
        self.section_busyness_array_pro = np.zeros((self.num_section + self.num_section_main, 1))

        # [par2 工区缓冲区+工作区当前订单待加工时间]section-busyness-time矩阵，表示各工区等待的订单需要在本工区加工的时间，主路是它即将去到的工区目前processing剩余的时间 [行数line:num_section,列数col:num_section[8个],顺序：012345，-1，-2]
        self.section_busyness_time_array = np.zeros((self.num_section + self.num_section_main, 1))
        self.section_waiting_time_array = np.zeros((self.num_section + self.num_section_main, 1))
        self.section_processleft_time_array = np.zeros((self.num_section + self.num_section_main, 1))

        # [par2-pro 工区缓冲区+工作区 即将到达+缓冲区 订单待加工时间]section-busyness-time矩阵，表示所有工区等待的订单需要在本工区加工的时间，主路是它即将去到的工区目前processing剩余的时间 [行数line:num_section,列数col:num_section[8个],顺序：012345，-1，-2]
        self.section_busyness_time_array_pro = np.zeros((self.num_section + self.num_section_main, 1))

        # 记录工区拥堵情况
        self.section_jam_array = np.zeros((self.num_section + self.num_section_main, 1))

    def func_workload_recorder(self):
        # 记录当前时刻的系统的繁忙情况，收集决策规则中与 $工区$ 相关的参数
        # [par1 工区缓冲区+工作区订单数量]section-busyness矩阵，表示各工区和主路等待订单的数量 [行数line:num_section,列数col:num_section[8个],顺序：012345，-1，-2]
        for j in range(-2, 6):
            # print(self.section_list[i].name)
            if (j >= 0):
                i = j
            elif (j == -1):
                i = 6
            elif (j == -2):
                i = 7
            self.section_waiting_array[i, 0] = len(self.section_list[i].waiting_order_list)
            self.section_process_array[i, 0] = len(self.section_list[i].process_order_list)
            self.section_finish_array[i, 0] = len(self.section_list[i].finish_order_list)
        self.section_busyness_array = self.section_waiting_array + self.section_finish_array + self.section_process_array
        # print(f'waiting:{np.transpose(self.section_waiting_array)},process:{np.transpose(self.section_process_array)},'
        #       f'finish:{np.transpose(self.section_finish_array)},busyness:{np.transpose(self.section_busyness_array)}')
        # print(f'busyness:{np.transpose(self.section_busyness_array)}')

        # [par1-pro 工区缓冲区+工作区 即将到达的 订单数量]section-busyness矩阵，表示各工区和主路等待订单的数量 [行数line:num_section,列数col:num_section[8个],顺序：012345，-1，-2]
        section_insystem_array = np.sum(self.order_insystem_array, axis=0)
        section_insystem_array_1 = np.array(section_insystem_array).reshape(8, 1)
        self.section_busyness_array_pro = self.section_process_array + self.section_finish_array + section_insystem_array_1
        # print(f'insystem+:{np.transpose(section_insystem_array_1)}')
        # print(f'onprocess:{np.transpose(self.section_busyness_array)}')
        # print(f'======pro:{np.transpose(self.section_busyness_array_pro)}\n')

        # [par2 工区缓冲区+工作区订单待加工时间]section-busyness-time矩阵，表示各工区等待的订单需要在本工区加工的时间，主路是它即将去到的工区目前processing剩余的时间 [行数line:num_section,列数col:num_section[8个],顺序：012345，-1，-2]
        for j in range(-2, 6):
            # print(self.section_list[j].name)
            if (j >= 0):
                self.section_waiting_time_array[j, 0], \
                self.section_processleft_time_array[j, 0], \
                self.section_busyness_time_array[j, 0] = self.section_list[j].Count_time_section(
                    order_array=self.order_array)

        # print(f'Twait:{np.transpose(self.section_waiting_time_array)}'
        #       f'process_left:{np.transpose(self.section_processleft_time_array)}'
        #       f'busy:{np.transpose(self.section_busyness_time_array)}')

        # [par2-pro 工区缓冲区+工作区 即将到达+缓冲区 订单待加工时间]section-busyness-time矩阵，表示所有工区等待的订单需要在本工区加工的时间，主路是它即将去到的工区目前processing剩余的时间 [行数line:num_section,列数col:num_section[8个],顺序：012345，-1，-2]
        order_insystem_array_time = self.order_insystem_array * self.order_array
        # print('111')
        # print(order_insystem_array_time)
        section_insystem_array_time = np.sum(order_insystem_array_time, axis=0)
        section_insystem_array_time_1 = np.array(section_insystem_array_time).reshape(8, 1)
        self.section_busyness_time_array_pro = self.section_processleft_time_array + section_insystem_array_time_1
        # print(f'TProinsystem+:{np.transpose(section_insystem_array_time_1)}')
        # print(f'onprocess:{np.transpose(self.section_processleft_time_array)}')
        # print(f'waiting  :{np.transpose(self.section_waiting_time_array)}')
        # print(f'======pro:{np.transpose(self.section_busyness_time_array_pro)}\n')

        # print(self.section_busyness_array)
        county = np.ones((6, 1))
        for i in range(0, 6):
            if self.section_busyness_array[i] == 0:
                county[i, 0] = 0
        # print(county)
        # # [obj1]记录全部工位实时的不平衡性：0-5
        busy_sad = 0
        abs_list = []
        for i in range(0, 6):
            for j in range(i + 1, 6):
                # busy_sad = busy_sad + abs(self.section_busyness_array[i, 0] - self.section_busyness_array[j, 0])
                busy_sad = busy_sad + abs(county[i, 0] - county[j, 0])
                abs_list.append(abs(county[i, 0] - county[j, 0]))
        # print(f'sum{sum(abs_list)},{abs_list}')
        self.busy_variance_sum = self.busy_variance_sum + busy_sad

        # # [obj2]记录主路的拥堵次数：-1,-2
        if (self.section_busyness_array[6, 0] != 0):
            self.data_analysis.main_jam_1 = self.data_analysis.main_jam_1 + 1  # 主路的拥堵情况
        if (self.section_busyness_array[7, 0] != 0):
            self.data_analysis.main_jam_2 = self.data_analysis.main_jam_2 + 1  # 主路的拥堵情况

        self.section_jam_array = np.zeros((self.num_section + self.num_section_main, 1))
        for a in range(0, len(self.section_busyness_array)):
            if a in [0, 1, 2, 3, 4, 5]:
                if self.section_busyness_array[a, 0] >= 6:
                    self.section_jam_array[a, 0] = 1
            else:
                if self.section_busyness_array[a, 0] >= 1:
                    self.section_jam_array[a, 0] = 1
        # print(self.section_jam_array)

    def Gantt(self):
        order_start_time = []
        order_duration_time = []
        n_bay_start = []
        n_job_id = []

        for order in self.order_start:
            # print(
            #     f'{order.num}-enter:{order.time.time_enter_section},duration:{self.order_array[order.num, 0:6]},leave:{order.time.time_leave_section}')
            start_time = [x for i, x in enumerate(order.time.time_enter_section) if x != 0]
            # start=list(filter(lambda x: x > 0, order.time.time_enter_section))
            order_start_time.append([int(x) for x in start_time])

            n_job_id.append(len(start_time) * [int(order.num)])

            start_bay = [i for i, x in enumerate(order.time.time_enter_section) if x != 0]
            n_bay_start.append([int(x) for x in start_bay])

            duration = list(filter(lambda x: x > 0, self.order_array[order.num, 0:6]))
            order_duration_time.append([int(x) for x in duration])
        # print(self.order_array)
        Gantt_config = {
            'op': range(0, self.num_order),
            'n_start_time': list(chain(*order_start_time)),
            'n_bay_start': list(chain(*n_bay_start)),
            'n_duration_time': list(chain(*order_duration_time)),
            'n_job_id': list(chain(*n_job_id)),
            'type': self.rule
        }
        # n_start_time = list(chain(*order_start_time))
        # n_bay_start = list(chain(*n_bay_start))
        # n_duration_array = list(chain(*order_duration_time))
        # n_job_id = list(chain(*n_job_id))
        # print('n_start_time', n_start_time, '\n', 'n_bay_start', n_bay_start, '\n', 'n_duration_array',
        #       n_duration_array, '\n', 'n_job_id', n_job_id)

        Gantt = DrawGantt(Gantt_config)
        Gantt.draw_fjssp_gantt()

    # 仿真主函数
    def run(self, rule,rule_buffer):
        # print('111')
        order_count_GA = 0
        self.weight = rule
        self.weight_buffer=rule_buffer
        self.order_array_weight_all_list = []

        if (self.type == 'dynamic'):
            if len(self.weight) == 3 and self.rule != 'mix':
                self.order_array_weight_all = self.rule_process_weight(rule=rule)
            else:
                for i in range(0, len(self.weight)):
                    self.order_array_weight_all_list.append(self.rule_process_weight(rule=rule[i]))

        # print(f'self.order_array:{self.order_array}')
        # print(self.order_array_weight_all)

        # 用于输出订单完成时间的排序
        a = np.sum(self.order_array, axis=1)
        self.order_total_time_rank = sorted(range(len(a)), key=lambda k: a[k], reverse=True)
        # print(self.order_total_time_rank[0])
        # self.order_total_time_rank[0]对应的，是有最大完成时间的order-id

        # 用于标记在系统中的订单情况，可以汇总所有工区潜在需要完成的订单数量和时间
        self.order_insystem_array = np.zeros((self.num_order, self.num_section + self.num_section_main))
        self.data_analysis.num_order = self.num_order

        # 用于记录各工站总工作时间
        self.section_busyness_time = np.zeros((self.num_section, 1))
        # print(self.section_busyness_time)
        # 用于抽查路径的测试函数
        # list_test=[4821, 3084, 4028, 5470, 4371, 5553,]
        # for order in self.order_notstart:
        #     if order.num in list_test:
        #         print(order.num)
        #         print(order.name)
        #         print(order.work_schedule)
        # 开始时序仿真
        for t in np.arange(1, self.T, self.step):  # range(0, self.T):
            # print("\n")
            # print(
            #     "--------------------------\n     当前时刻为%d\n--------------------------" %
            #     t)
            # display_order_list(self.section_list, type='main')

            # print(1)
            # step1：下发新的订单
            # print(len(self.order_notstart))
            if ((t + 1) % self.pace == 0):
                # 记录当前状态
                self.func_workload_recorder()
                # print('pace is OK')
                if (len(self.order_notstart) != 0):
                    if (self.type == 'static'):  # 按照已知顺序下发订单
                        # print(f'count:{order_count_GA},order_num:{self.order_list_GA[order_count_GA]}')
                        flag = self.Order_Select_OriginGA(time=t, order_num=self.order_list_GA[order_count_GA])
                        if flag == 1:  # 如果成功发出，下一个就+1转到下一个位置
                            order_count_GA = order_count_GA + 1

                    elif (self.type == 'dynamic'):  # 按照实时决策下发订单
                        self.Order_Select_Rules(time=t)
                else:
                    # print('*********无order可派发*********\n')
                    pass
            # print('各section当前情况：')

            # step2：储存绘图数据
            self.data_analysis.save_y_t(time=t, plot=self.data_analysis, busyness_array=self.section_busyness_array,
                                        waiting_array=self.section_waiting_array,
                                        process_array=self.section_process_array,
                                        order_notstart=len(self.order_notstart),
                                        )

            # print('各section初始情况：')
            # display_order_list(self.section_list, type='main')

            # step3：对每个section进行正序遍历，依次完成当前section中的任务
            #     print('\n*********对各section中订单进行遍历，依次完成*********')
            for i in range(0, 6):
                self.section_list[i].Process_order(time=t, order_insystem_array=self.order_insystem_array,
                                                   timestep=self.step)
            # print(f'guiling:{self.order_insystem_array}')

            # step4：对每个section+mainstream进行倒序遍历，依次对section中finish的订单进行移动
            list_test = [5, 4, -2, 3, 2, -1, 1, 0]
            for list_num in list_test:
                section_now = self.section_list[list_num]
                count = len(section_now.finish_order_list)

                while (count > 0):
                    order_now = section_now.finish_order_list[0]
                    section_now.finish_order_list.pop(0)
                    count = count - 1
                    # print('%s'%section_now.num,'中的%s'%order_now.num,'移动')

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

            # 对所有订单更新一下它工区的wait到process
            for i in range(0, 6):
                if (len(self.section_list[i].process_order_list) == 0):  # process中无：判断waiting中是否有order
                    if (len(self.section_list[i].waiting_order_list) != 0):  # waiting中无：return 0
                        self.section_list[i].process_order_list.append(self.section_list[i].waiting_order_list[0])
                        self.section_list[i].waiting_order_list.pop(0)
                        self.section_list[i].process_order_list[0].time.time_start_process[
                            self.section_list[i].num] = t + 1

            # 订单全部完成，退出循环
            if (len(self.order_finish) == self.num_order):
                T_last = t
                break
        # 展示数据（总结）

        self.data_analysis.xls_output(self.order_start, self.type)

        # print('order_start')
        # for order in self.order_start:
        #     print(order.num)

        results = {
            'T_last': T_last,
            'jam_1': self.data_analysis.main_jam_1,
            'jam_2': self.data_analysis.main_jam_2,
            'busy_variance': self.busy_variance_sum/T_last,
            'order_start_list': self.order_start_num,
            'all': T_last + self.busy_variance_sum / 5
        }
        print(results)
        # print(self.order_du)
        return results


if __name__ == "__main__":
    start = tm.perf_counter()  # 记录当前时刻
    import os
    import warnings

    warnings.filterwarnings('ignore')

    cwd = os.getcwd()  # 读取当前文件夹路径

    weight_list = [
        [1, 0, 0],
    ]

    # 0:first+,1:first-, 2:second+,3:second-, 4:third+,5:third-
    weight_list_buffer=[
        # [0.5,1,0.5,1,0.5,1],
        [1,1,1,1,1,1],
        # [0,1,0,1,0,1],
        # [1,0,1,0,1,0],
        # [0.538604736328125, 0.4159088134765625, 0.5791749954223633, 0.684051513671875, 0.9298982620239258,
        #  0.066192626953125]
        #
        # [0.5,1,0.5,1,0.5,1],
        # [1,2,0.3,1.5,0.1,1],

        # [1,1,0.1,0.1,0.05,0.05]
        # [0.1, 1, 0.1, 0.8, 0.1, 0.5]
        # [0.1, 1, 0.08, 0.8, 0.05, 0.5]
        # [1, 20, 1, 10, 1, 10]
    ]
    from Buffer_Dynamic_simulation_config import simulation_config

    # simulation_config['order_list_GA']=[0,1,2,3]
    simulation_1 = Simulation(simulation_config)  # 初始化仿真实例
    print(simulation_1.rule)
    for i in range(0, len(weight_list)):
        # if i > 0:
        simulation_1.recycle_initial()  # 第二次仿真需要重启部分设置
        # print(f"\nweight:{weight_list_buffer[i]}")
        # simulation1.run
        # results = simulation_1.run(rule=[1, 0, 0])  # 运行仿真

        # simulation_1.rule_buffer=weight_list_buffer[i]
        results = simulation_1.run(rule=weight_list[i],rule_buffer=weight_list_buffer[i])  # 运行仿真

        # T_last = results['T_last']
        # jam_1 = results['jam_1']
        # jam_2 = results['jam_2']
        # busy_variance = results['busy_variance']
        # sum_result = T_last+ busy_variance / 28

        # print(f"订单派发列表:{results['order_start_list']}")
        # print(T_last, jam_1,jam_2,busy_variance)
        # print(results['order_start_list'])
        # print(T_last,busy_variance)

        simulation_1.data_analysis.plot_results_plotly_nomain()  # 绘图
        # simulation_1.data_analysis.plot_results_plotly()
        print(results['T_last'], results['busy_variance'])
        # simulation_1.Gantt()
        # print(results['T_last'],results['busy_variance'])

    end = tm.perf_counter()
    print("程序共计用时 : %s Seconds " % (end - start))
