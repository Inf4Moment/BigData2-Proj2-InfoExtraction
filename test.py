from docparser import HTMLParser
from ner import NERTagger
from pyltp import SentenceSplitter

if __name__ == '__main__':

    html_parser = HTMLParser.HTMLParser()
    html_file_path = '../train_data/重大合同/html/4327.html'
    
    ner_model_dir_path = 'E:/WorkBench/Courses/Big-Data/Proj2-Finance/ltp_data_v3.4.0'
    ner_blacklist_file_path = 'config/ner_com_blacklist.txt'
    ner_tagger = NERTagger.NERTagger(ner_model_dir_path, ner_blacklist_file_path)
    
    paragraphs = html_parser.parse_content(html_file_path)
    for paragraph in paragraphs:
        tagged_text = ner_tagger.ner(paragraph, {})
        print(tagged_text.get_tagged_str())
        # print(tagged_text.tagged_seg_list)
        # sents = SentenceSplitter.split(paragraph)  # 分句
        # print('\n'.join(sents))
        print("*************")

