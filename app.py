# -*- coding: utf-8 -*-

import os
import codecs

from extract.ZengJianChiExtractor import ZengJianChiExtractor
from extract.DZExtractor import DZExtractor


def extract_zengjianchi(zjc_ex, html_dir_path, html_id):
    record_list = []
    for record in zjc_ex.extract(os.path.join(html_dir_path, html_id)):
        if record is not None and record.shareholderFullName is not None and \
                len(record.shareholderFullName) > 1 and \
                record.finishDate is not None and len(record.finishDate) >= 6:
            record_list.append("%s,%s" % (html_id, record.to_result()))
    for record in record_list:
        print(record)
    return record_list


def extract_zengjianchi_from_html_dir(zjc_ex, html_dir_path, res_path):
    with codecs.open(res_path, 'w', encoding = 'utf-8') as f:
        f.write("html文件,股东全称,股东简称,变动截止日期,变动价格,变动数量,变动后持股数,变动后持股比例\n")
        for html_id in os.listdir(html_dir_path):
            record_list = extract_zengjianchi(zjc_ex, html_dir_path, html_id)
            for record in record_list:
                f.write(record + "\n")


def extract_dz(dz_ex, html_dir_path, html_id):
    record_list = []
    for record in dz_ex.extract(os.path.join(html_dir_path, html_id)):
        if record is not None and record.addObject is not None and len(record.addObject) > 1 and\
                record.addNumber is not None and record.addNumber.isdigit():
            record_list.append("%s,%s" % (html_id, record.to_result()))
    for record in record_list:
        print(record)
    return record_list


def extract_dz_from_html_dir(dz_ex, html_dir_path, res_path):
    with codecs.open(res_path, 'w', encoding = 'utf-8') as f:
        f.write("html文件,增发对象,增发数量,增发金额,锁定期,认购方式\n")
        for html_id in os.listdir(html_dir_path):
            record_list = extract_dz(dz_ex, html_dir_path, html_id)
            for record in record_list:
                f.write(record + "\n")


if __name__ == "__main__":
    '''
    # 提取所有 html 中的记录
    zengjianchi_config_file_path = 'config/ZengJianChiConfig.json'
    # ner_model_dir_path = 'E:/WorkBench/Courses/Big-Data/Proj2-Finance/ltp_data_v3.4.0'
    ner_model_dir_path = '/home/swj/Tools/ltp_data_v3.4.0'
    ner_blacklist_file_path = 'config/ner_com_blacklist.txt'

    zjc_ex = ZengJianChiExtractor(zengjianchi_config_file_path, ner_model_dir_path, ner_blacklist_file_path)
    # extract_zengjianchi_from_html_dir(zjc_ex, '../train_data/增减持/html', './results/HodingChange.csv')
    extract_zengjianchi_from_html_dir(zjc_ex, '../data/train_data/增减持/html', './results/HodingChange.csv')
    '''
    # 提取所有 html 中的记录
    dz_config_file_path = './config/DZConfig.json'
    ner_model_dir_path = '/home/swj/Tools/ltp_data_v3.4.0'
    ner_blacklist_file_path = './config/ner_com_blacklist.txt'

    dz_ex = DZExtractor(dz_config_file_path, ner_model_dir_path, ner_blacklist_file_path)
    extract_dz_from_html_dir(dz_ex, './data', './results/DZ.csv')
