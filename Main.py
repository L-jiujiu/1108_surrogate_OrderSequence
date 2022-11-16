import time as tm
import numpy as np

from simulation_config import simulation_config
from surrogate_main import example_sop
from GA_main import example_GA


if __name__ == "__main__":
    start = tm.perf_counter()  # 记录当前时刻
    print(f"当前优化方法为:{simulation_config['optimization_method']},当前优化目标为{simulation_config['type']}")

    if simulation_config['optimization_method']=='surrogate':
        result = example_sop(simulation_config)
        best_object=result.value
        best_solution=np.array_str(result.params[0], max_line_width=np.inf, precision=5, suppress_small=True)

    elif simulation_config['optimization_method']=='GA':
        object_value_list, solution_list, min = example_GA(simulation_config)
        best_object = object_value_list[min]
        best_solution = solution_list[min]
    print(f"当前优化方法为:{simulation_config['optimization_method']},当前优化目标为{simulation_config['type']}")
    print(f"\n优化目标{simulation_config['type']}:{best_object}")
    print(f"最优解: {best_solution}")

    end = tm.perf_counter()
    print("程序共计用时 : %s Seconds " % (end - start))