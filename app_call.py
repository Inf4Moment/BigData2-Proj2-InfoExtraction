# -*- coding: utf-8 -*-

import os

from extract.ZengJianChiExtractor import ZengJianChiExtractor

from pycallgraph import PyCallGraph
from pycallgraph.output import GraphvizOutput

def extract_zengjianchi(zjc_ex, html_dir_path, html_id):
    record_list = []
    for record in zjc_ex.extract(os.path.join(html_dir_path, html_id)):
        if record is not None and record.shareholderFullName is not None and \
                len(record.shareholderFullName) > 1 and \
                record.finishDate is not None and len(record.finishDate) >= 6:
            record_list.append("%s\t%s" % (html_id, record.to_result()))
    for record in record_list:
        print(record)
    return record_list

def main():
    zengjianchi_config_file_path = 'config/ZengJianChiConfig.json'
    ner_model_dir_path = 'E:/WorkBench/Courses/Big-Data/Proj2-Finance/ltp_data_v3.4.0'
    ner_blacklist_file_path = 'config/ner_com_blacklist.txt'

    zjc_ex = ZengJianChiExtractor(zengjianchi_config_file_path, ner_model_dir_path, ner_blacklist_file_path)
    print('公告id\t股东全称\t股东简称\t变动截止日期\t变动价格\t变动数量\t变动后持股数\t变动后持股比例')
    extract_zengjianchi(zjc_ex, '../train_data/增减持/html', '6927.html')

if __name__ == "__main__":
    graphviz = GraphvizOutput()
    graphviz.output_file = 'basic.png'

    with PyCallGraph(output=graphviz):
        main()