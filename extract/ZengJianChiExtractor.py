# -*- coding: utf-8 -*-

import codecs
import json
import re

from docparser import HTMLParser
from utils import TextUtils
from ner import NERTagger

# 增减持记录
class ZengJianChiRecord(object):
    def __init__(self, shareholder_full_name, shareholder_short_name, finish_date,
                 share_price, share_num, share_num_after_chg, share_pcnt_after_chg):
        # 股东全称
        self.shareholderFullName = shareholder_full_name
        # 股东简称
        self.shareholderShortName = shareholder_short_name
        # 结束日期
        self.finishDate = finish_date
        # 增减持股价
        self.sharePrice = share_price
        # 增减持股数
        self.shareNum = share_num
        # 增减持变动后股数
        self.shareNumAfterChg = share_num_after_chg
        # 增减持变动后持股比例
        self.sharePcntAfterChg = share_pcnt_after_chg

    def __str__(self):
        return json.dumps(self.__dict__, ensure_ascii=False)

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
class ZengJianChiExtractor(object):

    def __init__(self, config_file_path, ner_model_dir_path, ner_blacklist_file_path):
        self.html_parser = HTMLParser.HTMLParser()
        self.config = None
        self.ner_tagger = NERTagger.NERTagger(ner_model_dir_path, ner_blacklist_file_path)
        # 公司简称对应公司全称
        self.com_abbr_dict = {}
        # 公司全称对应公司简称
        self.com_full_dict = {}
        # 
        self.com_abbr_ner_dict = {}

        # 读取保存在 json 中的增减持配置文件
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
            record = ZengJianChiRecord(None, None, None, None, None, None, None)
            for (field_name, col_index) in field_col_dict.items():
                try:
                    text = table_dict[row_index][col_index[0]] + col_index[1]
                    if field_name == 'shareholderFullName':
                        record.shareholderFullName = self.table_dict_field_pattern_dict.get(field_name).convert(text)
                    elif field_name == 'finishDate':
                        record.finishDate = self.table_dict_field_pattern_dict.get(field_name).convert(text)
                    elif field_name == 'sharePrice':
                        record.sharePrice = self.table_dict_field_pattern_dict.get(field_name).convert(text)
                    elif field_name == 'shareNum':
                        record.shareNum = self.table_dict_field_pattern_dict.get(field_name).convert(text)
                    elif field_name == 'shareNumAfterChg':
                        record.shareNumAfterChg = self.table_dict_field_pattern_dict.get(field_name).convert(text)
                    elif field_name == 'sharePcntAfterChg':
                        record.sharePcntAfterChg = self.table_dict_field_pattern_dict.get(field_name).convert(text)
                        exit_flag = True
                        break
                    else:
                        pass
                except KeyError:
                    pass
            rs.append(record)
            if exit_flag:
                break
        
        # 返回结果
        return rs

    def extract_from_paragraph(self, paragraph):
        '''
        从一个段落中进行抽取
        '''
        tag_res = self.ner_tagger.ner(paragraph, self.com_abbr_ner_dict)
        tagged_str = tag_res.get_tagged_str()
        # 抽取公司简称以及简称
        new_size = self.extract_company_name(tagged_str)
        if new_size > 0:
            tag_res = self.ner_tagger.ner(paragraph, self.com_abbr_ner_dict)
            tagged_str = tag_res.get_tagged_str()
        # 抽取变动记录，变动后记录
        change_records = self.extract_change(tagged_str)
        change_after_records = self.extract_change_after(tagged_str)
        return change_records, change_after_records

    def extract_company_name(self, paragraph):
        '''
        抽取股东名称以及简称，保存在 com_abbr_ner_dict 中
        返回增加 com_abbr_ner_dict 中增加的条目数量
        extract_from_paragraph 子例程
        '''
        targets = re.finditer(
            r'(股东|<org>){1,2}(?P<com>.{1,28}?)(</org>)?[(（].{0,5}?简称:?("|“|<org>)?(?P<com_abbr>.{2,20}?)("|”|</org>)?[)）]',
            paragraph)
        size_before = len(self.com_abbr_ner_dict)
        for target in targets:
            # 股东简称
            com_abbr = target.group("com_abbr")
            # 股东名称
            com_name = target.group("com")
            if '<' in com_abbr or '>' in com_abbr:
                com_abbr = self.delete_and_modify(com_abbr)
            if '<' in com_name or '>' in com_name:
                com_name = self.delete_and_modify(com_name)
            if com_abbr is not None and com_name is not None:
                self.com_abbr_dict[com_abbr] = com_name
                self.com_full_dict[com_name] = com_abbr
                self.com_abbr_ner_dict[com_abbr] = "Ni"
                self.com_abbr_ner_dict[com_name] = "Ni"
        return len(self.com_abbr_ner_dict) - size_before

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

    def extract_change(self, paragraph):
        '''
        用于抽取一个段落中的变动数量
        extract_from_paragraph 子例程
        '''
        records = []
        targets = re.finditer(r'(出售|减持|增持|买入)了?[^，。.,:：;!?？（）()“”"<>]*?(股票|股份|(<org>([^.。,，<>]*?)</org>))[^.。,，《》]{0,30}?<num>(?P<share_num>.{1,20}?)</num>股?',
                              paragraph)
        pat_dates = [k for k in re.finditer(r'<date>(.*?)</date>', paragraph)]
        for target in targets:
            # 变动数量
            share_num = target.group("share_num")
            start_pos = target.start()
            # 查找公司
            pat_com = re.compile(r'<org>(.*?)</org>')
            m_com = pat_com.findall(paragraph, 0, start_pos)
            shareholder = ""
            if m_com is not None and len(m_com) > 0:
                shareholder = m_com[-1]
            else:
                pat_person = re.compile(r'<person>(.*?)</person>')
                m_person = pat_person.findall(paragraph, 0, start_pos)
                if m_person is not None and len(m_person) > 0:
                    shareholder = m_person[-1]
            # 没有查找到股东名称
            if shareholder is None or len(shareholder) == 0:
                continue
            # 归一化公司全称简称
            full_name, short_name = self.get_shareholder(shareholder)
            # 查找日期
            period_find = re.compile(r'。|累计|合计')
            last_date = None
            change_date = ""
            for pat_date in pat_dates:
                # 循环至变动数量之前的最后一个时间段名词
                if pat_date.end() < start_pos:
                    last_date = pat_date
                else:
                    break
            if last_date is not None:
                tmp_end = last_date.end()
                # 日期与变动数量之间
                #   存在句号：说明日期与变动数量很可能没有联系
                #   存在 "累计" 等词语：
                if len(period_find.findall(paragraph, tmp_end, start_pos)) <= 0:
                    change_date = last_date.group().split('>')[1].split('<')[0]
            # 查找变动价格
            pat_price = re.compile(r'(均价|(平均)?(增持|减持|成交)?(价格|股价))([:：为])?<num>(?P<share_price>.*?)</num>')
            m_price = pat_price.search(paragraph, start_pos)
            share_price = ""
            if m_price is not None:
                share_price = m_price.group("share_price")
            # 成功抽取变动记录
            records.append(ZengJianChiRecord(full_name, short_name, change_date, share_price, share_num, "", ""))
        return records

    def extract_change_after(self, paragraph):
        '''
        用于抽取变动后持股数和变动后持股比例
        extract_from_paragraph 子例程
        '''
        records = []
        targets = re.finditer(r'(增持(计划实施)?后|减持(计划实施)?后|变动后)[^。;；]*?持有.{0,30}?<num>(?P<share_num_after>.*?)</num>(股|万股|百万股|亿股)?',
                              paragraph)
        for target in targets:
            share_num_after = target.group("share_num_after")
            start_pos = target.start()
            end_pos = target.end()
            # 查找公司
            pat_com = re.compile(r'<org>(.*?)</org>')
            m_com = pat_com.findall(paragraph, 0, end_pos)
            shareholder = ""
            if m_com is not None and len(m_com) > 0:
                shareholder = m_com[-1]
            else:
                pat_person = re.compile(r'<person>(.*?)</person>')
                m_person = pat_person.findall(paragraph, 0, end_pos)
                if m_person is not None and len(m_person) > 0:
                    shareholder = m_person[-1]
            # 没有查找到股东名称
            if shareholder is None or len(shareholder) == 0:
                continue
            # 归一化公司全称简称
            full_name, short_name = self.get_shareholder(shareholder)
            # 查找变动后持股比例
            pat_percent_after = re.compile(r'<percent>(?P<share_percent>.*?)</percent>')
            m_percent_after = pat_percent_after.search(paragraph, start_pos)
            share_percent_after = ""
            if m_percent_after is not None:
                share_percent_after = m_percent_after.group("share_percent")
            # 成功抽取变动后记录
            records.append(ZengJianChiRecord(full_name, short_name, "", "", "", share_num_after, share_percent_after))
        return records

    def get_shareholder(self, shareholder):
        '''
        归一化公司全称简称
        extract_change, extract_change_after 子例程
        '''
        if shareholder in self.com_full_dict:
            return shareholder, self.com_full_dict.get(shareholder, "")
        if shareholder in self.com_abbr_dict:
            return self.com_abbr_dict.get(shareholder, ""), shareholder
        # 股东为自然人时不需要简称
        return shareholder, ""

    def extract_from_paragraphs(self, paragraphs):
        '''
        从多个段落中进行抽取
        '''
        self.clear_com_abbr_dict()
        change_records = []
        change_after_records = []
        record_list = []
        # 对各个段落进行抽取
        for para in paragraphs:
            change_records_para, change_after_records_para = self.extract_from_paragraph(para)
            change_records += change_records_para
            change_after_records += change_after_records_para
        # 保持各条记录中的公司全称一致
        self.sort_and_modify(change_records, change_after_records)
        # 对截止日期相同的记录进行去重
        change_records = sorted(change_records, key=lambda r: r.finishDate)
        limit = len(change_records) - 1
        i = 0
        while i < limit:
            if change_records[i].finishDate == change_records[i+1].finishDate:
                del change_records[i]
                limit -= 1
            else:
                i += 1
        # 合并变动记录，变动后记录
        self.merge_record(change_records, change_after_records)
        for record in change_records:
            record_list.append(record)
        return record_list

    def clear_com_abbr_dict(self):
        self.com_abbr_dict = {}
        self.com_full_dict = {}
        self.com_abbr_ner_dict = {}

    def sort_and_modify(self, records, change_records):
        '''
        保持各条记录中的公司全称一致
        extract_from_paragraphs 子例程
        '''
        shareholder = {}
        for record in records:
            full_name = record.shareholderFullName
            if full_name in self.com_full_dict:
                if full_name not in shareholder:
                    shareholder[full_name] = 1
                else:
                    shareholder[full_name] += 1
        # records 中的股东全称一致
        if len(shareholder) == 1:
            for change_record in change_records:
                change_record.shareholderFullName = records[0].shareholderFullName
        # 有多个股东名称，需要处理冲突
        elif len(shareholder) > 1:
            shareholder_list = sorted(shareholder.items(), key=lambda r: r[1])
            # 两个出现次数最多的公司出现次数一样
            if shareholder_list[-1][1] == shareholder_list[-2][1]:
                return
            else:
                real_shareholder = shareholder_list[-1][0]
            real_short = self.com_full_dict[real_shareholder]
            # 替换 record, change_record 中的公司名称
            for record in records:
                record.shareholderFullName = real_shareholder
                record.shareholderShortName = real_short
            for change_record in change_records:
                change_record.shareholderFullName = real_shareholder

    def merge_record(self, change_records, change_after_records):
        '''
        合并变动记录，变动后记录
        extract_from_paragraphs 子例程
        '''
        if len(change_records) == 0 or len(change_after_records) == 0:
            return
        last_record = None
        for record in change_records:
            if last_record is not None and record.shareholderFullName != last_record.shareholderFullName:
                self.merge_change_after_info(last_record, change_after_records)
            last_record = record
        self.merge_change_after_info(last_record, change_after_records)

    @staticmethod
    def merge_change_after_info(change_record, change_after_records):
        '''
        增加 change_record 中的变动后信息
        merge_record 子例程
        '''
        for record in change_after_records:
            if record.shareholderFullName == change_record.shareholderFullName:
                change_record.shareNumAfterChg = record.shareNumAfterChg
                change_record.sharePcntAfterChg = record.sharePcntAfterChg

    def extract(self, html_file_path):
        '''
        对 html 文件进行解析
        '''
        # 1. 解析 Table Dict
        rs = []
        paragraphs = self.html_parser.parse_content(html_file_path)
        rs_paragraphs = self.extract_from_paragraphs(paragraphs)
        for table_dict in self.html_parser.parse_table(html_file_path):
            rs_table = self.extract_from_table_dict(table_dict)
            if len(rs_table) > 0:
                # 第二个有效表格一定是增减持之后的数量和占比
                if len(rs) > 0:
                    self.merge_record(rs, rs_table)
                    break
                else:
                    rs.extend(rs_table)
        # 2. 如果没有 Table Dict 则解析文本部分
        if len(rs) <= 0:
            return rs_paragraphs
        else:
            for record in rs:
                full_company_name, abbr_company_name = self.get_shareholder(record.shareholderFullName)
                record.shareholderFullName = full_company_name
                record.shareholderShortName = abbr_company_name
        return rs


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
        elif self.convert_method == 'getDateFromText':
            return self.get_date_from_text(text)
        elif self.convert_method == 'getLongFromText':
            return self.get_long_from_text(text)
        elif self.convert_method == 'getDecimalFromText':
            return self.get_decimal_from_text(text)
        elif self.convert_method == 'getDecimalRangeFromTableText':
            return self.get_decimal_range_from_table_text(text)
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
    def get_date_from_text(text):
        str_list = text.split("至")
        if len(str_list) < 2 and ("月" in text or "年" in text or "/" in text or "." in text):
            str_list = re.split("[-—~]", text)
        return str_list[-1]

    @staticmethod
    def get_long_from_text(text):
        return TextUtils.remove_comma_in_number(text)

    @staticmethod
    def get_decimal_from_text(text):
        return text

    @staticmethod
    def get_decimal_range_from_table_text(text):
        return text

