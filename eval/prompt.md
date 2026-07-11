## 生成测试集
【核心目标】
    根据 eval\hak180产品安全手册_new.md 
     生成一个用于 ragas测试的 评估测试集。
【要求】                   编码为utf-8 bom
   1生成的测试集格式csv文件，文件名为qa1.csv,
   2  测试集列为 question,ground_truth
   3  请使用“HAK 180 烫金机：” 作为每个问题的前缀 
   4  保存在eval目录下
   5  生成2对问题和答案


## 生成评估程序 
【核心目标】
     生成一个基于ragas的python评估程序，用于评估测试集，根据当前环境依赖版本生成
【程序要求】
    【输入要求】
        要读取eval/qa.csv，作为评估测试集。
    【过程要求】
        1 rag的流程入口 在 knowledge\processor\query_process\main_graph.py 中的query_app.invoke
        2 其中要求的上下文证据要从state中的reranked_docs中提取
        3 ragas需要的llm模型和embedding模型工具 
           分别从knowledge\utils\llm_client_util.py 
           和 knowledge\utils\bge_m3_util.py 获得 
        4 评估要求的5个指标：Faithfulness 、
            Answer Relevancy、Context Precision、
            Context Recall、Answer Correctness 
    【输出要求】
        1 评估输出文件为 qa_result.csv ，
                    保存在eval 目录下 ，编码集 utf-8 bom
        2 qa_result.csv 包括9列：question、 
             context、 answer、ground_truth、Faithfulness 、
             Answer Relevancy、Context Precision、
             Context Recall、Answer Correctness
     【代码风格要求】
         1 每个函数都要有注释
         2 每个核心步骤的函数名要求用step_1_xx step_2_xx来命名。
评估程序名称为:evaltest.py 保存在eval 目录下


## 生成调用远端embedding服务的工具代码
【核心目标】
   生成一个调用远端embedding服务的工具代码 。
【函数、参数、返回值的格式要求】
   参考 knowledge\utils\bge_m3_embedding_util.py 的函数名、传入参数 、 返回值，来制作工具程序。
  
  服务路径及参数：
   curl {BGE_M3_URL}/embeddings \
  -H "Content-Type: application/json" \
  -d '{"embedding_documents":["RS12 万用表如何测量交流电压？","如何判断电阻量程？"]}'
  其中 BGE_M3_URL 是bgem3的远程服务地址的环境变量 ，已经配置在.env文件中。