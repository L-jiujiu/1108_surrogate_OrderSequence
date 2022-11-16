# -*- coding:utf-8 -*-
"""
作者：l_jiujiu
日期：2021.11.17
"""
import numpy as np
import pandas as pd
import time as tm
import os

from Class import Sku, Section, Order, Time, Data_Analysis
from Other_Functions import Func_Cost_sequence, Find_Section_now_num, display_order_list_simple, display_order_list


class Simulation:
    def __init__(self, simulation_config):
        self.T = simulation_config['T']
        self.path_order_sku_map = simulation_config['path_order_sku_map']
        self.path_sku_time_map = simulation_config['path_sku_time_map']

        self.type = simulation_config['type_order']
        self.pace = simulation_config['pace']

        # 1、初始化section
        self.num_section = simulation_config['num_section']
        self.num_section_main = simulation_config['num_section_main']
        self.section_list = []
        # 2、初始化sku
        self.num_sku = 0
        self.sku_list = []
        self.sku_time_num = []
        # 3、初始化订单
        self.num_order = 0
        self.order_notstart = []  # 未发出的order
        self.order_start = []  # 已经开始流转的order
        self.order_finish = []  # 已经流转结束的order
        self.order_before_section = -1

        # 初始化分区/SKU/订单
        self.new_sku_time = simulation_config['new_sku_time']
        self.normal_info = simulation_config['normal_info']

        # 初始化画图工具

        self.data_analysis = Data_Analysis()
        self.init_sku()
        self.init_section()
        self.init_order()

        # + surrogate
        self.weight = simulation_config['weight']
        self.busy_section = [0, 0, 0, 0, 0, 0]  # 工站繁忙的总次数
        self.busy_variance_sum=0
        self.op_method = simulation_config['optimization_method']

        # 测试数据
        # for order in self.order_notstart:
        #     if(order.name=='89293976181700'):
        #         print(order.work_schedule)

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

        # 测试数据
        # 显示当前section命名方式，可以用section_list[-1]调用第一个mainstream节点，-2调用第二个
        # for section in self.section_list:
        #     print(section.name)
        # print('section_list[-2]=%d'%self.section_list[-2].num)
        # self.section_list[-1].waiting_order_list=[1,1]
        # self.section_list[3].waiting_order_list=[1,1,1,1,1,1,1]

    def init_sku(self):
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
        elif (self.new_sku_time == '111'):
            # print('正在更新sku时间……')
            self.data_analysis.init_sku_time_1(path_sku_time_map=self.path_sku_time_map, num_sku=self.num_sku)
            # print('sku时间已全部更新为1')
        else:
            pass
            # print('sku时间未更新')

        # 重新读取更新后的Time数据
        df = pd.read_excel(self.path_sku_time_map, sheet_name='Part 1', usecols='B,C,E')
        df.dropna(axis=0, how='any', inplace=True)
        data = df.values
        # Sku时间数据的统计信息
        self.sku_time_num = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0, 7: 0}
        for i in range(0, self.num_sku):
            self.sku_time_num[int(data[i][2])] = self.sku_time_num[int(data[i][2])] + 1

        for i in range(0, self.num_sku):
            sku_input = {
                'name': str(int(data[i][1])),  # sku名称
                'num': i,  # sku序号
                'sectionID': str(int(data[i][0])),  # GroupID,sku所在分区
                'sku_time': int(data[i][2]),  # sku处理所需时间（默认为1）
            }
            self.sku_list.append(Sku(sku_input))

        # # 测试数据
        # for sku in self.sku_list:
        #     print('name:%s'%sku.name+",num:%d"%sku.num,',time:%d'%sku.sku_time,',groupID:%s'%sku.sku_sectionID)

    def init_order(self):
        data = pd.read_excel(self.path_order_sku_map, sheet_name='Part 1', usecols='A,B,C,D',
                             names=['OrderID', 'CommodityID', 'Amount', 'PosGroupID'])

        data_num = data['PosGroupID'].count()  # order信息总条数
        data.dropna(axis=0, how='any', inplace=True)
        order_num = data['PosGroupID'].groupby(data['OrderID']).count()
        self.num_order = order_num.size

        # 根据SKU的处理用时和订单包含的SKU个数计算单SKU的处理时间
        data.insert(data.shape[1], 'Time*Amount', 0)
        for i in range(0, data_num):
            for sku in self.sku_list:
                if ((str(sku.name) == str(data['CommodityID'][i])) & (
                        str(sku.sku_sectionID) == str(data['PosGroupID'][i]))):
                    data['Time*Amount'][i] = sku.sku_time * data['Amount'][i]
                    break

        # 根据订单组成计算各工序用时，并加入主干道节点信息，生成工序表work_schedule
        for i in range(0, self.num_order):
            # 添加一列统计实际用时，总时间用实际用时加和而不是amount
            order_name = str(order_num.index[i])
            order_data = data.loc[data['OrderID'] == order_num.index[i], ['PosGroupID', 'Time*Amount', 'PosGroupID']]
            result_data = order_data['Time*Amount'].groupby(data['PosGroupID']).sum()
            work_schedule_origin = []
            for g in range(len(list(result_data.index))):
                work_schedule_origin.append([list(result_data.index)[g], list(result_data.values)[g]])
            # # 测试数据
            # print('[order_%d]work_schedule:'%i)
            # print(work_schedule_origin)

            # 在work_schedule中加入主干道的信息
            work_schedule_dic = {'0': 0, '1': 0, '-1': 0, '2': 0, '3': 0, '-2': 0, '4': 0, '5': 0}
            for p in range(len(work_schedule_origin)):
                key_num = int(int(work_schedule_origin[p][0]) / 100) - 17
                work_schedule_dic[str(key_num)] = work_schedule_origin[p][1]
            for i in range(6):
                if (work_schedule_dic[str(i)] == 0):
                    work_schedule_dic.pop(str(i))
            work_schedule = [[k, v] for k, v in work_schedule_dic.items()]  # 将字典转化为列表

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
        # print('所有Order数量为：%d ' % self.num_order)

        # 统计只去往一个分区的简单订单的个数和比例
        simple_num = 0
        for order in self.order_notstart:
            if (len(order.work_schedule) == 3):
                simple_num = simple_num + 1
        # print('simple_num=%d'%simple_num,',比例为:%.3f'%(simple_num/self.num_order))

    # 筛选出不被拥堵影响的订单
    def Func_Order_Filter(self):
        order_fluent = []  # 筛选在mainstream上可以不堵的订单
        order_can = []  # 进而筛选在section中排队次数小于6次的订单
        for order in self.order_notstart:
            # work_step[i][j]：[i]对应第i步；[j=0]对应section名，[j=1]对应工序用时
            work_step = order.work_schedule

            if (int(work_step[0][0]) >= 0):  # 如果第0步不为mainstream，则不堵
                order_fluent.append(order)
            else:
                if (len(self.section_list[int(work_step[0][0])].waiting_order_list) + len(self.section_list[int(
                        work_step[0][0])].finish_order_list) == 0):  # 如果第0步为mainstream，并且第0步等待数量为0，
                    if (int(work_step[1][0]) >= 0):  # 如果第1步不为mainstream，则不堵
                        order_fluent.append(order)
                    else:  # 如果第1步为mainstream，则继续判断第1步等待数量
                        if (len(self.section_list[int(work_step[1][0])].waiting_order_list) + len(self.section_list[int(
                                work_step[1][0])].finish_order_list) == 0):  # 如果第1步等待数量为0，则不堵，否则堵
                            order_fluent.append(order)
        # print('order_fluent%d:'%len(order_fluent), end='')
        # display_order_list_simple(order_fluent)

        for order_2 in order_fluent:
            work_step = order_2.work_schedule
            for i in range(len(work_step)):
                if (int(work_step[i][0]) < 0):  # 如果第i步为mainstream，跳过这一步判断下一步是否还为mainstream
                    continue
                else:
                    all_order_num = len(self.section_list[int(work_step[i][0])].waiting_order_list) + len(
                        self.section_list[int(work_step[i][0])].process_order_list) + len(
                        self.section_list[int(work_step[i][0])].finish_order_list)
                    if (all_order_num < 6):  # 找到第一步不是mainstream的判断，如果第i步的等待数量小于6，则可以被派发
                        order_can.append(order_2)
                        break
                    else:
                        break
        # # 测试数据
        # print('order_can:', end='')
        # display_order_list_simple(order_can)
        return order_can, order_fluent

    # 订单派发算法
    def Func_Assign_Order(self, time):
        # 1\过滤有堵塞问题的订单
        order_can, order_fluent = self.Func_Order_Filter()
        # print(f'weight:{self.weight}')

        # 2\按照cost选出影响最小的订单,赋予order_now
        if (len(order_can) > 0):
            # print(f'weight:{self.weight}')
            order_now = Func_Cost_sequence(order_can, self.section_list, self.order_notstart, self.order_before_section,
                                           self.weight)
        else:
            if (len(order_fluent) != 0):
                pass
                # print("section已满，本轮无订单被派发")
            else:
                pass
                # print("主干道堵塞，本轮无订单被派发")
            return 0

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
                self.order_start.append(self.order_notstart[i])
                self.order_notstart.pop(i)
                break

    # 发网原始算法
    def Func_Assign_Order_Origin(self, time):
        # 1\过滤可能有堵塞问题的订单
        order_can, order_fluent = self.Func_Order_Filter()
        # 2\按照cost选出影响最小的订单,赋予order_now
        key = 0
        if (len(order_can) > 0):
            # 求出只有一个section要去的，并且该section的waiting+process为空的订单
            for order in order_can:
                if (len(order.work_schedule) == 3):
                    section_now_num, schedule_now_num = Find_Section_now_num(order)
                    section_temp = self.section_list[section_now_num]
                    section_waiting_num = len(section_temp.waiting_order_list) + len(
                        section_temp.process_order_list) + len(section_temp.finish_order_list)
                    if (section_waiting_num == 0):
                        order_now = order
                        key = 1
                        break
            if (key == 0):
                order_now = order_can[0]

        else:
            if (len(order_fluent) != 0):
                # print("section已满，本轮无订单被派发")
                pass
            else:
                pass
                # print("主干道堵塞，本轮无订单被派发")
            return 0

        # 3\赋予section_now为order_now第一个不为负的section，得到第一个不为负section的编号和当前order所处的工序
        order_now.now_section_num, order_now.now_schedule_num = Find_Section_now_num(order_now)
        # print('当前派发的订单为%s'%order_now.name,',地点为%s'%self.section_list[order_now.now_section_num].name,"对应工序序号为%d"%order_now.now_schedule_num,'工序为:%s'%order_now.work_schedule)

        # 4\在section等待队列中加入订单信息(订单序号，订单在该区用时)
        self.section_list[order_now.now_section_num].Add_to_waiting_order_list(order_now, time)

        # 5\修改订单信息
        # time_enter_section记录
        order_now.time.time_enter_section = time

        # 6\在未发出订单信息中删除order_now
        for i in range(len(self.order_notstart)):
            if (self.order_notstart[i].name == order_now.name):
                self.order_start.append(self.order_notstart[i])
                self.order_notstart.pop(i)
                break

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
    def run(self):
        for t in range(1, self.T):
            # print("\n")
            # print(
            #     "--------------------------\n     当前时刻为%d\n--------------------------" %
            #     t)

            # step1：下发新的订单
            if ((t + 1) % self.pace == 0):
                # print('pace is OK')
                if (len(self.order_notstart) != 0):
                    if (self.type == 'origin'):
                        # print('origin')
                        self.Func_Assign_Order_Origin(time=t)
                    else:
                        self.Func_Assign_Order(time=t)
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

            # 记录各工位工作情况
            busy_scene=[0,0,0,0,0,0]
            for i in range(0, 6):
                if ((len(self.section_list[i].process_order_list) + len(self.section_list[i].waiting_order_list)) > 0):
                    self.busy_section[i] = self.busy_section[i] + 1
                    busy_scene[i]=len(self.section_list[i].process_order_list) + len(self.section_list[i].waiting_order_list)
            self.busy_variance_sum=self.busy_variance_sum+np.var(busy_scene)
            # print(self.busy_section)

            # 订单全部完成，退出循环
            if (len(self.order_finish) == self.num_order):
                T_last = t
                break

        # 展示数据（总结）
        if(self.op_method=='surrogate'):
            # print('[Order：%d ' % self.num_order,'Sku：%d]' % self.num_sku,',type:%s'%self.type,',pace:%d'%self.pace,'\nsku_time信息:%s'%self.sku_time_num)
            print('完成全部订单共计循环次数：%d' % T_last)
            print('主路-1拥堵情况：%d' % self.data_analysis.main_jam_1, '主路-2拥堵情况：%d' % self.data_analysis.main_jam_2)
            # # 计算忙碌的方差：
            print(f'各section忙碌情况的方差为：{np.var(self.busy_section)},平均值为：{np.mean(self.busy_section)},busy_section:{self.busy_section}')
            print(f'工时方差为：{self.busy_variance_sum}')

        self.data_analysis.xls_output(self.order_start, self.type)

        results={
                    'T_last': T_last,
                    'jam_1':self.data_analysis.main_jam_1,
                    'jam_2':self.data_analysis.main_jam_2,
                    'busy_variance':self.busy_variance_sum,
        }
        return results

if __name__ == "__main__":
    start = tm.perf_counter()  # 记录当前时刻
    # cwd = os.getcwd()  # 读取当前文件夹路径

    # surrogate_weight=[1,0,0]
    # surrogate_weight = [0.81708383,0.64884249,0.27365036]
    surrogate_weight = [1,0.76399,0.43427]
    # surrogate_weight=[1,0.7,0.5]

    from simulation_config import simulation_config
    simulation_config['weight'] = surrogate_weight

    simulation_1 = Simulation(simulation_config)  # 初始化仿真实例
    results = simulation_1.run()  # 运行仿真
    T_last=results['T_last']
    jam_1=results['jam_1']
    jam_2=results['jam_2']
    busy_variance=results['busy_variance']


    print(results)
    print(T_last,jam_1,jam_2,busy_variance)
    # simulation_1.data_analysis.plot_results_plotly() #绘图

    end = tm.perf_counter()
    print("程序共计用时 : %s Seconds " % (end - start))
