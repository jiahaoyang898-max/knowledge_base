import logging
from typing import Dict

from processor.import_processor.base import BaseNode, setup_logging
from processor.import_processor.exceptions import ImportProcessError

class TestNode(BaseNode):
    name ="test_node"
    def process(self,state:Dict)->Dict:
        state["processed_by"]=self.name
        self.log_step("数据清洗","移植空值完成")
        return state
if __name__ == '__main__':
    setup_logging(logging.INFO)
    node = TestNode()
    initial_state = {"data": [1, 2, 3], "status": "raw"}
    print("初始状态:", initial_state)
    print("\n开始执行节点...\n")
    try:
        final_state = node(initial_state)
        print("\n最终状态:", final_state)
    except ImportProcessError as e:
        print("捕获到流程错误:", e)