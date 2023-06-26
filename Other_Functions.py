# -*- coding:utf-8 -*-
"""
作者：l_jiujiu
日期：2022.01.20
"""

import operator
import numpy as np
from Class import CostList

# 找出订单工序表中第一个分区（非主路）


def Find_Section_now_num(order_now):
    # section_now为第一个不为负的section
    for i in range(len(order_now.work_schedule)):
        if (int(order_now.work_schedule[i][0]) <
                0):  # 如果第i步为mainstream，跳过这一步判断下一步是否还为mainstream
            continue
        else:
            section_now_num = int(order_now.work_schedule[i][0])
            schedule_now_num = i
            break
    return section_now_num, schedule_now_num

def Check_jam(order_return,section_busyness_array,max):
    # work_step[i][j]：[i]对应第i步；[j=0]对应section名，[j=1]对应工序用时
    order_now='error'

    if order_return is not None:
        work_step = order_return.work_schedule
        # print(f'order:{order_return.num},workstep:{work_step[0][0]}')
        if (int(work_step[0][0]) >= 0):  # 如果第0步不为mainstream，则不堵
            if section_busyness_array[int(work_step[0][0]),0]<max:# 找到第0步不是mainstream的判断，如果第i步的等待数量小于6，则可以被派发
                order_now = order_return
        else:  # 如果第0为mainstream
            if section_busyness_array[6,0]==0: # 如果第0步为mainstream -1，并且第0步等待数量为0，
                if (int(work_step[1][0]) >= 0):  # 如果第1步不为mainstream，则不堵
                    if (section_busyness_array[int(work_step[1][0]),0]<max):  # 找到第1步不是mainstream的判断，如果第i步的等待数量小于6，则可以被派发
                        order_now = order_return
                else:  # 如果第1步为mainstream，则继续判断第1步等待数量
                    if section_busyness_array[7,0]==0:  # 如果第1步等待数量为0，则不堵，否则堵
                        if (section_busyness_array[int(work_step[2][0]),0]<max):  # 找到第一步不是mainstream的判断，如果第i步的等待数量小于6，则可以被派发
                            order_now = order_return
    else:
        print('NONE')
    return order_now

def Check_jam_all(order_list,section_busyness_array,order_num):
    # work_step[i][j]：[i]对应第i步；[j=0]对应section名，[j=1]对应工序用时
    jam_all = np.ones((order_num, 1))
    jam_all=10000*jam_all
    for order_return in order_list:
        jam_all[order_return.num,0]=1000
        work_step = order_return.work_schedule
        # print(f'order:{order_return.num},workstep:{work_step[0][0]}')
        if (int(work_step[0][0]) >= 0):  # 如果第0步不为mainstream，则不堵
            if section_busyness_array[int(work_step[0][0]),0]<6:# 找到第0步不是mainstream的判断，如果第i步的等待数量小于6，则可以被派发
                jam_all[order_return.num,0]=0
        else:  # 如果第0为mainstream
            if section_busyness_array[6,0]==0: # 如果第0步为mainstream -1，并且第0步等待数量为0，
                if (int(work_step[1][0]) >= 0):  # 如果第1步不为mainstream，则不堵
                    if (section_busyness_array[int(work_step[1][0]),0]<6):  # 找到第1步不是mainstream的判断，如果第i步的等待数量小于6，则可以被派发
                        jam_all[order_return.num, 0] = 0
                else:  # 如果第1步为mainstream，则继续判断第1步等待数量
                    if section_busyness_array[7,0]==0:  # 如果第1步等待数量为0，则不堵，否则堵
                        if (section_busyness_array[int(work_step[2][0]),0]<6):  # 找到第一步不是mainstream的判断，如果第i步的等待数量小于6，则可以被派发
                            jam_all[order_return.num, 0] = 0
    # else:
        # print('NONE')
    # jam_all=100*jam_all
    # print(np.transpose(jam_all))
    return jam_all

def display_order_list_simple(order_list):
    for order in order_list:
        print(order.name, end=',')
    print("(%d)" % len(order_list))


def display_order_list_section(i, section_list):
    print("%s" % section_list[i].name, "的process", end=':')
    for order in section_list[i].process_order_list:
        print(order.num,order.work_schedule, end=',')
    print("(%d)" % len(section_list[i].process_order_list), end=';')

    print("     waiting", end=':')
    for order in section_list[i].waiting_order_list:
        print(order.num,order.work_schedule, end=',')
    print("(%d)" % len(section_list[i].waiting_order_list), end=';')

    print("     finish", end=':')
    for order in section_list[i].finish_order_list:
        print(order.num,order.work_schedule, end=',')
    print("(%d)" % len(section_list[i].finish_order_list))


def display_order_list(section_list, type):
    if(type == 'main'):
        list_test = [0, 1, -1, 2, 3, -2, 4, 5]
        for list_num in list_test:
            if(list_num >= 0):
                display_order_list_section(list_num, section_list)
            else:
                print(
                    "     %s" %
                    section_list[list_num].num,
                    "的finish",
                    end=':')
                for order in section_list[list_num].finish_order_list:
                    print(order.num,order.work_schedule, end=',')
                print("(%d)" % len(section_list[list_num].finish_order_list))
    if(type == 'all'):
        for i in range(0, 6):
            print("%s" % section_list[i].name, "的process", end=':')
            for order in section_list[i].process_order_list:
                print(order.num, end=',')
            print("(%d)" % len(section_list[i].process_order_list), end=';')

            print("     waiting", end=':')
            for order in section_list[i].waiting_order_list:
                print(order.num, end=',')
            print("(%d)" % len(section_list[i].waiting_order_list), end=';')

            print("     finish", end=':')
            for order in section_list[i].finish_order_list:
                print(order.num, end=',')
            print("(%d)" % len(section_list[i].finish_order_list))


# 【非矩阵运算】新订单派发算法：选出下一个新派发的订单
def Func_Cost_sequence_tool(order_min_can):
    # 优化1：把相同cost中比较复杂的订单先发:
    order_complex = order_min_can[0]
    for order in order_min_can:
        if (len(order.work_schedule) > len(order_complex.work_schedule)):
            order_complex = order
    return order_complex

def Func_Cost_sequence(
        order_can,
        section_list,
        order_list,
        order_before_section,
        weight):
    cost = []
    order_min_can = []  # cost相同的订单集合，从中选择最小
    order_min_can_can = []
    order_return = None
    # print(f'weight:{weight}')
    for i in range(len(order_can)):
        order_can[i].Cost_cal(section_list=section_list,weight=weight)
        cost_input = {
            'name': order_can[i].name,  # order名
            'order': 0,  # 即将进行的订单序号
            'cost': order_can[i].weighted_cost,  # cost
            'orderfororder': i,  # 原本的序号
        }
        cost.append(CostList(cost_input))
    # 对成本以cost为键排序
    sortkey = operator.attrgetter('cost')
    cost.sort(key=sortkey)

    for i in range(len(cost)):
        cost[i].order = i

# 优化：对于非上一时刻派发了工作，并且当前没有工作的section，优先派发在这个分区工作时间最长的订单；
    # 如果所有section都有工作，则派发整体cost最小的订单；
    section_all_num = 0  # 所有分区等待订单数量
    for section in section_list:
        # 1\很闲时：所有分区所有类型订单为空
        # section_all_num=section_all_num+len(section.finish_order_list)+len(section.waiting_order_list)+len(section.process_order_list)
        # 2\(效果更好)很闲时：所有订单只有waiting订单为空
        section_all_num = section_all_num + len(section.waiting_order_list)
    if(section_all_num == 0):
        # print('系统很闲！')
        for order in order_list:
            if (order.name == order_can[cost[-1].orderfororder].name):
                order_return = order
                break
    else:
        # print('系统不闲！')
        section_can = []  # 记录当前没有任务的空闲分区
        order_light_can = []  # 记录第一个可以发到空闲分区的订单

        for section in section_list:
            # 和上一个派发工作的section不同
            if(section.num == order_before_section):
                continue

            section_all = len(section.finish_order_list) + \
                len(section.waiting_order_list) + len(section.process_order_list)
            if(section_all == 0):
                section_can.append(section)

        # 如果有空闲分区，筛选出第一个工序为去空闲分区的订单为order_light_can
        if(len(section_can) != 0):
            for section in section_can:
                # print("当前没有任务的分区：%s" % section.name)
                for order in order_can:
                    section_now_num, schedule_now_num = Find_Section_now_num(
                        order)
                    if(section_now_num == section.num):
                        order_light_can.append(order)

        # 如果有第一个工序去空闲分区的订单，筛选在该空闲分区工作用时最长的订单先发
        if(len(order_light_can) != 0):
            order_return = order_light_can[0]
            section_now_num, schedule_now_num = Find_Section_now_num(
                order_light_can[0])
            schedule_max = order_return.work_schedule[schedule_now_num][1]
            # 找工作时间最长的订单
            for order in order_light_can:
                section_now_num, schedule_now_num = Find_Section_now_num(order)
                if(order.work_schedule[schedule_now_num][1] > schedule_max):
                    schedule_max = order.work_schedule[schedule_now_num][1]
                    order_return = order

        # 如果无第一个工序去空闲分区的订单，筛选cost最小的订单存入order_min_can，对于同样为cost最小的多个订单，进一步筛选条件为：
        elif(len(order_light_can) == 0):
            cost_min = cost[0].cost
            for order in order_can:
                if(order.weighted_cost == cost_min):
                    order_min_can.append(order)
        # 过滤与上一个派发order第一个去的section不同的单子存入order_can_can
            for order in order_min_can:
                section_now_num, schedule_now_num = Find_Section_now_num(order)
                if(section_now_num != order_before_section):
                    order_min_can_can.append(order)
        # 优先派发复杂订单（经停分区多）
            if(len(order_min_can_can) == 0):
                # print('所有派发的单子要去的第一个分区与上次派发相同')
                order_min = Func_Cost_sequence_tool(order_min_can)
            else:
                # print('order_before_section:%d' % order_before_section)
                order_min = Func_Cost_sequence_tool(order_min_can_can)

            for order in order_list:
                if (order.name == order_min.name):
                    order_return = order
                    break

    return order_return

# 输出格式函数，用于测试
def Func_Cost_sequence_simple_origin(
        order_can,
        section_list,
        order_list,
        order_before_section,
        weight):
    cost = []
    order_min_can = []  # cost相同的订单集合，从中选择最小
    order_min_can_can = []
    order_return = None
    # print(f'weight:{weight}')
    for i in range(len(order_can)):
        order_can[i].Cost_cal(section_list=section_list, weight=weight)
        cost_input = {
            'name': order_can[i].name,  # order名
            'order': 0,  # 即将进行的订单序号
            'cost': order_can[i].weighted_cost,  # cost
            'orderfororder': i,  # 原本的序号
        }
        cost.append(CostList(cost_input))
    # 对成本以cost为键排序
    sortkey = operator.attrgetter('cost')
    cost.sort(key=sortkey)

    for i in range(len(cost)):
        cost[i].order = i  # cost.order是按照cost排序后的order顺序
    order_return = order_can[cost[0].orderfororder]

    return order_return

def Func_Cost_sequence_simple(
        order_can,
        section_list,
        order_before_section,
        weight):

    cost = []
    order_return = None
    # print(f'weight:{weight}')
    for i in range(len(order_can)):
        order_can[i].Cost_cal(section_list=section_list,weight=weight)
        cost_input = {
            'name': order_can[i].name,  # order名
            'order': 0,  # 即将进行的订单序号
            'cost': order_can[i].weighted_cost,  # cost
            'orderfororder': i,  # 原本的序号
        }
        cost.append(CostList(cost_input))
    # 对成本以cost为键排序
    sortkey = operator.attrgetter('cost')
    cost.sort(key=sortkey)
    min_val=cost[0].cost
    # print(min_val)
    min_cost_list=[]

    for i in range(len(cost)):
        if cost[i].cost == min_val:
            min_cost_list.append(cost[i])
    # print(min_cost_list)

    flag=0
    if len(min_cost_list) > 1:
        for i in min_cost_list:
            section_now_num, schedule_now_num = Find_Section_now_num(order_can[i.orderfororder])
            if section_now_num!=order_before_section:
                flag=1
                return order_can[i.orderfororder]

    if (len(min_cost_list) ==1) or (flag==0):
        order_return = order_can[min_cost_list[0].orderfororder]
        return order_return
