# 大数据项目二 -- 金融文本信息抽取

孙伟杰 陈俊儒 林泽钦

## 概要

## docparser -- html 文件解析

## ner -- 命名实体识别

## extract -- 信息抽取

### 增减持

### 重大合同

在重大合同的信息抽取中，我们需要从文本中提取以下信息：

![hetong1](./img/hetong1.png)

我们仍然使用 ner 打标签 + 正则匹配的方式提取信息。由于绝大部分关于重大合同的公告中并没有表格，所以这些数据都需要制定特定的匹配规则，下面分别进行叙述。

__乙方__

乙方名称的识别比较容易。一般来说，重大合同的公告都是由乙方发出的，所以公告的标题行很多都是 "xx公司关于xx重大合同的公告"，如下所示：

![yifang1](E:\WorkBench\Courses\Big-Data\Proj2-Finance\BigData2-Proj2-InfoExtraction\img\yifang1.png)

![yifang2](E:\WorkBench\Courses\Big-Data\Proj2-Finance\BigData2-Proj2-InfoExtraction\img\yifang2.png)

观察经由 nerTagger 添加标签后的 html 文件发现，标题行中的公司名称一般都能正确地被识别为组织名，并且被 `<org><\org>` 分离开来。基于这个观察，我们决定将文本中第一个识别出来的组织名作为乙方名称。这个规则对所有的 html 文件都有输出 (也就是说所有 html 都能识别出组织名，尽管可能不是在标题行中识别到的)。但是这样识别出来的名称有一个问题：由于 html 解析段落时没能很好分离公告信息行以及标题行，公告信息最后的公告标号会跟标题中的公司名称黏在一起，被整个识别为一个组织。因此，需要一个额外的子程序 `remove_number_in_name` 来去除这些可能出现的编号。

```python
partyB_pattern = re.compile(r'(<org>)(?P<partyB>.{1,28}?)(</org>)')
        for text in tagged_paragraphs:
            search_obj = partyB_pattern.search(text)
            if search_obj:
                partyB_name = search_obj.group('partyB')
                return self.remove_number_in_name(partyB_name)
        return ''
```

__甲方__

甲方的提取就比乙方难了不少，一个原因是甲方在文中出现的位置并不像乙方那样有固定的模式，并且甲方的上下文环境类型较多，需要浏览大量 html 来确定出现频率较高的句法模式；另一个原因是有很多文件的甲方为 "xx市xx局" 这种不是以公司为后缀的命名实体，而 ner 对这类实体的识别效果并不理想，因此也不能像乙方那样直接用 `<org><\org>` 进行匹配。在经过对训练数据的观察之后，我们制定了如下规则来抽取可能的甲方名称：

+  "与|和 ... 签署|签订"：这里省略号的位置通常就是甲方，如下所示。

  ![jiafang1](E:\WorkBench\Courses\Big-Data\Proj2-Finance\BigData2-Proj2-InfoExtraction\img\jiafang1.png)

+ "接到|收到 ... 发来|发出"：一般这种句式用来说明乙方收到了甲方发来的中标通知。

  ![jiafang2](E:\WorkBench\Courses\Big-Data\Proj2-Finance\BigData2-Proj2-InfoExtraction\img\jiafang2.png)



### 定向增发

## 小结