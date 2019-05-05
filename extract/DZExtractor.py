# -*- coding: utf-8 -*-

import codecs
import json
import re

from docparser import HTMLParser
from utils import TextUtils
from ner import NERTagger


# 增减持记录
class DZRecord(object):
    def __init__(self, add_object, add_number, add_amount, lock_period, subscript_method):
        # 增发对象
        self.addObject = add_object
        # 增发数量
        self.addNumber = add_number
        # 增发金额
        self.addAmount = add_amount
        # 锁定期
        self.lockPeriod = lock_period
        # 认购方式
        self.subscriptMethod = subscript_method

    def __str__(self):
        return json.dumps(self.__dict__, ensure_ascii=False)

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
        if self.addNumber is not None:
            self.addNumber = self.normalize_num(self.addNumber)
        if self.addAmount is not None:
            self.addAmount = self.normalize_num(self.addAmount)
        if self.lockPeriod is not None:
            self.lockPeriod = self.normalize_num(self.lockPeriod)

    def to_result(self):
        '''
        用于输出各项值
        '''
        self.normalize()
        return "%s,%s,%s,%s,%s" % (
            self.addObject if self.addObject is not None else '',
            self.addNumber if self.addNumber is not None else '',
            self.addAmount if self.addAmount is not None else '',
            self.lockPeriod if self.lockPeriod is not None else '',
            self.subscriptMethod if self.subscriptMethod is not None else '')


# 增减持记录提取
class DZExtractor(object):

    def __init__(self, config_file_path, ner_model_dir_path, ner_blacklist_file_path):
        self.html_parser = HTMLParser.HTMLParser()
        self.config = None
        self.ner_tagger = NERTagger.NERTagger(ner_model_dir_path, ner_blacklist_file_path)
        #
        self.ner_dict = {}

        # 读取保存在 json 中的配置文件
        # 将读取结果保存在 self.table_dict_field_pattern_dict 中
        # 键：field_name
        # 值：TableDictFieldPattern 对象
        with codecs.open(config_file_path, encoding='utf-8', mode='r') as fp:
            self.config = json.loads(fp.read())
        self.table_dict_field_pattern_dict = {}
        for table_dict_field in self.config['table_dict']['fields']:
            field_name = table_dict_field['fieldName']
            if field_name is None:
                continue
            convert_method = table_dict_field['convertMethod']
            if convert_method is None:
                continue
            pattern = table_dict_field['pattern']
            if pattern is None:
                continue
            col_skip_pattern = None
            if 'colSkipPattern' in table_dict_field:
                col_skip_pattern = table_dict_field['colSkipPattern']
            row_skip_pattern = None
            if 'rowSkipPattern' in table_dict_field:
                row_skip_pattern = table_dict_field['rowSkipPattern']
            self.table_dict_field_pattern_dict[field_name] = \
                TableDictFieldPattern(field_name=field_name, convert_method=convert_method,
                                      pattern=pattern, col_skip_pattern=col_skip_pattern,
                                      row_skip_pattern=row_skip_pattern)

    def extract(self, html_file_path):
        '''
        对 html 文件进行解析
        '''
        # 1. 解析 Table Dict
        rs = []
        paragraphs = self.html_parser.parse_content(html_file_path)
        add_period, add_method = self.extract_pm(paragraphs)
        rs_paragraphs = self.extract_from_paragraphs(paragraphs)
        for table_dict in self.html_parser.parse_table(html_file_path):
            rs_table = self.extract_from_table_dict(table_dict)
            if len(rs_table) > 0:
                for rs_t in rs_table:
                    if rs_t.lockPeriod is None or len(rs_t.lockPeriod) < 1:
                        rs_t.lockPeriod = add_period
                    if rs_t.subscriptMethod is None or len(rs_t.subscriptMethod) < 1:
                        rs_t.subscriptMethod = add_method
                rs.extend(rs_table)
        # 2. 如果没有 Table Dict 则解析文本部分
        # if len(rs) <= 0:
        #     for rs_p in rs_paragraphs:
        #         if rs_p.lockPeriod is None or len(rs_p.lockPeriod) < 1:
        #             rs_p.lockPeriod = add_period
        #         if rs_p.subscriptMethod is None or len(rs_p.subscriptMethod) < 1:
        #             rs_p.subscriptMethod = add_method
        #     return rs_paragraphs
        # else:
        #     return rs
        for rs_p in rs_paragraphs:
            if rs_p.lockPeriod is None or len(rs_p.lockPeriod) < 1:
                rs_p.lockPeriod = add_period
            if rs_p.subscriptMethod is None or len(rs_p.subscriptMethod) < 1:
                rs_p.subscriptMethod = add_method
        rs.extend(rs_paragraphs)
        return rs


    def extract_from_table_dict(self, table_dict):
        '''
        尝试从表格中获取有效字段
        table_dict: HTML 解析得到的表格
        '''
        rs = []
        if table_dict is None or len(table_dict) <= 0:
            return rs
        row_length = len(table_dict)
        # field_col_dict：字典
        #   键：在表头中匹配到的 field
        #   值：对应的列数以及可能出现的单位信息
        field_col_dict = {}
        # 可以忽略的行对应的行数：集合
        skip_row_set = set()

        # 假定第一行是表头部分则尝试进行规则匹配这一列是哪个类型的字段
        # 必须满足 is_match_pattern is True and is_match_col_skip_pattern is False
        head_row = table_dict[0]
        col_length = len(head_row)
        # 遍历表格第一行 (表头) 的元素
        for i in range(col_length):
            text = head_row[i]
            # 尝试匹配 table_dict_field_pattern 中的各个模式
            for (field_name, table_dict_field_pattern) in self.table_dict_field_pattern_dict.items():
                # 匹配成功
                if table_dict_field_pattern.is_match_pattern(text) and \
                        not table_dict_field_pattern.is_match_col_skip_pattern(text):
                    if field_name not in field_col_dict:
                        field_col_dict[field_name] = (i, "")
                        if '%' in text:
                            field_col_dict[field_name] = (i, '%')
                        if '万' in text:
                            field_col_dict[field_name] = (i, '万')
                    # 逐行扫描这个字段的取值，如果满足 row_skip_pattern 则丢弃整行 row
                    for j in range(1, row_length):
                        try:
                            text = table_dict[j][i]
                            if table_dict_field_pattern.is_match_row_skip_pattern(text):
                                skip_row_set.add(j)
                        except KeyError:
                            pass
        # 没有扫描到有效的列
        if len(field_col_dict) <= 0:
            return rs

        # 遍历每个有效行，获取 record
        exit_flag = False
        for row_index in range(1, row_length):
            if row_index in skip_row_set:
                continue
            record = DZRecord(None, None, None, None, None)
            for (field_name, col_index) in field_col_dict.items():
                try:
                    text = table_dict[row_index][col_index[0]] + col_index[1]
                    if field_name == 'addObject':
                        record.addObject = self.table_dict_field_pattern_dict.get(field_name).convert(text)
                    elif field_name == 'addNumber':
                        record.addNumber = self.table_dict_field_pattern_dict.get(field_name).convert(text)
                    elif field_name == 'addAmount':
                        record.addAmount = self.table_dict_field_pattern_dict.get(field_name).convert(text)
                    elif field_name == 'lockPeriod':
                        record.lockPeriod = self.table_dict_field_pattern_dict.get(field_name).convert(text)
                    elif field_name == 'subsrciptMethod':
                        record.subscriptMethod = self.table_dict_field_pattern_dict.get(field_name).convert(text)
                    else:
                        pass
                except KeyError:
                    pass
            rs.append(record)
            if exit_flag:
                break

        # 返回结果
        return rs

    def extract_from_paragraphs(self, paragraphs):
        '''
        从多个段落中进行抽取
        '''
        self.ner_dict = {}  # clear dict
        addition_records = []
        record_list = []
        # 对各个段落进行抽取
        for para in paragraphs:
            addtion_records_para = self.extract_from_paragraph(para)
            addition_records += addtion_records_para
        for record in addition_records:
            record_list.append(record)
        return record_list

    def extract_from_paragraph(self, paragraph):
        '''
        从一个段落中进行抽取
        '''
        tag_res = self.ner_tagger.ner(paragraph, self.ner_dict)
        tagged_str = tag_res.get_tagged_str()
        # 抽取公司简称以及简称
        new_size = self.extract_object(tagged_str)
        if new_size > 0:
            tag_res = self.ner_tagger.ner(paragraph, self.ner_dict)
            tagged_str = tag_res.get_tagged_str()
        # 抽取变动记录，变动后记录
        addition_records = self.extract_record(tagged_str)
        return addition_records

    def extract_object(self, paragraph):
        '''
        抽取增发对象，保存在 ner_dict 中
        返回增加 ner_dict 中增加的条目数量
        extract_from_paragraph 子例程
        '''
        targets = re.finditer(
            r'(发行对象|企业名称|投资对象|<org>){1,2}(?P<obj>.{1,28}?)(</org>)?',
            paragraph)
        size_before = len(self.ner_dict)
        for target in targets:
            # 增发对象
            obj_name = target.group("obj")
            if '<' in obj_name or '>' in obj_name:
                obj_name = self.delete_and_modify(obj_name)
            if obj_name is not None:
                self.ner_dict[obj_name] = "Ni"
        return len(self.ner_dict) - size_before

    def extract_record(self, paragraph):
        '''
        用于抽取一个段落中的变动数量
        extract_from_paragraph 子例程
        '''
        records = []
        targets = re.finditer(r'(申购|认购|发行)(不超过|不少于|.{0,5})?<num>(?P<num>.*?)</num>股?',
                              paragraph)
        for target in targets:
            start_pos = target.start()

            # 增发数量
            add_num = target.group("num")

            # 查找对象
            pat_obj = re.compile(r'<org>(.*?)</org>')
            m_obj = pat_obj.findall(paragraph, 0, start_pos)
            add_obj = ""
            if m_obj is not None and len(m_obj) > 0:
                add_obj = m_obj[-1]
            else:
                pat_person = re.compile(r'<person>(.*?)</person>')
                m_person = pat_person.findall(paragraph, 0, start_pos)
                if m_person is not None and len(m_person) > 0:
                    add_obj = m_person[-1]
            # 没有查找到对象名称
            if add_obj is None or len(add_obj) == 0:
                continue

            # 查找金额
            pat_price = re.compile(r'(认缴|申购|认购|发行|资)?.{0,10}?(金额|资本|额)([:：为])?<num>(?P<price>.*?)</num>元?')
            m_price = pat_price.search(paragraph, start_pos)
            add_price = ""
            if m_price is not None:
                add_price = m_price.group("price")
            else:
                m_price = pat_price.findall(paragraph)
                if m_price is not None and len(m_price) > 0:
                    add_price = m_price[-1]

            # 查找锁定期
            pat_period = re.compile(r'自本次发行结束之日起(\s*)<num>(?P<period>.*?)</num>(\s*)个月内不得转让')
            m_period = pat_period.search(paragraph, start_pos)
            add_period = ""
            if m_period is not None:
                add_period = m_period.group("period")
            else:
                m_period = pat_period.findall(paragraph)
                if m_period is not None and len(m_period) > 0:
                    add_period = m_period[-1]

            # 查找方法
            pat_method = re.compile(r'以(?P<method>.{0,10})认购')
            m_method = pat_method.search(paragraph, start_pos)
            add_method = ""
            if m_method is not None:
                add_method = m_method.group("method")
            else:
                m_method = pat_method.findall(paragraph)
                if m_method is not None and len(m_method) > 0:
                    add_method = m_method[-1]

            # 成功抽取变动记录
            records.append(DZRecord(add_obj, add_num, add_price, add_period, add_method))
        return records

    def extract_pm(self, paragraphs):
        add_method = ""
        add_period = ""
        for paragraph in paragraphs:
            # 查找锁定期
            if add_period == "":
                pat_period = re.compile(r'自本次发行结束之日起(\s*)<num>(?P<period>.*?)</num>(\s*)个月内不得转让')
                m_period = pat_period.search(paragraph)
                if m_period is not None:
                    add_period = m_period.group("period")
                else:
                    m_period = pat_period.findall(paragraph)
                    if m_period is not None and len(m_period) > 0:
                        add_period = m_period[-1]

            # 查找方法
            if add_method == "":
                pat_method = re.compile(r'以(?P<method>.{0,10})认购')
                m_method = pat_method.search(paragraph)
                if m_method is not None:
                    add_method = m_method.group("method")
                else:
                    m_method = pat_method.findall(paragraph)
                    if m_method is not None and len(m_method) > 0:
                        add_method = m_method[-1]

        return add_period, add_method

    @staticmethod
    def delete_and_modify(name):
        '''
        去除 <...> 中的内容，extract_company_name 子例程
        '''
        new_name = ""
        state = 0
        for ch in name:
            if ch == '<':
                state = 1
            elif ch == '>':
                state = 0
            elif state != 1:
                new_name += ch
        return new_name


# 用于保存配置文件 field 中的一项内容
class TableDictFieldPattern(object):
    def __init__(self, field_name, convert_method, pattern, col_skip_pattern, row_skip_pattern):
        self.field_name = field_name
        self.convert_method = convert_method
        self.pattern = None
        if pattern is not None and len(pattern) > 0:
            self.pattern = re.compile(pattern)
        self.col_skip_pattern = None
        if col_skip_pattern is not None and len(col_skip_pattern) > 0:
            self.col_skip_pattern = re.compile(col_skip_pattern)
        self.row_skip_pattern = None
        if row_skip_pattern is not None and len(row_skip_pattern) > 0:
            self.row_skip_pattern = re.compile(row_skip_pattern)

    def is_match_pattern(self, text):
        '''
        检测 text 中是否能匹配 pattern
        '''
        if self.pattern is None:
            return False
        match = self.pattern.search(text)
        return True if match else False

    def is_match_col_skip_pattern(self, text):
        '''
        检测 text 中是否能匹配 col_skip_pattern
        '''
        if self.col_skip_pattern is None:
            return False
        match = self.col_skip_pattern.search(text)
        return True if match else False

    def is_match_row_skip_pattern(self, text):
        '''
        检测 text 中是否能匹配 row_skip_pattern
        '''
        if self.row_skip_pattern is None:
            return False
        match = self.row_skip_pattern.search(text)
        return True if match else False

    def get_field_name(self):
        return self.field_name

    def convert(self, text):
        '''
        根据 convert_method 对 text 进行转换
        '''
        if self.convert_method is None:
            return self.default_convert(text)
        elif self.convert_method == 'getStringFromText':
            return self.get_string_from_text(text)
        elif self.convert_method == 'getLongFromText':
            return self.get_long_from_text(text)
        else:
            return self.default_convert(text)

    # 各类转换方法，供 convert 调用
    @staticmethod
    def default_convert(text):
        return text

    @staticmethod
    def get_string_from_text(text):
        return text

    @staticmethod
    def get_long_from_text(text):
        return TextUtils.remove_comma_in_number(text)
