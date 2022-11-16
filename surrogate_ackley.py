import numpy as np
import os

from pySOT.optimization_problems.optimization_problem import OptimizationProblem
from Simulation import Simulation


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

    def eval(self, x):
        """Evaluate the Ackley function  at x

        :param x: Data point
        :type x: numpy.array
        :return: Value at x
        :rtype: float
        """
        self.__check_input__(x)
        from simulation_config import simulation_config

        surrogate_weight = x
        print(f'\nx:{x}')

        simulation_config['weight']=surrogate_weight
        simulation_1 = Simulation(simulation_config)  # 初始化仿真实例
        results = simulation_1.run()  # 运行仿真
        T_last = results['T_last']
        jam_1 = results['jam_1']
        jam_2 = results['jam_2']
        busy_variance = results['busy_variance']

        # print(f'111111111111,本轮仿真结果已更新:{T_last}')

        # min_timespan是减少总用时，min_jam_sum是减少拥堵次数
        if simulation_config['type']=='min_timespan':
            return float(T_last)
        elif simulation_config['type']=='min_sum':
            return float(jam_1+jam_2)
        elif simulation_config['type']=='min_mix':
            return float(T_last+jam_1+jam_2)
        elif simulation_config['type']=='min_variance':
            return float(busy_variance)
        elif simulation_config['type']=='min_all':
            return float(T_last/6.944+(jam_1+jam_2)/0.88+busy_variance/22.728)
        else:
            print('未定义返回参数！')
            return float(T_last)
