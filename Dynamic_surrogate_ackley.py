import numpy as np
import os

from pySOT.optimization_problems.optimization_problem import OptimizationProblem
from Simulation import Simulation
from Dynamic_simulation_config import simulation_config


class Ackley(OptimizationProblem):
    """Ackley function
    :ivar dim: Number of dimensions
    :ivar lb: Lower variable bounds
    :ivar ub: Upper variable bounds
    :ivar int_var: Integer variables
    :ivar cont_var: Continuous variables
    :ivar min: Global minimum value
    :ivar minimum: Global minimizer
    :ivar info: String with problem info
    """

    def __init__(self,):
        input_config = {
            'dim': 3,
            'lb': 0,
            'ub': 1,
        }
        self.dim = input_config['dim']
        self.min = 0
        self.minimum = np.zeros(input_config['dim'])
        self.lb = input_config['lb'] * np.ones(input_config['dim'])
        self.ub = input_config['ub'] * np.ones(input_config['dim'])
        self.int_var = np.array([])
        self.cont_var = np.arange(0, input_config['dim'])
        self.info = str(input_config['dim']) + "-dimensional Ackley function \n" + "Global optimum: f(0,0,...,0) = 0"
        # self.problem=Simulation(simulation_config)

    def eval(self, x):
        """Evaluate the Ackley function  at x

        :param x: Data point
        :type x: numpy.array
        :return: Value at x
        :rtype: float
        """
        self.__check_input__(x)

        surrogate_weight = list(x)

        print(f'\nx:{surrogate_weight}')
        # self.problem.recycle_initial()
        # results = self.problem.run(rule=surrogate_weight)  # 运行仿真

        problem=Simulation(simulation_config)
        results=problem.run(rule=surrogate_weight)
        # print(results)
        T_last = results['T_last']
        busy_variance = results['busy_variance']
        all = results['all']

        # print(f'111111111111,本轮仿真结果已更新:{T_last}')

        # min_timespan是减少总用时，min_jam_sum是减少拥堵次数
        if simulation_config['type']=='min_timespan':
            re=float(T_last)
        elif simulation_config['type']=='min_variance':
            re=float(busy_variance)
        elif simulation_config['type']=='min_all':
            re=float(all)
        else:
            print('未定义返回参数！')
            re=float(T_last)
        print(re)

        return re
