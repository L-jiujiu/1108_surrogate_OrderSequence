"""
.. module:: example_sop
  :synopsis: Example SOP
.. moduleauthor:: Taimoor Akhtar <erita@nus.edu.sg>
"""

import logging
import os.path
import numpy as np
from poap.controller import BasicWorkerThread, ThreadController
from pySOT.experimental_design import SymmetricLatinHypercube
from surrogate_ackley import Ackley
from pySOT.strategy import SOPStrategy
from pySOT.surrogate import CubicKernel, LinearTail, RBFInterpolant
import time as tm
from simulation_config import simulation_config


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
