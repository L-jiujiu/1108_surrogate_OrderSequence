def find_shorted_path(node_list,edge_list,section_list_work):
    #顶点列表
    '''计算各个顶点的Ve(v)最早发生时间'''

    #找出图的起点
    temp_start_list = []
    for edge in edge_list:
        temp_start_list.append(edge[1])
        # print(edge)
        # print(edge[1])
    start_node = [x for x in node_list if x not in temp_start_list]
    # print(f'start_node:{start_node}')

    Ve_node_dict = {}
    Ve_node_dict[start_node[0]] = 0
    # print(Ve_node_dict)

    for node in node_list:
        Ve_tempnode_list = []
        for edge in edge_list:
            # print(edge)
            if node == edge[1]:
                # print('fff',edge[1])
                # print('eee',Ve_node_dict[edge[0]])
                temp_Ve_node_value = Ve_node_dict[edge[0]] + edge[2]
                Ve_tempnode_list.append(temp_Ve_node_value)
        if len(Ve_tempnode_list) == 0:
            Ve_node_dict[node] = 0
        if len(Ve_tempnode_list) == 1:
            Ve_node_value = Ve_tempnode_list[0]
            Ve_node_dict[node] = Ve_node_value
        if len(Ve_tempnode_list) > 1:
            Ve_node_value = max(Ve_tempnode_list)
            Ve_node_dict[node] = Ve_node_value
    # print('Ve(v)最早发生时间:\n',Ve_node_dict,'\n')

    '''计算各个顶点的Vl(v)最迟发生时间'''
    #找出图的终点
    temp_end_list = []
    for edge in edge_list:
        temp_end_list.append(edge[0])
    end_node = [x for x in node_list if x not in temp_end_list]
    # print(end_node)

    Vl_node_dict = {}
    Vl_node_dict[end_node[0]] = Ve_node_dict[end_node[0]]

    reverse_edge_list = []
    for i in range(len(edge_list)-1,-1,-1):
        reverse_edge_list.append(edge_list[i])


    for node in reversed(node_list):
        Vl_tempnode_list = []
        for edge in reverse_edge_list:
            if node == edge[0]:
                # print(edge[1])
                # print(edge[2])
                # print(Vl_node_dict[edge[1]])
                temp_Vl_node_value = Vl_node_dict[edge[1]] - edge[2]
                Vl_tempnode_list.append(temp_Vl_node_value)
        if len(Vl_tempnode_list) == 0:
            Vl_node_dict[node] = Ve_node_dict[end_node[0]]
        if len(Vl_tempnode_list) == 1:
            Vl_node_value = Vl_tempnode_list[0]
            Vl_node_dict[node] = Vl_node_value
        if len(Vl_tempnode_list) > 1:
            Vl_node_value = min(Vl_tempnode_list)
            Vl_node_dict[node] = Vl_node_value
    # print('Vl(v)最迟发生时间:\n',Vl_node_dict,'\n')

    '''计算各个边的e(a)最早发生时间'''
    e_bian_dict = {}
    for edge in edge_list:
        e_bian_dict['{}-{}'.format(edge[0],edge[1])] = Ve_node_dict[edge[0]]
    # print('e(a)最早发生时间:\n',e_bian_dict,'\n')

    '''计算各个边的l(a)最迟发生时间'''

    l_bian_dict = {}
    for edge in edge_list:
        l_bian_dict['{}-{}'.format(edge[0],edge[1])] = Vl_node_dict[edge[1]] - edge[2]
    # print('l(a)最迟发生时间:\n',l_bian_dict,'\n')

    '''计算时间余量d(a)'''

    d_bian_dict = {}
    for bian in e_bian_dict.keys():
        d_bian_dict[bian] = l_bian_dict[bian] - e_bian_dict[bian]
    # print("d(a)时间余量:\n",d_bian_dict,'\n')

    dian_zuizaowancheng_dict={}
    for dian in Ve_node_dict.keys():
        # edge_list = [['E1', 'D', 1]
        # for in edge_list:
        count=0

        for edge in edge_list:
            if (edge[0]==dian) and (edge[1]=='D'):
                count=edge[2]
                break
        dian_zuizaowancheng_dict[dian]=Ve_node_dict[dian]+count
    # print(f'点的最早完成时间:\n{dian_zuizaowancheng_dict}\n')

    max_time=max(dian_zuizaowancheng_dict.values())
    dian_shengyushijian_dict = {}
    for dian in dian_zuizaowancheng_dict.keys():
        # print(max(dian_zuiwanwancheng_dict.values()))
        dian_shengyushijian_dict[dian]=max_time-dian_zuizaowancheng_dict[dian]
    # print(f'\n【后面的空余】各点从最早完成到关键路径间的剩余时间:\n{dian_shengyushijian_dict}')

    # max_time = max(dian_zuizaowancheng_dict.values())
    dian_shengyushijian_now_dict = {}

    # [[['E0', 1.0]], [['E1', 1.0]], [['A0', 2.0]], [], [['B0', 1.0], ['C0', 1.0]], [['A1', 1.0]]]
    # [['E1'], ['E2'], ['A1'], [], ['B1', 'C1'], ['A2']]

    # 每个工区记录最短少的剩余时间
    # print('【后面的空余】各点从最早完成到关键路径间的剩余时间:')
    section_list_lefttime=[0,0,0,0,0,0]
    for i in range(0,6):
        temp_list=[]
        if len(section_list_work[i])==0:
            section_list_lefttime[i] = max_time
            continue
        for work in section_list_work[i]:
            temp_list.append(dian_shengyushijian_dict[work[0]])
        # print(temp_list)
        section_list_lefttime[i]=min(temp_list)
    # print(f'*****所有工区后面的剩余时间:{section_list_lefttime}')

    # 如果订单已经开始做了，最迟开始时间就是0不能变
    section_list_lefttime_pre = [0, 0, 0, 0, 0, 0]
    for i in range(0, 6):
        temp_list = []
        if len(section_list_work[i]) == 0:
            section_list_lefttime_pre[i] = max_time
            continue
        for work in section_list_work[i]:
            temp_list.append(Vl_node_dict[work[0]])
        # print(temp_list)
        section_list_lefttime_pre[i] = min(temp_list)
    # print('【前面的空余】各店从现在到最迟开始时间的剩余时间')
    # print(f'*****所有工区前面的剩余时间:{section_list_lefttime_pre}\n')



    d_dian_dict = {}
    for dian in Ve_node_dict.keys():
        d_dian_dict[dian] = Vl_node_dict[dian]-Ve_node_dict[dian]
    # print("d(a)点的时间余量:\n", d_dian_dict, '\n')
    # print('Vl(v)最迟发生时间:\n',Vl_node_dict,'\n')
    # print('Ve(v)最早发生时间:\n',Ve_node_dict,'\n')
    # print("关键路径为：",[x for x in d_bian_dict if d_bian_dict[x] == 0])

    # 每个工序在关键路径内的剩余时间：
    # print(section_list_lefttime)
    return section_list_lefttime,section_list_lefttime_pre,max_time

if __name__ == "__main__":
    node_list = ['E1', 'E2', 'A1', 'A2', 'B1', 'C1', 'D']

    edge_list = [
        # [本工序，'D',本工序时间]
        ['E1', 'D', 1],
        ['E2', 'D', 1],
        ['A1', 'D', 2],
        ['A2', 'D', 1],
        ['B1', 'D', 1],
        ['C1', 'D', 1],
        # [同一个订单工序的前一，后一，前一的时间]
        ['E1', 'E2', 1],
        ['A1', 'A2', 2],
        # [同一个工区订单的前一，后一，前一的时间]
        ['B1', 'C1', 1],
        ]

    section_list_work=[]
    section_list_work.append(['E1'])
    section_list_work.append(['E2'])
    section_list_work.append(['A1'])
    section_list_work.append([])
    section_list_work.append(['B1','C1'])
    section_list_work.append(['A2'])
    print(f'section_list_work:{section_list_work}')
    section_list_lefttime,max_time=find_shorted_path(node_list,edge_list,section_list_work)
    print(f'关键路径用时：{max_time},各工区的空闲时间：{section_list_lefttime}')
