# -*- coding: utf-8 -*-

import codecs
import json
import re
import os

from docparser import HTMLParser
from utils import TextUtils
from ner import NERTagger


# 重大合同记录
class ZengJianChiRecord(object):
    
    def __init__(self, party_A, party_B, project_name, contract_name, max_amount, min_amount, consortium):
        # 甲方 -- string
        self.party_A = party_A
        # 乙方 -- string
        self.party_B = party_B
        # 项目名称 -- string
        self.project_name = project_name
        # 合同名称 -- string
        self.contract_name = contract_name
        # 合同金额上限 -- double
        self.max_amount = max_amount
        # 合同金额下限 -- double
        self.min_amount = min_amount
        # 联合体成员 -- list of strings
        self.consortium = consortium

    @staticmethod
    def normalize_finish_date(text):
        '''
        将结束日期转换为标准格式
        normalize 子例程
        '''
        pattern = re.compile(r'(\d\d\d\d)[-.年](\d{1,2})[-.月](\d{1,2})日?')
        match = pattern.search(text)
        if match:
            if len(match.groups()) == 3:
                year = int(match.groups()[0])
                month = int(match.groups()[1])
                day = int(match.groups()[2])
                return '%d-%02d-%02d' % (year, month, day)
        return text

    @staticmethod
    def normalize_num(text):
        '''
        将数字转换为标准格式
        normalize 子例程
        '''
        coeff = 1.0
        if '亿' in text:
            coeff *= 100000000
        if '万' in text:
            coeff *= 10000
        if '千' in text or '仟' in text:
            coeff *= 1000
        if '百' in text or '佰' in text:
            coeff *= 100
        if '%' in text:
            coeff *= 0.01
        try:
            number = float(TextUtils.extract_number(text))
            number_text = '%.4f' % (number * coeff)
            if '.' in number_text:
                idx = len(number_text)
                while idx > 1 and number_text[idx - 1] == '0':
                    idx -= 1
                if number_text[idx - 1] == '.':
                    number_text = number_text[:idx - 1]
                else:
                    number_text = number_text[:idx]
            return number_text
        except:
            return text

    def normalize(self):
        '''
        将各项值规范化
        '''
        if self.finishDate is not None:
            self.finishDate = self.normalize_finish_date(self.finishDate)
        if self.shareNum is not None:
            self.shareNum = self.normalize_num(self.shareNum)
        if self.shareNumAfterChg is not None:
            self.shareNumAfterChg = self.normalize_num(self.shareNumAfterChg)
        if self.sharePcntAfterChg is not None:
            self.sharePcntAfterChg = self.normalize_num(self.sharePcntAfterChg)

    def to_result(self):
        '''
        用于输出各项值
        '''
        self.normalize()
        return "%s,%s,%s,%s,%s,%s,%s" % (
            self.shareholderFullName if self.shareholderFullName is not None else '',
            self.shareholderShortName if self.shareholderShortName is not None else '',
            self.finishDate if self.finishDate is not None else '',
            self.sharePrice if self.sharePrice is not None else '',
            self.shareNum if self.shareNum is not None else '',
            self.shareNumAfterChg if self.shareNumAfterChg is not None else '',
            self.sharePcntAfterChg if self.sharePcntAfterChg is not None else '')


# 增减持记录提取
class Contract_Extractor(object):

    def __init__(self, ner_model_dir, ner_blacklist_file_path):
        self.html_parser = HTMLParser.HTMLParser()
        self.ner_tagger = NERTagger.NERTagger(ner_model_dir, ner_blacklist_file_path)
    
    def extract(self, html_path):
        paragraphs = self.html_parser.parse_content(html_path)
        tagged_paragraphs = []
        for paragraph in paragraphs:
            ner_obj = self.ner_tagger.ner(paragraph, {})
            # print(ner_obj.get_tagged_str())
            tagged_paragraphs.append(ner_obj.get_tagged_str())
        # partyB = self.extract_partyB(tagged_paragraphs)
        # return partyB
        # partyA_candidates = self.extract_partyA(tagged_paragraphs)
        # return partyA_candidates
        project_names = self.extract_project_name(tagged_paragraphs)
        return project_names


    def extract_partyB(self, tagged_paragraphs):
        '''
        提取乙方名称
        一般来说，文件中第一个出现的组织名就是乙方
        组织名一般由 <org> ... </org> 围成
        不过组织名可能跟前面的公告编号黏在一起，需要去除这些编号
        没有找到组织名时，返回 'null'
        '''
        partyB_pattern = re.compile(r'(<org>)(?P<partyB>.{1,28}?)(</org>)')
        for text in tagged_paragraphs:
            search_obj = partyB_pattern.search(text)
            if search_obj:
                partyB_name = search_obj.group('partyB')
                return self.remove_number_in_name(partyB_name)
        return 'null'

    def remove_number_in_name(self, party_name):
        '''
        主要用于去除乙方名称中出现的公告编号
        '''
        num_pattern = re.compile(r'\d*([-]\d*)+')
        search_obj = num_pattern.search(party_name)
        if search_obj:
            return(party_name[search_obj.end():])
        else:
            return(party_name)
    
    def extract_partyA(self, tagged_paragraphs):
        partyA_candidates = []
        '''
        partyA_pattern = re.compile(r'(与|和)(.*)(<org>)(?P<partyA>.{1,50}?)(</org>)(.*)(签订|签署)')
        for text in tagged_paragraphs:
            match_objs = partyA_pattern.finditer(text)
            for match_obj in match_objs:
                partyA_name = match_obj.group('partyA')
                partyA_candidates.append(partyA_name)

        partyA_pattern = re.compile(r'(收到|接到)(<org>)?(?P<partyA>.{1,28}?)(</org>)?(发出|发来)')
        for text in tagged_paragraphs:
            match_objs = partyA_pattern.finditer(text)
            for match_obj in match_objs:
                partyA_name = match_obj.group('partyA')
                partyA_candidates.append(partyA_name)
        '''
        partyA_pattern = re.compile(r'采购人|甲方|买方')
        for text in tagged_paragraphs:
            match_objs = partyA_pattern.finditer(text)
            for match_obj in match_objs:
                partyA_name = match_obj.group()
                partyA_candidates.append(partyA_name)
        return partyA_candidates

    def extract_project_name(self, tagged_paragraphs):
        project_names = []

        proj_name_pattern = re.compile(r'[《](?P<proj_name>.{1,30}项目.{1,20})[》]')
        for text in tagged_paragraphs:
            match_objs = proj_name_pattern.finditer(text)
            for match_obj in match_objs:
                proj_name = match_obj.group('proj_name')
                project_names.append(proj_name)

        proj_name_pattern = re.compile(r'[“](?P<proj_name>.{1,30}项目.{1,20})[”]')
        for text in tagged_paragraphs:
            match_objs = proj_name_pattern.finditer(text)
            for match_obj in match_objs:
                proj_name = match_obj.group('proj_name')
                project_names.append(proj_name)

        return project_names
    
    def extract_contract_name(self, tagged_paragraphs):
        contract_names = []

        contract_pattern = re.compile(r'[《](?P<contract_name>.{1,30}合同)[》]')
        for text in tagged_paragraphs:
            match_objs = contract_pattern.finditer(text)
            for match_obj in match_objs:
                contract_name = match_obj.group('contract_name')
                contract_names.append(contract_name)

        return contract_names
    
    

if __name__ == '__main__':
    ner_model_dir = 'E:/WorkBench/Courses/Big-Data/Proj2-Finance/ltp_data_v3.4.0'
    ner_blacklist_file_path = 'config/ner_com_blacklist.txt'
    html_dir_path = '../train_data/重大合同/html'
    contract_extractor = Contract_Extractor(ner_model_dir, ner_blacklist_file_path)

    op = 3

    if op == 1:
        res_path = './results/Contract_partyA.csv'
        with codecs.open(res_path, 'w', encoding = 'utf-8') as f:
            f.write('id,party_A\n')
            null_count = 0
            for html_id in os.listdir(html_dir_path):
                partyA_candidates = contract_extractor.extract(os.path.join(html_dir_path, html_id))
                if len(partyA_candidates) == 0:
                    f.write(html_id[:-5] + ',null\n')
                    null_count += 1
                else:
                    for partyA in partyA_candidates:
                        f.write(html_id[:-5] + ',' + partyA + '\n')
            print(null_count)
    elif op == 2:
        res_path = './results/Contract_partyB.csv'
        with codecs.open(res_path, 'w', encoding = 'utf-8') as f:
            f.write('id,party_B\n')
            null_count = 0
            for html_id in os.listdir(html_dir_path):
                partyB = contract_extractor.extract(os.path.join(html_dir_path, html_id))
                f.write(html_id[:-5] + ',' + partyB + '\n')
                if partyB == 'null':
                    null_count += 1
            print(null_count)
    elif op == 3:
        res_path = './results/Contract_proj_name.csv'
        with codecs.open(res_path, 'w', encoding = 'utf-8') as f:
            f.write('id,proj_name\n')
            null_count = 0
            for html_id in os.listdir(html_dir_path):
                project_names = contract_extractor.extract(os.path.join(html_dir_path, html_id))
                if len(project_names) == 0:
                    f.write(html_id[:-5] + ',null\n')
                    null_count += 1
                else:
                    for proj_name in project_names:
                        f.write(html_id[:-5] + ',' + proj_name + '\n')
            print(null_count)
    else:
        res = contract_extractor.extract('../train_data/重大合同/html/1122337.html')
        print(res)