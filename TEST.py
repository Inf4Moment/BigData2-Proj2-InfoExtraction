import re

if __name__ == "__main__":
    paragraph = "未减持<org>法拉电子</org>股份。加计本次减持，<org>建发集团</org>累计减持<org>法拉电子</org><num>11752826</num>股"
    targets = re.finditer(
        r'(增持(计划实施)?后|减持(计划实施)?后|变动后)[^。;；]*?持有.{0,30}?<num>(?P<share_num_after>.*?)</num>(股|万股|百万股|亿股)',
        paragraph)
    for target in targets:
        print(target)
