import time as tm
import numpy as np

from Dynamic_simulation_config import simulation_config
from Dynamic_surrogate_main import example_sop
from Dynamic_GA_main import example_GA
from Static_GA_main import example_GA_origin
import warnings

if __name__ == "__main__":
    warnings.filterwarnings('ignore')
    start = tm.perf_counter()  # 记录当前时刻
    if simulation_config['type_order']=='GA_origin':
        print(f"\n当前派单方式为:{simulation_config['type_order']},\n当前优化目标为{simulation_config['type']}")

        object_value_list, solution_list, min = example_GA_origin(simulation_config)
        best_object = object_value_list[min]
        best_solution = solution_list[min]

        print(f"\n当前派单方式为:{simulation_config['type_order']},\n当前优化目标为{simulation_config['type']},最优解:{best_solution}")


    elif simulation_config['type_order'] == 'rules_simple':
        print(f"\n当前派单方式为:{simulation_config['type_order']},\n优化方法为:{simulation_config['optimization_method']},当前优化目标为{simulation_config['type']}")

        if simulation_config['optimization_method'] == 'surrogate':
            result = example_sop(simulation_config)
            best_object = result.value
            best_solution = np.array_str(result.params[0], max_line_width=np.inf, precision=5, suppress_small=True)

        elif simulation_config['optimization_method'] == 'GA':
            object_value_list, solution_list, min = example_GA(simulation_config)
            best_object = object_value_list[min]
            best_solution = solution_list[min]
        print(f"\n当前派单方式为:{simulation_config['type_order']},\n优化方法为:{simulation_config['optimization_method']},当前优化目标为{simulation_config['type']},最优解:{best_solution}")



    end = tm.perf_counter()
    print("\n程序共计用时 : %s Seconds " % (end - start))