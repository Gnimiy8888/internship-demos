import os
import shutil
import json
import glob
import jsonlines
import time
import numpy as np
import cv2

from tqdm import tqdm
from openpyxl import Workbook
import get_rosetta_json
from stardust import rosetta
from stardust import rosetta_new


def get_demo():
    demo = {}
    return demo


def main(project_id, pool_id, project_path, export_path, project_name_CN):
    time_now = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())

    file_list = glob.glob(f'{project_path}/*.json')
    # file_list = glob.glob(f'{project_path}/*/**.json')
    qbar = tqdm(file_list, postfix=dict(msg='working'))
    for file_name in qbar:
        if file_name.endswith('.DS_Store'):
            continue
        demo = get_demo()
        out_file_name = file_name.split('/')[-1]
        out_file_name = out_file_name.split('.')[0]
        with open(file_name, 'r', encoding='utf-8') as f:
            data = json.load(f)
        # region 这里写处理逻辑
        for anno in data['result']['annotations']:
            anno_type = anno['type'].replace('slot','slots')
            for obj in anno[anno_type]:
                pass
            pass
        pass
        # endregion

        export_path1 = f'/Users/stardust/Desktop/Babytree_母婴问答/{export_path}/{project_name_CN}-{project_id}_{time_now}'
        os.makedirs(export_path1, exist_ok=True)
        with open(f'{export_path1}/{out_file_name}.json', 'w') as f:
            # json.dump(demo,f)
            pass
    pass


def init(project_id, pool_id, is_check_pool, export_path, project_name_cd):
    save_path = '/Users/stardust/Desktop/Babytree_母婴问答'
    abs_addr = os.path.abspath(save_path)
    project_path = '/'.join([save_path, str(project_id)])

    test_flag = True
    test_flag = False

    if not test_flag:
        # region 下载数据 开发时注掉，省去下载数据
        if os.path.exists(project_path):
            shutil.rmtree(project_path)
            print(f'已删除目录：{project_path}')
        print('数据下载中')
        get_rosetta_json.GetRosData(project_id, pool_id, save_path=save_path,
                                    is_check_pool=is_check_pool).get_unziped_data()
        # get_rosetta_json_big_backdoor.GetRosData(project_id, pool_id, save_path=save_path,
        #                             is_check_pool=is_check_pool).get_unziped_data()

        print('数据下载完成')
        # endregion

        # region 拆帧 如无需拆帧注掉即可
        print('开始拆帧')
        rosetta.to_split(project_path)
        # rosetta_new.to_split(project_path)
        print('数据拆帧完毕')
        # endregion

    # print('开始处理')
    # main(project_id, pool_id, project_path, export_path, project_name_cd)
    # print('完活')

    if test_flag:
        print('本次导出为测试导出，并未重新下载数据')
    else:
        print('本次导出为正式导出，重新下载数据')


if __name__ == '__main__':
    init(3554, [71038], True, export_path='user_export', project_name_cd='测试项目')
    # rosetta_new.to_split('/Users/stardust/Documents/RS_info/test1')