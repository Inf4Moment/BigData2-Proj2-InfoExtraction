#!/bin/python
# -*- coding: utf-8 -*-

import os
import re
import pyltp


class NERTaggedText(object):

    def __init__(self, text, tagged_seg_list):
        self.text = text
        # 进行词性标注之后的分词列表 (word, tag)
        self.tagged_seg_list = tagged_seg_list
        # Nh -- person name 人名 实体
        # Ni -- organization name 组织名 实体 
        # nt -- temporal noun 时间名词
        # v -- verb 动词
        # m -- number 数量
        # q -- quantity 量词
        self.valid_tag_set = {'Nh', 'Ni', 'nt', 'v', 'm', 'q'}
        self.tag_entity_dict = {'Nh': 'person', 'Ni': 'org', 'nt': 'date', 'm': 'num', 'mp': 'percent'}

    def get_tagged_seg_list(self):
        return self.tagged_seg_list

    def get_filtered_tagged_seg_list(self):
        """
        筛选之后的具有词性标注的分词列表 (词性需要为 valid_tag_set 中的一种)
        """
        rs_list = []
        for tagged_seg in self.tagged_seg_list:
            if tagged_seg[1] in self.valid_tag_set:
                rs_list.append(tagged_seg)
        return rs_list

    def get_tagged_str(self):
        """
        对于 tagged_seg_list，给词性在 tag_entity_dict 中的单词打上标签
        然后拼接成文本
        """
        tagged_str = ""
        for word, tag in self.tagged_seg_list:
            if tag in self.tag_entity_dict:
                tagged_str += "<%s>%s</%s>" % (self.tag_entity_dict[tag], word, self.tag_entity_dict[tag])
            else:
                tagged_str += word
        return tagged_str


class NERTagger(object):

    def __init__(self, model_dir_path, blacklist_path):
        """
        model_dir_path: pyltp 模型文件路径
        blacklist_path: 黑名单文件路径
        """
        # 初始化相关模型文件路径
        self.model_dir_path = model_dir_path
        self.cws_model_path = os.path.join(self.model_dir_path, 'cws.model')  # 分词模型路径，模型名称为`cws.model`
        self.pos_model_path = os.path.join(self.model_dir_path, 'pos.model')  # 词性标注模型路径，模型名称为`pos.model`
        self.ner_model_path = os.path.join(self.model_dir_path, 'ner.model')  # 命名实体识别模型路径，模型名称为`pos.model`

        # 初始化分词模型
        self.segmentor = pyltp.Segmentor()
        self.segmentor.load(self.cws_model_path)

        # 初始化词性标注模型
        self.postagger = pyltp.Postagger()
        self.postagger.load(self.pos_model_path)

        # 初始化NER模型
        self.recognizer = pyltp.NamedEntityRecognizer()
        self.recognizer.load(self.ner_model_path)

        # 初始化公司名黑名单
        self.com_blacklist = set()
        with open(blacklist_path, 'r', encoding='utf-8') as f_com_blacklist:
            for line in f_com_blacklist:
                if len(line.strip()) > 0:
                    self.com_blacklist.add(line.strip())

    def ner(self, text, entity_dict):
        words = self.segmentor.segment(text)  # 分词
        post_tags = self.postagger.postag(words)  # 词性标注
        ner_tags = self.recognizer.recognize(words, post_tags)  # 命名实体识别
        entity_list = self.construct_entity_list(words, post_tags, ner_tags)
        entity_list = self.ner_tag_by_dict(entity_dict, entity_list)
        return NERTaggedText(text, entity_list)

    def construct_entity_list(self, words, post_tags, ner_tags):
        entity_list = []
        entity = ""
        '''
        ner 子例程，用于词性列表、命名实体列表的调整
        命名实体识别 (ner_tags) 格式：
            位置标签(B,I,E,S,O)-实体类型标签(Nh,Ns,Ni)
            O后不跟-符号
        位置标签含义：B-实体开始词；I-实体中间词；E-实体结束词；S-单独实体；O-不构成实体
        实体类型标签：Nh-人名；Ns-地名；Ni-机构名
        '''
        for word, post_tag, ner_tag in zip(words, post_tags, ner_tags):
            tag = ner_tag[0]  # 位置标签
            entity_type = ner_tag[2:]  # 实体类型标签
            # 单独实体，直接加入 entity_list
            if tag == 'S':
                entity_list.append((word, entity_type))
            # 有多个组成部分的实体，循环直至组成一个完整实体
            elif tag in 'BIE':
                entity += word
                if tag == 'E':
                    # 判断公司名黑名单
                    if entity in self.com_blacklist:
                        entity_list.append((entity, "n"))
                    else:
                        entity_list.append((entity, entity_type))
                    entity = ""
            # 非实体
            elif tag == 'O':
                # 循环直至识别一个完整的时间名词
                if post_tag == 'nt':
                    entity += word
                else:
                    if entity != "":
                        entity_list.append((entity, 'nt'))
                        entity = ""
                    # 排除错误数字识别，例如“大宗”
                    if post_tag == 'm' and not re.match("[0-9]+.*", word):
                        post_tag = 'n'
                    # 识别数字中的百分数
                    if post_tag == 'm' and re.match("[0-9.]+%", word):
                        post_tag = 'mp'
                    entity_list.append((word, post_tag))
        return entity_list

    def ner_tag_by_dict(self, entity_dict, entity_list):
        # 检测单个分词标注中，是否包含多个已知的实体，有则提取出来
        legal_tag = entity_dict.values()
        j = 0
        limit = len(entity_list)
        while j < limit:
            if entity_list[j][1] in legal_tag:
                long_entity = entity_list[j][0]
                if long_entity in entity_dict:
                    j += 1
                    continue
                else:
                    k = 0
                    new_entity = []
                    while k < len(long_entity) - 1:
                        has_entity = False
                        for entity_len in range(len(long_entity) - k, 0, -1):
                            segment = long_entity[k:k + entity_len]
                            if segment in entity_dict:
                                has_entity = True
                                new_entity.append((long_entity[0:k], 'raw'))
                                new_entity.append((segment, entity_dict[segment]))
                                long_entity = long_entity[k + entity_len:]
                                k = 0
                                break
                        if not has_entity:
                            k += 1
                    if len(new_entity) == 0:
                        j += 1
                        continue
                    new_entity.append((long_entity, 'raw'))
                    del entity_list[j]
                    for cut in new_entity:
                        if cut[1] in legal_tag:
                            entity_list.insert(j, cut)
                            j += 1
                        else:
                            words = self.segmentor.segment(cut[0])
                            post_tags = self.postagger.postag(words)
                            ner_tags = self.recognizer.recognize(words, post_tags)
                            for entity in self.construct_entity_list(words, post_tags, ner_tags):
                                entity_list.insert(j, entity)
                                j += 1
                    limit = len(entity_list)
                    continue
            j += 1

        # 尝试将相邻的分词合并，检测是否在 entity_dict 中
        i = 0
        while i < len(entity_list) - 1:
            has_entity = False
            for entity_len in range(4, 1, -1):
                segment = "".join([x[0] for x in entity_list[i: i + entity_len]])
                # 将 2 到 4 个相邻的分词合并
                segment_uni = segment
                if segment_uni in entity_dict:
                    has_entity = True
                    entity_list[i] = (segment, entity_dict[segment_uni])
                    del entity_list[i + 1: i + entity_len]
                    i = i + entity_len
                    break
            if not has_entity:
                i += 1
        return entity_list

    def __del__(self):
        self.segmentor.release()
        self.postagger.release()
        self.recognizer.release()


if __name__ == "__main__":
    text = "2018年4月25日，公司收到证券公司的通知：证券公司已于2018年4 月25日处置了钟波先生质押标的证券，违约处置数量为90.3万股，成交金额779.4482万元，平均成交价8.632元/股。本次减持前，钟波先生持有公司股份1000万股，占公司总股本的2.77%。本次减持后，钟波先生持有公司股份909.7万股，占公司总股本的2.52%。"
    # text = "2018年4月25日，公司收到证券公司的通知：证券公司已于2018年4 月25日处置了钟波先生质押标的证券，违约处置数量为90.3万股，成交金额779.4482万元，平均成交价8.632元/股。本次减持前，钟波先生持有公司股份1000万股，占公司总股本的2.77%。本次减持后，钟波先生持有公司股份909.7万股，占公司总股本的2.52%。"
    # text = "2018年4月24日、4月25日，公司实际控制人之一黄盛秋先生因股票质押违约，被证券公司强行平仓247.65万股。2018年4月25日，公司实际控制人之一钟波先生因股票质押违约，被证券公司强行平仓90.3万股。上述二人合计被强行平仓337.95万股，占公司总股本的0.94%，根据相关规定，公司实际控制人以集中竞价方式减持公司股份在任意连续九十个自然日内，减持股份的总数不得超过公司股份总数的百分之一即361.43万股。"
    # text = '中华人民共和国中央人民政府于1949年10月1日在伟大首都北京成立了'
    ner_tagger = NERTagger("../../ltp_data_v3.4.0", "../config/ner_com_blacklist.txt")

    res = ner_tagger.ner(text, {"券": "Ni"})
    for ent in res.get_tagged_seg_list():
        print('\t'.join(ent))
    print(res.get_tagged_str())
