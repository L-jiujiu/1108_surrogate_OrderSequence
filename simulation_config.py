import os

cwd = os.getcwd()  # 读取当前文件夹路径

simulation_config = {
    'T': 50000000000,  # 仿真时长
    # 'T': 5,  # 仿真时长
    'num_section': 6,  # 分区个数
    'num_section_main': 2,  # 主路节点个数


    'pace':1,  # 订单派发节奏

    # 订单数据
    'path_order_sku_map': cwd + '/Fa_data/OrderPickDetail.xlsx',
    # 'path_order_sku_map': cwd + '/Fa_data/OrderPickDetail_less.xlsx',
    # 'path_order_sku_map': cwd + '/Fa_data/random_data_orders_1000/OrderPickDetail_random_0.xlsx',

    'path_sku_time_map': cwd + '/Fa_data/PickLinePos_time.xlsx',
    # 'path_order_sku_map': cwd + '/Fa_data/OrderPickDetail_median.xlsx',

    # 是否新建sku_time
    'new_sku_time': '0',  # '1'表示随机按照正态分布生成，'111'表示全部设定为1，'0'表示不新生成
    'normal_info': [2.4, 0.5],  # [Mean, StandardDeviation]

    # 不同策略：静态优化（直接排序），还是动态优化（决策规则）
    'schedule_type':'dynamic',

    # 对于动态优化 测试需要选择一种动态规划策略
    'rule': 'rule1',  # 决策规则1：多项式 𝒄𝒐𝒔𝒕=𝒂×𝑷_𝟎+𝒃×𝑷_𝟏+𝒄×𝑷_𝟐,多个最小就选第1个


    # todo: later
    # 优化方法：surrogate/GA
    # 'optimization_method':'surrogate',
    'optimization_method': 'GA',

    # 优化目标
    'type': 'min_timespan',  # min_timespan是减少总用时，min_jam_sum是减少拥堵次数,min_variance是减少各工站的繁忙程度
    # 'type': 'min_sum',
    # 'type': 'min_variance',
    # 'type': 'min_all',

    # + surrogate参数设置
    'weight': None,
    'num_threads': 1,  # 线程数
    'max_evals': 2,  # 迭代次数

    # + GA参数设置
    'seed_num': 1,  # 随机种子数量
    'MaxGen': 1,  # 最大进化次数
    'MaxTime': 100000,  # 最长运行时间
    'NIND': 1,  # 初始种群数量，建议>=10

    # 'test_version': 1,  # 1为显示print内容
    'test_version': 0,  # 1为显示print内容
}