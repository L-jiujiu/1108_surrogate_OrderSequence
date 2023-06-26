import time
import pandas as pd
import plotly as py
import plotly.figure_factory as ff
import numpy as np
import plotly.graph_objects
import random


class DrawGantt:
    def __init__(self,Gantt_config):
        # 每个工序的开始时间  # x轴, 对应于画图位置的起始坐标x
        self.n_start_time=Gantt_config['n_start_time']
        # 每个工序的持续时间 # length, 对应于每个图形在x轴方向的长度
        self.n_duration_time=Gantt_config['n_duration_time']
        # section号  # y轴, 对应于画图位置的起始坐标y
        self.n_bay_start =Gantt_config['n_bay_start']
        # order号
        self.n_job_id = Gantt_config['n_job_id']
        # 所有section号
        self.op = Gantt_config['op']
        self.colors=[]
        self.type=Gantt_config['type']

        for i in self.op:
            self.colors.append(
                'rgb(' + str(random.randint(0, 255)) + ',' + str(random.randint(0, 255)) + ',' + str(
                    random.randint(0, 255)) + ')')
        # print(self.colors)

        # self.colors = ('rgb(46, 137, 205)',
        #           'rgb(114, 44, 121)',
        #           'rgb(198, 47, 105)',
        #           'rgb(58, 149, 136)',
        #           'rgb(107, 127, 135)',
        #           'rgb(46, 180, 50)',
        #           'rgb(150, 44, 50)',
        #           'rgb(100, 47, 150)',
        #           'rgb(58, 100, 180)',
        #           'rgb(150, 127, 50)')

        self.millis_seconds_per_minutes = 1000 * 60
        self.start_time = time.time() * 1000
        self.initial_time=time.time()*1000
        # self.start_time = 0 * 1000
        # self.start_time=0
        # self.step=1
        self.job_sumary = {}

    # 获取工件对应的第几道工序
    def get_op_num(self,job_num):
        index = self.job_sumary.get(str(job_num))
        new_index = 0
        if index:
            new_index = index + 1
        self.job_sumary[str(job_num)] = new_index
        return new_index


    def create_draw_defination(self):
        df = []
        # print(len(self.n_job_id))
        for index in range(len(self.n_job_id)):
            operation = {}
            # 机器，纵坐标
            # operation['Task'] = 'section' + str(self.n_bay_start.__getitem__(index))

            operation['Task'] = str(int(self.n_bay_start.__getitem__(index))+17)+'01'
            operation['Start'] = self.start_time.__add__(self.n_start_time.__getitem__(index) * self.millis_seconds_per_minutes)
            operation['Finish'] = self.start_time.__add__(
                (self.n_start_time.__getitem__(index) + self.n_duration_time.__getitem__(index)) * self.millis_seconds_per_minutes)

            # operation['Task'] = 'section' + str(self.n_bay_start.__getitem__(index))
            # operation['Start'] = self.start_time.__add__(
            #     self.n_start_time.__getitem__(index) * self.step)
            # operation['Finish'] = self.start_time.__add__(
            #     (self.n_start_time.__getitem__(index) + self.n_duration_time.__getitem__(
            #         index)) * self.step)

            # 工件，
            # print(index)
            # print(self.op.index(self.n_job_id.__getitem__(0)))
            job_num = self.op.index(self.n_job_id.__getitem__(index))
            operation['Resource'] = 'O' + str(job_num)
            df.append(operation)
        df.sort(key=lambda x: x["Task"], reverse=True)
        return df

    def draw_prepare(self):
        df = self.create_draw_defination()
        # return ff.create_gantt(df, colors=self.colors, index_col='Resource',
        #                        title='当前调度结果', show_colorbar=True,
        #                        group_tasks=True, data=self.n_duration_time,
        #                        showgrid_x=True, showgrid_y=True)

        return ff.create_gantt(df, colors=self.colors, index_col='Resource',
                           title='当前调度结果', show_colorbar=True,
                           group_tasks=True, data=self.n_duration_time,
                           showgrid_x=True, showgrid_y=True)

    def add_annotations(self,fig):
        y_pos = 0
        for index in range(len(self.n_job_id)):
            # 机器，纵坐标
            y_pos = self.n_bay_start.__getitem__(index)

            x_start = self.start_time.__add__(self.n_start_time.__getitem__(index) * self.millis_seconds_per_minutes)
            x_end = self.start_time.__add__(
                (self.n_start_time.__getitem__(index) + self.n_duration_time.__getitem__(index)) * self.millis_seconds_per_minutes)
            x_pos = (x_end - x_start) / 2 + x_start

            # x_start = self.start_time.__add__(self.n_start_time.__getitem__(index) * self.step)
            # x_end = self.start_time.__add__(
            #     (self.n_start_time.__getitem__(index) + self.n_duration_time.__getitem__(
            #         index)) * self.step)
            # x_pos = (x_end - x_start) / 2 + x_start

            # 工件，
            job_num = self.op.index(self.n_job_id.__getitem__(index))
            text = 'J(' + str(job_num) + "," + str(self.get_op_num(job_num)) + ")=" + str(self.n_duration_time.__getitem__(index))
            # text = 'T' + str(job_num) + str(get_op_num(job_num))
            text_font = dict(size=8, color='black')
            # text=[x_pos]
            # print(pd.to_datetime(x_pos)) #.day for d in x_pos)
            # print(int(datetime.datetime.timestamp(x_pos)))

            fig['layout']['annotations'] += tuple(
                [dict(x=x_pos, y=y_pos, text=text, textangle=-30, showarrow=False, font=text_font,
                )])

    def draw_fjssp_gantt(self):
        print(
            f'op({len(self.op)}):{self.op}',
            f'n_start_time({len(self.n_start_time)}):{self.n_start_time}\n,',
            f'n_bay_start({len(self.n_bay_start)}):{self.n_bay_start}\n',
            f'n_duration_time({len(self.n_duration_time)}):{self.n_duration_time}\n',
            f'n_job_id({len(self.n_job_id)}):{self.n_job_id}'
              )
        # import datetime
        print(pd.to_datetime(self.initial_time).minute)
        print(pd.to_datetime(self.start_time).minute)
        print(self.initial_time)
        print(self.start_time)
        # text=str(int(datetime.datetime.timestamp(self.initial_time)))
        # print(text)

        # text = pd.date_range('2021-08-01', '2021-08-17', freq='D')
        # text = [pd.to_datetime(d).day for d in text]
        # # text=[x+1 for x in range(len(text))]
        # # text=[str(int(datetime.datetime.timestamp(x))) for x in text]

        # text=range(0,(self.start_time-time.time()*1000)*1000)
        fig = self.draw_prepare()
        # layout=plotly.graph_objects.Layout(
        #     xaxis=dict(tickvals=np.arange(1,),ticktext=text))
        self.add_annotations(fig)
        # fig.layout=layout
        py.offline.plot(fig, filename='fjssp-gantt-picture'+self.type)


if __name__ == '__main__':
    Gantt_config = {
        # 所有section号
        'op': [0, 1, 2, 3, 4, 5],

        # 每个工序的开始时间  # x轴, 对应于画图位置的起始坐标x
        'n_start_time': [1, 2, 3,
                         2, 4,
                         3, 4,
                         4],
        # 每个工序的持续时间 # length, 对应于每个图形在x轴方向的长度
        'n_duration_time': [1, 1, 1,
                            2, 1,
                            1, 1,
                            1],
        # section号  # y轴, 对应于画图位置的起始坐标y
        'n_bay_start': [0, 2, 4,
                        0, 2,
                        2, 4,
                        0],
        # order号
        'n_job_id': [0, 0, 0,
                     1, 1,
                     2, 2,
                     3],
        'type':'test'
    }
    # Gantt_config={
    #     'op': [0, 1, 2, 3, 4, 5],
    #     'n_start_time': [1, 4, 2, 3, 6, 4, 6, 10, 16, 11, 14, 19, 16, 17, 18, 20, 25, 25, 40, 26, 36, 40, 36, 42, 37,
    #                         42, 38, 47, 42, 45, 43, 56, 44, 56, 45, 55, 60, 60, 69, 61, 69, 75, 70, 76, 71, 78, 73, 75,
    #                         77, 83, 85, 92, 94, 95, 100, 124, 96, 101, 97, 101, 102, 124, 136, 105, 136, 137, 138, 139,
    #                         144, 147, 145, 146, 149, 154, 157, 157, 160, 158, 161, 159, 160, 161, 168, 168, 173, 169,
    #                         175, 177, 173, 175, 183, 184, 183, 189, 184, 185, 186, 187, 189, 190, 192, 193, 194, 195,
    #                         195, 200, 196, 202, 197, 198, 200, 201, 204, 207, 205, 208, 216, 209, 218, 219, 220, 220,
    #                         233, 221, 222, 223, 233, 233, 241, 248, 239, 241, 244, 243, 244, 245, 245, 250, 255, 251,
    #                         268, 252, 254, 259, 259, 268, 260, 268, 273, 276, 269, 276, 281, 270, 273, 281, 282, 298,
    #                         282, 304, 283, 298, 284, 298, 306, 307, 308, 309, 309, 310, 311, 311, 312, 317, 323, 318,
    #                         321, 319, 322, 324, 321, 328, 322, 328, 336, 323, 328, 328, 334, 342, 329, 336, 342, 337,
    #                         338, 339, 342, 342, 343, 369, 347, 349, 348, 353, 349, 353, 356, 352, 357, 353, 364, 366,
    #                         365, 367, 366, 369, 369, 374, 379, 370, 376, 371, 374, 376, 377, 382, 385, 379, 383, 380,
    #                         385, 387, 395, 396, 403, 397, 403, 408, 404, 405, 408, 412, 409, 412, 413, 414, 418, 415,
    #                         420, 420, 421, 421, 426, 442, 426, 441, 427, 432, 442, 446, 443, 459, 444, 447, 459, 447,
    #                         448, 452, 448, 461, 462, 463, 465, 464, 465, 468, 476, 476, 484, 477, 480, 480, 482, 498,
    #                         484, 493, 498, 501, 499, 504, 500, 505, 508, 508, 513, 509, 514],
    #
    #     'n_bay_start': [2, 5, 0, 1, 2, 0, 1, 2, 4, 4, 1, 5, 2, 3, 4, 3, 5, 3, 5, 1, 3, 4, 1, 5, 0, 2, 1, 2, 3, 4, 0,
    #                        3, 1, 5, 3, 2, 4, 2, 5, 1, 2, 5, 1, 5, 0, 5, 1, 3, 2, 4, 5, 5, 5, 0, 3, 5, 1, 2, 3, 1, 0, 2,
    #                        4, 0, 2, 3, 1, 0, 0, 3, 2, 5, 3, 3, 5, 3, 5, 1, 2, 4, 3, 1, 4, 2, 4, 1, 2, 4, 5, 1, 3, 5, 1,
    #                        3, 4, 2, 5, 0, 5, 1, 4, 5, 0, 2, 0, 3, 1, 5, 3, 5, 4, 0, 3, 5, 1, 3, 5, 5, 5, 1, 4, 1, 2, 3,
    #                        0, 2, 4, 0, 2, 4, 1, 0, 5, 1, 0, 3, 0, 0, 2, 1, 5, 5, 1, 3, 1, 3, 1, 1, 2, 5, 0, 2, 5, 4, 1,
    #                        1, 2, 5, 3, 5, 0, 2, 1, 3, 5, 1, 0, 4, 2, 0, 3, 5, 0, 2, 5, 3, 5, 1, 2, 4, 1, 3, 0, 2, 5, 3,
    #                        4, 0, 2, 4, 1, 0, 3, 1, 4, 3, 5, 2, 0, 5, 2, 5, 3, 5, 1, 3, 5, 1, 3, 4, 1, 2, 3, 4, 1, 2, 0,
    #                        3, 5, 3, 5, 2, 5, 4, 0, 2, 4, 3, 4, 1, 2, 5, 4, 1, 4, 5, 1, 2, 3, 4, 0, 5, 1, 2, 4, 0, 2, 1,
    #                        2, 1, 5, 1, 2, 5, 1, 5, 1, 3, 3, 5, 0, 2, 1, 2, 5, 1, 3, 4, 1, 2, 1, 3, 4, 5, 0, 2, 4, 2, 4,
    #                        1, 3, 1, 3, 4, 2, 5, 3, 5, 0, 2, 1, 1, 5, 1, 3, 2, 4],
    #     'n_duration_time': [3, 7, 2, 3, 4, 10, 8, 2, 1, 5, 5, 2, 6, 3, 4, 5, 15, 3, 2, 10, 3, 4, 1, 1, 5, 5, 5, 8,
    #                             3, 4, 1, 3, 9, 13, 11, 5, 4, 8, 6, 4, 2, 1, 3, 1, 7, 7, 1, 4, 6, 8, 7, 2, 30, 4, 2, 5,
    #                             5, 4, 3, 17, 3, 12, 4, 9, 8, 3, 8, 5, 3, 2, 2, 1, 5, 3, 2, 3, 5, 3, 2, 9, 4, 1, 5, 2, 2,
    #                             6, 2, 4, 11, 8, 1, 2, 6, 2, 4, 8, 3, 5, 4, 6, 4, 4, 1, 12, 5, 4, 6, 5, 3, 1, 2, 4, 2, 2,
    #                             3, 5, 2, 7, 6, 1, 9, 5, 4, 2, 4, 10, 6, 8, 7, 15, 4, 3, 2, 8, 1, 5, 5, 5, 5, 3, 2, 16,
    #                             5, 1, 1, 1, 2, 5, 3, 5, 5, 2, 17, 4, 8, 1, 2, 6, 5, 2, 5, 5, 3, 5, 5, 8, 1, 7, 8, 1, 1,
    #                             4, 8, 5, 13, 3, 2, 2, 2, 3, 3, 4, 5, 6, 5, 5, 5, 1, 6, 3, 8, 5, 3, 8, 4, 3, 2, 5, 25, 5,
    #                             2, 2, 5, 2, 3, 3, 8, 5, 3, 2, 2, 3, 2, 2, 1, 1, 4, 5, 5, 3, 2, 1, 2, 4, 5, 2, 10, 4, 2,
    #                             5, 2, 10, 8, 7, 2, 15, 5, 4, 5, 4, 3, 2, 6, 2, 4, 4, 2, 5, 1, 1, 20, 5, 8, 3, 1, 1, 5,
    #                             5, 4, 5, 5, 2, 3, 12, 5, 1, 4, 9, 7, 7, 8, 2, 2, 10, 1, 8, 8, 5, 4, 3, 1, 2, 16, 5, 9,
    #                             4, 3, 3, 5, 5, 5, 3, 2, 5, 5, 5, 5],
    #     'n_job_id': [81, 81, 62, 0, 0, 171, 1, 2, 2, 3, 150, 150, 158, 93, 107, 104, 104, 21, 21, 51, 51, 51, 126,
    #                     126, 52, 52, 151, 151, 37, 37, 32, 32, 33, 33, 152, 27, 27, 105, 105, 127, 82, 82, 106, 106, 22,
    #                     22, 16, 16, 4, 4, 128, 63, 53, 17, 17, 17, 10, 10, 108, 64, 129, 129, 129, 5, 130, 131, 83, 134,
    #                     109, 109, 6, 7, 132, 38, 38, 94, 94, 133, 133, 95, 99, 54, 54, 65, 65, 110, 110, 110, 159, 111,
    #                     111, 111, 135, 135, 39, 84, 11, 75, 8, 9, 42, 96, 12, 12, 165, 165, 14, 14, 15, 97, 112, 122,
    #                     19, 19, 40, 40, 40, 20, 55, 66, 66, 160, 160, 88, 157, 23, 23, 161, 161, 161, 24, 136, 136, 25,
    #                     89, 89, 124, 13, 13, 26, 26, 28, 41, 41, 162, 162, 67, 85, 85, 85, 18, 18, 18, 113, 86, 43, 43,
    #                     43, 137, 137, 68, 68, 44, 44, 153, 69, 163, 163, 141, 169, 169, 98, 80, 29, 29, 30, 30, 70, 70,
    #                     70, 154, 154, 71, 71, 71, 72, 72, 56, 56, 56, 138, 61, 61, 31, 34, 114, 114, 74, 35, 35, 36, 36,
    #                     57, 57, 172, 172, 172, 139, 139, 140, 45, 45, 46, 46, 47, 47, 73, 73, 73, 115, 115, 142, 142,
    #                     155, 116, 116, 116, 164, 164, 143, 143, 143, 117, 118, 118, 58, 59, 59, 92, 76, 144, 144, 87,
    #                     119, 168, 166, 166, 48, 48, 145, 145, 146, 146, 146, 156, 156, 120, 120, 121, 121, 123, 123, 77,
    #                     77, 77, 78, 78, 78, 167, 79, 100, 50, 50, 170, 60, 60, 60, 90, 90, 125, 125, 91, 91, 91, 147,
    #                     147, 148, 148, 101, 101, 49, 102, 102, 103, 103, 149, 149],
    #     'type':'Gantt'
    # }

    Gantt=DrawGantt(Gantt_config)
    Gantt.draw_fjssp_gantt()

    from Buffer_Simulation import Simulation
    from Buffer_Dynamic_simulation_config import simulation_config

    simulation_config['order_list_GA']=[0,1,2,3]
    # simulation_config['order_list_GA']=[3,2,1,0]

    simulation_1=Simulation(simulation_config)
    print(simulation_1.order_array)
    # simulation1.run
    results = simulation_1.run(rule=[1,0,0])  # 运行仿真
    print(results)