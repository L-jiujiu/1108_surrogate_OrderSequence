import time as tm
import geatpy as ea
import numpy as np
import pandas as pd

from a_Simulation import Simulation
from Static_simulation_config import simulation_config

# 静态 遗传算法直接排序
class GaSolver(ea.Problem):

    def __init__(self, simulation_config):
        # self.problem_instance = Simulation(simulation_config) # 初始化仿真实例
        self.iteration_counter = 0
        name = 'GA_Simulation'
        M = 2  # 目标维数
        maxormins = [1,1]  # 目标最小最大化标记列表，1：最小化该目标；-1：最大化该目标

        path_order_sku_map = simulation_config['path_order_sku_map']
        data = pd.read_excel(path_order_sku_map, sheet_name='Part 1', usecols='A,B,C,D',
                             names=['OrderID', 'CommodityID', 'Amount', 'PosGroupID'])
        data.dropna(axis=0, how='any', inplace=True)
        order_num = data['PosGroupID'].groupby(data['OrderID']).count()

        Dim = order_num.size  # 决策变量维数 a,b,c共"订单个数"个参数

        varTypes = [1] * Dim  # 决策变量的类型列表，0：实数；1：整数
        lb = [0] * Dim  # 决策变量下界
        ub = [order_num.size-1] * Dim  # 决策变量上界

        lbin = [1] * Dim  # 决策变量下边界（0表示不包含该变量的下边界，1表示包含）
        ubin = [1] * Dim  # 决策变量上边界（0表示不包含该变量的上边界，1表示包含）
        # 调用父类构造方法完成实例化
        ea.Problem.__init__(self, name, M, maxormins, Dim, varTypes, lb, ub, lbin, ubin)

    def evalVars(self, Vars):
        # 评估目标函数
        total_timespan_array = np.zeros(Vars.shape[0])
        total_balance_array = np.zeros(Vars.shape[0])

        simulation_1=Simulation(simulation_config)
        for i in range(Vars.shape[0]):
            simulation_1.recycle_initial_GA(list(Vars[i,:]))  # 第二次仿真需要重启部分设置
            print(f'i:{i},当前自变量是：{list(Vars[i, :])}')
            results = simulation_1.run(rule='GA')  # 运行仿真

            T_last = results['T_last']
            busy_variance = results['busy_variance']


            total_timespan_array[i] = float(T_last)
            total_balance_array[i]= float(busy_variance)

        f1=total_timespan_array
        f2=total_balance_array
        f = np.array(list(zip(f1, f2)))
        print(f)
        # self.iteration_counter += 1
        return f # 固定为1列，多少行不知道

def example_GA_origin(simulation_config):
    # 实例化问题对象
    problem = GaSolver(simulation_config)
    # 构建算法：增强精英保留的遗传算法模板
    algorithm=ea.moea_NSGA2_templet(problem=problem,
                                    population=ea.Population(Encoding='P', NIND=simulation_config['NIND']), # 10+
                                    MAXGEN=simulation_config['MaxGen'],  # 最大进化代数
                                    MAXTIME=simulation_config['MaxTime'],  # 最大运行时间
                                    logTras=1,  # 表示每隔多少代记录一次日志信息，0表示不记录。
                                    trappedValue=1e-6,  # 单目标优化陷入停滞的判断阈值。
                                    maxTrappedCount=15)  # 进化停滞计数器最大上限值。

    # algorithm.mutOper = ea.Mutbga(Pm=0.25, MutShrink=0.5, Gradient=20)  # 变异率设定
    algorithm.mutOper.Pm=0.5 # 变异率设定
    algorithm.recOper.XOVR = 0.9  # 修改交叉算子的交叉概率
    # 求解
    res = ea.optimize(algorithm,
                      seed=1,  # int - 随机数种子
                      verbose=True,  # bool - 控制是否在输入输出流中打印输出日志信息。
                      drawing=0,  # int  - 算法类控制绘图方式的参数,0表示不绘图；
                      outputMsg=True,  # bool - 控制是否输出结果以及相关指标信息。
                      drawLog=False,  # bool - 用于控制是否根据日志绘制迭代变化图像。
                      saveFlag=False,  # bool - 控制是否保存结果。
                      dirName=None  # str  - 文件保存的路径。当缺省或为None时，默认保存在当前工作目录的文件夹下
                      )

    # 评估最优解并输出图像
    test_solution = Simulation(simulation_config)
    test_solution.order_list_GA=res['Vars'][0]
    results = test_solution.run(rule='GA')  # 运行仿真

    print('当前最优顺序是:',res['Vars'][0])
    print('timespan,balance:',res['ObjV'][0][0],res['ObjV'][0][1])
    # solution_list.append(res['Vars'][0])
    # object_value_list.append(results)

    # 多个seed迭代结束后，取最小的object value
    # print(object_value_list)
    # min = object_value_list.index(np.min(object_value_list))  # 总成本最小方案
    # print('\n\n当前object_value_list:{},取第{}个结果'.format(object_value_list, min))
    return res['ObjV'][0][0],res['ObjV'][0][1],res['Vars'][0]

if __name__ == '__main__':
    start = tm.time()
    min_timespan,min_balance,vars=example_GA_origin(simulation_config)

    print('当前min的目标是:NSGA II')
    print(f'最优解为:{vars},\n目标值为:{min_timespan},{min_balance}')

    end = tm.perf_counter()
    print("程序共计用时 : %s Seconds " % (end - start))