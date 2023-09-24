"""
.. module:: example_sop
  :synopsis: Example SOP
.. moduleauthor:: Taimoor Akhtar <erita@nus.edu.sg>
"""

import logging
import os.path
import time as tm
import numpy as np
import os

from poap.controller import BasicWorkerThread, ThreadController
from pySOT.experimental_design import SymmetricLatinHypercube
from pySOT.strategy import SOPStrategy
from pySOT.surrogate import CubicKernel, LinearTail, RBFInterpolant
from pySOT.optimization_problems.optimization_problem import OptimizationProblem

from a_Simulation import Simulation
from a_Dynamic_simulation_config import simulation_config

# 原surrogate ackley中对应的class
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


# 原surrogate main中对应的class
def example_sop(sop_config):
    if not os.path.exists("./logfiles"):
        os.makedirs("logfiles")
    if os.path.exists("./logfiles/example_simple.log"):
        os.remove("./logfiles/example_simple.log")
    logging.basicConfig(filename="./logfiles/example_simple.log", level=logging.INFO)

    num_threads = sop_config['num_threads']
    max_evals = sop_config['max_evals']

    ackley = Ackley()
    rbf = RBFInterpolant(dim=ackley.dim, lb=ackley.lb, ub=ackley.ub, kernel=CubicKernel(), tail=LinearTail(ackley.dim))
    slhd = SymmetricLatinHypercube(dim=ackley.dim, num_pts=2 * (ackley.dim + 1))
    # Create a strategy and a controller
    controller = ThreadController()
    controller.strategy = SOPStrategy(
        max_evals=max_evals,
        opt_prob=ackley,
        exp_design=slhd,
        surrogate=rbf,
        asynchronous=False,
        ncenters=num_threads,
        batch_size=num_threads,
    )
    print("Number of threads: {}".format(num_threads))
    print("Maximum number of evaluations: {}".format(max_evals))
    print("Strategy: {}".format(controller.strategy.__class__.__name__))
    print("Experimental design: {}".format(slhd.__class__.__name__))
    print("Surrogate: {}".format(rbf.__class__.__name__))

    # Launch the threads and give them access to the objective function
    for _ in range(num_threads):
        worker = BasicWorkerThread(controller, ackley.eval)
        controller.launch_worker(worker)

    # Run the optimization strategy
    result = controller.run()

    # print("\nBest value found: {0}".format(result.value))
    # print(
    #     "Best solution found: {0}\n".format(
    #         np.array_str(result.params[0], max_line_width=np.inf, precision=5, suppress_small=True)
    #     )
    # )
    return result


if __name__ == "__main__":
    start = tm.perf_counter()  # 记录当前时刻
    result=example_sop(simulation_config)

    print("\nBest value found: {0}".format(result.value))
    print(
        "Best solution found: {0}\n".format(
            np.array_str(result.params[0], max_line_width=np.inf, precision=5, suppress_small=True)
        )
    )
    end = tm.perf_counter()
    print("程序共计用时 : %s Seconds " % (end - start))
