# -*- coding: utf-8 -*-

import re

BlankCharSet = {' ', '\n', '\t', '\r'}
CommaNumberPattern = re.compile(r'\d{1,3}([,，]\d\d\d)+')
CommaCharInNumberSet = {',', '，'}
NumberSet = {'0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '.'}
PartDataPattern = re.compile(r'(?P<year>\d\d\d\d年)\d{1,2}月\d{1,2}日至\d{1,2}月\d{1,2}日')


def clean_text(text):
    return add_date(clean_number_in_text(remove_blank_chars(text)))


def add_date(text):
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
    comma_numbers = CommaNumberPattern.finditer(text)
    new_text, start = [], 0
    for comma_number in comma_numbers:
        new_text.append(text[start:comma_number.start()])
        start = comma_number.end()
        new_text.append(remove_comma_in_number(comma_number.group()))
    new_text.append(text[start:])
    return ''.join(new_text)


def remove_blank_chars(text):
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
    new_text = []
    if text is not None:
        for ch in text:
            if ch not in CommaCharInNumberSet:
                new_text.append(ch)
    return ''.join(new_text)


def extract_number(text):
    new_text = []
    for ch in text:
        if ch in NumberSet:
            new_text.append(ch)
    return ''.join(new_text)


if __name__ == "__main__":
    text = "总股 2,000,000 总价 300,000,000,000 元 2014年5月4日至6月3日"
    print(text)
    print(clean_text(text))
