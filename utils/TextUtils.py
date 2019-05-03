# -*- coding: utf-8 -*-

import re

# 空格符
BlankCharSet = {' ', '\n', '\t', '\r'}
# 匹配逗号分隔的数字
CommaNumberPattern = re.compile(r'\d{1,3}([,，]\d\d\d)+')
# 逗号
CommaCharInNumberSet = {',', '，'}
# 数字
NumberSet = {'0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '.'}
# 匹配时间段
PartDataPattern = re.compile(r'(?P<year>\d\d\d\d年)\d{1,2}月\d{1,2}日至\d{1,2}月\d{1,2}日')


def clean_text(text):
    '''
    1. 去除没有用处的空格符
    2. 去除带逗号的数字中的逗号
    3. 规范化时间段文本
    '''
    return add_date(clean_number_in_text(remove_blank_chars(text)))


def extract_number(text):
    '''
    提取文本中的数字
    '''
    new_text = []
    for ch in text:
        if ch in NumberSet:
            new_text.append(ch)
    return ''.join(new_text)


def add_date(text):
    '''
    规范化时间段文本，使 "至" 前后都有年份
    例如 "2014年5月4日至6月3日" 将转化为 "2014年5月4日至2014年6月3日"
    clean_text 子例程
    '''
    part_dates = PartDataPattern.finditer(text)
    new_text, start = [], 0
    for part_data in part_dates:
        new_text.append(text[start:part_data.start()])
        start = part_data.end()
        year = part_data.group('year')
        str_list = part_data.group().split('至')
        new_text.append(str_list[0] + '至' + year + str_list[1])
    new_text.append(text[start:])
    return ''.join(new_text)


def clean_number_in_text(text):
    '''
    对给定文本，去除文本中带逗号数字中的逗号
    clean_text 子例程
    '''
    # 匹配到的带逗号数字在文本中的位置
    comma_numbers = CommaNumberPattern.finditer(text)
    new_text, start = [], 0
    for comma_number in comma_numbers:
        # 非数字文本
        new_text.append(text[start:comma_number.start()])
        start = comma_number.end()
        # 去除逗号的数字文本
        new_text.append(remove_comma_in_number(comma_number.group()))
    new_text.append(text[start:])
    return ''.join(new_text)


def remove_blank_chars(text):
    '''
    去除文本中的空格符，并将中文百分号符改为英文百分号符
    clean_text 子例程
    '''
    new_text = []
    if text is not None:
        for ch in text:
            if ch not in BlankCharSet:
                if ch == '％':
                    new_text.append('%')
                else:
                    new_text.append(ch)
    return ''.join(new_text)


def remove_comma_in_number(text):
    '''
    去除文本中的逗号
    主要用于去除数字中的逗号，clean_number_in_text 子例程
    '''
    new_text = []
    if text is not None:
        for ch in text:
            if ch not in CommaCharInNumberSet:
                new_text.append(ch)
    return ''.join(new_text)


if __name__ == "__main__":
    text = "总股 2,000,000 总价 300,000,000,000 元 2014年5月4日至6月3日"
    print(text)
    print(clean_text(text))
    print(add_date(text))
