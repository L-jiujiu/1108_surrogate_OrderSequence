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

from Class import Sku, Section, Order, Time, Data_Analysis
from Other_Functions import Find_Section_now_num, Check_jam, Check_jam_all, \
    display_order_list_simple, display_order_list


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

        # 初始化画图工具
        self.data_analysis = Data_Analysis()
        self.buffer_num = simulation_config['buffer_num']

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
        self.section_HF_x = np.zeros(6)

        # 学习率相关参数
        self.z = 0.5
        self.lam = 0.5
        # 是否是新手section,是新手为1，不是新手为0
        self.section_newlearn = [1, 1, 1, 1, 1, 1]
        # self.section_newlearn=[0,0,0,0,0,0]
        # self.section_newlearn=[1,0,0,0,0,0]
        # x到多少的时候可以不优先新手
        self.x_max = 100

    def HF_LearningRate_function(self, time_original, x):
        if x == 0:
            x = 1
        time_real = 1 / self.z * time_original * (self.z + (1 - self.z) * (x ** (-self.lam)))

        return time_real

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

        # print(self.num_order)
        # print(data_skuorder)
        data_order_gb = data_skuorder.groupby(['OrderID', 'PosGroupID'])['Time*Amount'].sum()  # 统计order在各section的用时之和
        data_order = pd.DataFrame(data_order_gb)
        data_order.reset_index(inplace=True)
        data_order['id'] = data_order['OrderID'].rank(ascending=1, method='dense').astype(int)
        # print(data_order)
        self.order_array = np.zeros((self.num_order, self.num_section))
        self.order_array_01 = np.zeros((self.num_order, self.num_section))

        # 创建初始order-section矩阵[行数line:num_order,列数col:num_section[8个],按照012345，-1，-2]
        for index, row in data_order.iterrows():
            # 修改订单用时矩阵
            self.order_array[int(row['id']) - 1, int(row['PosGroupID'] / 100 - 17)] = row['Time*Amount']
            self.order_array_01[int(row['id']) - 1, int(row['PosGroupID'] / 100 - 17)] = 1
        # np.set_printoptions(threshold=np.sys.maxsize)
        # print(f'order_array 6:{self.order_array}')
        order_mainstream_workstep = np.ones((1, self.num_order))
        self.order_array = np.insert(self.order_array, 6, order_mainstream_workstep, axis=1)
        self.order_array = np.insert(self.order_array, 7, order_mainstream_workstep, axis=1)
        self.order_array_01 = np.insert(self.order_array_01, 6, np.zeros((1, self.num_order)), axis=1)
        self.order_array_01 = np.insert(self.order_array_01, 7, np.zeros((1, self.num_order)), axis=1)
        # print(f'self.order_array_01:{self.order_array_01}')

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
                          'time_enter_section': 0,
                          'time_start_process': 0,
                          'period_process': 0,
                          'time_leave_section': 0}

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
        # 修改order now的workschedule
        # print(order_now.work_schedule)
        # print(self.section_HF_x)
        # print(self.section_HF_x[1])
        for kk in order_now.work_schedule:
            if kk[0] not in ['-1', '-2']:
                # print(kk)
                if (self.section_newlearn[int(kk[0])] == 1):  # 如果是新手section，则乘上学习率
                    kk[1] = round(self.HF_LearningRate_function(time_original=kk[1], x=self.section_HF_x[int(kk[0])]),
                                  1)
        # print(order_now.work_schedule)

        # 3\赋予section_now为order_now第一个不为负的section，得到第一个不为负section的编号和当前order所处的工序
        order_now.now_section_num, order_now.now_schedule_num = Find_Section_now_num(order_now)
        # print('当前派发的订单为%s'%order_now.name,',地点为%s'%self.section_list[order_now.now_section_num].name,"对应工序序号为%d"%order_now.now_schedule_num,'工序为:%s'%order_now.work_schedule)

        # 4\在section等待队列中加入订单信息(订单序号，订单在该区用时)
        self.section_list[order_now.now_section_num].Add_to_waiting_order_list(order_now, time)

        # print(order_now.num, order_now.now_section_num)
        # self.section_waiting_array[self.section_list[order_now.now_section_num].num][0]+=1
        # self.section_waiting_time_array[self.section_list[order_now.now_section_num].num][0]+=self.order_array[order_now.num][self.section_list[order_now.now_section_num].num]

        # 5\更新order_before_section：上一个派发订单第一个去的非主路section
        self.order_before_section = order_now.now_section_num

        # 6\修改订单时间信息
        order_now.time.time_enter_section = time

        # 7\在未发出订单信息中删除order_now
        for i in range(len(self.order_notstart)):
            if (self.order_notstart[i].name == order_now.name):
                # print(f'num:{self.order_notstart[i].num},')
                self.order_notstart_array[(self.order_notstart[i].num, 0)] = 10000
                self.order_start.append(self.order_notstart[i])
                self.order_notstart.pop(i)
                break
        # 8\在section_busyness_array，section_busyness_time_array中加入order now的信息，时间加入及时的信息
        # print(f'order_now section: {self.section_list[order_now.now_section_num].num}')

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
        order_array_weight22 = np.zeros((self.num_order, self.num_section))

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
        # 加上主路，都是必经之路
        order_mainstream_workstep = np.zeros((1, self.num_order))
        order_array_weight = np.insert(order_array_weight, 6, order_mainstream_workstep, axis=1)
        order_array_weight = np.insert(order_array_weight, 7, order_mainstream_workstep, axis=1)

        weight_flag = 6
        # 生成先后要去的不同工区各自的权重
        # print(len(order_array_nonzero[0]))
        self.order_first_section = []
        for i in range(0, len(order_array_nonzero[0])):
            if (i == 0):
                weight_flag = 6
            elif (order_array_nonzero[0][i] == order_array_nonzero[0][i - 1]):
                weight_flag = weight_flag + 1
            else:
                weight_flag = 6
            order_array_weight22[order_array_nonzero[0][i], order_array_nonzero[1][i]] = rule[weight_flag]
            if (weight_flag == 6):
                self.order_first_section.append(order_array_nonzero[1][i])
                self.order_array_first[order_array_nonzero[0][i], order_array_nonzero[1][i]] = 1
        # 加上主路，都是必经之路
        order_mainstream_workstep = np.zeros((1, self.num_order))
        order_array_weight22 = np.insert(order_array_weight22, 6, order_mainstream_workstep, axis=1)
        order_array_weight22 = np.insert(order_array_weight22, 7, order_mainstream_workstep, axis=1)
        # np.set_printoptions(threshold=np.sys.maxsize)
        # print(f'order_array 7:{order_array_weight}')

        # print(order_total_time_rank)
        # 计算每个订单的用时 time
        # learning_order_array = self.cal_learning_array()
        order_array_weight2 = np.zeros((self.num_order, self.num_section))
        weight_flag = 3
        order_array_nonzero = np.nonzero(self.order_array[:, :6])
        # 生成先后要去的不同工区各自的权重
        for i in range(0, len(order_array_nonzero[0])):
            if (i == 0):
                weight_flag = 3
            elif (order_array_nonzero[0][i] == order_array_nonzero[0][i - 1]):
                weight_flag = weight_flag + 1
            else:
                weight_flag = 3
            order_array_weight2[order_array_nonzero[0][i], order_array_nonzero[1][i]] = self.order_array[
                                                                                            order_array_nonzero[0][i],
                                                                                            order_array_nonzero[1][i]] \
                                                                                        * rule[weight_flag]
        self.order_time_sum = np.array(order_array_weight2.sum(axis=1)).reshape(self.num_order, 1)

        order_array_weight3 = np.zeros((self.num_order, self.num_section))
        weight_flag = 9
        order_array_nonzero = np.nonzero(self.order_array[:, :6])
        # 生成先后要去的不同工区各自的权重
        for i in range(0, len(order_array_nonzero[0])):
            if (i == 0):
                weight_flag = 3
            elif (order_array_nonzero[0][i] == order_array_nonzero[0][i - 1]):
                weight_flag = weight_flag + 1
            else:
                weight_flag = 3
            order_array_weight3[order_array_nonzero[0][i], order_array_nonzero[1][i]] = self.order_array[
                                                                                            order_array_nonzero[0][i],
                                                                                            order_array_nonzero[1][i]] \
                                                                                        * rule[weight_flag]
        self.order_time_sum2 = np.array(order_array_weight3.sum(axis=1)).reshape(self.num_order, 1)

        return order_array_weight, order_array_weight22

    def cal_learning_array(self):
        # print(f'self.section_HF_x:{self.section_HF_x}')
        learning_order_array = []
        for i in range(0, 6):
            learning_order_array.append(
                self.HF_LearningRate_function(np.transpose(self.order_array[:, i]), self.section_HF_x[i]))

        learning = np.transpose(
            np.stack((
                learning_order_array[0],
                learning_order_array[1],
                learning_order_array[2],
                learning_order_array[3],
                learning_order_array[4],
                learning_order_array[5],
            )))
        # print(learning)
        return learning

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

        elif self.rule == 'T+time':
            cost_all = np.dot(self.order_array_weight_all, self.section_busyness_time_array)  # 订单次序权重 点乘 工站实时工作状态
            a = self.order_time_sum
            cost = cost_all + self.order_notstart_array + a  # 将已经完成派发的订单赋极大值
            line, col = np.where(cost == np.min(cost))  # line就是当前最小的order序号，对于已经派发的订单，他的order array weight是极大的数10000
            return line[0]

        elif self.rule == 'Npro+time':
            # 决策规则1pro：多项式 𝒄𝒐𝒔𝒕=𝒂×N_𝟎+𝒃×N_𝟏+𝒄×N_𝟐，多个最小就选第1个，N代表工区缓冲区+工作区（当前+即将到达的）订单数量
            cost_all = np.dot(self.order_array_weight_all, self.section_busyness_array_pro)  # 订单次序权重 点乘 工站实时工作状态
            a = self.order_time_sum

            cost = cost_all + self.order_notstart_array + a  # 将已经完成派发的订单赋极大值
            line, col = np.where(cost == np.min(cost))  # line就是当前最小的order序号，对于已经派发的订单，他的order array weight是极大的数10000
            return line[0]

        elif self.rule == 'Tpro+time':
            # 决策规则2pro：多项式 𝒄𝒐𝒔𝒕=𝒂×T_𝟎+𝒃×T_𝟏+𝒄×T_𝟐，多个最小就选第1个，T代表工区缓冲区+工作区（当前+即将到达的）订单待加工时间
            # HF新规则：对x进行if then判断，如果某工站又是新手，又是x不满500，则增多给他派订单的机会，然后再优化订单time的选择，选择time最少的订单（通过将参数-0.5取得[-0.5,0.5]的效果）
            self.flag_new1 = copy.deepcopy(self.section_newlearn)

            for s in range(0, 6):
                if self.section_newlearn[s] != 0:
                    if self.section_HF_x[s] >= self.x_max:
                        self.flag_new1[s] = 0
            self.flag_new1.append(0)
            self.flag_new1.append(0)

            # 有新手
            if sum(np.array(self.flag_new1)) != 0:
                new_pro = self.section_busyness_time_array_pro - np.array(self.flag_new1).reshape((8, 1)) * 5
                cost_all = np.dot(self.order_array_weight_all2, new_pro)  # 订单次序权重 点乘 工站实时工作状态
                a = self.order_time_sum2
                cost = cost_all + self.order_notstart_array + a  # 将已经完成派发的订单赋极大值
                line, col = np.where(
                    cost == np.min(cost))  # line就是当前最小的order序号，对于已经派发的订单，他的order array weight是极大的数10000
            else:
                cost_all = np.dot(self.order_array_weight_all,
                                  self.section_busyness_time_array_pro)  # 订单次序权重 点乘 工站实时工作状态
                a = self.order_time_sum
                cost = cost_all + self.order_notstart_array + a  # 将已经完成派发的订单赋极大值
                line, col = np.where(
                    cost == np.min(cost))  # line就是当前最小的order序号，对于已经派发的订单，他的order array weight是极大的数10000

            return line[0]

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
            # 决定要派发订单后，把order now对应的section的经验都+1(不管订单用时多久都是+1)
            self.section_HF_x = self.section_HF_x + self.order_array_01[order_now.num][0:6]
            # print(self.section_HF_x)
            # print(order_now.work_schedule)

            # 发出订单到waiting list
            self.Func_Assign_Order_Tools(order_now, time)
            self.order_start_num.append(order_now.num)
            self.order_insystem_array[order_now.num, :] = self.order_array_01[order_now.num, :]
            # print(f'befor:{self.order_insystem_array}')
            # print(f'派发的订单是:order_{order_now.num}:{order_now.name},工序是:{order_now.work_schedule}')
            return 1

    # 已知订单排序的-配合GA的订单派发算法
    def Order_Select_OriginGA(self, time, order_num):
        # print(order_num)
        # if len(self.order_notstart)==0:
        #     return 0
        for order in self.order_notstart:
            if order.num == order_num:
                order_pick = order
                break

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

                    # self.order_insystem_array[(order_now.num, section_list[int(order_now.work_schedule[order_now.now_schedule_num][0])].num)] = 0  # 不是系统即将需要处理的订单，当前section任务归0

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
        # print(np.transpose(section_insystem_array_time_1))
        self.section_busyness_time_array_pro = self.section_processleft_time_array + section_insystem_array_time_1
        # print(f'TProinsystem+:{np.transpose(section_insystem_array_time_1)}')
        # print(f'onprocess:{np.transpose(self.section_processleft_time_array)}')
        # print(f'waiting  :{np.transpose(self.section_waiting_time_array)}')
        # print(f'======pro:{np.transpose(self.section_busyness_time_array_pro)}\n')

        # print(self.section_busyness_array)
        county = np.ones((6, 1))
        for i in range(0, 6):
            if self.section_process_array[i] + self.section_waiting_array[i] == 0:
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

    def display_section_busyness_array(self):
        print(f'\nself.section_busyness_array:{np.transpose(self.section_busyness_array)},\n'
              f'self.section_waiting_array:{np.transpose(self.section_waiting_array)},\n'
              f'self.section_process_array:{np.transpose(self.section_process_array)},\n'
              f'self.section_finish_array:{np.transpose(self.section_finish_array)},\n')
        print(f'self.section_busyness_array_pro:{np.transpose(self.section_busyness_array_pro)},\n')

        print(f'self.section_busyness_time_array:{np.transpose(self.section_busyness_time_array)},\n'
              f'self.section_waiting_time_array:{np.transpose(self.section_waiting_time_array)},\n'
              f'self.section_processleft_time_array:{np.transpose(self.section_processleft_time_array)},\n')

        print(f'self.section_busyness_time_array_pro:{np.transpose(self.section_busyness_time_array_pro)},\n'
              f'self.section_jam_array:{np.transpose(self.section_jam_array)}')

    # 仿真主函数
    def run(self, rule):
        # print('111')
        order_count_GA = 0
        self.weight = rule
        self.order_array_weight_all_list = []
        self.order_array_weight_all, self.order_array_weight_all2 = self.rule_process_weight(rule=rule)

        # 用于标记在系统中的订单情况，可以汇总所有工区潜在需要完成的订单数量和时间
        self.order_insystem_array = np.zeros((self.num_order, self.num_section + self.num_section_main))
        self.data_analysis.num_order = self.num_order

        # 用于记录各工站总工作时间
        self.section_busyness_time = np.zeros((self.num_section, 1))
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

            # step1：下发新的订单
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
            # self.display_section_busyness_array()

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

            # 订单全部完成，退出循环
            if (len(self.order_finish) == self.num_order):
                T_last = t
                break
            # if sum(np.array(self.flag_new1)) == 0:
            #     T_last = t
            #     break
        # 展示数据（总结）
        if ((self.op_method == 'surrogate') and (self.type == 'new')) or (
                (self.op_method == 'surrogate') and (self.type == 'rules_simple')):
            print('[Order：%d ' % self.num_order, 'Sku：%d]' % self.num_sku, ',type:%s' % self.type,
                  ',pace:%d' % self.pace)
            # print('[Order：%d ' % self.num_order,'Sku：%d]' % self.num_sku,',type:%s'%self.type,',pace:%d'%self.pace,'\nsku_time信息:%s'%self.sku_time_num)
            print('完成全部订单共计循环次数：%d' % T_last)
            print('主路-1拥堵情况：%d' % self.data_analysis.main_jam_1,
                  '主路-2拥堵情况：%d' % self.data_analysis.main_jam_2)
            # # 计算忙碌的方差：
            print(
                f'各section忙碌情况的绝对差之和SAD(sum of absolute difference)为:{self.busy_variance_sum}')

        self.data_analysis.xls_output(self.order_start, self.type)

        results = {
            'T_last': T_last,
            'jam_1': self.data_analysis.main_jam_1,
            'jam_2': self.data_analysis.main_jam_2,
            'busy_variance': self.busy_variance_sum / T_last,
            'order_start_list': self.order_start_num,
            'all': T_last + self.busy_variance_sum * 2662
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
        # [1, 0, 0],
        # [0.4479534002020955, 0.252059786580503, 0.19736248161643744, 0.0, 0.7906538723036647, 0.1579495333135128]
        # [0.99609375, 0.3337383270263672, 0.0,1, 0, 0],
        # [0.78448486328125, 0.2732839584350586, 0.0, 0.92315673828125, 0.0, 0.0]
        # [0.4810476303100586, 0.1325979232788086, 0.0, 0.907501220703125, 0.0, 0.0]
        # [0.9846572875976562, 0.5547189712524414, 0.20981597900390625, 1.0,0, 0.0]
        # [0.4810476303100586, 0.1325979232788086, 0.0, 0.907501220703125, 0.0, 0.0]
        # [0.4810476303100586, 0.1325979232788086, 0.0, 1, 1, 1]

        # [0.2613859176635742, 0.104522705078125, 0.007813453674316406, 0.696563720703125, 0.0, 0.0144195556640625, 0.5702180862426758, 0.17809295654296875, 1.0, 0.1526632308959961, 0.7933673858642578, 0.3660879135131836]
        [0.2613859176635742, 0.104522705078125, 0.007813453674316406, 0.696563720703125, 0.0, 0.0144195556640625,0.5702180862426758, 0.17809295654296875, 1.0, 0.1526632308959961, 0.7933673858642578, 0.3660879135131836],
        # [0.6246633529663086, 0.096832275390625, 0.0],
        # [0.86831, 0.13416, 0.]
        # [0.36916,0.55963,0.]
    ]

    rule_list = ['Fa_origin', 'random', 'N', 'Npro', 'T', 'Tpro']

    from Dynamic_simulation_config_HF import simulation_config

    simulation_1 = Simulation(simulation_config)  # 初始化仿真实例
    print(simulation_1.rule)
    for i in range(0, len(weight_list)):
        # if i > 0:
        simulation_1.recycle_initial()  # 第二次仿真需要重启部分设置
        print(f"\nweight:{weight_list[i]}")
        results = simulation_1.run(rule=weight_list[i])  # 运行仿真
        T_last = results['T_last']
        jam_1 = results['jam_1']
        jam_2 = results['jam_2']
        busy_variance = results['busy_variance']
        sum_result = T_last + busy_variance / 28

        # print(f"订单派发列表:{results['order_start_list']}")
        # print(T_last, jam_1,jam_2,busy_variance)
        print(results['order_start_list'])
        print(T_last, busy_variance)

        # simulation_1.data_analysis.plot_results_plotly_nomain()  # 绘图
        # simulation_1.data_analysis.plot_results_plotly()
    end = tm.perf_counter()
    print("程序共计用时 : %s Seconds " % (end - start))
