"""
导入流程节点基类
定义统一的节点接口规范，提供通用功能9
"""
import colorlog
from processor.import_processor.config_base import ImportConfig,get_config
from processor.import_processor.exceptions import ImportProcessError
from utils.task_utils import add_running_task, add_done_task

"""
导入流程节点基类
定义统一的节点接口规范，提供通用功能
"""
from abc import ABC,abstractmethod
from typing import TypeVar,Optional
import logging
T=TypeVar('T')#泛型状态类型
class BaseNode(ABC):
    name :str = "base_node"
    def __init__(self,config:Optional[ImportConfig]=None):
        """
        初始化节点
        Args:
            config:配置对象，默认使用全局配置
        """
        self.config = config or get_config()
        #日志记录器：命名import.{self.name}
        self.logger = logging.getLogger(f"import.{self.name}")
    def __call__(self, state: T) -> T:
        """
                节点执行入口

                LangGraph 调用节点时会调用此方法。
                提供统一的日志输出、任务追踪和异常处理。

                 Args:
                    state: 图状态字典

                Returns:
                    更新后的状态字典

                Raises:
                    ImportProcessError: 节点执行失败时抛出
        """
        try:
            #1.开始准备执行节点
            self.logger.info(f"----{self.name}开始啦-------")
            # 开始：记录节点运行状态
            add_running_task(state["task_id"], self.name)
            #2.执行节点
            result=self.process(state)
            # 结束：记录节点完成状态
            add_done_task(state["task_id"], self.name)
            #3.执行节点成功
            self.logger.info(f"----{self.name}完成啦-----")
            return result
        except Exception as e:
            self.logger.error(f"{self.name}执行失败：{e}")
            raise ImportProcessError(
                message=str(e),
                node_name=self.name,
                cause=e,
            )

    @abstractmethod
    def process(self, state: T) -> T:
        """
        节点核心处理逻辑
        子类必须实现此方法
        Args:
            state: 图状态字典
        Returns:
            更新后的状态字典
        """
        pass

    def log_step(self, step_name: str, message: str = ""):
        """
        记录步骤日志
            [步骤名称]传递进来的消息
        Args:
            step_name: 步骤名称
            message: 附加信息
        """
        log_msg = f"[{step_name}]"
        if message:
            log_msg += f" {message}"
        self.logger.info(log_msg)

#配置日志格式：设置只显示 INFO 及以上的日志
def setup_logging(level:int=logging.INFO):
    """
    配置日志格式
    Args:
        level: 日志级别
    """
    # 1. 创建 Logger（记录器）
    logger = logging.getLogger()
    # 设置全局级别
    logger.setLevel(level)
    handler = colorlog.StreamHandler()
    handler.setFormatter(colorlog.ColoredFormatter(
        '%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        log_colors = {
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'bold_red',
        }
    ))
    logger.handlers.clear()
    logger.addHandler(handler)




