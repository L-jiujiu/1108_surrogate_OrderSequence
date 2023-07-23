import time as tm
import geatpy as ea
import numpy as np

from Simulation_HF import Simulation
from Dynamic_simulation_config import simulation_config

import multiprocessing as mp


class GaSolver(ea.Problem):

    def __init__(self, simulation_config):
        # self.problem_instance = Simulation(simulation_config)
        self.iteration_counter = 0
        name = 'GA_Simulation'
        M = 1  # 目标维数
        maxormins = [1]  # 目标最小最大化标记列表，1：最小化该目标；-1：最大化该目标
        Dim = 6  # 决策变量维数 a,b,c共3个参数
        varTypes = [0] * Dim  # 决策变量的类型列表，0：实数；1：整数
        lb = [0] * Dim  # 决策变量下界
        ub = [1] * Dim  # 决策变量上界
        lbin = [1] * Dim  # 决策变量下边界（0表示不包含该变量的下边界，1表示包含）
        ubin = [1] * Dim  # 决策变量上边界（0表示不包含该变量的上边界，1表示包含）
        # 调用父类构造方法完成实例化
        ea.Problem.__init__(self, name, M, maxormins, Dim, varTypes, lb, ub, lbin, ubin)
        self.simulation_1=Simulation(simulation_config)

    def obj_for_parallel(self,x_id,x):
        results=[]
        print(x)

        # self.simulation_1 = Simulation(simulation_config)
        self.simulation_1.recycle_initial()  # 第二次仿真需要重启部分设置
        results_sim = self.simulation_1.run(rule=x)  # 运行仿真

        T_last = results_sim['T_last']
        busy_variance = results_sim['busy_variance']
        all = results_sim['all']

        if simulation_config['type'] == 'min_timespan':
            result_x = float(T_last)
        elif simulation_config['type'] == 'min_variance':
            result_x= float(busy_variance)
        elif simulation_config['type'] == 'min_all':
            result_x = float(all)
        else:
            print('未定义返回参数！')
            result_x= float(T_last)

        results.append([x_id,result_x])
        # print(results)

        return results

    def evalVars(self, Vars):
        # 评估目标函数
        ObjV=[]
        # total_cost_array = np.zeros(Vars.shape[0])
        num_cores = 5  # 并行核数
        print('num_cores:', num_cores)
        param_list = []  # 保存并行参数
        for id in range(Vars.shape[0]):
            param_list.append([id, Vars.tolist()[id]])

        pool = mp.Pool(num_cores)
        result = [pool.apply_async(self.obj_for_parallel, args=(item[0], item[1])) for item in param_list]
        result = [p.get() for p in result]  # result is a list of list
        flatten_result = []
        for item in result:
            flatten_result.extend(item)
        flatten_result.sort(key=lambda x: x[0])  # 根据id顺序排序(升序)
        for i in range(Vars.shape[0]):
            ObjV.append([flatten_result[i][1]])
        ObjV = np.array(ObjV)
        return ObjV  # , CV  返回目标函数值矩阵和违反约束程度矩阵

        # return total_cost_array.reshape(-1, 1)  # 固定为1列，多少行不知道

def example_GA(simulation_config):
    # 实例化问题对象
    object_value_list = []
    solution_list = []

    seed_list = range(0, simulation_config['seed_num'])

    # test_solution = Simulation(simulation_config)

    problem = GaSolver(simulation_config)
    # 实例化种群对象:Encoding编码方式,NIND所需要的个体数,RI-实整数编码，实数和整数的混合编码
    population = ea.Population(Encoding='RI', NIND=simulation_config['NIND'])
    # 试图加入初始解[未成功]
    # chrome=np.zeros((simulation_config['NIND'],3))
    # chrome=np.array([[1,0,0],[1,0.5,0.3]])
    # tempPop.initChrom()  # 初始化种群染色体矩阵
    # population.Phen=chrome
    # print(population.__str__())

    # 构建算法：增强精英保留的遗传算法模板
    algorithm = ea.soea_SEGA_templet(problem=problem, population=population,
                                     # ea.Population(Encoding='RI', NIND=simulation_config['NIND']), # 10+
                                     # 实例化种群对象:Encoding编码方式,NIND所需要的个体数,RI-实整数编码，实数和整数的混合编码
                                     MAXGEN=simulation_config['MaxGen'],  # 最大进化代数
                                     MAXTIME=simulation_config['MaxTime'],  # 最大运行时间
                                     logTras=1,  # 表示每隔多少代记录一次日志信息，0表示不记录。
                                     trappedValue=1e-6,  # 单目标优化陷入停滞的判断阈值。
                                     maxTrappedCount=15)  # 进化停滞计数器最大上限值。
    algorithm.mutOper = ea.Mutbga(Pm=0.25, MutShrink=0.5, Gradient=20)  # 变异率设定

    for seed in seed_list:
        # 求解
        print("\n当前seed:{}".format(seed))
        res = ea.optimize(algorithm,
                          seed=seed,  # int - 随机数种子
                          verbose=True,  # bool - 控制是否在输入输出流中打印输出日志信息。
                          drawing=0,  # int  - 算法类控制绘图方式的参数,0表示不绘图；
                          outputMsg=True,  # bool - 控制是否输出结果以及相关指标信息。
                          drawLog=False,  # bool - 用于控制是否根据日志绘制迭代变化图像。
                          saveFlag=False,  # bool - 控制是否保存结果。
                          dirName=None  # str  - 文件保存的路径。当缺省或为None时，默认保存在当前工作目录的文件夹下
                          )

        # 评估最优解并输出图像
        test_solution = Simulation(simulation_config)
        results = test_solution.run(rule=res['Vars'][0])  # 运行仿真
        solution_list.append(res['Vars'][0])
        object_value_list.append(results['T_last'])

    # 多个seed迭代结束后，取最小的object value
    # print(object_value_list)
    min = object_value_list.index(np.min(object_value_list))  # 总成本最小方案
    print('\n\n当前object_value_list:{},取第{}个结果'.format(object_value_list, min))
    return object_value_list,solution_list,min

if __name__ == '__main__':
    start = tm.time()
    object_value_list, solution_list, min=example_GA(simulation_config)

    best_object = object_value_list[min]
    best_solution=solution_list[min]

    print('当前min的目标是:',simulation_config['type'])
    print(f'最优解为:{list(best_solution)},目标值为:{best_object}')

    end = tm.perf_counter()
    print("程序共计用时 : %s Seconds " % (end - start))