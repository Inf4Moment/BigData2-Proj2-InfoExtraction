# -*- coding: utf-8 -*-

import codecs
import json
import re
import os

from docparser import HTMLParser
from utils import TextUtils
from ner import NERTagger


# 重大合同记录
class Contract_Record(object):
    
    def __init__(self, partyA, partyB, project_name, contract_name, amount):
        '''
        初始化以及标准化
        '''
        # 甲方 -- string
        self.partyA = partyA
        # 乙方 -- string
        self.partyB = partyB
        # 项目名称 -- string
        self.project_name = project_name
        # 合同名称 -- string
        self.contract_name = contract_name
        # 合同金额上限 -- double
        # 合同金额下限 -- double
        normalized_amount = self.normalize_num(amount) 
        self.max_amount = normalized_amount
        self.min_amount = normalized_amount

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

    def to_result(self):
        '''
        用于输出各项值
        '''
        return "%s,%s,%s,%s,%s,%s," % (self.partyA, self.partyB, self.project_name, self.contract_name, self.max_amount, self.min_amount)


# 增减持记录提取
class Contract_Extractor(object):

    def __init__(self, ner_model_dir, ner_blacklist_file_path):
        '''
        初始化
        '''
        self.html_parser = HTMLParser.HTMLParser()
        self.ner_tagger = NERTagger.NERTagger(ner_model_dir, ner_blacklist_file_path)
    
    # 主例程
    def extract(self, html_path):
        '''
        提取记录
        '''
        # 解析 html
        paragraphs = self.html_parser.parse_content(html_path)
        tagged_paragraphs = []
        for paragraph in paragraphs:
            # ner 打标签
            ner_obj = self.ner_tagger.ner(paragraph, {})
            # print(ner_obj.get_tagged_str())
            # print("*************")
            tagged_paragraphs.append(ner_obj.get_tagged_str())

        # 抽取各项内容
        partyA = self.extract_partyA(tagged_paragraphs)
        partyB = self.extract_partyB(tagged_paragraphs)
        project_name = self.extract_project_name(tagged_paragraphs)
        contract_name = self.extract_contract_name(tagged_paragraphs)
        amount = self.extract_amount(tagged_paragraphs)

        # 组合得到的抽取内容
        contract_record = Contract_Record(partyA, partyB, project_name, contract_name, amount)
        return contract_record.to_result()

    # 子例程
    def extract_partyA(self, tagged_paragraphs):
        '''
        提取甲方名称
        '''
        partyA_candidates = []
        
        partyA_pattern = re.compile(r'(与|和)(.*)(<org>)(?P<partyA>.{1,50}?)(</org>)(.*)(签订|签署)')
        for text in tagged_paragraphs:
            match_objs = partyA_pattern.finditer(text)
            for match_obj in match_objs:
                partyA_name = match_obj.group('partyA')
                partyA_candidates.append(partyA_name)
        if len(partyA_candidates) > 0:
            return self.select_partyA(partyA_candidates)

        partyA_pattern = re.compile(r'(收到|接到)(<org>)?(?P<partyA>.{1,28}?)(</org>)?(发出|发来)')
        for text in tagged_paragraphs:
            match_objs = partyA_pattern.finditer(text)
            for match_obj in match_objs:
                partyA_name = match_obj.group('partyA')
                pos = partyA_name.find('</org>')
                if pos > -1:
                    partyA_name = partyA_name[:pos]
                pos = partyA_name.find('<org>')
                if pos > -1:
                    partyA_name = partyA_name[pos+5:]
                partyA_candidates.append(partyA_name)
        if len(partyA_candidates) > 0:
            return self.select_partyA(partyA_candidates)

        return ''
    
    def extract_partyB(self, tagged_paragraphs):
        '''
        提取乙方名称
        一般来说，文件中第一个出现的组织名就是乙方
        组织名一般由 <org> ... </org> 围成
        不过组织名可能跟前面的公告编号黏在一起，需要去除这些编号
        没有找到组织名时，返回 ''
        '''
        partyB_pattern = re.compile(r'(<org>)(?P<partyB>.{1,28}?)(</org>)')
        for text in tagged_paragraphs:
            search_obj = partyB_pattern.search(text)
            if search_obj:
                partyB_name = search_obj.group('partyB')
                return self.remove_number_in_name(partyB_name)
        return ''

    def extract_project_name(self, tagged_paragraphs):
        '''
        抽取项目名称
        '''
        proj_name_pattern = re.compile(r'《(?P<proj_name>[^，。）》]{1,100}?(标|标段|项目|工程))[^，。）》]{1,10}》')
        for text in tagged_paragraphs:
            search_obj = proj_name_pattern.search(text)
            if search_obj:
                proj_name = self.remove_tag_in_name(search_obj.group('proj_name'))
                if len(proj_name) > 10:
                    return proj_name
        
        proj_name_pattern = re.compile(r'“(?P<proj_name>[^，。）》]{1,100}?(标|标段|项目|工程))[^，。）》]{1,10}”')
        for text in tagged_paragraphs:
            search_obj = proj_name_pattern.search(text)
            if search_obj:
                proj_name = self.remove_tag_in_name(search_obj.group('proj_name'))
                if len(proj_name) > 10:
                    return proj_name

        proj_name_pattern = re.compile(r'(中标项目|项目名称)([：“])(?P<proj_name>[^，。）》]{1,100}?)([。”）（])')
        for text in tagged_paragraphs:
            search_obj = proj_name_pattern.search(text)
            if search_obj:
                proj_name = self.remove_tag_in_name(search_obj.group('proj_name'))
                if len(proj_name) > 10:
                    return proj_name

        proj_name_pattern = re.compile(r'(中标)(?P<proj_name>[^，。）》]{1,100}?标段[）]?)')
        for text in tagged_paragraphs:
            search_obj = proj_name_pattern.search(text)
            if search_obj:
                proj_name = self.remove_tag_in_name(search_obj.group('proj_name'))
                pos = proj_name.find('中标')
                if pos > -1:
                    return proj_name[pos+2:]
                if len(proj_name) > 10:
                    return proj_name
        
        proj_name_pattern = re.compile(r'([为])(?P<proj_name>[^，。）》]{1,60}?(标|标段|项目))')
        for text in tagged_paragraphs:
            search_obj = proj_name_pattern.search(text)
            if search_obj:
                proj_name = self.remove_tag_in_name(search_obj.group('proj_name'))
                if len(proj_name) > 10:
                    return proj_name

        return ''
    
    def extract_contract_name(self, tagged_paragraphs):
        '''
        抽取合同名称
        '''
        contract_pattern = re.compile(r'(合同名称)([：“])(?P<contract_name>.{1,60}?)([。”）（])')
        contract_name = self.extract_contract_name_pattern(tagged_paragraphs, contract_pattern)
        if len(contract_name) > 0:
            return contract_name
        
        contract_pattern = re.compile(r'(签订|签署)(了)?(?P<contract_name>.{1,60}?合同)')
        contract_name = self.extract_contract_name_pattern(tagged_paragraphs, contract_pattern)
        if len(contract_name) > 0:
            return contract_name

        contract_pattern = re.compile(r'《(?P<contract_name>.{1,60}?合同)》')
        contract_name = self.extract_contract_name_pattern(tagged_paragraphs, contract_pattern)
        if len(contract_name) > 0:
            return contract_name

        contract_pattern = re.compile(r'“(?P<contract_name>.{1,60}?合同)”')
        contract_name = self.extract_contract_name_pattern(tagged_paragraphs, contract_pattern)
        if len(contract_name) > 0:
            return contract_name

        return ''
    
    def extract_contract_name_pattern(self, tagged_paragraphs, contract_pattern):
        for text in tagged_paragraphs:
            search_obj = contract_pattern.search(text)
            if search_obj:
                contract_name = search_obj.group('contract_name')
                if len(contract_name) <= 6:
                    continue
                if contract_name.find('，') > -1 or contract_name.find('。') > -1 or contract_name.find('、') > -1:
                    continue                    
                else:
                    pos = contract_name.find("《")
                    if pos > -1:
                        contract_name = contract_name[pos+1:]
                    return self.remove_tag_in_name(contract_name)
        return ''

    def extract_amount(self, tagged_paragraphs):
        amount_pattern = re.compile(r'<num>(?P<contract_amount>.*?)</num>元')
        for text in tagged_paragraphs:
            match_obj = amount_pattern.search(text)
            if match_obj:
                contract_amount = match_obj.group('contract_amount')
                return self.clean_amount(contract_amount)
        return ''

    # 辅助例程
    def select_partyA(self, partyA_candidates):
        # 只有一个甲方名称
        if len(partyA_candidates) == 1:
            return partyA_candidates[0]
        # 有多个甲方名称，进行计数
        partyA_count = {}
        for partyA in partyA_candidates:
            if partyA not in partyA_count:
                partyA_count[partyA] = 1
            else:
                partyA_count[partyA] += 1
        # 出现的名称重复
        if len(partyA_count) == 1:
            return partyA_candidates[0]
        # 有不同的名称
        else:
            partyA_list = sorted(partyA_count.items(), key=lambda r: r[1])
            if(partyA_list[-1][1] == partyA_list[-2][1]):
                name1 = partyA_list[-1][0]
                name2 = partyA_list[-2][0]
                if name1.find(name2) > -1:
                    return name2
                elif name2.find(name1) > -1:
                    return name1
                elif len(name1) > len(name2):
                    return name2
                else:
                    return name1
            else:
                return partyA_list[-1][0] 

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
    
    def remove_tag_in_name(self, proj_name):
        new_name = ""
        state = 0
        for ch in proj_name:
            if ch == '<':
                state = 1
            elif ch == '>':
                state = 0
            elif state != 1:
                new_name += ch
        return new_name

    def clean_amount(self, contract_amount):
        flag = False
        for i in range(len(contract_amount)-1, -1, -1):
            if contract_amount[i] == '>':
                flag = True
                break
        if flag:
            return contract_amount[i+1:]
        else:
            return contract_amount


# 测试
if __name__ == '__main__':
    ner_model_dir = 'E:/WorkBench/Courses/Big-Data/Proj2-Finance/ltp_data_v3.4.0'
    ner_blacklist_file_path = 'config/ner_com_blacklist.txt'
    html_dir_path = '../hetong/重大合同/html'
    contract_extractor = Contract_Extractor(ner_model_dir, ner_blacklist_file_path)

    res_path = './results/Contract_Test.csv'

    with codecs.open(res_path, 'w', encoding = 'utf-8') as f:
        f.write('公告id,甲方,乙方,项目名称,合同名称,合同金额上限,合同金额下限,联合体成员\n')
        for html_id in os.listdir(html_dir_path):
            record = contract_extractor.extract(os.path.join(html_dir_path, html_id))
            f.write(html_id[:-5] + ',' + record + '\n')

    '''
    op = 0

    if op == 1:
        res_path = './results/Contract_partyA.csv'
        with codecs.open(res_path, 'w', encoding = 'utf-8') as f:
            f.write('id,party_A\n')
            null_count = 0
            for html_id in os.listdir(html_dir_path):
                partyA = contract_extractor.extract(os.path.join(html_dir_path, html_id))
                f.write(html_id[:-5] + ',' + partyA + '\n')
                if partyA == 'null':     
                    null_count += 1
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
            f.write('id,party_A\n')
            null_count = 0
            for html_id in os.listdir(html_dir_path):
                proj_name = contract_extractor.extract(os.path.join(html_dir_path, html_id))
                f.write(html_id[:-5] + ',' + proj_name + '\n')
                if proj_name == 'null':     
                    null_count += 1
            print(null_count)
    elif op == 4:
        res_path = './results/Contract_amount.csv'
        with codecs.open(res_path, 'w', encoding = 'utf-8') as f:
            f.write('id,amount\n')
            null_count = 0
            for html_id in os.listdir(html_dir_path):
                amount = contract_extractor.extract(os.path.join(html_dir_path, html_id))
                f.write(html_id[:-5] + ',' + amount + '\n')
                if amount == 'null':     
                    null_count += 1
            print(null_count)
    elif op == 5:
        res_path = './results/Contract_name.csv'
        with codecs.open(res_path, 'w', encoding = 'utf-8') as f:
            f.write('id,contract_name\n')
            null_count = 0
            for html_id in os.listdir(html_dir_path):
                contract_name = contract_extractor.extract(os.path.join(html_dir_path, html_id))
                f.write(html_id[:-5] + ',' + contract_name + '\n')
                if contract_name == 'null':     
                    null_count += 1
            print(null_count)
    else:
        res = contract_extractor.extract('../hetong/重大合同/html/713915.html')
        print(res)
    '''